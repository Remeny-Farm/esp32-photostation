# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Removed

- Station light control (GPIO2 PWM, `light` console command, `light=` INFO field, `light_pwm` visit
  JSON field). Lighting is now external.

### Added

- Mechanical reference dimensions for the case (`hardware/case/ref/DIMENSIONS.md`).
- The v1 case test bed in `hardware/case/`: parametric Blender model, printable STLs, assembly checks
  and a slicer check.

## 0.3.0 - 2026-11-05

First public release. Earlier versions were unpublished prototypes.

### Added

- Station firmware for the Seeed XIAO ESP32S3 Sense (`firmware/station`): PIR-triggered visits
  with 3 to 5 photos, an SD upload queue with verified writes, BLE tag identification by median
  RSSI with a threshold and a margin, HTTPS upload of photos and visit JSON with backoff,
  heartbeats every 5 minutes, password-protected ArduinoOTA and a serial console.
- Host tests for the protocol-level logic in `firmware/station/src/core`.
- Bench sketches `firmware/blescan`, `firmware/camtest` and `firmware/sdhealth`.
- Tools: `tools/provision.py`, `tools/serial_run.py` and the reference upload server
  `tools/mock_server.py` with its tests.
- Documentation: `docs/architecture.md`, `docs/protocol.md`, `docs/tag-protocol.md`,
  `docs/hardware.md`, `docs/bench-testing.md` and `hardware/case/README.md`.
- `firmware/station/sketch.yaml` pinning the `esp32:esp32` core 3.3.12 and the board options.
- CI: host tests, Python tests and a firmware compile with the pinned core.
