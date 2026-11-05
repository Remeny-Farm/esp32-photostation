# Security policy

## Reporting a vulnerability

Report vulnerabilities through the repository's private vulnerability reporting (the "Security"
tab, "Report a vulnerability"). Do not open a public issue for a security problem. There is no
dedicated email address. You will get an acknowledgement in the report thread; fixes ship as a
normal release with a `CHANGELOG.md` entry.

## Security model

- **Device key.** Every station has its own bearer key (`key` in NVS), sent as
  `Authorization: Bearer <key>` on every request. A server should store only a hash of the key,
  bind it to the `X-Station-Id`, revoke it per station, and rate-limit per station. A `401` or `403`
  stops uploads until reboot or a new `set key`.
- **HTTPS.** Upload URLs are verified against the Arduino core's CA bundle. The firmware never
  disables certificate checks. Redirects are not followed.
- **OTA.** Over-the-air updates are enabled only when an OTA password is set (`ota` in NVS). Without
  a password, OTA stays off. ArduinoOTA checks the password with a challenge-response on the local
  network, but the image is neither signed nor encrypted: anyone on the LAN who knows the password
  can flash any firmware. Use a long, unique OTA password per station and leave it unset when you
  do not need OTA.
- **Plain `http://`.** Only for the local mock server in `tools/mock_server.py`, with a throwaway
  key, on a trusted network. The mock's `POST /__mode` test hook is unauthenticated; bind it to
  `127.0.0.1` unless a board must reach it.
- **Secrets at rest.** Secrets live only in the board's NVS and in the gitignored
  `firmware/station/secrets.local.env`. NVS is not encrypted: a flash dump holds every secret in
  clear, so keep dumps out of the repository (`backup/` and `*.bin` are gitignored). The serial
  `info` command shows only the last 4 characters of the key and shows the Wi-Fi and OTA passwords
  as set or unset, but prints the SSID and upload URL. The console never echoes `set` values.
  Do not commit credentials, paste them into issues, or put them in logs.
- **Physical access.** The serial console (USB, 115200 baud) gives full control: anyone with a
  cable can read the SD card, change the configuration, and set a new key or OTA password. Treat
  physical access as root access.
- **Data.** Photos and visit records are stored unencrypted on the SD card and sent to the server
  you configure. The station holds no other personal data.

## Scope

In scope: the station firmware, the bench sketches, the Python tools and the documented upload
protocol. Out of scope: your own server implementation and the arduino-esp32 core and its SDK
(report those upstream).
