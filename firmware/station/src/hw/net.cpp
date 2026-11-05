#include "net.h"

#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <NetworkClient.h>
#include <NetworkClientSecure.h>
#include <WiFi.h>
#include <esp_task_wdt.h>
#include <string.h>
#include <time.h>

#include <atomic>

#include "log.h"
#include "uploader.h"  // heapNoteLargest()

namespace {
constexpr const char* kTz = "UTC0";
constexpr time_t kMinSyncedEpoch = 1700000000;  // 2023-11-14; anything below means "not synced"
constexpr uint32_t kHttpTimeoutMs = 15000;        // HTTPClient response wait and plain-socket read/write
// TCP connect. NetworkClientSecure::connect(.., timeout) passes this same value to ssl_client as its
// socket_timeout, and HTTPClient's later setTimeout() does not reach it. So over https this 5 s is
// also the TLS write stall limit (send_ssl_data) and the TLS read poll, not the 15 s above.
constexpr uint32_t kConnectTimeoutMs = 5000;
constexpr unsigned long kHandshakeTimeoutS = 15;  // TLS handshake (the core default is 120 s)

bool g_otaOn = false;

// Wi-Fi events run in the arduino_events task (4 KB stack). No logLine (stack and SD lock) there:
// the callback only counts, netLoop() logs from the loop task.
std::atomic<uint32_t> g_evUp{0}, g_evDown{0};

void onWifiEvent(arduino_event_id_t ev) {
  if (ev == ARDUINO_EVENT_WIFI_STA_GOT_IP) g_evUp.fetch_add(1);
  else if (ev == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) g_evDown.fetch_add(1);
}

// The request body as a Stream, so HTTPClient sends it in 1460-byte chunks and the task watchdog
// is fed per chunk: a slow but moving upload never trips the 30 s watchdog, a stalled one still
// ends on the transport's stall limit (5 s over https, see kConnectTimeoutMs; 15 s over http). Feeds only when the calling task is subscribed.
class BodyStream : public Stream {
 public:
  BodyStream(const uint8_t* p, size_t n) : p_(p), n_(n), feed_(esp_task_wdt_status(nullptr) == ESP_OK) {}
  int available() override { return (int)(n_ - pos_); }
  int read() override { return pos_ < n_ ? p_[pos_++] : -1; }
  int peek() override { return pos_ < n_ ? p_[pos_] : -1; }
  using Stream::readBytes;
  size_t readBytes(char* buf, size_t len) override {
    if (feed_) esp_task_wdt_reset();
    size_t k = len < n_ - pos_ ? len : n_ - pos_;
    memcpy(buf, p_ + pos_, k);
    pos_ += k;
    return k;
  }
  size_t write(uint8_t) override { return 0; }

 private:
  const uint8_t* p_;
  size_t n_;
  size_t pos_ = 0;
  bool feed_;
};

void wifiBegin(const StationConfig& cfg) {
  if (cfg.ssid.empty()) return;
  if (cfg.pass.empty()) WiFi.begin(cfg.ssid.c_str());  // open network
  else WiFi.begin(cfg.ssid.c_str(), cfg.pass.c_str());
}
}  // namespace

void netStart(const StationConfig& cfg) {
  WiFi.persistent(false);  // credentials live in our own NVS namespace, not the Wi-Fi one
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setHostname(cfg.stationId.c_str());
  WiFi.onEvent(onWifiEvent);
  configTzTime(kTz, "pool.ntp.org");
  wifiBegin(cfg);

  if (!cfg.otaPass.empty()) {
    ArduinoOTA.setHostname(cfg.stationId.c_str());  // also the mDNS name (ArduinoOTA starts mDNS)
    ArduinoOTA.setPassword(cfg.otaPass.c_str());
    ArduinoOTA.onStart([]() { logLine("OTA start"); });
    ArduinoOTA.onEnd([]() { logLine("OTA end"); });
    ArduinoOTA.onError([](ota_error_t e) { logLine("OTA error %u", (unsigned)e); });
    ArduinoOTA.begin();
    g_otaOn = true;
  } else {
    MDNS.begin(cfg.stationId.c_str());  // no OTA password: OTA stays off, never open on the LAN
  }
  logLine("NET start ssid_set=%d ota=%s", (int)!cfg.ssid.empty(), g_otaOn ? "on" : "off(no password)");
}

void netReconfigure(const StationConfig& cfg) {
  WiFi.disconnect(false);
  wifiBegin(cfg);
}

void netLoop() {
  if (g_otaOn) ArduinoOTA.handle();
  static uint32_t seenUp = 0, seenDown = 0;
  uint32_t up = g_evUp.load(), down = g_evDown.load();
  if (up != seenUp) {
    logLine("WIFI up ip=%s rssi=%d (events %u)", netIp().c_str(), netRssi(), (unsigned)(up - seenUp));
    seenUp = up;
  }
  if (down != seenDown) {
    logLine("WIFI down (events %u)", (unsigned)(down - seenDown));
    seenDown = down;
  }
}

bool netUp() { return WiFi.status() == WL_CONNECTED; }
bool netTimeSynced() { return time(nullptr) >= kMinSyncedEpoch; }
int64_t netEpoch() {
  time_t t = time(nullptr);
  return t >= kMinSyncedEpoch ? (int64_t)t : -1;
}
int netRssi() { return netUp() ? (int)WiFi.RSSI() : 0; }
std::string netIp() { return netUp() ? WiFi.localIP().toString().c_str() : ""; }

int httpPost(const std::string& path, const char* contentType, const uint8_t* body, size_t len,
             const std::vector<std::pair<std::string, std::string>>& headers) {
  StationConfig cfg = configGet();
  std::string base = cfg.baseUrl;
  while (!base.empty() && base.back() == '/') base.pop_back();
  bool https = base.rfind("https://", 0) == 0;
  bool http = base.rfind("http://", 0) == 0;
  if (!https && !http) return -1;
  String url = (base + path).c_str();

  // ORDER MATTERS: the transports are declared before HTTPClient. Locals are destroyed in reverse
  // order, and ~HTTPClient() calls _client->stop(), so the transport must outlive it on every
  // return path (failed begin(), network error, TLS failure, timeout).
  NetworkClientSecure tls;
  NetworkClient plain;
  HTTPClient client;
  client.setReuse(false);
  // HTTPClient applies these to the transport on connect (the transports' own setTimeout() takes
  // ms and would be overwritten anyway).
  client.setTimeout(kHttpTimeoutMs);
  client.setConnectTimeout(kConnectTimeoutMs);
  bool begun;
  if (https) {
    tls.useBuiltinCACertBundle();  // verifies the chain and the host name; no setInsecure()
    tls.setHandshakeTimeout(kHandshakeTimeoutS);  // seconds
    begun = client.begin(tls, url);
  } else {
    begun = client.begin(plain, url);
  }
  if (!begun) return -1;
  client.addHeader("Content-Type", contentType);
  for (const auto& h : headers) client.addHeader(h.first.c_str(), h.second.c_str());
  int status;
  if (len > 0) {
    BodyStream bs(body, len);
    status = client.sendRequest("POST", &bs, len);
  } else {
    status = client.POST(const_cast<uint8_t*>(body), len);  // the Stream path never ends on size 0
  }
  heapNoteLargest();  // TLS context and its buffers are still allocated here: catches the handshake dip
  client.end();
  return status;
}
