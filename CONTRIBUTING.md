# Contributing to esp32-photostation

Thanks for helping. Issues and pull requests are welcome for firmware, tools, documentation and the
case.

## Setup

- `arduino-cli` with the `esp32:esp32` core, version 3.3.12 (the version is pinned in
  `firmware/station/sketch.yaml`).
- A C++17 compiler for the host tests (`c++` on macOS or Linux).
- Python 3.9 or newer; `python3 -m pip install -r tools/requirements.txt` for the tools.

## Checks before a pull request

Run all three; CI runs the same.

```sh
bash firmware/station/test/run.sh
(cd tools && python3 -m unittest test_mock_server)
arduino-cli compile --profile xiao_esp32s3 firmware/station
```

`run.sh [name]` runs one suite (`ident`, `policy`, `record`, `visit`) or all of them.

## Style

- C++17. The host tests build with `-Werror`; keep the code warning-free.
- `firmware/station/src/core` holds the protocol-level logic (identification, upload policy,
  records, visit state machine). It includes no Arduino or ESP-IDF headers, so it builds and tests
  on the host. Hardware access lives in `firmware/station/src/hw`.
- Comments explain *why*, not what. A constant with a limit names the reason for the limit.
- English only, in code, comments, docs and commit messages.
- No real secrets, MAC addresses, SSIDs, LAN addresses or private hostnames in code, tests, docs
  or logs. Use the documentation values (`https://upload.example.com`, `ps-01`,
  `AA:BB:CC:DD:EE:01`, `192.168.1.50`).

## Hardware-in-the-loop

Changes that touch the camera, SD, BLE, Wi-Fi or the uploader need a run on a real board. The
checks and the limits they must meet are in [docs/bench-testing.md](docs/bench-testing.md). Paste
the relevant `info` output into the pull request.

## Case contributions

The 3D-printed case lives under `hardware/case/`. Contribute source files (CAD) together with
exported meshes, and note the printer, material and settings you verified with.

## Pull request expectations

- One topic per pull request, with a short description of what changed and why.
- Tests for `src/core` changes; a bench note for `src/hw` changes.
- Update the docs that describe the changed behaviour (`docs/protocol.md` for anything on the
  wire, `docs/tag-protocol.md` for the advertisement format).
- Add a line under `Unreleased` in `CHANGELOG.md`.
- Bump `kFirmware` in `firmware/station/station.ino` only in a release pull request.
