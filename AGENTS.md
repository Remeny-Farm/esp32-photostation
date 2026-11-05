# esp32-photostation: guide for contributors and coding agents

esp32-photostation is an open-source ESP32-S3 camera station (Seeed XIAO ESP32S3 Sense). A PIR sensor
opens a visit, the camera takes 3 to 5 photos onto an SD queue, BLE identifies the animal by its
tag, and a background task uploads photos and a visit JSON over HTTPS to your own server.
License: MIT.

## Reading order

1. [README.md](README.md): what the project does and how to build it.
2. [docs/architecture.md](docs/architecture.md): design and facts. Section "6. Design invariants"
   holds the binding rules; a change that breaks one is a bug even if the board runs.
3. [docs/protocol.md](docs/protocol.md): the upload contract.
4. [docs/tag-protocol.md](docs/tag-protocol.md): the BLE advertisement format.
5. [docs/hardware.md](docs/hardware.md): board, pins and wiring.
6. [docs/bench-testing.md](docs/bench-testing.md): checks on a real board and their limits.
7. [firmware/station/README.md](firmware/station/README.md): build, flash, provisioning, console.
8. [CONTRIBUTING.md](CONTRIBUTING.md): setup, checks, style, pull request expectations.

## Repo map

- `firmware/station/`: the production sketch (`station.ino`).
  - `src/core/`: pure C++ protocol logic (identification, upload policy, records, visit state
    machine). No Arduino or ESP-IDF headers; tested on the host in `test/`.
  - `src/hw/`: hardware code (BLE, camera, SD, Wi-Fi, PIR, light, uploader, console).
- `firmware/blescan/`, `firmware/camtest/`, `firmware/sdhealth/`: bench sketches.
- `tools/`: host Python tools (stdlib plus pyserial): `mock_server.py` (the upload server for
  tests), `provision.py`, `serial_run.py`. Run them with `python -I` so no sibling module is
  imported by accident.
- `hardware/case/`: the 3D-printed enclosure (future work).
- `docs/`: design, protocol and bench documents.

## Checks to run

Run all three before a pull request; CI runs the same.

```sh
bash firmware/station/test/run.sh
(cd tools && python3 -m unittest test_mock_server)
arduino-cli compile --profile xiao_esp32s3 firmware/station
```

`bash firmware/station/test/run.sh [name]` runs one suite (`ident`, `policy`, `record`, `visit`).
Changes to camera, SD, BLE, Wi-Fi or the uploader also need a board run; see
[docs/bench-testing.md](docs/bench-testing.md).

## Rules

- English only: code, comments, docs, commit messages.
- No real secrets, MAC addresses, SSIDs, LAN addresses or private hostnames in tracked files. Use
  the documentation values `https://upload.example.com`, `192.168.1.50` and
  `AA:BB:CC:DD:EE:01` (and `:02`, `:03`, ...).
- Secrets live only in `firmware/station/secrets.local.env`, which is gitignored. The tracked
  template is `firmware/station/secrets.local.env.example`.
- The upload contract in [docs/protocol.md](docs/protocol.md) changes only together with
  `tools/mock_server.py` and its tests (`tools/test_mock_server.py`).
- Keep the docs in sync with the code in the same change.
- Comments explain why, not what. Add a line under `Unreleased` in [CHANGELOG.md](CHANGELOG.md).
- Releases only: bump `kFirmware` in `firmware/station/station.ino` and update `CHANGELOG.md`.
