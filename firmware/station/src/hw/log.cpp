#include "log.h"

#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <stdarg.h>
#include <stdio.h>

#include "storage.h"

namespace {
constexpr size_t kRotateBytes = 1024 * 1024;
const char* kLog = "/log/station.log";
const char* kLog1 = "/log/station.1.log";
}  // namespace

void logLine(const char* fmt, ...) {
  char msg[256];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(msg, sizeof msg, fmt, ap);
  va_end(ap);

  char line[288];
  int n = snprintf(line, sizeof line, "[%lu] %s\n", (unsigned long)millis(), msg);
  if (n < 0) return;
  if (n >= (int)sizeof line) n = sizeof line - 1;
  // Unattended on a USB adapter there is no host: never wait on the serial port then.
  if (Serial) Serial.write((const uint8_t*)line, n);

  if (!storageReady()) return;
  storageLock();
  File f = SD.open(kLog, FILE_APPEND);
  if (f) {
    if (f.size() >= kRotateBytes) {
      f.close();
      SD.remove(kLog1);
      SD.rename(kLog, kLog1);
      f = SD.open(kLog, FILE_WRITE);
    }
    if (f) {
      f.write((const uint8_t*)line, n);
      f.close();
    }
  }
  storageUnlock();
}
