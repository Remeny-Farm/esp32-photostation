#!/usr/bin/env python3
"""Send the station configuration from secrets.local.env to the board over serial.

Usage (pyserial needed for a real run, see tools/requirements.txt):
  python3 -m pip install -r tools/requirements.txt
  python3 -I tools/provision.py [--env FILE] [--port PORT] [--no-reboot]
  python3 -I tools/provision.py --dry-run [--env firmware/station/secrets.local.env.example]
  (or: uvx --with pyserial python -I tools/provision.py ...)

Serial port: `--port`, else the env variable PHOTOSTATION_PORT, else auto-detect when exactly
one USB serial port is present. Examples: /dev/cu.usbmodem* on macOS, /dev/ttyACM0 on Linux,
COM5 on Windows. Example UPLOAD_BASE_URL: https://upload.example.com, or the local mock
http://192.168.1.50:8787 (see tools/mock_server.py).

Reads WIFI_SSID, WIFI_PASS, STATION_ID, DEVICE_KEY, UPLOAD_BASE_URL, OTA_PASS (KEY=VALUE lines,
comments, one pair of surrounding quotes is removed). Sends `set wifi`, `set pass`, `set id`,
`set key`, `set url`, `set ota`, then `reboot`. Values are never printed: not in the dry run,
not in errors, not from the board's replies (the board never echoes them either).
"""
import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ENV = os.path.join(HERE, "..", "firmware", "station", "secrets.local.env")
MASK = "********"

# (env key, firmware command, required)
FIELDS = [
    ("WIFI_SSID", "wifi", True),
    ("WIFI_PASS", "pass", False),
    ("STATION_ID", "id", False),
    ("DEVICE_KEY", "key", True),
    ("UPLOAD_BASE_URL", "url", True),
    ("OTA_PASS", "ota", False),
]


def read_env(path):
    values = {}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
            if not m:
                continue
            val = m.group(2)
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            values[m.group(1)] = val
    return values


def check_value(key, val):
    """Return an error text without the value, or None when the value can be sent."""
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in val):
        return "%s contains a control character" % key
    if key != "WIFI_PASS" and '"' in val:
        return "%s contains a double quote, which the console cannot quote" % key
    if key == "UPLOAD_BASE_URL" and not re.match(r"^https?://\S+$", val):
        return "UPLOAD_BASE_URL must start with http:// or https:// and have no spaces"
    if key in ("DEVICE_KEY", "STATION_ID", "OTA_PASS") and re.search(r"\s", val):
        return "%s must not contain spaces" % key
    return None


def build(values):
    """Return (commands, problems, notes). A command is (line, label)."""
    cmds, problems, notes = [], [], []
    for key, cmd, required in FIELDS:
        val = values.get(key, "")
        if val == "" and cmd == "pass":
            # An empty WIFI_PASS means an open network: `set pass` with nothing clears the password.
            cmds.append(("set pass", "set pass"))
            continue
        if val == "":
            if required:
                problems.append("%s is empty" % key)
            else:
                notes.append("%s is empty, skipped" % key)
            continue
        err = check_value(key, val)
        if err:
            problems.append(err)
            continue
        if cmd == "wifi":
            line = 'set wifi "%s"' % val
        else:  # `set pass` takes the rest of the line verbatim
            line = "set %s %s" % (cmd, val)
        cmds.append((line, "set %s" % cmd))
    return cmds, problems, notes


def resolve_port(flag):
    """Return --port, else env PHOTOSTATION_PORT, else the only USB serial port; None after an error."""
    port = flag or os.environ.get("PHOTOSTATION_PORT", "").strip()
    if port:
        return port
    from serial.tools import list_ports
    ports = list_ports.comports()
    usb = [p for p in ports if p.vid is not None]
    if len(usb) == 1:
        return usb[0].device
    if usb:
        print("error: %d USB serial ports found, pass --port or set PHOTOSTATION_PORT:" % len(usb),
              file=sys.stderr)
    else:
        print("error: no USB serial port found, pass --port or set PHOTOSTATION_PORT", file=sys.stderr)
    for p in usb or ports:
        print("  %s  %s" % (p.device, p.description), file=sys.stderr)
    return None


def send_all(cmds, port, baud, reboot):
    try:
        import serial
    except ImportError:
        print("pyserial missing: python3 -m pip install -r tools/requirements.txt", file=sys.stderr)
        return 2
    port = resolve_port(port)
    if port is None:
        return 2
    ser = serial.Serial()
    ser.port, ser.baudrate, ser.timeout = port, baud, 0.1
    ser.dtr = False  # opening with DTR/RTS low avoids resetting the USB CDC board
    ser.rts = False
    ser.open()
    failed = False
    try:
        time.sleep(0.5)
        ser.reset_input_buffer()
        for line, label in cmds:
            ser.write((line + "\n").encode("utf-8"))
            reply = None
            end = time.monotonic() + 5
            buf = b""
            while time.monotonic() < end and reply is None:
                buf += ser.read(256)
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    text = raw.decode("utf-8", errors="replace").strip()
                    if text.startswith("OK ") or text.startswith("ERR "):
                        reply = text
                        break
            # Print only the status word and the field name; never the board's text.
            if reply and reply.startswith("OK "):
                print("OK    %s" % label)
            else:
                print("FAIL  %s (%s)" % (label, "board refused" if reply else "no reply"))
                failed = True
        if reboot and not failed:
            ser.write(b"reboot\n")
            print("OK    reboot")
    finally:
        ser.close()
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default=DEFAULT_ENV)
    ap.add_argument("--port", default=None,
                    help="serial port; default: env PHOTOSTATION_PORT, else the single USB serial port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--dry-run", action="store_true", help="print the commands with masked values, send nothing")
    ap.add_argument("--no-reboot", action="store_true")
    a = ap.parse_args()

    try:
        values = read_env(a.env)
    except OSError as e:
        print("cannot read %s: %s" % (a.env, e.strerror), file=sys.stderr)
        return 2
    cmds, problems, notes = build(values)
    for n in notes:
        print("note: %s" % n, file=sys.stderr)
    if a.dry_run:
        sent = {label for _, label in cmds}
        for key, cmd, required in FIELDS:
            label = "set %s" % cmd
            if label in sent:
                print("%s %s" % (label, MASK))
            elif values.get(key, "") == "":
                print("%s %s   (%s empty: %s)" % (label, MASK, key, "a real run stops" if required else "skipped"))
        if not a.no_reboot:
            print("reboot")
        for p in problems:
            print("would stop: %s" % p, file=sys.stderr)
        print("dry run: %d commands, %d problems, nothing sent" % (len(cmds), len(problems)), file=sys.stderr)
        return 0
    if problems:
        for p in problems:
            print("error: %s" % p, file=sys.stderr)
        return 2
    return send_all(cmds, a.port, a.baud, not a.no_reboot)


if __name__ == "__main__":
    sys.exit(main())
