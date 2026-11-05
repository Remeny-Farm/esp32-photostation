// PIR input on GPIO1 (D0). The ISR only sets a flag.
#pragma once
#include <stdint.h>

void pirInit();
// True when a rising edge (or simulated edge) was latched since the last call, or the pin is HIGH
// now. The AM312 holds its output HIGH while motion continues, so no new edges arrive then.
// In stuck mode (see pirNoteClose) the level is ignored, edges only, until the pin reads LOW once.
bool pirTakeEdge();
bool pirPending();   // same condition as pirTakeEdge() but does not consume the latched edge
void pirSimulate();  // serial `pir` command
// The visit task reports each close. Three forced (10-minute) closes in a row mean the pin is stuck
// HIGH: stuck mode starts (logged once). A silence close resets the run.
void pirNoteClose(bool forced);
bool pirStuck();                 // stuck mode is on
uint32_t pirForcedCloses();      // forced closes since boot
