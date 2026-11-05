// Wi-Fi station, SNTP, mDNS, ArduinoOTA and the HTTP client used by the uploader.
#pragma once
#include <stddef.h>
#include <stdint.h>

#include <string>
#include <utility>
#include <vector>

#include "config.h"

// Wi-Fi STA with auto-reconnect, SNTP (pool.ntp.org, TZ UTC0),
// mDNS name = station id, ArduinoOTA only when an OTA password is set.
void netStart(const StationConfig& cfg);
// Applies a changed SSID / password without a reboot. Call from the console task.
void netReconfigure(const StationConfig& cfg);
// ArduinoOTA.handle(); call from loop().
void netLoop();

bool netUp();           // Wi-Fi associated and has an IP
bool netTimeSynced();   // SNTP has set the clock
int64_t netEpoch();     // UTC seconds, or -1 while the clock is not synced
int netRssi();          // dBm, 0 when down
std::string netIp();    // "" when down

// POST body to <baseUrl><path>. Returns the HTTP status, or <= 0 on any network or TLS error
// (-1 also for a bad base URL). Timeouts: connect 5 s, TLS handshake 15 s. The 5 s connect
// timeout is also the TLS write stall limit and TLS read poll (ssl_client socket_timeout, fixed at
// connect); the 15 s HTTPClient timeout covers the response wait and plain http:// socket I/O. The body goes out
// in chunks that feed the caller's task watchdog. https:// verifies the server with the core's CA
// bundle (never setInsecure()); http:// is used only when the base URL says so. Not re-entrant:
// only the uploader task calls it.
int httpPost(const std::string& path, const char* contentType, const uint8_t* body, size_t len,
             const std::vector<std::pair<std::string, std::string>>& headers);
