#include "pir.h"

#include <Arduino.h>
#include <atomic>

#include "log.h"

namespace {
constexpr int kPin = 1;
constexpr int kStuckAfterForced = 3;
std::atomic<bool> g_edge{false};
std::atomic<bool> g_stuck{false};       // ignore the level, edges only
std::atomic<uint32_t> g_forcedTotal{0};
int g_forcedRun = 0;                    // visit task only
void IRAM_ATTR onRise() { g_edge.store(true, std::memory_order_relaxed); }

bool levelHigh() { return !g_stuck.load() && digitalRead(kPin) == HIGH; }
}  // namespace

void pirInit() {
  // Pull-down: an unwired or floating pin must not fake visits.
  pinMode(kPin, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(kPin), onRise, RISING);
}

bool pirTakeEdge() {
  if (g_stuck.load() && digitalRead(kPin) == LOW) {
    g_stuck.store(false);
    g_forcedRun = 0;
    logLine("PIR pin LOW again: level detection back on");
  }
  bool latched = g_edge.exchange(false);
  return latched || levelHigh();
}

bool pirPending() { return g_edge.load() || levelHigh(); }

void pirSimulate() { g_edge.store(true); }

void pirNoteClose(bool forced) {
  if (!forced) {
    g_forcedRun = 0;
    return;
  }
  g_forcedTotal.fetch_add(1);
  if (++g_forcedRun >= kStuckAfterForced && !g_stuck.load()) {
    g_stuck.store(true);
    logLine("PIR stuck HIGH: %d forced closes in a row, level ignored (edges only) until the pin reads LOW",
            g_forcedRun);
  }
}

bool pirStuck() { return g_stuck.load(); }
uint32_t pirForcedCloses() { return g_forcedTotal.load(); }
