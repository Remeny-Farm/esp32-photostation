#include "record.h"

#include <cstdio>
#include <ctime>

namespace {

std::string fmtTime(int64_t epochSec, const char* fmt) {
  time_t t = static_cast<time_t>(epochSec);
  struct tm tmv;
  gmtime_r(&t, &tmv);
  char buf[32];
  strftime(buf, sizeof buf, fmt, &tmv);
  return buf;
}

std::string pad4(uint32_t v) {
  char buf[16];
  std::snprintf(buf, sizeof buf, "%04u", static_cast<unsigned>(v));
  return buf;
}

std::string quote(const std::string& s) {
  std::string out = "\"";
  for (char ch : s) {
    unsigned char c = static_cast<unsigned char>(ch);
    if (c == '"') {
      out += "\\\"";
    } else if (c == '\\') {
      out += "\\\\";
    } else if (c < 0x20) {
      char buf[8];
      std::snprintf(buf, sizeof buf, "\\u%04x", c);
      out += buf;
    } else {
      out += ch;
    }
  }
  out += '"';
  return out;
}

std::string timeOrNull(int64_t epochSec) {
  return epochSec < 0 ? "null" : quote(isoUtc(epochSec));
}

std::string strOrNull(bool present, const std::string& s) { return present ? quote(s) : "null"; }

}  // namespace

std::string makeVisitId(const std::string& station, int64_t epochSec, uint32_t bootCount,
                        uint32_t counter) {
  if (epochSec < 0) return station + "-B" + pad4(bootCount) + "-" + pad4(counter);
  return station + "-" + fmtTime(epochSec, "%Y%m%dT%H%M%SZ") + "-" + pad4(counter);
}

std::string isoUtc(int64_t epochSec) { return fmtTime(epochSec, "%Y-%m-%dT%H:%M:%SZ"); }

std::string photoPath(const std::string& visitId, int n) {
  return "/q/" + visitId + "_" + std::to_string(n) + ".jpg";
}

std::string metaPath(const std::string& visitId) { return "/q/" + visitId + ".json"; }

std::string sentDir(int64_t epochSec) {
  if (epochSec < 0) return "/sent/unsynced";
  return "/sent/" + fmtTime(epochSec, "%Y%m%d");
}

std::string visitJson(const VisitRecord& r) {
  std::string j = "{";
  j += "\"station_id\":" + quote(r.station);
  j += ",\"visit_id\":" + quote(r.visitId);
  j += ",\"started_at\":" + timeOrNull(r.startedAt);
  j += ",\"ended_at\":" + timeOrNull(r.endedAt);
  j += std::string(",\"time_synced\":") + (r.timeSynced ? "true" : "false");
  j += ",\"photos\":[";
  for (size_t i = 0; i < r.photos.size(); i++) {
    const PhotoInfo& p = r.photos[i];
    if (i) j += ",";
    j += "{\"n\":" + std::to_string(p.n);
    j += ",\"captured_at\":" + timeOrNull(p.capturedAt);
    j += ",\"bytes\":" + std::to_string(p.bytes);
    j += ",\"width\":" + std::to_string(p.width);
    j += ",\"height\":" + std::to_string(p.height) + "}";
  }
  j += "],\"identification\":{";
  j += std::string("\"decision\":") + (r.decision.known ? "\"tag\"" : "\"unknown\"");
  j += ",\"tag_mac\":" + strOrNull(r.decision.known, r.decision.mac);
  j += ",\"tag_name\":" + strOrNull(r.decision.known, r.decision.name);
  j += ",\"candidates\":[";
  for (size_t i = 0; i < r.decision.candidates.size(); i++) {
    const Candidate& c = r.decision.candidates[i];
    if (i) j += ",";
    j += "{\"mac\":" + quote(c.mac);
    j += ",\"median\":" + std::to_string(c.median);
    j += ",\"count\":" + std::to_string(c.count);
    j += ",\"min\":" + std::to_string(c.min);
    j += ",\"max\":" + std::to_string(c.max) + "}";
  }
  j += "],\"threshold_dbm\":" + std::to_string(r.thresholdDbm);
  j += ",\"margin_db\":" + std::to_string(r.marginDb) + "}";
  j += ",\"firmware\":" + quote(r.firmware) + "}";
  return j;
}
