# esp32-photostation architecture

esp32-photostation is an open-source ESP32-S3 camera station that photographs animals and identifies
them by BLE tag. This document explains what the station does, why it is built this way, and the
facts the firmware relies on. The upload contract is in [protocol.md](protocol.md), the tag
advertisement format in [tag-protocol.md](tag-protocol.md), the board and wiring in
[hardware.md](hardware.md), and the build, flash and serial details in
[../firmware/station/README.md](../firmware/station/README.md).

The motivating example is a backyard flock of hens, each wearing a small BLE tag. Nothing in the
firmware is specific to hens: any animal that carries a tag and walks into a box works.

## 1. Intent

A small box stands in the animals' area with a bait bowl at the far end. One animal fits inside at
a time. When an animal walks in, a PIR sensor wakes the station: the light ramps up, the camera
takes three to five photos, and the station decides from the BLE tags it heard which animal was in
front of the camera. The photos and a visit record go to an SD card first, and from there to your
upload server over HTTPS. The server side (gallery, review queue, per-animal profile) is yours to
build; this repository defines the station and the contract it speaks.

## 2. Goals, non-goals and anti-goals

Goals:

- Three to five photos per visit, so the server can pick the best one.
- A visit is attributed to a tag only when the evidence is clear. Otherwise it is `unknown`.
- No photo is lost because of a Wi-Fi or server problem: SD first, upload later.
- Remote supervision: a heartbeat every five minutes shows whether the station is healthy.

Non-goals (v1):

- No battery, no deep sleep, no solar: the station runs on mains USB power.
- No video; still images only.
- No image recognition on the device; selection and review run on the server.
- One station per deployment. Multi-station use only means that every station has its own id and
  its own device key.

Anti-goals (a failure even when it "works"):

- A photo published under the wrong animal's name. `unknown` beats a guess.
- Dozens of near-identical photos of one animal.
- A station that scares the animals away (flashing light, noise).
- A secret (Wi-Fi password, device key) in the source tree.

## 3. Constraints and facts

- Board: Seeed XIAO ESP32S3 Sense with an OV3660 camera (OV2640 and OV5640 variants exist), 8 MB
  OPI PSRAM, microSD slot. One u.FL connector: Wi-Fi and BLE share the same antenna. Without the
  antenna BLE is practically deaf.
- Free GPIOs next to the Sense expansion board: GPIO1-6, 43, 44. The SD card uses GPIO7/8/9/21,
  and GPIO21 is also the user LED. GPIO3 is a strapping pin; avoid it.
- Power: 5 V over USB-C, mains powered. Strong Wi-Fi at the site is assumed.
- The tag advertises about once per second. Its name and manufacturer data are in the scan
  response, so the station must scan actively.
- One BLE RSSI sample is not reliable (20-25 dB spread between packets from the same tag). The
  station decides on the median of several packets.
- The case must survive summer heat (42 C in the shade) and dust; see
  [../hardware/case/README.md](../hardware/case/README.md).
- The SD card is FAT32. The ESP-IDF FatFs does not handle exFAT.

## 4. System picture

```
 PIR ---+                               +-> SD: /q (queue) --> uploader --HTTPS--> upload server /api/photostation/*
 BLE ---+-> visit machine -> camera     |                                              |
 light <+   (visit)        + light      +-> SD: /sent (archive)                        +-> photo attached to the animal
                                                                                       +-> best photo selected
                       heartbeat every 5 minutes ---------------HTTPS----------------> +-> unknown visit -> review
```

The "upload server" is any HTTPS service that implements [protocol.md](protocol.md). Its base URL
is a configuration value on the station (`https://upload.example.com` in the examples). A local
mock, `tools/mock_server.py`, implements the same contract for bench tests.

## 5. Firmware structure

The firmware lives in `firmware/station/` and builds with `arduino-cli` on the `esp32:esp32`
core 3.3.12 (`arduino-cli compile --profile xiao_esp32s3 firmware/station`). It uses no external
libraries.

- `src/core/`: pure C++17 logic with no Arduino headers. Identification (`ident`), the visit
  state machine (`visit`), visit ids, SD paths and the visit JSON (`record`), and the upload
  policy, queue order and console parsing (`policy`). These modules have host tests under
  `firmware/station/test/` that run on any machine with a C++17 compiler.
- `src/hw/`: hardware glue. Camera, light, PIR, SD storage, serial console, log, BLE scan,
  config (NVS), network (Wi-Fi, SNTP, HTTP, OTA) and the uploader task.
- `station.ino`: wiring. It starts the tasks, registers the serial commands and owns the visit
  loop.

### 5.1 FreeRTOS tasks

| Task | Core | Responsibility |
|---|---|---|
| `visit` | 1 | Ticks the visit state machine every 50 ms. Opens a visit on a PIR edge, turns the light on, captures photos into the SD queue, closes the visit, runs identification and writes the visit JSON. |
| `ble` | 0 | Keeps a continuous active scan running on the NimBLE host and prunes the tag table every 5 s. The scan callback itself runs on the NimBLE host task and only appends samples to the tag table. |
| `upload` | 1 | Drains `/q` outside visits, sends the heartbeat, applies the retry policy and prunes `/sent`. |
| `loop` (Arduino) | 1 | Serial console, Wi-Fi event logging, OTA handler, one BLE/heap statistics line per minute. |

Wi-Fi and BLE share one radio. The rule is that the visit has priority: on a PIR edge the uploader
finishes the request in flight (about one second on good Wi-Fi) and starts no new request until
the visit closes. Uploads never run while a visit is open. The heartbeat waits for the same gate,
except that a heartbeat older than 15 minutes goes out anyway (it is a small request; photos stay
gated).

### 5.2 Visit state machine

The machine (`src/core/visit.cpp`) is driven by a 50 ms tick and a PIR edge flag.

- `IDLE` -> PIR edge -> `VISIT`: a new `visit_id` is made and the light ramps up over 300 ms.
- Settle 1500 ms (the animal reaches the bait), then photos 1-3 at 1500 ms spacing. Photo 1
  takes four warm-up frames first so exposure and white balance settle.
- Photos 4 and 5 come at 20 s spacing, and only if a PIR edge arrived after the previous photo.
  At most five photos per visit.
- Close on 30 s of PIR silence (once the first three photos are taken), or a forced close after
  10 minutes. After a close the next PIR edge opens a new visit.
- At close the light ramps down, identification runs over the visit window, and the visit JSON is
  written next to the photos in `/q`.

All interval comparisons use unsigned subtraction, so they survive the `millis()` wrap after
49.7 days. These timings are starting values; tune them in the field.

If three forced closes happen in a row, the station marks the PIR as stuck: the level is ignored,
only edges count, until the pin reads LOW again. The heartbeat reports `pir_stuck` and
`forced_closes`.

### 5.3 Identification

The BLE task feeds every accepted tag advertisement into a tag table: per tag MAC, a ring of
(timestamp, RSSI) samples for the last 60 s (or back to 5 s before the visit opened, whichever is
older). The table holds at most 32 tags and 1024 samples per tag.

At visit close the station summarizes the window from 5 s before the visit opened to the close
time: per tag the median RSSI, the packet count, and the min and max. The decision rule
(`identify()` in `src/core/ident.cpp`):

1. The strongest tag (highest median) wins only if
   - at least 3 packets came from it,
   - its median is at or above the threshold `T` (default -60 dBm), and
   - it leads the runner-up's median by at least the margin `X` (default 8 dB).
2. Otherwise the decision is `unknown`.

Two tags close in RSSI, or one tag with one or two packets, never produce a name. The raw
candidates (median, count, min, max per tag) go into the visit JSON, so the threshold and margin
can be tuned later from server-side data. `T` and `X` are stored in NVS (`t_dbm`, `x_db`) and
set with `set t <dbm>` and `set x <db>`.

The median uses the middle value for an odd count and `floor((a+b)/2)` of the two middle values
for an even count. The tag advertisement format the station accepts is described in
[tag-protocol.md](tag-protocol.md).

### 5.4 SD layout

| Path | Content |
|---|---|
| `/q/<visit_id>_<n>.jpg`, `/q/<visit_id>.json` | Upload queue. Files are written as `.tmp`, verified by read-back, then renamed. |
| `/sent/<YYYYMMDD>/` (`/sent/unsynced/`) | Uploaded files. Above 80 % card usage the oldest day is removed, one day per pass. |
| `/bad/` | Files the server refused for good (400, 413, 415, 422), and files the station cannot use (empty, over 1 MiB, unreadable three times in a row). |
| `/log/station.log` | Log, rotated to `station.1.log` at 1 MB. |
| `/benchls/` | Bench files made by the `benchls` command; never uploaded. |

`/q` is never deleted automatically. `snap_*.jpg` files from the `snap` command stay in `/q` and
are never uploaded.

Visit id: `<station_id>-<YYYYMMDD>T<HHMMSS>Z-<counter>` (UTC) once the clock is synced, or
`<station_id>-B<boot>-<counter>` before SNTP has set it. The boot counter lives in NVS, so the
unsynced form is unique across reboots.

### 5.5 Visit JSON

One record per visit, written at close and uploaded after the visit's photos:

```json
{
  "station_id": "ps-01",
  "visit_id": "ps-01-20261103T101500Z-0042",
  "started_at": "2026-11-03T10:15:00Z",
  "ended_at": "2026-11-03T10:16:10Z",
  "time_synced": true,
  "photos": [
    {"n": 1, "captured_at": "2026-11-03T10:15:02Z", "bytes": 135012, "width": 1600, "height": 1200}
  ],
  "identification": {
    "decision": "tag",
    "tag_mac": "AA:BB:CC:DD:EE:01",
    "tag_name": "TAG-0001",
    "candidates": [{"mac": "AA:BB:CC:DD:EE:01", "median": -48, "count": 12, "min": -54, "max": -45}],
    "threshold_dbm": -60,
    "margin_db": 8
  },
  "firmware": "0.3.0",
  "light_pwm": 180
}
```

Times are UTC ISO-8601 with `Z`, or `null` when the clock was not synced at that moment.
`time_synced` refers to the visit opening: when SNTP completes during a visit, `started_at` is
`null` while `ended_at` and later `captured_at` values are real. `tag_mac` and `tag_name` are
`null` when the decision is `unknown`. The firmware writes this JSON by hand (no JSON library);
strings are escaped and the output is compact.

### 5.6 Configuration and secrets

All settings live in NVS, namespace `station`:

| Key | Meaning | Default |
|---|---|---|
| `ssid`, `pass` | Wi-Fi network and password (empty password = open network) | empty |
| `id` | Station id; also the hostname and mDNS name | `ps-01` |
| `key` | Device key sent as `Authorization: Bearer` | empty |
| `url` | Upload base URL (`https://upload.example.com`) | empty |
| `ota` | ArduinoOTA password; OTA stays off while empty | empty |
| `t_dbm`, `x_db` | Identification threshold and margin | -60, 8 |

Values are set once over USB with the serial `set` commands or with `tools/provision.py`, which
reads a gitignored `firmware/station/secrets.local.env`. The source tree holds no secret. The
`info` command shows only the last four characters of the key, and shows the Wi-Fi and OTA
passwords as set or unset. Every value is validated before it is stored (SSID 1-32 characters,
WPA2 password 8-63 or empty, id 1-31 letters, digits and `-`, URL starting with `http://` or
`https://`); an invalid value changes nothing. Wi-Fi credentials are kept in this namespace, not
in the Wi-Fi driver's own storage (`WiFi.persistent(false)`).

### 5.7 Networking

- Wi-Fi station mode with auto-reconnect. Hostname and mDNS name are the station id.
- SNTP from `pool.ntp.org`, time zone `UTC0`. All timestamps in file names, records and requests
  are UTC.
- Uploads go over HTTPS with the certificate chain and host name verified against the core's
  built-in CA bundle. `setInsecure()` is never used. A `http://` base URL is accepted only for
  local mocks; it sends the device key in clear.
- Timeouts: 5 s for TCP connect, which over TLS is also the write-stall limit and the read poll;
  15 s for the HTTP response wait and plain-socket I/O; 15 s for the TLS handshake. Request bodies
  are streamed in 1460-byte chunks with the task watchdog fed per chunk, so a slow but moving
  upload never trips the 30 s watchdog.
- Over `https://` the uploader waits for SNTP before the first request, because certificate dates
  cannot be checked without a clock (`upload_state` = `no_time`).
- The station does not follow 3xx redirects: a redirect counts as a retry and the heartbeat shows
  `upload_state` = `redirect`. The base URL must be the final host.
- OTA: ArduinoOTA on the local network, password protected, only when the `ota` password is set.
  No remote OTA in v1.

### 5.8 Reliability

- Task watchdog, 30 s, on the `visit` and `upload` tasks and on the idle task of core 0. A stuck
  task restarts the board.
- SD and camera init: three tries one second apart. If one still fails, the board restarts, but
  not into a fast loop: NVS counts the consecutive failed boots, and the third such boot stays up
  without the failing part. The heartbeat reports `sd_ok` and `cam_ok`. A boot with both parts up
  resets the counter.
- Upload retry: exponential backoff `min(5000 * 2^n, 600000)` ms. A 401 or 403 stops uploads until
  reboot or a new `set key` / `set url`. One unreadable file goes to `/bad` after three failed
  reads so it cannot block the queue.
- Memory: the photo body is copied into PSRAM before any network call; TLS needs about 40 KB of
  contiguous internal heap, which is why uploads and visits never overlap. The uploader keeps a
  window of the 16 oldest queue names in internal RAM instead of listing the whole directory into
  memory. The BLE scan runs on the raw NimBLE GAP API with fixed-size tables, because the Arduino
  `BLEScan` class keeps every advertiser and grows with every packet.
- Serial log plus a rotating `/log/station.log` on the SD card.

### 5.9 Serial console

115200 baud, one command per line. The command table with arguments and reply formats is in
[../firmware/station/README.md](../firmware/station/README.md#serial-commands).

## 6. Design invariants

These are the properties the host tests protect. A change that breaks one of them is a bug even
if the board still runs.

1. `millis()` wraps after 49.7 days on a mains-powered device: every interval comparison uses
   unsigned subtraction (`now - start >= d`), in the visit machine and in the tag table window.
2. Clock not yet synced (no Wi-Fi at boot): visit ids stay unique, the JSON says
   `time_synced: false`, and unknown timestamps are `null`, never a guessed time.
3. Two tags close in RSSI, or one tag with fewer than three packets: the decision is `unknown`,
   never a guessed name.
4. Server returns 5xx, times out, or answers a duplicate: retry without losing or duplicating a
   file; a duplicate (200) counts as sent.
5. Long Wi-Fi outage, then recovery: the backlog uploads oldest visit first, and a visit's photos
   before that visit's JSON.

## 7. Risks

| Risk | Effect | Handling |
|---|---|---|
| The PIR barely detects at 42 C (a hen's body is about 41 C) | Missed visits in summer | The trigger is a replaceable module; an IR light barrier at the entrance is the fallback. Measure in summer. |
| Small in/out RSSI difference | Wrong or many `unknown` decisions | Calibrate `T` and `X` in the real box; if the margin stays small, add shielding or a directional antenna. |
| Wi-Fi and BLE coexistence | Fewer BLE packets during uploads | Uploads only outside visits; check the packet count with Wi-Fi active. |
| Dust, ammonia, humidity | Hazy window, corrosion | Cleanable window, closed electronics compartment, silica gel. |
| The light scares the animal | Few visits | Slow 300 ms ramp, steady light during the visit, no flashing. |
| TLS heap peak | Out-of-memory during a handshake | Uploads never overlap a visit; the heartbeat reports `min_heap` and `int_largest_min`, and [bench-testing.md](bench-testing.md) sets the limits. |
