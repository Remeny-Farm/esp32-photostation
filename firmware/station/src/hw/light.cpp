#include "light.h"

#include <Arduino.h>
#include <mutex>

namespace {
constexpr int kPin = 2;
constexpr uint32_t kHz = 5000;
constexpr uint8_t kBits = 8;
// The camera clock owns LEDC channel 0 / timer 0, so use a channel on another timer.
constexpr uint8_t kChannel = 4;
constexpr int kRampSteps = 15;
constexpr uint32_t kRampMs = 300;

std::mutex g_mu;
volatile uint8_t g_level = 0;
}  // namespace

void lightInit() {
  ledcAttachChannel(kPin, kHz, kBits, kChannel);
  ledcWrite(kPin, 0);
  g_level = 0;
}

void lightSet(uint8_t pwm) {
  std::lock_guard<std::mutex> lock(g_mu);
  int from = g_level;
  if (from == pwm) return;
  for (int i = 1; i <= kRampSteps; i++) {
    ledcWrite(kPin, from + (int)(pwm - from) * i / kRampSteps);
    delay(kRampMs / kRampSteps);
  }
  ledcWrite(kPin, pwm);
  g_level = pwm;
}

uint8_t lightLevel() { return g_level; }
