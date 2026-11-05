# esp32-photostation

[![CI](https://github.com/Remeny-Farm/esp32-photostation/actions/workflows/ci.yml/badge.svg)](https://github.com/Remeny-Farm/esp32-photostation/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An open-source animal camera station for the ESP32-S3 (Seeed XIAO ESP32S3 Sense). A motion sensor
triggers a short photo burst, a BLE tag tells *which* animal it was, and the photos and a visit
record wait on the SD card until they are uploaded over HTTPS to **your own server**. It keeps
working offline, and nothing in it depends on a cloud service.

The motivating example is a backyard hen coop: each hen wears a small BLE tag, and the station
records who visited the nest box and when. Nothing in the firmware is hen-specific. Any animal that
can carry a tag, and any server that speaks the small HTTPS contract in [docs/protocol.md](docs/protocol.md), works.

## What it does

1. A PIR sensor wakes the station and opens a *visit*: the LED light turns on.
2. The camera takes up to 5 photos per visit and queues them on the microSD card.
3. The always-on BLE scan supplies the advertisements seen from 5 s before the visit opened until
   it closes. The station picks the tag with the strongest **median RSSI** above a threshold and with a clear margin over
   the runner-up; otherwise the visit is `unknown`.
4. The light turns off and a visit JSON (photos, timing, identification candidates) is written next
   to the photos in the SD queue.
5. Outside visits, a background task uploads the queue over Wi-Fi to **your own server** by HTTPS:
   photos first, then the visit JSON, oldest visit first. Heartbeats with health counters go out
   every 5 minutes. Failed uploads back off and retry; a rejected device key stops uploads until
   reboot.

Firmware runs on the Arduino core for ESP32 with no external libraries. The protocol-level logic
(`firmware/station/src/core`) is plain C++17 with host-side unit tests.

## Hardware

- Seeed **XIAO ESP32S3 Sense** with an OV2640, OV3660 or OV5640 camera module
- microSD card, FAT32
- AM312 PIR sensor
- LED light (PWM-dimmable)
- u.FL antenna on the board's connector (without it, BLE range is near zero)
- BLE tags: any beacon that sends the advertisement described in [docs/tag-protocol.md](docs/tag-protocol.md)

Wiring, pins and the GPIO conflicts are in [docs/hardware.md](docs/hardware.md).

## Repository layout

| Path | Content |
|---|---|
| `firmware/station/` | The station firmware (sketch, `src/core`, `src/hw`, host tests) |
| `firmware/blescan/` | Bench sketch: scans and prints nearby tags |
| `firmware/camtest/` | Bench sketch: camera bring-up |
| `firmware/sdhealth/` | Bench sketch: microSD read/write check |
| `tools/` | `provision.py` (writes secrets to the board), `mock_server.py` (local upload server), `serial_run.py` |
| `docs/` | Architecture, protocol, tag protocol, hardware, bench testing |
| `hardware/case/` | The 3D-printed case (not yet published) |

## Quick start

1. Install [arduino-cli](https://arduino.github.io/arduino-cli/). The profile build in step 2
   installs the pinned `esp32:esp32` core, version 3.3.12, using its configured package index.
2. Compile the firmware: `arduino-cli compile --profile xiao_esp32s3 firmware/station`
   (the profile is in `firmware/station/sketch.yaml`).
3. Copy `firmware/station/secrets.local.env.example` to `firmware/station/secrets.local.env` and
   fill in Wi-Fi, station id, device key, upload URL and OTA password. The file is gitignored.
4. Install the Python tools: `python3 -m pip install -r tools/requirements.txt`
5. Flash the board. Replace the port with yours (see `firmware/station/README.md`) and keep
   `compile &&` so a failed build never flashes an old binary:
   `arduino-cli compile --profile xiao_esp32s3 firmware/station && arduino-cli upload --profile xiao_esp32s3 -p /dev/ttyACM0 firmware/station`.
   Then write the secrets over USB: `python3 -I tools/provision.py`
   (pick the port with `--port` or the `PHOTOSTATION_PORT` environment variable; with one USB serial
   port attached it is auto-detected).
6. For a local end-to-end test without a real server, run
   `python3 tools/mock_server.py --host 0.0.0.0 --port 8787 --key test-not-secret --store /tmp/mock-store`
   and set the upload URL to `http://<your-computer-ip>:8787` with a throwaway key.

The full build, flash, OTA and serial-console reference is in [firmware/station/README.md](firmware/station/README.md).

## Bring your own server

The station needs an HTTPS endpoint that implements the three routes in [docs/protocol.md](docs/protocol.md)
(`/api/photostation/photo`, `/visit`, `/heartbeat`) behind a per-station bearer key. The base URL is
the `url` config value, for example `https://upload.example.com`. The mock server in
`tools/mock_server.py` is a reference implementation of the contract and is good enough to test
a station on a bench; it is not a production backend.

## Documentation

- [docs/architecture.md](docs/architecture.md): tasks, visit state machine, SD layout, reliability rules, design invariants
- [docs/protocol.md](docs/protocol.md): the upload contract (routes, headers, JSON, status handling, idempotency)
- [docs/tag-protocol.md](docs/tag-protocol.md): the BLE advertisement the station accepts and how identification works
- [docs/hardware.md](docs/hardware.md): parts, wiring, pin map, board quirks
- [docs/bench-testing.md](docs/bench-testing.md): hardware-in-the-loop checks and the limits they must meet
- [hardware/case/README.md](hardware/case/README.md): the case
- [firmware/station/README.md](firmware/station/README.md): build, flash, provision, serial commands

## Status

Version 0.3.0, first public release. Verified on one board. The 3D-printed case is not yet
published. Expect rough edges around other camera modules and other ESP32 boards.

## Contributing, security, license

- Contributions: see [CONTRIBUTING.md](CONTRIBUTING.md)
- Vulnerabilities: see [SECURITY.md](SECURITY.md)
- License: MIT, see [LICENSE](LICENSE). Third-party notices: [NOTICE](NOTICE).
