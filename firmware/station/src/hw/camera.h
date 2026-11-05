// OV3660/OV2640/OV5640 camera: UXGA JPEG, 2 frame buffers in PSRAM.
#pragma once
#include <esp_camera.h>

bool cameraInit();   // safe to call again after a failure (setup() retries it)
bool cameraReady();  // true after a successful cameraInit()
// Returns a JPEG frame or nullptr. warmup = discard 4 frames first (auto exposure/white balance).
// The caller must pass the frame to cameraRelease(); the camera stays locked until then.
camera_fb_t* cameraCapture(bool warmup);
void cameraRelease(camera_fb_t* fb);
const char* cameraSensorName();  // "OV3660", ... or "none"
