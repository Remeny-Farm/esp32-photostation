// Serial + SD log. Rotates /log/station.log to /log/station.1.log at 1 MB.
#pragma once

void logLine(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
