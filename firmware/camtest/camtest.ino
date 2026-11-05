// Camera + SD smoke test for Seeed XIAO ESP32S3 Sense.
// Prints sensor info, captures a JPEG, saves it to SD (if present),
// and dumps it as base64 over USB serial between markers.
// Serial commands: 'c' = capture again, 'i' = print board/sensor/SD info, 'l' = list SD root.

#include "esp_camera.h"
#include "FS.h"
#include "SD.h"
#include "SPI.h"
#include "mbedtls/base64.h"

// XIAO ESP32S3 Sense camera pins (Seeed CAMERA_MODEL_XIAO_ESP32S3)
#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  10
#define SIOD_GPIO_NUM  40
#define SIOC_GPIO_NUM  39
#define Y9_GPIO_NUM    48
#define Y8_GPIO_NUM    11
#define Y7_GPIO_NUM    12
#define Y6_GPIO_NUM    14
#define Y5_GPIO_NUM    16
#define Y4_GPIO_NUM    18
#define Y3_GPIO_NUM    17
#define Y2_GPIO_NUM    15
#define VSYNC_GPIO_NUM 38
#define HREF_GPIO_NUM  47
#define PCLK_GPIO_NUM  13
#define SD_CS_PIN      21

static bool sdOk = false;
static int shot = 0;

static const char *sensorName(uint16_t pid) {
  switch (pid) {
    case OV2640_PID: return "OV2640";
    case OV3660_PID: return "OV3660";
    case OV5640_PID: return "OV5640";
    default: return "unknown";
  }
}

static bool initCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM; c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM; c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_UXGA;  // 1600x1200, supported by all three sensors
  c.jpeg_quality = 10;
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("CAM_INIT_FAIL 0x%x\n", err);
    return false;
  }
  sensor_t *s = esp_camera_sensor_get();
  Serial.printf("SENSOR pid=0x%04x name=%s\n", s->id.PID, sensorName(s->id.PID));
  return true;
}

static void captureAndDump() {
  // Drop a few frames so auto exposure / white balance settle.
  for (int i = 0; i < 4; i++) {
    camera_fb_t *f = esp_camera_fb_get();
    if (f) esp_camera_fb_return(f);
    delay(150);
  }
  uint32_t t0 = millis();
  camera_fb_t *fb = esp_camera_fb_get();
  uint32_t dt = millis() - t0;
  if (!fb) {
    Serial.println("CAPTURE_FAIL");
    return;
  }
  shot++;
  Serial.printf("CAPTURE ok %ux%u bytes=%u grab_ms=%u\n", fb->width, fb->height, fb->len, dt);

  if (sdOk) {
    char path[32];
    snprintf(path, sizeof(path), "/camtest_%03d.jpg", shot);
    File f = SD.open(path, FILE_WRITE);
    if (f) {
      size_t w = f.write(fb->buf, fb->len);
      f.close();
      Serial.printf("SD_WRITE %s %s (%u/%u)\n", path, w == fb->len ? "ok" : "SHORT", w, fb->len);
      // Read back and compare byte by byte.
      File r = SD.open(path, FILE_READ);
      size_t same = 0, total = r ? r.size() : 0;
      uint8_t chunk[512];
      while (r && r.available()) {
        int n = r.read(chunk, sizeof(chunk));
        if (n <= 0 || memcmp(chunk, fb->buf + same, n) != 0) break;
        same += n;
      }
      if (r) r.close();
      Serial.printf("SD_VERIFY %s %s (size=%u match=%u)\n", path,
                    (total == fb->len && same == fb->len) ? "ok" : "MISMATCH", total, same);
    } else {
      Serial.printf("SD_WRITE %s FAIL\n", path);
    }
  }

  size_t outLen = 0;
  mbedtls_base64_encode(nullptr, 0, &outLen, fb->buf, fb->len);
  unsigned char *b64 = (unsigned char *)ps_malloc(outLen + 1);
  if (b64 && mbedtls_base64_encode(b64, outLen + 1, &outLen, fb->buf, fb->len) == 0) {
    Serial.println("-----JPEG BEGIN-----");
    for (size_t i = 0; i < outLen; i += 76) {
      Serial.write(b64 + i, min((size_t)76, outLen - i));
      Serial.write('\n');
    }
    Serial.println("-----JPEG END-----");
  } else {
    Serial.println("B64_FAIL");
  }
  free(b64);
  esp_camera_fb_return(fb);
}

void setup() {
  Serial.begin(115200);
  uint32_t t = millis();
  while (!Serial && millis() - t < 5000) delay(10);
  delay(500);

  Serial.printf("BOOT chip=%s rev=%d psram=%u free_psram=%u\n", ESP.getChipModel(),
                ESP.getChipRevision(), ESP.getPsramSize(), ESP.getFreePsram());

  sdOk = SD.begin(SD_CS_PIN);
  if (sdOk) {
    Serial.printf("SD ok type=%u size_mb=%llu\n", SD.cardType(), SD.cardSize() / (1024 * 1024));
  } else {
    Serial.println("SD none_or_fail");
  }

  if (initCamera()) captureAndDump();
}

void loop() {
  if (Serial.available()) {
    int ch = Serial.read();
    if (ch == 'c') captureAndDump();
    if (ch == 'l' && sdOk) {
      File root = SD.open("/");
      for (File e = root.openNextFile(); e; e = root.openNextFile())
        Serial.printf("LS %s %u\n", e.name(), e.size());
      Serial.printf("LS_END used_kb=%llu total_kb=%llu\n", SD.usedBytes() / 1024, SD.totalBytes() / 1024);
    }
    if (ch == 'i') {
      sensor_t *s = esp_camera_sensor_get();
      Serial.printf("INFO chip=%s rev=%d psram=%u free_psram=%u sd=%d sensor_pid=0x%04x name=%s\n",
                    ESP.getChipModel(), ESP.getChipRevision(), ESP.getPsramSize(), ESP.getFreePsram(),
                    sdOk, s ? s->id.PID : 0, s ? sensorName(s->id.PID) : "none");
    }
  }
  delay(10);
}
