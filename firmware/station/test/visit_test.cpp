#include <cstdint>
#include <functional>
#include <vector>

#include "check.h"
#include "core/visit.h"

namespace {

struct Rec {
  uint32_t ms;  // relative to base
  VisitStep step;
};

// Drives the machine with a 10 ms tick from rel 0..durationMs (inclusive).
// edgeAt(rel) says whether a PIR edge arrives on that tick.
std::vector<Rec> drive(uint32_t base, uint32_t durationMs,
                       const std::function<bool(uint32_t)>& edgeAt, VisitMachine& m) {
  std::vector<Rec> out;
  for (uint32_t rel = 0; rel <= durationMs; rel += 10) {
    VisitStep s = m.tick(base + rel, edgeAt(rel));
    if (s.ev != VisitEv::None) out.push_back({rel, s});
  }
  return out;
}

bool isCapture(const Rec& r, uint32_t ms, int n) {
  return r.ms == ms && r.step.ev == VisitEv::Capture && r.step.n == n;
}

bool isClose(const Rec& r, uint32_t ms, CloseReason why) {
  return r.ms == ms && r.step.ev == VisitEv::Close && r.step.reason == why;
}

void burstThree(uint32_t base) {
  VisitMachine m;
  auto ev = drive(base, 100000, [](uint32_t rel) { return rel == 0; }, m);
  CHECK_EQ(ev.size(), (size_t)5);
  if (ev.size() != 5) return;
  CHECK(ev[0].ms == 0 && ev[0].step.ev == VisitEv::Open);
  CHECK(isCapture(ev[1], 1500, 1));
  CHECK(isCapture(ev[2], 3000, 2));
  CHECK(isCapture(ev[3], 4500, 3));
  CHECK(isClose(ev[4], 30000, CloseReason::Silence));
  CHECK(!m.open());
  CHECK_EQ(m.photos(), 3);
  CHECK_EQ(m.startMs(), base);
  CHECK_EQ(m.endMs(), base + 30000u);
}

}  // namespace

TEST(visit_burst_three) { burstThree(0); }

TEST(visit_spacing_after_slow_photo) {
  VisitMachine m;
  std::vector<Rec> ev;
  for (uint32_t t = 0; t <= 8000; t += 10) {
    VisitStep s = m.tick(t, t == 0);
    if (s.ev != VisitEv::None) ev.push_back({t, s});
    if (t == 2400) m.photoDone(2400);  // capture 1 took 900 ms
    if (t == 4000) m.photoDone(4000);
  }
  CHECK_EQ(ev.size(), (size_t)4);
  if (ev.size() != 4) return;
  CHECK(isCapture(ev[1], 1500, 1));
  CHECK(isCapture(ev[2], 3900, 2));
  CHECK(isCapture(ev[3], 5500, 3));
}

TEST(visit_extra_photos_when_pir_continues) {
  VisitMachine m;
  auto ev = drive(0, 110000, [](uint32_t rel) { return rel % 5000 == 0 && rel <= 70000; }, m);
  CHECK_EQ(ev.size(), (size_t)7);
  if (ev.size() != 7) return;
  CHECK(ev[0].ms == 0 && ev[0].step.ev == VisitEv::Open);
  CHECK(isCapture(ev[1], 1500, 1));
  CHECK(isCapture(ev[2], 3000, 2));
  CHECK(isCapture(ev[3], 4500, 3));
  CHECK(isCapture(ev[4], 24500, 4));
  CHECK(isCapture(ev[5], 44500, 5));
  CHECK(isClose(ev[6], 100000, CloseReason::Silence));
  CHECK_EQ(m.photos(), 5);
}

TEST(visit_no_extra_without_new_pir) {
  VisitMachine m;
  auto ev = drive(0, 60000, [](uint32_t rel) { return rel == 0 || rel == 2000; }, m);
  int captures = 0;
  for (const Rec& r : ev) captures += r.step.ev == VisitEv::Capture;
  CHECK_EQ(captures, 3);
  CHECK_EQ(ev.size(), (size_t)5);
  if (ev.size() == 5) CHECK(isClose(ev[4], 32000, CloseReason::Silence));
}

TEST(visit_forced_close) {
  VisitMachine m;
  auto ev = drive(0, 600000, [](uint32_t rel) { return rel % 1000 == 0 && rel < 600000; }, m);
  CHECK(!ev.empty());
  if (ev.empty()) return;
  CHECK(isClose(ev.back(), 600000, CloseReason::Forced));
  CHECK(!m.open());
  CHECK_EQ(m.endMs(), 600000u);
  VisitStep s = m.tick(601000, true);
  CHECK(s.ev == VisitEv::Open);
  CHECK(m.open());
  CHECK_EQ(m.startMs(), 601000u);
  CHECK_EQ(m.photos(), 0);
}

TEST(visit_wraps_millis) { burstThree(0xFFFFF000u); }

TEST(visit_idle_ignores_time) {
  VisitMachine m;
  auto ev = drive(0xFFFF0000u, 1000000, [](uint32_t) { return false; }, m);
  CHECK(ev.empty());
  CHECK(!m.open());
}

TEST(visit_edge_after_close_reopens) {
  VisitMachine m;
  drive(0, 30000, [](uint32_t rel) { return rel == 0; }, m);
  CHECK(!m.open());
  VisitStep s = m.tick(40000, true);
  CHECK(s.ev == VisitEv::Open);
  CHECK_EQ(m.startMs(), 40000u);
}

CHECK_MAIN()
