// Light MOSFET gate on GPIO2 (D1), LEDC PWM. No flashing: levels change by a 300 ms ramp.
#pragma once
#include <stdint.h>

constexpr uint8_t kLightVisitPwm = 180;  // default level while a visit is open

void lightInit();
void lightSet(uint8_t pwm);  // blocks ~300 ms while ramping to pwm
uint8_t lightLevel();
