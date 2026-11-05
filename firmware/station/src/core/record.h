// Visit ids, SD paths and the visit JSON (docs/architecture.md, SD layout). Pure C++17, no Arduino headers.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

#include "ident.h"

struct PhotoInfo {
  int n;
  int64_t capturedAt;  // < 0 = unknown
  uint32_t bytes;
  int width, height;
};

struct VisitRecord {
  std::string station, visitId, firmware;
  int64_t startedAt = -1, endedAt = -1;  // < 0 = unknown
  bool timeSynced = false;
  std::vector<PhotoInfo> photos;
  Decision decision;
  int thresholdDbm = 0, marginDb = 0, lightPwm = 0;
};

// epochSec < 0 = clock not synced. Synced: <station>-<YYYYMMDD>T<HHMMSS>Z-<counter:4>.
// Unsynced: <station>-B<bootCount:4>-<counter:4>.
std::string makeVisitId(const std::string& station, int64_t epochSec, uint32_t bootCount,
                        uint32_t counter);
std::string isoUtc(int64_t epochSec);  // 2026-11-03T10:15:00Z
std::string photoPath(const std::string& visitId, int n);
std::string metaPath(const std::string& visitId);
std::string sentDir(int64_t epochSec);  // /sent/YYYYMMDD, or /sent/unsynced when epochSec < 0
std::string visitJson(const VisitRecord& r);
