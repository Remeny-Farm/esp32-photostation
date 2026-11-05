// BLE tag scanner: continuous active scan, only tag advertisements (kTagMfrPrefix) enter the TagTable.
#pragma once
#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include <string>

#include "../core/ident.h"

// Starts a continuous active scan (NimBLE host, no stored scan results) and a maintenance task
// that restarts the scan if it stops and prunes the table every 5 s. The maintenance task never
// logs. `lock` guards `table`; the scan callback and the maintenance task take it, the caller takes
// it for summarize(). Never hold it across SD or camera work.
void bleStart(TagTable& table, SemaphoreHandle_t lock);
bool bleRunning();  // started and the scan is active right now

// The visit task tells the scanner when a visit is open, so prune keeps visitStart - 5000.
void bleSetVisit(bool open, uint32_t startMs);

// Last battery voltage (mV) seen for a tag, 0 when unknown. Takes the lock briefly.
int bleVbatMv(const std::string& mac);

struct BleStats {
  uint32_t adv;       // advertisements seen (all devices)
  uint32_t tag;       // tag advertisements stored in the table
  uint32_t lockMiss;  // tag advertisements dropped because the lock was busy
  uint32_t restarts;  // scan restarts
};
BleStats bleStats();
