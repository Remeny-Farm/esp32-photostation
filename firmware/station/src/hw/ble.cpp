#include "ble.h"

#include <BLEDevice.h>
#include <host/ble_gap.h>
#include <host/ble_hs.h>

#include <cstring>

#if !defined(CONFIG_NIMBLE_ENABLED)
#error "ble.cpp drives the NimBLE host directly (ESP32-S3 core 3.3.x builds BLE with NimBLE)"
#endif

// Why not BLEScan: in the NimBLE build, BLEScan stores every advertiser in its result map for the
// whole scan (m_maxResults is private and defaults to 0xFF), re-parses each new packet into the
// stored device (payload realloc-appended, service UUID vectors pushed again) and hands the
// callback a deep copy. Heap then falls with every packet until the scan ends. Here each report is
// parsed in place on the NimBLE host task and nothing is allocated per packet except the transient
// strings of TagTable::add.

namespace {
constexpr uint32_t kPruneEveryMs = 5000;
constexpr uint32_t kKeepMs = 60000;
constexpr uint32_t kPreRollMs = 5000;
constexpr size_t kMaxName = 20;
constexpr size_t kMaxMeta = TagTable::kMaxTags;
constexpr uint16_t kItvlUnits = 160;    // 100 ms in 0.625 ms units
constexpr uint16_t kWindowUnits = 158;  // 99 ms in 0.625 ms units (truncated, as BLEScan::setWindow)

// Per-tag name and battery, kept apart from TagTable (its samples carry neither).
// Fixed array, least recently seen entry replaced when full. Guarded by g_lock.
struct Meta {
  char mac[18];  // "AA:BB:CC:DD:EE:FF"; empty = free slot
  char name[kMaxName + 1];
  int vbatMv;
  uint32_t lastMs;
};
Meta g_meta[kMaxMeta];

TagTable* g_table = nullptr;
SemaphoreHandle_t g_lock = nullptr;

volatile bool g_running = false;
volatile bool g_visitOpen = false;
volatile uint32_t g_visitStart = 0;
// adv/tag/lockMiss are written only by the NimBLE host task, restarts only by the ble task.
volatile uint32_t g_adv = 0, g_tag = 0, g_lockMiss = 0, g_restarts = 0;

// Tag advertisement manufacturer data (company id included): company id 0xFFFF (test/unassigned)
// followed by ASCII "CHRPT", then one firmware byte (offset 7) and one battery byte (offset 8;
// mV = 2000 + 10 * byte; 0xFF = unknown); packet length >= 9. Wire format: docs/tag-protocol.md.
constexpr uint8_t kTagMfrPrefix[] = {0xFF, 0xFF, 'C', 'H', 'R', 'P', 'T'};

bool isTagAdvert(const uint8_t* d, size_t n) {
  return n >= 9 && memcmp(d, kTagMfrPrefix, sizeof kTagMfrPrefix) == 0;
}

// NimBLE stores the address little-endian; print it most significant byte first, uppercase.
void formatMac(const ble_addr_t& a, char out[18]) {
  static const char kHex[] = "0123456789ABCDEF";
  for (int i = 0; i < 6; i++) {
    uint8_t b = a.val[5 - i];
    out[i * 3] = kHex[b >> 4];
    out[i * 3 + 1] = kHex[b & 0x0F];
    out[i * 3 + 2] = i < 5 ? ':' : '\0';
  }
}

// Printable ASCII only (else '?'), at most kMaxName characters.
void sanitizeName(const uint8_t* s, size_t n, char out[kMaxName + 1]) {
  if (n > kMaxName) n = kMaxName;
  for (size_t i = 0; i < n; i++) out[i] = (s[i] >= 0x20 && s[i] <= 0x7E) ? (char)s[i] : '?';
  out[n] = '\0';
}

Meta* findMeta(const char* mac) {
  for (auto& m : g_meta)
    if (m.mac[0] && strcmp(m.mac, mac) == 0) return &m;
  return nullptr;
}

Meta* findOrAddMeta(const char* mac, uint32_t now) {
  if (Meta* m = findMeta(mac)) return m;
  Meta* slot = &g_meta[0];
  for (auto& m : g_meta) {
    if (!m.mac[0]) {
      slot = &m;
      break;
    }
    if ((int32_t)(m.lastMs - slot->lastMs) < 0) slot = &m;  // least recently seen
  }
  memcpy(slot->mac, mac, sizeof slot->mac);
  slot->name[0] = '\0';
  slot->vbatMv = 0;
  slot->lastMs = now;
  return slot;
}

// Hot path, NimBLE host task: no logging, no SD, no blocking beyond a 5 ms lock wait.
int onGap(struct ble_gap_event* ev, void*) {
  if (ev->type != BLE_GAP_EVENT_DISC) return 0;  // DISC_COMPLETE: the ble task restarts the scan
  const ble_gap_disc_desc& d = ev->disc;
  g_adv = g_adv + 1;
  if (d.rssi == 127) return 0;  // RSSI unavailable

  const uint8_t* mfr = nullptr;
  size_t mfrLen = 0;
  const uint8_t* nm = nullptr;
  size_t nmLen = 0;
  for (size_t i = 0; i + 1 < d.length_data;) {  // AD structures: [len][type][data len-1]
    size_t len = d.data[i];
    if (len == 0 || i + 1 + len > d.length_data) break;
    uint8_t type = d.data[i + 1];
    if (type == 0xFF) {
      mfr = &d.data[i + 2];
      mfrLen = len - 1;
    } else if (type == 0x09 || (type == 0x08 && !nm)) {  // complete name wins over shortened
      nm = &d.data[i + 2];
      nmLen = len - 1;
    }
    i += 1 + len;
  }
  bool tag = mfr && isTagAdvert(mfr, mfrLen);
  char name[kMaxName + 1] = "";
  if (nm) sanitizeName(nm, nmLen, name);
  if (!tag && !name[0]) return 0;

  char mac[18];
  formatMac(d.addr, mac);
  uint32_t now = millis();

  if (!tag) {
    // A scan response carries the name but no manufacturer data: keep it for a known tag.
    if (xSemaphoreTake(g_lock, pdMS_TO_TICKS(5)) != pdTRUE) return 0;
    if (Meta* m = findMeta(mac)) memcpy(m->name, name, sizeof m->name);
    xSemaphoreGive(g_lock);
    return 0;
  }

  int vbat = mfr[8] != 0xFF ? 2000 + 10 * (int)mfr[8] : 0;  // 0 = unknown
  if (xSemaphoreTake(g_lock, pdMS_TO_TICKS(5)) != pdTRUE) {
    g_lockMiss = g_lockMiss + 1;
    return 0;
  }
  Meta* m = findOrAddMeta(mac, now);
  m->lastMs = now;
  if (name[0]) memcpy(m->name, name, sizeof m->name);
  if (vbat > 0) m->vbatMv = vbat;
  g_table->add(mac, m->name, now, d.rssi, vbat);
  xSemaphoreGive(g_lock);
  g_tag = g_tag + 1;
  return 0;
}

// Continuous active scan, every report delivered (no duplicate filter). Thread-safe in NimBLE.
bool startScan() {
  uint8_t own = 0;
  if (ble_hs_id_infer_auto(0, &own) != 0) return false;
  ble_gap_disc_params p;
  memset(&p, 0, sizeof p);
  p.itvl = kItvlUnits;
  p.window = kWindowUnits;
  p.filter_policy = BLE_HCI_SCAN_FILT_NO_WL;
  p.passive = 0;
  p.filter_duplicates = 0;
  return ble_gap_disc(own, BLE_HS_FOREVER, &p, onGap, nullptr) == 0;
}

// Restarts the scan whenever it is not running (host reset, controller error), prunes every 5 s.
// No logging here: logLine (vsnprintf + SD/FATFS) does not belong on this small stack.
void bleTask(void*) {
  uint32_t lastPrune = millis();
  for (;;) {
    if (ble_hs_synced() && !ble_gap_disc_active() && startScan()) g_restarts = g_restarts + 1;
    vTaskDelay(pdMS_TO_TICKS(250));
    uint32_t now = millis();
    if (now - lastPrune >= kPruneEveryMs) {
      lastPrune = now;
      uint32_t keep = now - kKeepMs;
      if (g_visitOpen) {
        uint32_t vs = g_visitStart - kPreRollMs;
        if ((int32_t)(vs - keep) < 0) keep = vs;  // the older of the two
      }
      if (xSemaphoreTake(g_lock, pdMS_TO_TICKS(200)) == pdTRUE) {
        g_table->prune(keep);
        xSemaphoreGive(g_lock);
      }
    }
  }
}
}  // namespace

void bleStart(TagTable& table, SemaphoreHandle_t lock) {
  if (g_running) return;
  g_table = &table;
  g_lock = lock;
  BLEDevice::init("");  // starts the NimBLE host and waits for sync; BLEScan is never created
  g_running = true;
  xTaskCreatePinnedToCore(bleTask, "ble", 4096, nullptr, 1, nullptr, 0);
}

bool bleRunning() { return g_running && ble_gap_disc_active(); }

void bleSetVisit(bool open, uint32_t startMs) {
  if (open) g_visitStart = startMs;  // start first, then the flag
  g_visitOpen = open;
}

int bleVbatMv(const std::string& mac) {
  int v = 0;
  if (g_lock && xSemaphoreTake(g_lock, pdMS_TO_TICKS(200)) == pdTRUE) {
    if (const Meta* m = findMeta(mac.c_str())) v = m->vbatMv;
    xSemaphoreGive(g_lock);
  }
  return v;
}

BleStats bleStats() { return {g_adv, g_tag, g_lockMiss, g_restarts}; }
