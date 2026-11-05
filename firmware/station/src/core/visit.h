// Visit state machine: PIR edges in, Open/Capture/Close events out.
// Pure C++17, no Arduino headers. All time math is wrap-safe (uint32 millis).
#pragma once
#include <cstdint>

enum class VisitEv { None, Open, Capture, Close };
enum class CloseReason { None, Silence, Forced };

struct VisitStep {
  VisitEv ev;
  int n;  // photo 1..5 for Capture, else 0
  CloseReason reason;
};

struct VisitTiming {
  uint32_t settleMs = 1500, spacingMs = 1500, extraSpacingMs = 20000, silenceMs = 30000,
           forcedMs = 600000;
  int burst = 3, maxPhotos = 5;
};

class VisitMachine {
 public:
  explicit VisitMachine(VisitTiming t = {});
  // Call every <= 50 ms. Returns at most one event.
  VisitStep tick(uint32_t nowMs, bool pirEdge);
  // Call when the capture of the last Capture event has finished (or failed). The next photo is
  // then due spacingMs (burst) or extraSpacingMs (extra) after nowMs. Without it, the next photo
  // is due from the Capture emission time as before.
  void photoDone(uint32_t nowMs);
  bool open() const { return open_; }
  uint32_t startMs() const { return start_; }
  uint32_t endMs() const { return end_; }
  int photos() const { return photos_; }

 private:
  VisitTiming t_;
  bool open_ = false;
  bool pirSincePhoto_ = false;
  bool doneValid_ = false;  // photoDone() was called for the last emitted Capture
  uint32_t start_ = 0, end_ = 0, lastPir_ = 0, lastPhoto_ = 0, lastDone_ = 0;
  int photos_ = 0;
};
