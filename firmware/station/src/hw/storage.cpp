#include "storage.h"

#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>
#include <esp_task_wdt.h>
#include <algorithm>
#include <mutex>
#include <utility>
#include <vector>

#include "log.h"

namespace {
constexpr int kCs = 21, kSck = 7, kMiso = 8, kMosi = 9;
constexpr uint32_t kSdHz = 20000000;
constexpr uint8_t kPruneAbovePct = 80;
constexpr size_t kYieldEvery = 32;

bool g_ready = false;
std::recursive_mutex g_mu;

struct Guard {
  Guard() { g_mu.lock(); }
  ~Guard() { g_mu.unlock(); }
};

std::string baseName(const std::string& p) {
  size_t i = p.rfind('/');
  return i == std::string::npos ? p : p.substr(i + 1);
}

bool mkdirs(const std::string& dir) {
  size_t pos = 1;
  while (pos <= dir.size()) {
    size_t next = dir.find('/', pos);
    if (next == std::string::npos) next = dir.size();
    std::string part = dir.substr(0, next);
    if (!part.empty() && !SD.exists(part.c_str()) && !SD.mkdir(part.c_str())) return false;
    pos = next + 1;
  }
  return true;
}

// One readdir pass over dir; the caller holds g_mu. fn(bareName, isDir) returns false to stop.
// getNextFileName() reads the directory entry only: no fopen/stat per entry (openNextFile() opens
// every entry, which made a long /q listing O(N^2) on FAT). Yields one tick every kYieldEvery entries.
template <typename Fn>
void scanDir(const char* dir, Fn fn) {
  File d = SD.open(dir);
  if (!d) return;
  if (d.isDirectory()) {
    size_t seen = 0;
    for (;;) {
      bool isDir = false;
      String p = d.getNextFileName(&isDir);
      if (p.isEmpty()) break;  // end of directory (FAT has only files and directories)
      if (!fn(baseName(p.c_str()), isDir)) break;
      if (++seen % kYieldEvery == 0) vTaskDelay(1);
    }
  }
  d.close();
}

// Each FAT remove scans the directory from its start, so a large day can take many seconds. Every
// batch that made progress feeds the task watchdog of a subscribed caller (the uploader).
void feedWatchdog() {
  if (esp_task_wdt_status(nullptr) == ESP_OK) esp_task_wdt_reset();
}

// Removes dir and everything below it in batches of kYieldEvery entries. The lock is taken per
// batch, never for the whole tree. Stops when a batch removes nothing (the caller sees dir remain).
void removeTree(const std::string& dir) {
  for (;;) {
    std::vector<std::pair<std::string, bool>> batch;
    size_t removed = 0;
    {
      Guard g;
      scanDir(dir.c_str(), [&](const std::string& n, bool isDir) {
        batch.push_back({dir + "/" + n, isDir});
        return batch.size() < kYieldEvery;
      });
      for (const auto& e : batch) {
        if (!e.second && SD.remove(e.first.c_str())) removed++;
      }
    }
    for (const auto& e : batch) {
      if (!e.second) continue;
      removeTree(e.first);
      Guard g;
      if (!SD.exists(e.first.c_str())) removed++;
    }
    if (batch.empty() || removed == 0) break;
    feedWatchdog();
    vTaskDelay(1);
  }
  Guard g;
  SD.rmdir(dir.c_str());
}
}  // namespace

bool storageReady() { return g_ready; }
void storageLock() { g_mu.lock(); }
void storageUnlock() { g_mu.unlock(); }

bool storageInit() {
  Guard g;
  SPI.begin(kSck, kMiso, kMosi, kCs);
  g_ready = SD.begin(kCs, SPI, kSdHz) && SD.cardType() != CARD_NONE;
  if (!g_ready) return false;
  for (const char* d : {"/q", "/sent", "/bad", "/log"}) mkdirs(d);
  std::vector<std::string> tmps;
  scanDir("/q", [&](const std::string& n, bool isDir) {
    if (!isDir && n.size() > 4 && n.compare(n.size() - 4, 4, ".tmp") == 0) tmps.push_back("/q/" + n);
    return true;
  });
  for (const auto& p : tmps) SD.remove(p.c_str());
  return true;
}

bool storageWriteVerified(const char* path, const uint8_t* buf, size_t len) {
  if (!g_ready) return false;
  Guard g;
  std::string tmp = std::string(path) + ".tmp";
  bool ok = false;
  File f = SD.open(tmp.c_str(), FILE_WRITE);
  if (f) {
    size_t w = f.write(buf, len);
    f.flush();
    f.close();
    if (w == len) {
      File r = SD.open(tmp.c_str(), FILE_READ);
      if (r && r.size() == len) {
        uint8_t chunk[512];
        size_t same = 0;
        ok = true;
        while (same < len) {
          int n = r.read(chunk, sizeof chunk);
          if (n <= 0 || (size_t)n > len - same || memcmp(chunk, buf + same, n) != 0) {
            ok = false;
            break;
          }
          same += n;
        }
        if (same != len) ok = false;
      }
      if (r) r.close();
    }
  }
  if (ok) {
    SD.remove(path);  // the SD library rename does not overwrite
    ok = SD.rename(tmp.c_str(), path);
  }
  if (!ok) SD.remove(tmp.c_str());
  return ok;
}

bool storageWriteText(const char* path, const std::string& s) {
  return storageWriteVerified(path, reinterpret_cast<const uint8_t*>(s.data()), s.size());
}

size_t storageForEach(const char* dir, const std::function<void(const std::string&)>& fn) {
  if (!g_ready) return 0;
  Guard g;
  size_t files = 0;
  scanDir(dir, [&](const std::string& n, bool isDir) {
    if (!isDir) {
      files++;
      fn(n);
    }
    return true;
  });
  return files;
}

int64_t storageFileSize(const char* path) {
  if (!g_ready) return -1;
  Guard g;
  File f = SD.open(path, FILE_READ);
  if (!f) return -1;
  int64_t n = f.isDirectory() ? -1 : (int64_t)f.size();
  f.close();
  return n;
}

bool storageReadTail(const char* path, std::string& out, size_t maxBytes) {
  if (!g_ready) return false;
  Guard g;
  File f = SD.open(path, FILE_READ);
  if (!f || f.isDirectory()) {
    if (f) f.close();
    return false;
  }
  size_t size = f.size();
  if (size > maxBytes) f.seek(size - maxBytes);
  out.clear();
  uint8_t chunk[256];
  int n;
  while ((n = f.read(chunk, sizeof chunk)) > 0) out.append((const char*)chunk, n);
  f.close();
  return true;
}

bool storageEnsureDir(const char* dir) {
  if (!g_ready) return false;
  Guard g;
  return mkdirs(dir);
}

bool storageMove(const char* from, const char* toDir) {
  if (!g_ready) return false;
  Guard g;
  if (!mkdirs(toDir)) return false;
  std::string to = std::string(toDir) + "/" + baseName(from);
  SD.remove(to.c_str());
  return SD.rename(from, to.c_str());
}

bool storageRemoveTree(const char* dir) {
  // Containment: only /benchls itself or a path below it (no ".." component).
  if (!dir || !g_ready) return false;
  std::string d(dir);
  bool inside = d == "/benchls" || d.rfind("/benchls/", 0) == 0;
  if (!inside || d.find("..") != std::string::npos) return false;
  removeTree(d);
  Guard g;
  return !SD.exists(d.c_str());
}

uint64_t storageSizeMb() {
  if (!g_ready) return 0;
  Guard g;
  return SD.cardSize() / (1024 * 1024);
}

uint8_t storageUsedPct() {
  if (!g_ready) return 0;
  Guard g;
  uint64_t total = SD.totalBytes();
  if (total == 0) return 0;
  return (uint8_t)std::min<uint64_t>(100, SD.usedBytes() * 100 / total);
}

void storagePruneSent() {
  if (!g_ready || storageUsedPct() <= kPruneAbovePct) return;
  // "unsynced" has no known date, so it counts as the oldest.
  auto older = [](const std::string& a, const std::string& b) {
    bool ua = a == "unsynced", ub = b == "unsynced";
    if (ua != ub) return ua;
    return a < b;
  };
  std::string oldest;
  {
    Guard g;
    scanDir("/sent", [&](const std::string& n, bool isDir) {
      if (isDir && (oldest.empty() || older(n, oldest))) oldest = n;
      return true;
    });
  }
  if (oldest.empty()) return;
  std::string dir = "/sent/" + oldest;
  logLine("PRUNE %s (used %u%%)", dir.c_str(), storageUsedPct());
  removeTree(dir);  // one day per call: the next pass prunes the next day if still above 80 %
  Guard g;
  if (SD.exists(dir.c_str())) logLine("PRUNE %s FAILED", dir.c_str());
}
