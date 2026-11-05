#include "camera.h"

#include <Arduino.h>
#include <mutex>

#include "log.h"

namespace {
// XIAO ESP32S3 Sense camera pins (same as firmware/camtest)
constexpr int PWDN = -1, RESET = -1, XCLK = 10, SIOD = 40, SIOC = 39;
constexpr int Y9 = 48, Y8 = 11, Y7 = 12, Y6 = 14, Y5 = 16, Y4 = 18, Y3 = 17, Y2 = 15;
constexpr int VSYNC = 38, HREF = 47, PCLK = 13;
constexpr int kWarmupFrames = 4;

bool g_ok = false;
uint16_t g_pid = 0;
SemaphoreHandle_t g_lock = nullptr;  // held from cameraCapture() to cameraRelease()
}  // namespace

bool cameraInit() {
  if (!g_lock) g_lock = xSemaphoreCreateMutex();
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2; c.pin_d1 = Y3; c.pin_d2 = Y4; c.pin_d3 = Y5;
  c.pin_d4 = Y6; c.pin_d5 = Y7; c.pin_d6 = Y8; c.pin_d7 = Y9;
  c.pin_xclk = XCLK; c.pin_pclk = PCLK; c.pin_vsync = VSYNC; c.pin_href = HREF;
  c.pin_sccb_sda = SIOD; c.pin_sccb_scl = SIOC;
  c.pin_pwdn = PWDN; c.pin_reset = RESET;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_UXGA;  // 1600x1200
  c.jpeg_quality = 10;
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    logLine("CAM init failed 0x%x", (unsigned)err);
    return false;
  }
  sensor_t* s = esp_camera_sensor_get();
  g_pid = s ? s->id.PID : 0;
  g_ok = true;
  logLine("CAM ok %s pid=0x%04x", cameraSensorName(), g_pid);
  return true;
}

bool cameraReady() { return g_ok; }

camera_fb_t* cameraCapture(bool warmup) {
  if (!g_ok || xSemaphoreTake(g_lock, pdMS_TO_TICKS(10000)) != pdTRUE) return nullptr;
  if (warmup) {
    for (int i = 0; i < kWarmupFrames; i++) {
      camera_fb_t* f = esp_camera_fb_get();
      if (f) esp_camera_fb_return(f);
      delay(150);
    }
  }
  // CAMERA_GRAB_LATEST with two buffers can hand back the frame captured before this call.
  // Discard one frame so the next one is fresh.
  if (camera_fb_t* stale = esp_camera_fb_get()) esp_camera_fb_return(stale);
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) xSemaphoreGive(g_lock);
  return fb;
}

void cameraRelease(camera_fb_t* fb) {
  if (!fb) return;
  esp_camera_fb_return(fb);
  xSemaphoreGive(g_lock);
}

const char* cameraSensorName() {
  if (!g_ok) return "none";
  switch (g_pid) {
    case OV2640_PID: return "OV2640";
    case OV3660_PID: return "OV3660";
    case OV5640_PID: return "OV5640";
    default: return "unknown";
  }
}
