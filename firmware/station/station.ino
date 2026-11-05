// esp32-photostation: PIR visit loop with SD queue, BLE tag identification, Wi-Fi upload,
// heartbeat and OTA. PIR edge -> light on -> 3..5 photos -> SD queue (/q) -> light off + visit
// JSON; the uploader task drains /q outside visits.
#include <Arduino.h>
#include <Preferences.h>
#include <esp_heap_caps.h>
#include <esp_task_wdt.h>

#include "src/core/ident.h"
#include "src/core/policy.h"
#include "src/core/record.h"
#include "src/core/visit.h"
#include "src/hw/ble.h"
#include "src/hw/camera.h"
#include "src/hw/config.h"
#include "src/hw/console.h"
#include "src/hw/light.h"
#include "src/hw/log.h"
#include "src/hw/net.h"
#include "src/hw/pir.h"
#include "src/hw/storage.h"
#include "src/hw/uploader.h"

namespace {
const char* kFirmware = "0.3.0";
constexpr int kDefaultThresholdDbm = -60;
constexpr int kDefaultMarginDb = 8;
constexpr int kMinPackets = 3;
constexpr uint32_t kPreRollMs = 5000;  // identification window starts 5 s before the visit opens
constexpr uint32_t kScanSummaryMs = 30000;
constexpr uint32_t kBleStatsEveryMs = 60000;
constexpr uint32_t kWdtTimeoutMs = 30000;  // above a 10 s camera lock wait and a 15 s socket timeout
constexpr int kInitTries = 3;
constexpr uint8_t kMaxInitFailBoots = 3;
constexpr size_t kLsMax = 64;
constexpr size_t kBenchMax = 1000;

uint32_t g_boot = 0;
std::string g_stationId = "ps-01";  // NVS id, loaded in setup() before the tasks start
volatile bool g_visitOpen = false;
volatile int g_thresholdDbm = kDefaultThresholdDbm;  // NVS t_dbm
volatile int g_marginDb = kDefaultMarginDb;          // NVS x_db
TagTable g_tags;
SemaphoreHandle_t g_tagLock = nullptr;

void visitTask(void*) {
  if (esp_task_wdt_add(nullptr) != ESP_OK) logLine("VISIT task watchdog subscribe FAILED");
  VisitMachine vm;
  VisitRecord rec;
  uint32_t counter = 0;
  uint32_t visitStartMs = 0;
  int visitT = kDefaultThresholdDbm, visitX = kDefaultMarginDb;
  TickType_t last = xTaskGetTickCount();
  for (;;) {
    esp_task_wdt_reset();
    uint32_t now = millis();
    VisitStep s = vm.tick(now, pirTakeEdge());
    switch (s.ev) {
      case VisitEv::Open:
        visitStartMs = now;
        visitT = g_thresholdDbm;  // T and X are fixed for the whole visit
        visitX = g_marginDb;
        bleSetVisit(true, visitStartMs);
        g_visitOpen = true;
        rec = VisitRecord();
        rec.station = g_stationId;
        rec.firmware = kFirmware;
        {
          int64_t t = netEpoch();  // -1 until SNTP has set the clock: the unsynced id form
          rec.visitId = makeVisitId(g_stationId, t, g_boot, ++counter);
          rec.timeSynced = t >= 0;
          rec.startedAt = t;
          uploaderNoteVisit(t);
        }
        rec.thresholdDbm = visitT;
        rec.marginDb = visitX;
        rec.lightPwm = kLightVisitPwm;
        logLine("Open %s", rec.visitId.c_str());
        lightSet(kLightVisitPwm);
        break;
      case VisitEv::Capture: {
        camera_fb_t* fb = cameraCapture(s.n == 1);
        if (!fb) {
          logLine("Capture %d FAIL camera", s.n);
          vm.photoDone(millis());
          break;
        }
        std::string path = photoPath(rec.visitId, s.n);
        bool ok = storageWriteVerified(path.c_str(), fb->buf, fb->len);
        if (ok) rec.photos.push_back({s.n, netEpoch(), (uint32_t)fb->len, (int)fb->width, (int)fb->height});
        logLine("Capture %d %s %u bytes %ux%u %s", s.n, path.c_str(), (unsigned)fb->len,
                (unsigned)fb->width, (unsigned)fb->height, ok ? "ok" : "WRITE FAIL");
        cameraRelease(fb);
        heapNoteLargest();
        vm.photoDone(millis());
        break;
      }
      case VisitEv::Close: {
        lightSet(0);
        pirNoteClose(s.reason == CloseReason::Forced);
        rec.endedAt = netEpoch();
        {
          std::vector<Candidate> cands;
          if (xSemaphoreTake(g_tagLock, pdMS_TO_TICKS(500)) == pdTRUE) {
            cands = g_tags.summarize(visitStartMs - kPreRollMs, now);  // copy only, no SD under the lock
            xSemaphoreGive(g_tagLock);
          } else {
            logLine("Close ident: tag lock busy, decision unknown");
          }
          rec.decision = identify(cands, visitT, visitX, kMinPackets);
        }
        bleSetVisit(false, 0);
        std::string path = metaPath(rec.visitId);
        bool ok = storageWriteText(path.c_str(), visitJson(rec));
        logLine("Close %s %s photos=%d %s decision=%s tag=%s cands=%u", s.reason == CloseReason::Forced ? "Forced" : "Silence",
                rec.visitId.c_str(), (int)rec.photos.size(), ok ? "json ok" : "json WRITE FAIL",
                rec.decision.known ? "tag" : "unknown", rec.decision.known ? rec.decision.mac.c_str() : "-",
                (unsigned)rec.decision.candidates.size());
        g_visitOpen = false;
        break;
      }
      case VisitEv::None:
        break;
    }
    vTaskDelayUntil(&last, pdMS_TO_TICKS(50));
  }
}

void cmdInfo(const Command&) {
  Serial.printf("INFO station=%s fw=%s boot=%u uptime_s=%lu visit_open=%d\n", g_stationId.c_str(), kFirmware,
                (unsigned)g_boot, (unsigned long)(millis() / 1000), (int)g_visitOpen);
  Serial.printf("INFO camera=%s\n", cameraSensorName());
  if (storageReady()) {
    Serial.printf("INFO sd=mounted size_mb=%llu used_pct=%u\n", (unsigned long long)storageSizeMb(),
                  (unsigned)storageUsedPct());
  } else {
    Serial.println("INFO sd=none");
  }
  {
    BleStats b = bleStats();
    size_t tags = 0;
    if (xSemaphoreTake(g_tagLock, pdMS_TO_TICKS(200)) == pdTRUE) {
      tags = g_tags.tagCount();
      xSemaphoreGive(g_tagLock);
    }
    Serial.printf("INFO ble=%s adv=%u tag=%u lock_miss=%u restarts=%u tags=%u t_dbm=%d x_db=%d\n",
                  bleRunning() ? "running" : "off", (unsigned)b.adv, (unsigned)b.tag, (unsigned)b.lockMiss,
                  (unsigned)b.restarts, (unsigned)tags, (int)g_thresholdDbm, (int)g_marginDb);
  }
  {
    StationConfig c = configGet();
    Serial.printf("INFO net wifi=%s ssid=%s ip=%s rssi=%d time_synced=%d\n", netUp() ? "up" : "down", c.ssid.c_str(),
                  netIp().c_str(), netRssi(), (int)netTimeSynced());
    // Only the key shows its last 4 characters; pass and OTA password show set/unset.
    Serial.printf("INFO cfg url=%s id=%s pass=%s key=%s ota=%s\n", c.baseUrl.empty() ? "-" : c.baseUrl.c_str(),
                  c.stationId.c_str(), c.pass.empty() ? "-" : "****", c.key.empty() ? "-" : maskSecret(c.key).c_str(),
                  c.otaPass.empty() ? "-" : "****");
    Serial.printf("INFO upload state=%s queue=%u\n", uploaderState().c_str(), (unsigned)uploaderQueueLen());
  }
  Serial.printf("INFO pir_stuck=%d forced_closes=%u\n", (int)pirStuck(), (unsigned)pirForcedCloses());
  Serial.printf("INFO light=%u heap=%u min_heap=%u psram_free=%u int_free=%u int_largest=%u int_largest_min=%u\n",
                (unsigned)lightLevel(), (unsigned)ESP.getFreeHeap(), (unsigned)ESP.getMinFreeHeap(),
                (unsigned)ESP.getFreePsram(), (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL), (unsigned)heapLargestMin());
}

void cmdPir(const Command&) {
  pirSimulate();
  Serial.println("OK pir");
}

void cmdSnap(const Command&) {
  if (g_visitOpen) {
    Serial.println("ERR snap: visit open");
    return;
  }
  camera_fb_t* fb = cameraCapture(true);
  if (!fb) {
    Serial.println("ERR snap: capture failed");
    return;
  }
  char path[48];
  snprintf(path, sizeof path, "/q/snap_%lu.jpg", (unsigned long)millis());
  bool ok = storageWriteVerified(path, fb->buf, fb->len);
  Serial.printf("%s snap %s %u bytes\n", ok ? "OK" : "ERR", path, (unsigned)fb->len);
  cameraRelease(fb);
}

// One directory pass. Names and sizes of the first kLsMax files (sorted); a longer directory prints
// only the count of the rest (each size is one more FAT lookup, so 500 sizes would take seconds).
void cmdLs(const Command& c) {
  std::string dir = c.args.empty() ? "/" : c.args[0];
  std::vector<std::string> names;
  size_t total = storageForEach(dir.c_str(), [&](const std::string& n) {
    if (names.size() < kLsMax) names.push_back(n);
  });
  std::sort(names.begin(), names.end());
  for (const auto& n : names) {
    std::string p = dir == "/" ? "/" + n : dir + "/" + n;
    Serial.printf("LS %s %lld\n", n.c_str(), (long long)storageFileSize(p.c_str()));
  }
  if (total > names.size()) Serial.printf("LS_MORE %u not shown\n", (unsigned)(total - names.size()));
  Serial.printf("LS_END %s files=%u\n", dir.c_str(), (unsigned)total);
}

void cmdCat(const Command& c) {
  if (c.args.empty()) {
    Serial.println("ERR usage: cat <path>");
    return;
  }
  std::string s;
  if (!storageReadTail(c.args[0].c_str(), s, 8192)) {
    Serial.printf("ERR cat: cannot read %s\n", c.args[0].c_str());
    return;
  }
  Serial.println("CAT_BEGIN");
  Serial.write((const uint8_t*)s.data(), s.size());
  Serial.println();
  Serial.println("CAT_END");
}

void cmdLight(const Command& c) {
  int v = c.args.empty() ? -1 : atoi(c.args[0].c_str());
  if (v < 0 || v > 255) {
    Serial.println("ERR usage: light <0-255>");
    return;
  }
  lightSet((uint8_t)v);
  Serial.printf("OK light %u\n", (unsigned)lightLevel());
}

// scan: the last 30 s per tag: mac name median count min max vbat_mv
void cmdScan(const Command&) {
  std::vector<Candidate> cands;
  uint32_t now = millis();
  if (xSemaphoreTake(g_tagLock, pdMS_TO_TICKS(500)) == pdTRUE) {
    cands = g_tags.summarize(now - kScanSummaryMs, now);
    xSemaphoreGive(g_tagLock);
  } else {
    Serial.println("ERR scan: tag lock busy");
    return;
  }
  Serial.println("SCAN_BEGIN mac name median count min max vbat_mv");
  std::sort(cands.begin(), cands.end(),
            [](const Candidate& a, const Candidate& b) { return a.median > b.median; });
  for (const auto& c : cands) {
    Serial.printf("TAG %s %s %d %d %d %d %d\n", c.mac.c_str(), c.name.empty() ? "-" : c.name.c_str(),
                  c.median, c.count, c.min, c.max, bleVbatMv(c.mac));
  }
  Serial.printf("SCAN_END tags=%u window_s=%u\n", (unsigned)cands.size(), (unsigned)(kScanSummaryMs / 1000));
}

// benchls <n>: n tiny files (max kBenchMax) in /benchls, created once and then reused. /benchls is
// outside /q, so nothing is uploaded. Times one listing with the uploader's own queue count.
// benchls clean: deletes /benchls and its files. Both are refused while a visit is open.
bool allDigits(const std::string& s) {
  if (s.empty()) return false;
  for (char ch : s) {
    if (ch < '0' || ch > '9') return false;
  }
  return true;
}

void cmdBenchLs(const Command& c) {
  if (g_visitOpen) {
    Serial.println("ERR benchls: visit open");
    return;
  }
  if (c.args.size() == 1 && c.args[0] == "clean") {
    if (!storageReady()) {
      Serial.println("ERR benchls: no sd");
      return;
    }
    bool gone = storageRemoveTree("/benchls");
    Serial.printf("%s benchls clean\n", gone ? "OK" : "ERR");
    return;
  }
  long n = (c.args.size() == 1 && allDigits(c.args[0])) ? strtol(c.args[0].c_str(), nullptr, 10) : 0;
  if (n < 1 || n > (long)kBenchMax) {
    Serial.printf("ERR usage: benchls <1..%u> | clean\n", (unsigned)kBenchMax);
    return;
  }
  if (!storageReady() || !storageEnsureDir("/benchls")) {
    Serial.println("ERR benchls: no sd");
    return;
  }
  static const uint8_t kJpg[4] = {0xff, 0xd8, 0xff, 0xd9};
  size_t have = uploaderCountQueueable("/benchls");
  if (have < (size_t)n) {
    Serial.printf("BENCHLS creating files=%ld have=%u\n", n, (unsigned)have);
    for (long i = 1; i <= n; i++) {
      char path[64];
      snprintf(path, sizeof path, "/benchls/ps-01-B9999-%04ld_1.jpg", i);
      if (storageFileSize(path) < 0 && !storageWriteVerified(path, kJpg, sizeof kJpg)) {
        Serial.printf("ERR benchls: write failed at %ld\n", i);
        return;
      }
      if (esp_task_wdt_status(nullptr) == ESP_OK) esp_task_wdt_reset();  // 500 FAT creates take long
      delay(1);
    }
  }
  uint32_t t0 = millis();
  size_t files = uploaderCountQueueable("/benchls");
  uint32_t ms = millis() - t0;
  Serial.printf("BENCHLS files=%u ms=%u\n", (unsigned)files, (unsigned)ms);
}

// Values are never echoed back. A field that fails validation leaves the stored value unchanged.
bool setField(const char* field, const std::string& value) {
  if (!configValid(field, value)) {
    Serial.printf("ERR set %s: invalid value\n", field);
    return false;
  }
  configSet(field, value);
  return true;
}

// The rest of the raw line after "set pass" and one separator: quotes and spaces are kept.
bool rawRestAfter(const std::string& line, const char* word, std::string& rest) {
  size_t i = line.find_first_not_of(" \t");
  if (i == std::string::npos || line.compare(i, 3, "set") != 0) return false;
  i = line.find_first_not_of(" \t", i + 3);
  size_t w = strlen(word);
  if (i == std::string::npos || line.compare(i, w, word) != 0) return false;
  i += w;
  if (i < line.size() && line[i] != ' ' && line[i] != '\t') return false;
  rest = i < line.size() ? line.substr(i + 1) : std::string();
  return true;
}

// set t <dbm> | set x <db> | set wifi <ssid> [<pass>] | set pass [<raw rest of line>] | set key <k>
// | set url <base> | set id <station> | set ota <pass> | set   (shows t and x).
void cmdSet(const Command& c) {
  if (c.args.empty()) {
    Serial.printf("OK set t=%d x=%d\n", (int)g_thresholdDbm, (int)g_marginDb);
    return;
  }
  const std::string& f = c.args[0];
  if (f == "pass") {
    std::string rest;
    if (!rawRestAfter(consoleRawLine(), "pass", rest)) {
      Serial.println("ERR usage: set pass [<password, rest of the line>]");
      return;
    }
    if (!setField("pass", rest)) return;  // empty rest clears the password (open network)
    netReconfigure(configGet());
    Serial.println("OK set pass");
    return;
  }
  if (f == "wifi") {
    if (c.args.size() < 2 || c.args.size() > 3) {
      Serial.println("ERR usage: set wifi <ssid> [<pass>]");
      return;
    }
    // Validate both values before storing either: an invalid one stores nothing.
    bool okSsid = configValid("ssid", c.args[1]);
    bool okPass = c.args.size() < 3 || configValid("pass", c.args[2]);
    if (!okSsid || !okPass) {
      Serial.printf("ERR set wifi: invalid %s\n", !okSsid ? "ssid" : "pass");
      return;
    }
    configSet("ssid", c.args[1]);
    if (c.args.size() == 3) configSet("pass", c.args[2]);
    netReconfigure(configGet());
    Serial.println("OK set wifi");
    return;
  }
  if (f == "key" || f == "url" || f == "id" || f == "ota") {
    if (c.args.size() != 2) {
      Serial.printf("ERR usage: set %s <value>\n", f.c_str());
      return;
    }
    if (!setField(f.c_str(), c.args[1])) return;
    Serial.printf("OK set %s%s\n", f.c_str(), (f == "id" || f == "ota") ? " (reboot to apply)" : "");
    return;
  }
  if (c.args.size() != 2 || (f != "t" && f != "x")) {
    Serial.println("ERR usage: set t <dbm -100..-20> | x <db 0..40> | wifi | pass | key | url | id | ota");
    return;
  }
  char* end = nullptr;
  long v = strtol(c.args[1].c_str(), &end, 10);
  bool isT = f == "t";
  bool bad = c.args[1].empty() || *end != '\0' || (isT ? (v < -100 || v > -20) : (v < 0 || v > 40));
  if (bad) {
    Serial.println("ERR set: value out of range");
    return;
  }
  Preferences prefs;
  prefs.begin("station", false);
  prefs.putInt(isT ? "t_dbm" : "x_db", (int)v);
  prefs.end();
  if (isT) g_thresholdDbm = (int)v;
  else g_marginDb = (int)v;
  Serial.printf("OK set %s=%ld\n", isT ? "t" : "x", v);
}

// docs/architecture.md (reliability): up to kInitTries tries, 1 s apart.
bool initWithRetry(bool (*init)(), const char* what) {
  for (int i = 1; i <= kInitTries; i++) {
    if (init()) return true;
    logLine("BOOT %s init failed (try %d/%d)", what, i, kInitTries);
    if (i < kInitTries) delay(1000);
  }
  return false;
}

// A failed SD or camera init restarts the board, but never into a fast reboot loop: NVS "init_fail"
// counts the consecutive boots with a failed init, and the kMaxInitFailBoots-th such boot stays up
// without the failing part (the heartbeat reports sd_ok / cam_ok). A boot with both parts up resets
// the count.
void checkInit(bool sd, bool cam) {
  Preferences prefs;
  prefs.begin("station", false);
  uint8_t fails = prefs.getUChar("init_fail", 0);
  if (sd && cam) {
    if (fails) prefs.putUChar("init_fail", 0);
    prefs.end();
    return;
  }
  if (fails < 255) fails++;
  prefs.putUChar("init_fail", fails);
  prefs.end();
  if (fails < kMaxInitFailBoots) {
    logLine("BOOT init failed sd=%d cam=%d: restart (failed boot %u of %u)", (int)sd, (int)cam, (unsigned)fails,
            (unsigned)kMaxInitFailBoots);
    Serial.flush();
    delay(100);
    ESP.restart();
  }
  logLine("BOOT init failed sd=%d cam=%d on %u boots in a row: staying up without it", (int)sd, (int)cam,
          (unsigned)fails);
}

void cmdReboot(const Command&) {
  Serial.println("OK reboot");
  Serial.flush();
  delay(100);
  ESP.restart();
}
}  // namespace

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(10);  // a stalled host must not hold the visit task for long
  uint32_t t = millis();
  while (!Serial && millis() - t < 2000) delay(10);

  Preferences prefs;
  prefs.begin("station", false);
  g_boot = prefs.getUInt("boot", 0) + 1;
  prefs.putUInt("boot", g_boot);
  prefs.end();
  StationConfig cfg = configLoad();
  g_thresholdDbm = cfg.tDbm;
  g_marginDb = cfg.xDb;
  g_stationId = cfg.stationId;

  bool sd = initWithRetry(storageInit, "sd");
  logLine("BOOT station=%s fw=%s boot=%u sd=%d", g_stationId.c_str(), kFirmware, (unsigned)g_boot, (int)sd);
  bool cam = initWithRetry(cameraInit, "camera");
  checkInit(sd, cam);  // may restart
  if (sd) storagePruneSent();
  lightInit();
  pirInit();

  g_tagLock = xSemaphoreCreateMutex();
  uint32_t heapBefore = ESP.getFreeHeap();
  bleStart(g_tags, g_tagLock);
  logLine("BLE start heap_before=%u heap_after=%u t=%d x=%d", (unsigned)heapBefore,
          (unsigned)ESP.getFreeHeap(), (int)g_thresholdDbm, (int)g_marginDb);

  consoleRegister("info", cmdInfo);
  consoleRegister("pir", cmdPir);
  consoleRegister("snap", cmdSnap);
  consoleRegister("ls", cmdLs);
  consoleRegister("cat", cmdCat);
  consoleRegister("light", cmdLight);
  consoleRegister("scan", cmdScan);
  consoleRegister("set", cmdSet);
  consoleRegister("benchls", cmdBenchLs);
  consoleRegister("reboot", cmdReboot);

  // docs/architecture.md (reliability): the visit and uploader tasks subscribe to the task watchdog. 30 s instead of the
  // default 5 s; IDLE0 stays watched as before (CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU0).
  esp_task_wdt_config_t wdt = {};
  wdt.timeout_ms = kWdtTimeoutMs;
  wdt.idle_core_mask = 1u << 0;
  wdt.trigger_panic = true;
  if (esp_task_wdt_reconfigure(&wdt) != ESP_OK) logLine("BOOT task watchdog reconfigure FAILED");

  xTaskCreatePinnedToCore(visitTask, "visit", 8192, nullptr, 2, nullptr, 1);
  netStart(cfg);
  uploaderStart({[]() { return (bool)g_visitOpen; }, kFirmware});
  logLine("READY");
}

// Free stack bytes at the lowest point so far (ESP-IDF stacks are counted in bytes); 0 = no task.
unsigned stackFree(const char* task) {
  TaskHandle_t h = xTaskGetHandle(task);
  return h ? (unsigned)uxTaskGetStackHighWaterMark(h) : 0;
}

// One BLE/heap line per minute in the log (loop task: 8 KB stack, already does SD work).
void logBleStats() {
  static uint32_t last = millis();
  uint32_t now = millis();
  if (now - last < kBleStatsEveryMs) return;
  last = now;
  BleStats b = bleStats();
  size_t tags = 0;
  if (xSemaphoreTake(g_tagLock, pdMS_TO_TICKS(200)) == pdTRUE) {
    tags = g_tags.tagCount();
    xSemaphoreGive(g_tagLock);
  }
  logLine("BLE adv=%u tag=%u lock_miss=%u restarts=%u tags=%u heap=%u min_heap=%u int_free=%u int_largest=%u "
          "stack_free visit=%u upload=%u ble=%u",
          (unsigned)b.adv, (unsigned)b.tag, (unsigned)b.lockMiss, (unsigned)b.restarts, (unsigned)tags,
          (unsigned)ESP.getFreeHeap(), (unsigned)ESP.getMinFreeHeap(),
          (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
          (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL), stackFree("visit"), stackFree("upload"),
          stackFree("ble"));
}

void loop() {
  consolePoll();
  netLoop();
  logBleStats();
  delay(10);
}
