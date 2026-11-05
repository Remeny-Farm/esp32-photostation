#include "visit.h"

VisitMachine::VisitMachine(VisitTiming t) : t_(t) {}

void VisitMachine::photoDone(uint32_t now) {
  if (!open_ || photos_ == 0) return;
  lastDone_ = now;
  doneValid_ = true;
}

VisitStep VisitMachine::tick(uint32_t now, bool pirEdge) {
  if (!open_) {
    if (!pirEdge) return {VisitEv::None, 0, CloseReason::None};
    open_ = true;
    start_ = end_ = lastPir_ = lastPhoto_ = now;
    photos_ = 0;
    pirSincePhoto_ = false;
    doneValid_ = false;
    return {VisitEv::Open, 0, CloseReason::None};
  }

  if (pirEdge) lastPir_ = now;

  // The forced cap wins over everything else.
  if (now - start_ >= t_.forcedMs) {
    open_ = false;
    end_ = now;
    return {VisitEv::Close, 0, CloseReason::Forced};
  }

  VisitStep step{VisitEv::None, 0, CloseReason::None};
  if (photos_ < t_.burst) {
    bool isDue;
    if (photos_ > 0 && doneValid_) {
      isDue = now - lastDone_ >= t_.spacingMs;
    } else {
      uint32_t due = t_.settleMs + static_cast<uint32_t>(photos_) * t_.spacingMs;
      isDue = now - start_ >= due;
    }
    if (isDue) step = {VisitEv::Capture, ++photos_, CloseReason::None};
  } else if (photos_ < t_.maxPhotos && pirSincePhoto_ &&
             now - (doneValid_ ? lastDone_ : lastPhoto_) >= t_.extraSpacingMs) {
    step = {VisitEv::Capture, ++photos_, CloseReason::None};
  }

  if (step.ev == VisitEv::Capture) {
    lastPhoto_ = now;
    doneValid_ = false;
    pirSincePhoto_ = false;
  } else if (photos_ >= t_.burst && now - lastPir_ >= t_.silenceMs) {
    open_ = false;
    end_ = now;
    step = {VisitEv::Close, 0, CloseReason::Silence};
  }

  // An edge on the same tick as a photo counts as after that photo.
  if (pirEdge) pirSincePhoto_ = true;
  return step;
}
