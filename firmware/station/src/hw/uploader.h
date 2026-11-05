// Upload queue and heartbeat in their own FreeRTOS task (never in the visit task).
#pragma once
#include <stdint.h>

#include <string>

struct UploaderHooks {
  bool (*visitOpen)();  // true while a visit is open: no request may start
  const char* firmware;
};

// Starts the task. Needs the SD card, config and netStart() to be initialised.
void uploaderStart(const UploaderHooks& hooks);
// The visit task calls this when a visit opens, so the heartbeat can report last_visit_at.
// epochSec < 0 = clock not synced (reported as null).
void uploaderNoteVisit(int64_t epochSec);
// "idle", "uploading", "retry", "auth_stop", "no_wifi", "no_time", "no_config", or "redirect"
// while the last response was a 3xx (UPLOAD_BASE_URL is not the final host).
std::string uploaderState();
// Running minimum of heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL) since boot. Any task
// may call heapNoteLargest() to take a sample; heapLargestMin() takes one too, so it never
// returns the "no sample yet" value.
void heapNoteLargest();
uint32_t heapLargestMin();
// Files waiting in /q that the uploader would send (snap_* bench files excluded). Counted in one
// directory pass, no names stored.
size_t uploaderQueueLen();
// The same single-pass count over any directory (bench: timing a long listing outside /q).
size_t uploaderCountQueueable(const char* dir);
