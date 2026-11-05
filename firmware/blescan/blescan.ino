// BLE discovery scan for Seeed XIAO ESP32S3.
// Active scan, prints every advertisement as one line:
// ADV <mac> <addr_type> <rssi> name=<name> mfr=<hex> svc=<uuids>
// Serial commands: 's' = run a 30 s scan;
// 'L <mac> <n>\n' = connect to a reference tag and blink its LED n times (1/s).

#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <BLEClient.h>

// LED control service of the reference tag firmware (docs/tag-protocol.md)
static BLEUUID kTagSvcUuid("43485250-0001-4348-4952-50434f4f5000");
static BLEUUID kTagLedUuid("43485250-0002-4348-4952-50434f4f5000");

static BLEScan *scan;

class Cb : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice d) override {
    String mfr;
    if (d.haveManufacturerData()) {
      String raw = d.getManufacturerData();
      char h[3];
      for (size_t i = 0; i < raw.length(); i++) {
        snprintf(h, sizeof(h), "%02x", (uint8_t)raw[i]);
        mfr += h;
      }
    }
    String svc;
    for (int i = 0; i < d.getServiceUUIDCount(); i++) {
      if (i) svc += ",";
      svc += d.getServiceUUID(i).toString().c_str();
    }
    Serial.printf("ADV %s %d %d name=%s mfr=%s svc=%s\n", d.getAddress().toString().c_str(),
                  d.getAddressType(), d.getRSSI(), d.haveName() ? d.getName().c_str() : "",
                  mfr.c_str(), svc.c_str());
  }
};

static void runScan(uint32_t sec) {
  Serial.printf("SCAN_START %u\n", sec);
  scan->start(sec, false);
  scan->clearResults();
  Serial.println("SCAN_END");
}

static void blink(const String &mac, uint8_t n) {
  BLEClient *c = BLEDevice::createClient();
  uint32_t t0 = millis();
  bool ok = c->connect(BLEAddress(mac.c_str()), BLE_ADDR_RANDOM, 8000);
  if (!ok) {
    Serial.printf("BLINK %s CONNECT_FAIL\n", mac.c_str());
  } else {
    BLERemoteService *svc = c->getService(kTagSvcUuid);
    BLERemoteCharacteristic *ch = svc ? svc->getCharacteristic(kTagLedUuid) : nullptr;
    if (!ch) {
      Serial.printf("BLINK %s NO_LED_CHAR\n", mac.c_str());
    } else {
      bool w = ch->writeValue(&n, 1, true);
      Serial.printf("BLINK %s %s n=%u ms=%u\n", mac.c_str(), w ? "ok" : "WRITE_FAIL", n, millis() - t0);
    }
    c->disconnect();
  }
  delay(300);
  delete c;
}

void setup() {
  Serial.begin(115200);
  uint32_t t = millis();
  while (!Serial && millis() - t < 5000) delay(10);
  BLEDevice::init("");
  scan = BLEDevice::getScan();
  scan->setAdvertisedDeviceCallbacks(new Cb(), true);  // report duplicates
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(99);
  Serial.println("READY");
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line == "s") runScan(30);
    else if (line.startsWith("L ")) {
      int sp = line.indexOf(' ', 2);
      String mac = line.substring(2, sp > 0 ? sp : line.length());
      uint8_t n = sp > 0 ? (uint8_t)line.substring(sp + 1).toInt() : 10;
      blink(mac, n);
    }
  }
  delay(10);
}
