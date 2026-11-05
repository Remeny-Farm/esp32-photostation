# esp32-photostation firmware

Firmware for the Seeed XIAO ESP32S3 Sense. A PIR edge opens a visit: 3 to 5 photos to the
SD queue, BLE identifies the tag in front of the camera, visit JSON written. A background
task uploads the queue over Wi-Fi to your upload server.

Design, including the SD layout and visit ids: [docs/architecture.md](../../docs/architecture.md).
Upload contract: [docs/protocol.md](../../docs/protocol.md). Tag advert format:
[docs/tag-protocol.md](../../docs/tag-protocol.md). Pins and wiring:
[docs/hardware.md](../../docs/hardware.md). Bench checks on a real board:
[docs/bench-testing.md](../../docs/bench-testing.md). Host tests and pull request checks:
[CONTRIBUTING.md](../../CONTRIBUTING.md).

## Build and upload

Tool: `arduino-cli`. `sketch.yaml` pins the `esp32:esp32` core (3.3.12) and the board options in the
`xiao_esp32s3` profile, so the profile build needs no `core install` step; `arduino-cli` downloads
the core on the first run.

```sh
arduino-cli compile --profile xiao_esp32s3 firmware/station
```

The same build with an explicit FQBN (for example on an already installed core):

```sh
FQBN='esp32:esp32:XIAO_ESP32S3:PSRAM=opi,PartitionScheme=default_8MB,CDCOnBoot=default,USBMode=hwcdc'
arduino-cli compile --fqbn "$FQBN" --build-path firmware/station/build firmware/station
```

Always chain `compile && upload`: after a failed build, `upload` would flash the old binary in the
build directory.

```sh
PORT=/dev/ttyACM0  # replace with the board's port
arduino-cli compile --profile xiao_esp32s3 --build-path firmware/station/build firmware/station \
  && arduino-cli upload --profile xiao_esp32s3 --build-path firmware/station/build -p "$PORT" firmware/station
```

`PORT` is the USB serial port of the board, for example `/dev/cu.usbmodem101` on macOS,
`/dev/ttyACM0` on Linux or `COM5` on Windows.

`PSRAM=opi` is required (the board has OPI PSRAM). If the board does not answer on USB (for example
the first flash over the factory firmware), put it in download mode: hold B, press R, release B.
After the first flash of this firmware the automatic reset of `arduino-cli upload` works.

After the first USB flash, OTA works over the LAN once `OTA_PASS` is set (OTA stays off without a
password). The station answers mDNS as `<station-id>.local`; its IP address works too:

```sh
STATION_ID=ps-01  # replace with the configured station id
OTA_PASS=your-ota-password  # replace with the configured OTA password
arduino-cli upload --profile xiao_esp32s3 --build-path firmware/station/build \
  -p "$STATION_ID.local" --protocol network --upload-field "password=$OTA_PASS" firmware/station
```

## Provision (secrets)

1. Copy `firmware/station/secrets.local.env.example` to
   `firmware/station/secrets.local.env` (gitignored) and fill in all values.
2. Install the tool dependency: `python3 -m pip install -r tools/requirements.txt`
   (or run the tools with `uvx --with pyserial python -I ...` instead of `python3 -I ...`).
3. Check the commands without sending anything: `python3 -I tools/provision.py --dry-run`.
4. Send them: `python3 -I tools/provision.py`. Add `--port PORT` or `--no-reboot` if needed.

The serial port comes from `--port`, else the environment variable `PHOTOSTATION_PORT`, else
auto-detection when exactly one USB serial port exists (for example `/dev/cu.usbmodem*` on macOS,
`/dev/ttyACM0` on Linux, `COM5` on Windows). With several ports the tool stops and lists them.

The tool sends `set wifi`, `set pass`, `set id`, `set key`, `set url`, `set ota`, then `reboot`. It
never prints values, and the board never echoes them. Values are stored in NVS (namespace
`station`).

`UPLOAD_BASE_URL` examples: the local mock `http://192.168.1.50:8787` (your computer's LAN IP), a
real server `https://upload.example.com`. `STATION_ID` example: `ps-01`.

For mock runs, `DEVICE_KEY` must be a separate test key, never the production key: `http://` sends
the key in clear over the LAN. Give the mock the same test key (`--key`, below).

## Mock server

`tools/mock_server.py` implements the upload contract of `docs/protocol.md`
(`/api/photostation/photo`, `/visit`, `/heartbeat`; Bearer device key):

```sh
python3 tools/mock_server.py --host 0.0.0.0 --port 8787 --key test-not-secret --store /tmp/mock-store
```

`test-not-secret` is a throwaway key for the mock. You can make another with `openssl rand -hex 16`.

The mock binds `127.0.0.1` by default; `--host 0.0.0.0` lets the board reach it over the LAN. The
`POST /__mode` hook (`{"fail": N}` makes the next N requests return 503) is unauthenticated. Run the
mock only on a trusted network and only while testing.

## Serial commands

115200 baud, one command per line. Replies start with `OK`, `ERR` or a tag (`INFO`, `LS`, `TAG`,
...). Quote values with spaces in double quotes. `tools/serial_run.py` sends a sequence of commands
(same port lookup as `provision.py`), for example
`python3 -I tools/serial_run.py "info" "pir" "sleep 40" "ls /q"`.

| Command | Effect |
|---|---|
| `info` | Station id, firmware, SD, BLE counters (`tag=` adverts and tags seen), Wi-Fi, config (secrets masked), upload state, PIR stuck flag, heap (internal free, largest block and its running minimum `int_largest_min`). |
| `pir` | Simulates a PIR edge (opens a visit). |
| `snap` | Takes one photo into `/q/snap_<ms>.jpg` (refused while a visit is open; never uploaded). |
| `ls [dir]` | Lists the files of a directory (default `/`): the first 64 with sizes, then `LS_MORE <n> not shown` and `LS_END <dir> files=<total>`. |
| `cat <path>` | Prints the last 8 KB of a file. |
| `benchls <n>` | Bench: creates `n` (max 1000, digits only) tiny files in `/benchls` once, reuses them later, and times one listing with the uploader's queue count. Prints `BENCHLS files=<n> ms=<t>`. Outside `/q`, so nothing is uploaded. Refused while a visit is open. |
| `benchls clean` | Deletes `/benchls` and its files. Refused while a visit is open. |
| `scan` | Per tag over the last 30 s: mac, name, RSSI median, count, min, max, battery mV. |
| `set` | Shows threshold `t` and margin `x`. |
| `set t <dbm>` / `set x <db>` | Identification threshold (-100..-20) and margin (0..40), stored in NVS. |
| `set wifi <ssid> [<pass>]` | Wi-Fi network; reconnects at once. Both values are validated first; one `ERR` line and nothing stored when either is invalid. |
| `set pass <password>` | Wi-Fi password: the raw rest of the line, spaces and quotes kept. |
| `set key <k>` / `set url <base>` | Device key and upload base URL. |
| `set id <station>` / `set ota <pass>` | Station id and OTA password; reboot to apply. |
| `reboot` | Restarts the board. |
