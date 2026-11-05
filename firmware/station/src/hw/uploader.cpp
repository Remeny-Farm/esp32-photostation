#include "uploader.h"

#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <esp_heap_caps.h>
#include <esp_system.h>
#include <esp_task_wdt.h>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <string.h>
#include <string>
#include <utility>
#include <vector>

#include "../core/policy.h"
#include "../core/record.h"
#include "camera.h"
#include "config.h"
#include "log.h"
#include "net.h"
#include "pir.h"
#include "storage.h"

namespace {
constexpr size_t kMaxBodyBytes = 1048576;     // server limit; larger files go to /bad untouched
constexpr uint32_t kHeartbeatMs = 300000;
constexpr uint32_t kHeartbeatForceMs = 900000;  // older than this: the heartbeat ignores the upload gate
constexpr uint32_t kTickMs = 1000;
constexpr size_t kWindow = 16;                // oldest queue names kept per pass (internal RAM)
constexpr int kMaxLocalFails = 3;             // read failures of one file before it goes to /bad
constexpr uint32_t kRedirectLogMs = 600000;   // at most one redirect line per 10 minutes
const char* kPhotoPath = "/api/photostation/photo";
const char* kVisitPath = "/api/photostation/visit";
const char* kHeartbeatPath = "/api/photostation/heartbeat";

UploaderHooks g_hooks{nullptr, ""};
std::atomic<int64_t> g_lastVisitEpoch{-1};
std::atomic<int> g_state{0};  // index into kStates
std::atomic<bool> g_redirect{false};  // last response was a 3xx; cleared by any other response
const char* const kStates[] = {"idle", "uploading", "retry", "auth_stop", "no_wifi", "no_time", "no_config"};
enum State { Idle, Uploading, Retry, AuthStop, NoWifi, NoTime, NoConfig };

// Heartbeat timing, uploader task only. g_lastHbMs starts at task start, so the first
// heartbeat also bypasses the gate once the task has run 15 minutes without one.
uint32_t g_lastHbMs = 0;
bool g_hbDone = false;

// The file whose local read failed last, and how often in a row.
std::string g_failName;
int g_failCount = 0;

void setState(State s) { g_state.store(s); }

std::atomic<uint32_t> g_largestMin{UINT32_MAX};

// Never start a request while a visit is open or the PIR has fired. Checked before each request.
bool gateOpen() { return !(g_hooks.visitOpen && g_hooks.visitOpen()) && !pirPending(); }

bool isBenchFile(const std::string& n) { return n.rfind("snap_", 0) == 0; }

// A /q name the uploader sends: not a bench file, and a name uploadOrder() accepts.
bool queueable(const std::string& n) {
  return !isBenchFile(n) && !uploadOrder(std::vector<std::string>{n}).empty();
}

// One directory pass. Returns the kWindow oldest queue names in upload order (oldest visit first,
// photos by n, then the JSON). The buffer is cut back to kWindow whenever it reaches 2 * kWindow,
// so it is always the exact prefix of uploadOrder() over the whole queue, and the photo-before-JSON
// rule holds inside and across windows.
std::vector<std::string> oldestQueueNames() {
  std::vector<std::string> window;
  storageForEach("/q", [&](const std::string& name) {
    if (!queueable(name)) return;
    window.push_back(name);
    if (window.size() >= 2 * kWindow) {
      window = uploadOrder(std::move(window));
      window.resize(kWindow);
    }
  });
  window = uploadOrder(std::move(window));
  if (window.size() > kWindow) window.resize(kWindow);
  return window;
}

size_t countQueueable(const char* dir = "/q") {
  size_t n = 0;
  storageForEach(dir, [&](const std::string& name) {
    if (queueable(name)) n++;
  });
  return n;
}

bool endsWith(const std::string& s, const char* suffix) {
  size_t n = strlen(suffix);
  return s.size() >= n && s.compare(s.size() - n, n, suffix) == 0;
}

// httpPost() plus the redirect report: a 3xx is classified Retry (policy unchanged), so the
// uploader says once per 10 minutes why it never gets through, and shows state "redirect".
int post(const char* ep, const char* ctype, const uint8_t* body, size_t len,
         const std::vector<std::pair<std::string, std::string>>& hdr) {
  int status = httpPost(ep, ctype, body, len, hdr);
  heapNoteLargest();
  bool redirect = status >= 300 && status < 400;
  if (redirect) {
    static uint32_t lastLog = 0;
    static bool logged = false;
    uint32_t now = millis();
    if (!logged || now - lastLog >= kRedirectLogMs) {
      logLine("UP redirect %d — UPLOAD_BASE_URL must be the final host", status);
      logged = true;
      lastLog = now;
    }
  }
  if (status > 0) g_redirect.store(redirect);
  return status;
}

// Copies the file into a PSRAM buffer while holding the storage lock. The lock is released
// before any network call. Returns the size (0 = empty file) or -1 on error / too large (*tooBig).
struct Loaded {
  uint8_t* buf = nullptr;
  size_t len = 0;
  int64_t mtime = -1;
  bool tooBig = false;
  bool ok = false;
  ~Loaded() {
    if (buf) heap_caps_free(buf);
  }
};

void loadFile(const std::string& path, Loaded& out) {
  storageLock();
  File f = SD.open(path.c_str(), FILE_READ);
  if (f && !f.isDirectory()) {
    size_t size = f.size();
    time_t lw = f.getLastWrite();
    out.mtime = lw > 0 ? (int64_t)lw : -1;
    if (size > kMaxBodyBytes) {
      out.tooBig = true;
    } else if (size == 0) {
      out.ok = true;  // empty: classified as Bad by the caller
    } else {
      out.buf = (uint8_t*)ps_malloc(size);
      if (out.buf) {
        size_t got = 0;
        while (got < size) {
          int n = f.read(out.buf + got, size - got < 4096 ? size - got : 4096);
          if (n <= 0) break;
          got += (size_t)n;
        }
        if (got == size) {
          out.len = size;
          out.ok = true;
        }
      }
    }
  }
  if (f) f.close();
  storageUnlock();
}

struct Attempt {
  UploadOutcome outcome;
  int status;  // 0 when no request was made
  bool requested;
  bool moveFailed;
};

// Uploads one /q file. Sent/Bad files are moved here. A closed gate or a local read error
// returns Retry with requested=false (the caller waits, no backoff growth). The third local
// read failure in a row of the same file moves it to /bad, so one bad file cannot block the queue.
Attempt uploadOne(const std::string& name, const StationConfig& cfg) {
  std::string path = "/q/" + name;
  if (!gateOpen()) return {UploadOutcome::Retry, 0, false, false};

  Loaded l;
  loadFile(path, l);
  if (l.tooBig || (l.ok && l.len == 0)) {
    logLine("UP %s unusable size, to /bad", name.c_str());
    bool moved = storageMove(path.c_str(), "/bad");
    return {UploadOutcome::Bad, 0, false, !moved};
  }
  if (!l.ok) {
    g_failCount = name == g_failName ? g_failCount + 1 : 1;
    g_failName = name;
    if (g_failCount < kMaxLocalFails) return {UploadOutcome::Retry, 0, false, false};
    logLine("UP %s read failed %d times (no memory or SD error), to /bad", name.c_str(), g_failCount);
    g_failName.clear();
    g_failCount = 0;
    bool moved = storageMove(path.c_str(), "/bad");
    return {UploadOutcome::Bad, 0, false, !moved};
  }
  if (name == g_failName) {
    g_failName.clear();
    g_failCount = 0;
  }
  if (!gateOpen()) return {UploadOutcome::Retry, 0, false, false};  // re-check right before the request

  std::vector<std::pair<std::string, std::string>> hdr;
  hdr.push_back({"Authorization", "Bearer " + cfg.key});
  hdr.push_back({"X-Station-Id", cfg.stationId});
  const char* ctype;
  const char* ep;
  if (endsWith(name, ".jpg")) {
    std::string stem = name.substr(0, name.size() - 4);
    size_t us = stem.rfind('_');
    hdr.push_back({"X-Visit-Id", stem.substr(0, us)});
    hdr.push_back({"X-Photo-N", stem.substr(us + 1)});
    int64_t now = netEpoch();
    bool plausible = l.mtime >= 1700000000 && now >= 0 && l.mtime <= now + 86400;
    if (plausible) hdr.push_back({"X-Captured-At", isoUtc(l.mtime)});  // omitted when unknown
    ctype = "image/jpeg";
    ep = kPhotoPath;
  } else {
    ctype = "application/json";
    ep = kVisitPath;
  }
  setState(Uploading);
  int status = post(ep, ctype, l.buf, l.len, hdr);
  UploadOutcome o = classify(status);
  logLine("UP %s %u bytes -> %d", name.c_str(), (unsigned)l.len, status);
  bool moved = true;
  if (o == UploadOutcome::Sent) {
    moved = storageMove(path.c_str(), sentDir(netEpoch()).c_str());
  } else if (o == UploadOutcome::Bad) {
    moved = storageMove(path.c_str(), "/bad");
  }
  if (!moved) logLine("UP %s move FAILED, file stays in /q, pass stops and backs off", name.c_str());
  return {o, status, true, !moved};
}

std::string heartbeatJson(const StationConfig& cfg) {
  int64_t lv = g_lastVisitEpoch.load();
  std::string lastVisit = lv >= 0 ? "\"" + isoUtc(lv) + "\"" : "null";
  float t = temperatureRead();
  char temp[16];
  if (std::isfinite(t)) snprintf(temp, sizeof temp, "%.1f", t);
  else snprintf(temp, sizeof temp, "null");  // NaN/inf would break the JSON
  size_t bad = storageForEach("/bad", [](const std::string&) {});
  // Worst case (31-char id, every number at its maximum width, longest state): 499 bytes.
  char j[768];
  int n = snprintf(j, sizeof j,
           "{\"station_id\":\"%s\",\"firmware\":\"%s\",\"uptime_s\":%lu,"
           "\"free_heap\":%u,\"min_heap\":%u,\"free_psram\":%u,\"free_int\":%u,\"largest_int_block\":%u,\"int_largest_min\":%u,"
           "\"sd_ok\":%s,\"cam_ok\":%s,\"sd_used_pct\":%u,\"queue_len\":%u,\"bad_len\":%u,"
           "\"wifi_rssi\":%d,\"chip_temp_c\":%s,\"time_synced\":%s,\"last_visit_at\":%s,"
           "\"upload_state\":\"%s\",\"pir_stuck\":%s,\"forced_closes\":%u}",
           cfg.stationId.c_str(), g_hooks.firmware, (unsigned long)(millis() / 1000), (unsigned)ESP.getFreeHeap(),
           (unsigned)ESP.getMinFreeHeap(),
           (unsigned)ESP.getFreePsram(), (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
           (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL), (unsigned)heapLargestMin(), storageReady() ? "true" : "false",
           cameraReady() ? "true" : "false", (unsigned)storageUsedPct(), (unsigned)countQueueable(), (unsigned)bad,
           netRssi(), temp, netTimeSynced() ? "true" : "false", lastVisit.c_str(), uploaderState().c_str(),
           pirStuck() ? "true" : "false", (unsigned)pirForcedCloses());
  if (n < 0 || (size_t)n >= sizeof j) return "";  // truncated JSON must never be sent
  return j;
}

void sendHeartbeat(const StationConfig& cfg) {
  std::string j = heartbeatJson(cfg);
  if (j.empty()) {
    logLine("HB payload too long, not sent");
    return;
  }
  std::vector<std::pair<std::string, std::string>> hdr;
  hdr.push_back({"Authorization", "Bearer " + cfg.key});
  hdr.push_back({"X-Station-Id", cfg.stationId});
  int status = post(kHeartbeatPath, "application/json", (const uint8_t*)j.data(), j.size(), hdr);
  logLine("HB -> %d", status);
}

// Sends the heartbeat when it is due. It waits for the upload gate like any request, except when
// the last one is 15 minutes old: then it goes anyway (a small request; photos stay gated).
void heartbeatIfDue(const StationConfig& cfg) {
  uint32_t since = millis() - g_lastHbMs;
  if (g_hbDone && since < kHeartbeatMs) return;
  if (!gateOpen() && since < kHeartbeatForceMs) return;
  sendHeartbeat(cfg);
  g_hbDone = true;
  g_lastHbMs = millis();
  esp_task_wdt_reset();
}

void uploaderTask(void*) {
  // docs/architecture.md (reliability): the task watchdog (30 s, set in setup()) covers this task.
  if (esp_task_wdt_add(nullptr) != ESP_OK) logLine("UP task watchdog subscribe FAILED");
  uint32_t attempt = 0;
  uint32_t nextTryMs = millis();
  g_lastHbMs = millis();
  bool authStopped = false;
  uint32_t stopVersion = 0;
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(kTickMs));
    esp_task_wdt_reset();
    StationConfig cfg = configGet();
    bool https = cfg.baseUrl.rfind("https://", 0) == 0;
    if (cfg.baseUrl.empty() || cfg.key.empty()) {
      setState(NoConfig);
      continue;
    }
    if (!netUp()) {
      setState(NoWifi);
      continue;
    }
    if (https && !netTimeSynced()) {  // certificate dates cannot be checked before SNTP
      setState(NoTime);
      continue;
    }
    if (authStopped && configCredVersion() != stopVersion) {  // `set key` / `set url` ends AuthStop
      authStopped = false;
      attempt = 0;
      nextTryMs = millis();
    }

    // All three gates above passed: a stale NoConfig/NoWifi/NoTime from before must not reach the
    // heartbeat (the first one after boot went out as "no_wifi" although it was sent over Wi-Fi).
    // The stale state becomes what the task really is: stopped on auth, backing off, or idle.
    int st = g_state.load();
    if (st == NoConfig || st == NoWifi || st == NoTime)
      setState(authStopped ? AuthStop : ((int32_t)(millis() - nextTryMs) < 0 ? Retry : Idle));
    heartbeatIfDue(cfg);
    if (authStopped) {
      setState(AuthStop);
      continue;
    }
    if ((int32_t)(millis() - nextTryMs) < 0) continue;  // backing off

    std::vector<std::string> names = oldestQueueNames();
    if (names.empty()) {
      setState(Idle);
      continue;
    }
    bool anySent = false;
    for (const std::string& name : names) {
      esp_task_wdt_reset();
      heartbeatIfDue(cfg);  // a long backlog pass still reports every 5 minutes
      Attempt a = uploadOne(name, cfg);
      esp_task_wdt_reset();
      if (a.moveFailed) {  // never re-upload every pass: back off like a retry
        uint32_t wait = backoffMs(attempt++);
        nextTryMs = millis() + wait;
        setState(Retry);
        break;
      }
      if (!a.requested && a.outcome == UploadOutcome::Retry) {
        nextTryMs = millis() + 2000;  // gate closed or local read problem: look again soon
        break;
      }
      if (a.outcome == UploadOutcome::Sent || a.outcome == UploadOutcome::Bad) {
        attempt = 0;
        anySent = anySent || a.outcome == UploadOutcome::Sent;
        continue;
      }
      if (a.outcome == UploadOutcome::AuthStop) {
        authStopped = true;
        stopVersion = configCredVersion();
        setState(AuthStop);
        logLine("UP auth rejected (%d): upload stopped until `set key` or reboot", a.status);
        break;
      }
      uint32_t wait = backoffMs(attempt++);  // Retry
      nextTryMs = millis() + wait;
      setState(Retry);
      logLine("UP retry in %lu ms (attempt %u)", (unsigned long)wait, (unsigned)attempt);
      break;
    }
    if (anySent) storagePruneSent();
    if (g_state.load() == Uploading) setState(Idle);
  }
}
}  // namespace

void uploaderStart(const UploaderHooks& hooks) {
  g_hooks = hooks;
  // TLS needs ~40 KB of contiguous internal heap and a deep stack; the body buffer is in PSRAM.
  // Core 1, priority 1: long SD passes and TLS work never starve IDLE0, which the task
  // watchdog checks (CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU0).
  xTaskCreatePinnedToCore(uploaderTask, "upload", 12288, nullptr, 1, nullptr, 1);
}

void heapNoteLargest() {
  uint32_t now = (uint32_t)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL);
  uint32_t cur = g_largestMin.load();
  while (now < cur && !g_largestMin.compare_exchange_weak(cur, now)) {
  }
}

uint32_t heapLargestMin() {
  heapNoteLargest();
  return g_largestMin.load();
}

void uploaderNoteVisit(int64_t epochSec) { g_lastVisitEpoch.store(epochSec); }

std::string uploaderState() { return g_redirect.load() ? "redirect" : kStates[g_state.load()]; }

size_t uploaderQueueLen() { return countQueueable(); }
size_t uploaderCountQueueable(const char* dir) { return countQueueable(dir); }
