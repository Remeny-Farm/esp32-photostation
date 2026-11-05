#include "check.h"
#include "core/record.h"

static VisitRecord sample() {
  VisitRecord r;
  r.station = "ps-01";
  r.visitId = "ps-01-20261103T101500Z-0042";
  r.firmware = "station 0.1.0";
  r.startedAt = 1793700900;
  r.endedAt = 1793700970;
  r.timeSynced = true;
  r.photos.push_back({1, 1793700910, 135012, 1600, 1200});
  r.photos.push_back({2, 1793700920, 130000, 1600, 1200});
  r.decision.known = true;
  r.decision.mac = "AA:BB:CC:DD:EE:01";
  r.decision.name = "TAG-0001";
  r.decision.candidates.push_back({"AA:BB:CC:DD:EE:01", "TAG-0001", -48, 12, -54, -45});
  r.decision.candidates.push_back({"AA:BB:CC:DD:EE:02", "TAG-0002", -70, 3, -75, -66});
  r.thresholdDbm = -60;
  r.marginDb = 8;
  r.lightPwm = 180;
  return r;
}

TEST(visit_id_synced) {
  CHECK_EQ(makeVisitId("ps-01", 1793700900, 7, 42), std::string("ps-01-20261103T101500Z-0042"));
}

TEST(visit_id_unsynced) {
  CHECK_EQ(makeVisitId("ps-01", -1, 7, 42), std::string("ps-01-B0007-0042"));
}

TEST(iso_utc) {
  CHECK_EQ(isoUtc(1793700900), std::string("2026-11-03T10:15:00Z"));
}

TEST(paths) {
  CHECK_EQ(photoPath("v1", 2), std::string("/q/v1_2.jpg"));
  CHECK_EQ(metaPath("v1"), std::string("/q/v1.json"));
  CHECK_EQ(sentDir(1793700900), std::string("/sent/20261103"));
  CHECK_EQ(sentDir(-1), std::string("/sent/unsynced"));
}

TEST(json_known_tag) {
  const std::string expected =
      "{\"station_id\":\"ps-01\",\"visit_id\":\"ps-01-20261103T101500Z-0042\","
      "\"started_at\":\"2026-11-03T10:15:00Z\",\"ended_at\":\"2026-11-03T10:16:10Z\","
      "\"time_synced\":true,"
      "\"photos\":[{\"n\":1,\"captured_at\":\"2026-11-03T10:15:10Z\",\"bytes\":135012,"
      "\"width\":1600,\"height\":1200},"
      "{\"n\":2,\"captured_at\":\"2026-11-03T10:15:20Z\",\"bytes\":130000,"
      "\"width\":1600,\"height\":1200}],"
      "\"identification\":{\"decision\":\"tag\",\"tag_mac\":\"AA:BB:CC:DD:EE:01\","
      "\"tag_name\":\"TAG-0001\","
      "\"candidates\":[{\"mac\":\"AA:BB:CC:DD:EE:01\",\"median\":-48,\"count\":12,"
      "\"min\":-54,\"max\":-45},"
      "{\"mac\":\"AA:BB:CC:DD:EE:02\",\"median\":-70,\"count\":3,\"min\":-75,\"max\":-66}],"
      "\"threshold_dbm\":-60,\"margin_db\":8},"
      "\"firmware\":\"station 0.1.0\",\"light_pwm\":180}";
  CHECK_EQ(visitJson(sample()), expected);
}

TEST(json_unsynced_times_null) {
  VisitRecord r = sample();
  r.startedAt = -1;
  r.endedAt = -1;
  r.timeSynced = false;
  r.photos[0].capturedAt = -1;
  std::string j = visitJson(r);
  CHECK(j.find("\"started_at\":null") != std::string::npos);
  CHECK(j.find("\"ended_at\":null") != std::string::npos);
  CHECK(j.find("\"time_synced\":false") != std::string::npos);
  CHECK(j.find("\"n\":1,\"captured_at\":null") != std::string::npos);
}

TEST(json_escapes_name) {
  VisitRecord r = sample();
  r.decision.name = "TAG-\"x\"\\";
  CHECK(visitJson(r).find("\"TAG-\\\"x\\\"\\\\\"") != std::string::npos);
}

TEST(json_escapes_control_chars) {
  VisitRecord r = sample();
  r.decision.name = std::string("a\nb\x01") + "c";
  CHECK(visitJson(r).find("\"a\\u000ab\\u0001c\"") != std::string::npos);
}

TEST(json_unknown_decision) {
  VisitRecord r = sample();
  r.decision.known = false;
  r.decision.mac.clear();
  r.decision.name.clear();
  std::string j = visitJson(r);
  CHECK(j.find("\"decision\":\"unknown\"") != std::string::npos);
  CHECK(j.find("\"tag_name\":null") != std::string::npos);
  CHECK(j.find("\"tag_mac\":null") != std::string::npos);
}

TEST(json_no_photos_no_candidates) {
  VisitRecord r = sample();
  r.photos.clear();
  r.decision.candidates.clear();
  std::string j = visitJson(r);
  CHECK(j.find("\"photos\":[]") != std::string::npos);
  CHECK(j.find("\"candidates\":[]") != std::string::npos);
}

CHECK_MAIN()
