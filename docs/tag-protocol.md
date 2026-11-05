# Tag protocol

The station identifies animals by the BLE advertisements of a small tag each animal carries. This
document describes the advertisement format the firmware accepts by default, where that format is
decoded in the code, and how to adapt the station to a tag of your own.

The station only listens. It never connects to a tag during normal operation and needs no
pairing. Any BLE beacon that follows the format below, or a format you add in `ble.cpp`, works.

## Reference tag advertisement

The reference tag advertises about once per second from a static random address. Its name and
its manufacturer data are in the scan response, not in the primary advertisement, so the station
runs an active scan (interval 100 ms, window 99 ms, no duplicate filter).

The manufacturer-specific AD structure (type `0xFF`) carries, company id included:

```
offset  0 1   2 3 4 5 6   7    8     9...
bytes   FF FF 'C' 'H' 'R' 'P' 'T'  fw   vbat  (reserved by the tag firmware)
```

- Bytes 0-1: company id `0xFFFF` (the Bluetooth SIG value reserved for testing and unassigned
  use), little-endian on the wire.
- Bytes 2-6: the ASCII magic `CHRPT`. This is the prefix the firmware matches.
- Byte 7: tag firmware version, `MAJOR * 10 + MINOR` (`0x23` = 3.5).
- Byte 8: battery, `mV = 2000 + 10 * byte`; `0xFF` means unknown. Example: `0x60` = 2960 mV.
- Bytes 9 and up: activity counters and orientation data of the reference tag. The station
  ignores them.

The tag name comes from the Complete Local Name (`0x09`) or, failing that, the Shortened Local
Name (`0x08`) AD structure. The station keeps at most 20 printable ASCII characters and replaces
other bytes with `?`. Example values used in the docs and tests: address `AA:BB:CC:DD:EE:01`,
name `TAG-0001`.

Because the reference tag's address is a static random address derived from the chip's factory
data, it stays the same after a reboot or a battery change. That makes `tag_mac` a stable key
for the server-side tag-to-animal mapping.

## Where the firmware decodes it

Everything is in `firmware/station/src/hw/ble.cpp`:

- `kTagMfrPrefix` holds the prefix bytes `FF FF 'C' 'H' 'R' 'P' 'T'`.
- `isTagAdvert(const uint8_t* d, size_t n)` returns true when the manufacturer data is at least
  9 bytes long and starts with `kTagMfrPrefix`. Only advertisements that pass this check are
  added to the tag table; a scan response with a name but no manufacturer data updates the name
  of a tag that was already seen.
- The GAP callback (`onGap`) walks the AD structures, formats the address as uppercase
  colon-separated hex (most significant byte first), reads the battery byte, and appends one
  (timestamp, RSSI) sample to the `TagTable` under a 5 ms lock. Reports with RSSI 127 (not
  available) are dropped.
- The `info` command and the once-a-minute `BLE` log line count accepted advertisements under
  the key `tag=` (and all advertisements under `adv=`).

The per-tag name and battery live in a fixed array of 32 entries apart from the sample table; the
least recently seen entry is replaced when it is full.

## Adapting to another tag format

To use a different beacon (an iBeacon, an Eddystone frame, your own manufacturer data):

1. Change `kTagMfrPrefix` and, if the match is more than a prefix, `isTagAdvert()`. The function
   receives the manufacturer data with the company id at offset 0.
2. If your tag has no battery byte, make the battery parse return 0 (unknown); if it is
   somewhere else, change the offset in `onGap`.
3. If your tag puts the name in the primary advertisement rather than the scan response, nothing
   changes: both are parsed the same way. If it has no name, the station reports the name as
   empty and the server sees `tag_name` as the empty string.
4. If your tag advertises less often than once per second, review the identification window
   (5 s before the visit to its close) and the minimum packet count (3): a short visit may not
   collect three packets. See [architecture.md section 5.3](architecture.md#53-identification).
5. Keep the `TagTable` limits in mind: 32 tags, 1024 samples per tag. The scan sees every BLE
   device nearby; only the ones that pass `isTagAdvert()` take a slot.

Host tests in `firmware/station/test/ident_test.cpp` cover the decision rule and are independent
of the wire format.

## Reference tag LED service

The reference tag also exposes a small GATT service to blink its LED, used by the
`firmware/blescan` sketch to find a tag physically (`L <mac> <n>` connects and blinks `n` times,
one per second). `blescan` sends `n` as one byte and uses 10 when `n` is omitted; it enforces no
upper limit, so any cap on the blink count is up to the tag firmware. The station firmware never
uses it.

| UUID | Role |
|---|---|
| `43485250-0001-4348-4952-50434f4f5000` | LED control service |
| `43485250-0002-4348-4952-50434f4f5000` | LED characteristic; write one byte = number of blinks |

Connecting and writing takes about 2 s. If your tag has no such service, ignore `blescan`'s `L`
command; its `s` command (a 30 s scan that prints every advertisement with raw manufacturer data)
is useful with any tag to see what it sends.
