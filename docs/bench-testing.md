# Bench testing

How to prove a firmware build on a real board before it goes into the field. The checks below
are generic: any XIAO ESP32S3 Sense with the station firmware, a microSD card and a computer on
the same LAN.

## Tools

- `tools/serial_run.py` sends a sequence of serial commands and prints the board's replies
  (install and port selection: [../firmware/station/README.md](../firmware/station/README.md#provision-secrets)).
  `sleep N` steps wait locally while printing whatever the board logs. Opening the port resets the
  board, so each call starts from boot (`--boot-wait` controls how long it waits before the first
  command).

- `tools/mock_server.py` is the reference upload server ([protocol.md](protocol.md)). Start it
  bound to the LAN as in [../firmware/station/README.md](../firmware/station/README.md#mock-server),
  then on the board: `set key test-not-secret`, `set url http://<your-computer-ip>:8787`
  (for example `http://192.168.1.50:8787`).

- The firmware's own `info` command prints the heap figures used below: `heap`, `min_heap`,
  `int_free`, `int_largest`, `int_largest_min`. The once-a-minute `BLE ...` log line repeats
  `heap`, `min_heap`, `int_free` and `int_largest` (not `int_largest_min`, which only `info` and
  the heartbeat report) together with the free stack of the `visit`, `upload` and `ble` tasks and
  the BLE counters (`adv=` all advertisements, `tag=` accepted tag advertisements).

## Limits

| Figure | Limit | Why |
|---|---|---|
| `min_heap` (lowest free heap since boot) | >= 60000 during a forced 10-minute visit | Keeps room for the TLS handshake that follows the visit. |
| `int_largest_min` (running minimum of the largest free internal block) | >= 20480 | One mbedTLS record buffer is about 16.7 KB (`SSL_MAX_CONTENT_LEN` 16384 plus overhead); 20480 leaves about 3.5 KB margin. |
| `stack_free` of `visit`, `upload`, `ble` | >= 1024 bytes | Headroom on the fixed task stacks. |
| 500-file `benchls 500` scan of `/benchls` | under 3 s | The uploader's directory pass must stay cheap with a backlog. |

Reference values from one board (firmware 0.2.x, BLE scanning): `int_largest_min` 31732 during
the upload burst after a forced visit, and 24564 inside an HTTPS handshake with BLE running.
`min_heap` 69924 at the end of a 10-minute visit; the HTTPS handshake alone pushed it to about
31000, which is the lifetime low and is why uploads never overlap a visit.

## Checks

### 1. Host tests

No board needed. The host tests and the mock server tests in
[../CONTRIBUTING.md](../CONTRIBUTING.md#checks-before-a-pull-request) must pass before any board
check.

### 2. 500-file listing

The uploader lists `/q` on every pass. A long backlog (a day of Wi-Fi outage) must not make that
slow.

1. `benchls 500` over the console. The first run creates 500 tiny JPEG stubs in `/benchls`
   (about 160 s on the card; the task watchdog is fed per file). Later runs reuse them.
2. Read `BENCHLS files=500 ms=<t>`. Pass: `t` under 3000. Typical: about 300 ms.
3. `info` shows `queue=0`: `/benchls` is outside the queue and is never uploaded.
4. `benchls clean` removes the directory.

`benchls` is refused while a visit is open. Opening a new serial session resets the board and
aborts a running creation; the next run resumes it.

### 3. Forced 10-minute visit: heap and stacks

1. Disconnect the PIR and connect D0 (GPIO1) to 3V3, or send `pir` every 5 s with
   `serial_run.py` for 11 minutes.
2. Watch the log for 12 minutes (`"sleep 720"`). Expect `Open`, five `Capture` lines (the PIR
   keeps firing), and after 600 s `Close Forced ... photos=5 json ok`.
3. Read the 60 s `BLE ...` lines (`min_heap`, `stack_free`) and a final `info` (`int_largest_min`).
   Pass: `min_heap` >= 60000, `int_largest_min` >= 20480, every `stack_free` value >= 1024.
4. With the mock running, the five photos and the visit JSON upload right after the close
   (`-> 201`), `/q` is empty afterwards and `boot=` in `info` did not change (no watchdog
   reboot).
5. Optional: leave D0 on 3V3 for 30 minutes. After the third forced close expect one
   `PIR stuck HIGH` line, then no new visit, uploads resume, and the heartbeat shows
   `"pir_stuck":true` and `"forced_closes":3`. Remove the wire: `PIR pin LOW again`.

### 4. HTTPS handshake with BLE running

Proves the certificate check and the TLS handshake work next to the continuous BLE scan, and
measures the handshake's heap dip.

1. `set key test-not-secret`, `set url https://<public-https-host>`: any reachable public host
   with a valid certificate (your own `https://upload.example.com`, or a public test host such as
   `https://httpbin.org`). The heartbeat path does not need to exist there.
2. `reboot`, wait about 25 s, `info`. The first heartbeat goes out about 6 s after boot.
3. Pass: `HB -> 404` or another real HTTP status in the log (a negative value means the
   handshake or the certificate check failed), and `int_largest_min` >= 20480 in `info`.
4. Put the mock key and URL back.

Note that `int_largest_min` is sampled inside the HTTP request while the TLS context is still
allocated, so it does catch the handshake dip; `int_largest` is the current value only.

### 5. USB-charger run

Proves the station runs without a host computer.

1. With the mock running on the LAN, move the board from the computer to a USB phone charger.
2. Trigger three visits over 30 minutes (wave a hand at the PIR).
3. Pass: the mock store gets the photos and visit JSONs, and `heartbeat.jsonl` gets a line about
   every 5 minutes with a rising `uptime_s` (no reboot).
4. Move the board back. `cat /log/station.log` shows no `BOOT` line inside the charger window.

### 6. Retry path

1. `curl -X POST http://127.0.0.1:8787/__mode -d '{"fail":3}'` on the mock host.
2. `pir`, wait for the close.
3. Pass: three `503` lines in the mock log, then `201`s; nothing lost, nothing duplicated
   (`/q` empty, one file per photo in the store).

### 7. OTA

After `set ota <password>` and a reboot, compile and flash over the network with the OTA
command in [../firmware/station/README.md](../firmware/station/README.md#build-and-upload).

Pass: `Authenticating ... OK`, upload to 100 %, the board reboots and its first heartbeat shows
the new `firmware` string.

## Reading the log

Log lines of interest, each with a millisecond timestamp:

| Line | Meaning |
|---|---|
| `BOOT station=ps-01 fw=0.3.0 boot=<n> sd=1` | boot; `boot=` rises on every reset |
| `WIFI up ip=... rssi=...` | Wi-Fi connected |
| `Open <visit_id>` / `Capture <n> ...` / `Close Silence\|Forced ...` | the visit machine |
| `HB -> <status>` | heartbeat result |
| `UP <file> <bytes> bytes -> <status>` | one upload; `UP retry in <ms>` on failure |
| `UP redirect <status> ...` | the base URL redirects; fix the URL |
| `BLE adv=... tag=... heap=... min_heap=... int_largest=... stack_free ...` | one line per minute |
