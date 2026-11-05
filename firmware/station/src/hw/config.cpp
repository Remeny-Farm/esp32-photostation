#include "config.h"

#include <Arduino.h>
#include <Preferences.h>

#include <mutex>

namespace {
std::mutex g_mu;
StationConfig g_cfg;
uint32_t g_credVersion = 0;

const char* nvsKey(const std::string& f) {
  if (f == "ssid") return "ssid";
  if (f == "pass") return "pass";
  if (f == "id") return "id";
  if (f == "key") return "key";
  if (f == "url") return "url";
  if (f == "ota") return "ota";
  return nullptr;
}

std::string* member(StationConfig& c, const std::string& f) {
  if (f == "ssid") return &c.ssid;
  if (f == "pass") return &c.pass;
  if (f == "id") return &c.stationId;
  if (f == "key") return &c.key;
  if (f == "url") return &c.baseUrl;
  if (f == "ota") return &c.otaPass;
  return nullptr;
}

bool startsWith(const std::string& s, const char* p) { return s.rfind(p, 0) == 0; }
}  // namespace

StationConfig configLoad() {
  Preferences p;
  p.begin("station", true);
  StationConfig c;
  c.ssid = p.getString("ssid", "").c_str();
  c.pass = p.getString("pass", "").c_str();
  c.stationId = p.getString("id", "ps-01").c_str();
  c.key = p.getString("key", "").c_str();
  c.baseUrl = p.getString("url", "").c_str();
  c.otaPass = p.getString("ota", "").c_str();
  c.tDbm = p.getInt("t_dbm", -60);
  c.xDb = p.getInt("x_db", 8);
  p.end();
  if (c.stationId.empty()) c.stationId = "ps-01";
  std::lock_guard<std::mutex> l(g_mu);
  g_cfg = c;
  return c;
}

StationConfig configGet() {
  std::lock_guard<std::mutex> l(g_mu);
  return g_cfg;
}

bool configValid(const std::string& field, const std::string& value) {
  for (unsigned char ch : value) {
    if (ch < 0x20 || ch == 0x7f) return false;
  }
  if (field == "ssid") return !value.empty() && value.size() <= 32;
  if (field == "pass") return value.empty() || (value.size() >= 8 && value.size() <= 63);  // empty = open network; WPA2 needs 8..63
  if (field == "id") {
    if (value.empty() || value.size() > 31) return false;
    for (char ch : value) {  // also the mDNS host name: letters, digits, '-'
      if (!isalnum((unsigned char)ch) && ch != '-') return false;
    }
    return true;
  }
  if (field == "key") return !value.empty() && value.size() <= 128;
  if (field == "ota") return !value.empty() && value.size() <= 63;
  if (field == "url") {
    return value.size() <= 200 && (startsWith(value, "http://") || startsWith(value, "https://")) &&
           value.size() > 8;
  }
  return false;
}

void configSet(const std::string& field, const std::string& value) {
  const char* k = nvsKey(field);
  if (!k) return;
  Preferences p;
  p.begin("station", false);
  p.putString(k, value.c_str());
  p.end();
  std::lock_guard<std::mutex> l(g_mu);
  *member(g_cfg, field) = value;
  if (field == "key" || field == "url") g_credVersion++;
}

uint32_t configCredVersion() {
  std::lock_guard<std::mutex> l(g_mu);
  return g_credVersion;
}
