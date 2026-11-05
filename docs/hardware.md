# Hardware

What to buy, how to wire it, and the board facts the firmware relies on. The case is described
in [../hardware/case/README.md](../hardware/case/README.md).

## Parts list

| # | Item | Qty | Notes |
|---|---|---|---|
| 1 | Seeed XIAO ESP32S3 Sense (camera and u.FL antenna in the box) | 1 | The whole station: ESP32-S3, camera, microSD slot, Wi-Fi/BLE. |
| 2 | microSD card, 16-32 GB, high endurance, FAT32 | 1 | Format as FAT32; exFAT does not mount. |
| 3 | AM312 mini PIR module | 1 | Trigger. Any 3.3 V PIR with a digital output works. |
| 4 | 5 V white LED strip, about 0.5 W, with a diffuser | 1 | A single 5 mm LED is not enough light. |
| 5 | Logic-level N-MOSFET (AO3400 or similar), 100 ohm gate resistor, 10 kohm pull-down | 1 | Switches the LED strip from GPIO2. A 2N7000 opens unreliably at 3.3 V gate drive. |
| 6 | 5 V / 2 A outdoor USB power supply and USB-C cable | 1 | Mains powered; no battery in v1. |
| 7 | Pin header, silicone wire, heat-shrink tubing | 1 set | |
| 8 | USB-C data cable | 1 | For flashing and the serial console. |
| 9 | Acrylic or polycarbonate window | 1 | In front of the camera; cleanable. |
| 10 | Silica gel, aluminium tape | | Humidity and optional RF shielding. |
| 11 | PETG filament | | For the case; PLA softens in summer heat. |

Optional: a spare FPC antenna from the board vendor (cheap, order it with the board). A
multimeter with a microamp range if you want to measure sleep currents for a future battery
version.

## XIAO ESP32S3 Sense facts

- ESP32-S3, dual core, 240 MHz, 8 MB flash, 8 MB OPI PSRAM. Compile with `PSRAM=opi`; the
  project's `sketch.yaml` profile `xiao_esp32s3` sets this.
- USB-Serial/JTAG on the USB-C port. It appears as `/dev/cu.usbmodem*` on macOS,
  `/dev/ttyACM*` on Linux and a `COM` port on Windows.
- Camera on the Sense expansion board: boards ship with OV2640, OV3660 or OV5640 (with
  autofocus) depending on the production run. The firmware prints the detected sensor in `info`
  (`camera=OV3660`). At 1600x1200 JPEG quality 10 one photo is 120-145 KB and takes about 1 ms
  to pull from the frame buffer after four warm-up frames. In dim room light without the LED the
  picture is dark and purple; the light is required.
- One u.FL connector; Wi-Fi and BLE share the antenna. There is no on-board antenna. Without the
  external antenna every BLE signal was below -80 dBm and most tags were invisible; with it the
  same tag went from -82 to -48 dBm. Always keep the antenna plugged in.
- Power figures from the vendor: about 154 mA average and 366 mA peak while taking a photo;
  100 mA LiPo charge current. The deep-sleep current is quoted inconsistently (14 uA for the
  chip, about 3 mA for the board); measure it before planning a battery build.
- The microSD slot is wired to SPI. At 20 MHz the bus limits throughput to about 1.3 MB/s write
  and 1.7 MB/s read, so one photo saves in about 0.1 s.

## Pinout

Firmware pins (`firmware/station/src/hw/pir.cpp`, `light.cpp`, `storage.cpp`):

| Function | GPIO | XIAO label |
|---|---|---|
| PIR output | GPIO1 | D0 |
| Light MOSFET gate (LEDC PWM, 5 kHz, 8 bit) | GPIO2 | D1 |
| SD card CS | GPIO21 | |
| SD card SCK | GPIO7 | |
| SD card MISO | GPIO8 | |
| SD card MOSI | GPIO9 | |

Camera pins follow the Seeed `CAMERA_MODEL_XIAO_ESP32S3` definition: XCLK 10, SIOD 40, SIOC 39,
Y9-Y2 on 48/11/12/14/16/18/17/15, VSYNC 38, HREF 47, PCLK 13; no PWDN or RESET.

Free GPIOs with the Sense board attached: GPIO1-6, 43, 44. GPIO3 is a strapping pin; do not use
it.

### The GPIO21 user-LED conflict

GPIO21 is both the SD card chip select and the on-board user LED. While the SD card is in use the
LED flickers with SD activity and cannot be used as an indicator. The firmware does not touch the
user LED; the visit light on GPIO2 is the only light output.

## Wiring

- PIR: VCC to 3V3, GND to GND, OUT to D0 (GPIO1). The AM312 output is 3.3 V, so no divider is
  needed.
- Light: LED strip + to 5 V, LED strip - to the MOSFET drain, MOSFET source to GND, gate to D1
  (GPIO2) through 100 ohm, 10 kohm from gate to GND. The firmware drives the gate with PWM and
  ramps the level over 300 ms, so the animal never sees a flash. Visit level is PWM 180 of 255.
- Power: USB-C from a 5 V / 2 A supply. The board's own 5 V pin can feed the LED strip at
  0.5 W.
- Antenna: plug the u.FL antenna in and route it inside the case roof, above the animal's back,
  away from metal.

To bench-test a forced visit without a PIR, connect D0 to 3V3: the visit opens, takes photos, and
the 10-minute cap closes it.

## Antenna lessons

- 2.4 GHz has a wavelength of about 12.5 cm. An entrance of 20-25 cm is larger than half a
  wavelength, so a metal-lined box alone does not keep outside tags out. Put the antenna close to
  where the animal stands (a near tag is a strong tag) and decide on the median RSSI with a
  margin, instead of relying on shielding.
- Aluminium tape on the walls, except around the entrance, is an optional second step if the
  in/out difference turns out small. It also weakens Wi-Fi, because both radios share the one
  antenna, so v1 ships without it.
- A single RSSI value is worthless: tags a few metres away showed a 20-25 dB spread and 3-27
  packets in 30 s. The tag right next to the antenna was about 13 dB stronger than the next one.

## Build tools and quirks

Toolchain, the pinned `sketch.yaml` profile, the FQBN, download mode and OTA are in
[../firmware/station/README.md](../firmware/station/README.md#build-and-upload). Board quirks:

- With `esptool` in the bootloader, `--before no-reset` made the second connection fail;
  `--before usb-reset` worked.
- The Arduino `SD` library mounts FAT only. Raw card access and formatting go through ESP-IDF
  `sdspi` and `esp_vfs_fat_sdcard_format()` (see the `firmware/sdhealth` sketch).
- On core 3.3.x the ESP32-S3 BLE stack is NimBLE. The Arduino `BLEScan` class keeps every
  advertiser for the whole scan and grows per packet (about 20 KB of heap lost in 24 s on a busy
  bench), so the station scans with the raw `ble_gap_disc` API and fixed-size tables.
- Opening the serial port resets the board. Every `tools/serial_run.py` call starts from a fresh
  boot, so `boot=` in `info` rises between sessions.

## macOS Bluetooth permission

A BLE scan from a terminal on macOS (for example with `bleak`) runs only when the terminal
application has Bluetooth permission in System Settings, Privacy and Security. Without it the
process dies with SIGABRT (exit 134) and prints nothing. The station itself does not need this;
it matters only for host-side scanning tools.
