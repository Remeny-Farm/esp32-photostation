// Station configuration in NVS (namespace "station"). Secrets live only here, never in source.
#pragma once
#include <stdint.h>

#include <string>

struct StationConfig {
  std::string ssid, pass, stationId, key, baseUrl, otaPass;
  int tDbm = -60, xDb = 8;
};

// Reads NVS once at boot (defaults: station id "ps-01", T -60 dBm, X 8 dB) and caches the result.
StationConfig configLoad();
// Thread-safe copy of the current cache (the uploader reads it before every pass).
StationConfig configGet();
// field: ssid | pass | id | key | url | ota. Stores into NVS and the cache. Unknown field: ignored.
void configSet(const std::string& field, const std::string& value);
// Same fields. Checks length and content only (no control characters; url must start http:// or https://).
bool configValid(const std::string& field, const std::string& value);
// Incremented by every configSet("key"|"url", ...): the uploader leaves AuthStop when it changes.
uint32_t configCredVersion();
