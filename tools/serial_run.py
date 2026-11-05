#!/usr/bin/env python3
"""Send a sequence of serial commands to the station and print the response lines.

Usage (pyserial needed, see tools/requirements.txt):
  python3 -m pip install -r tools/requirements.txt
  python3 -I tools/serial_run.py "info" "pir" "sleep 40" "ls /q"
  (or: uvx --with pyserial python -I tools/serial_run.py ...)

Serial port: `--port`, else the env variable PHOTOSTATION_PORT, else auto-detect when exactly
one USB serial port is present. Examples: /dev/cu.usbmodem* on macOS, /dev/ttyACM0 on Linux,
COM5 on Windows.

Each argument is one step:
  "sleep N"   wait N seconds locally, printing whatever the board sends meanwhile
  anything else  is sent as a command line, then replies are read for --wait seconds

Lines that look like base64 (long, only base64 characters) are replaced by a count.
Options: --port, --boot-wait (read boot output first), --wait (reply window per command).
"""
import argparse
import os
import re
import sys
import time

import serial

B64 = re.compile(r"^[A-Za-z0-9+/=]{60,}$")


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


class Reader:
    def __init__(self, ser):
        self.ser = ser
        self.buf = b""
        self.skipped = 0

    def pump(self, seconds):
        end = time.monotonic() + seconds
        while True:
            left = end - time.monotonic()
            if left <= 0:
                break
            try:
                data = self.ser.read(256)
            except (serial.SerialException, OSError):
                self.reopen()
                continue
            if data:
                self.buf += data
                self.flush_lines()
        self.flush_lines()

    def flush_lines(self):
        while b"\n" in self.buf:
            raw, self.buf = self.buf.split(b"\n", 1)
            line = raw.decode("utf-8", errors="replace").rstrip("\r")
            if B64.match(line):
                self.skipped += 1
                continue
            if self.skipped:
                print(f"[{self.skipped} base64 lines filtered]")
                self.skipped = 0
            print(line, flush=True)

    def reopen(self):
        try:
            self.ser.close()
        except Exception:
            pass
        for _ in range(100):
            time.sleep(0.2)
            try:
                self.ser.open()
                print("[port reopened]", flush=True)
                return
            except (serial.SerialException, OSError):
                continue
        print("[port lost]", file=sys.stderr)
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("steps", nargs="+")
    ap.add_argument("--port", default=None,
                    help="serial port; default: env PHOTOSTATION_PORT, else the single USB serial port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--boot-wait", type=float, default=3.0)
    ap.add_argument("--wait", type=float, default=1.5)
    a = ap.parse_args()

    port = resolve_port(a.port)
    if port is None:
        sys.exit(2)
    ser = serial.Serial()
    ser.port, ser.baudrate, ser.timeout = port, a.baud, 0.1
    # DTR/RTS low before open: do not hold the chip in the download/reset state. The USB-CDC
    # board still resets on open, hence --boot-wait.
    ser.dtr = False
    ser.rts = False
    ser.open()
    rd = Reader(ser)
    rd.pump(a.boot_wait)
    for step in a.steps:
        m = re.fullmatch(r"sleep\s+([0-9.]+)", step.strip())
        if m:
            print(f"--- sleep {m.group(1)}", flush=True)
            rd.pump(float(m.group(1)))
            continue
        print(f"--- > {step}", flush=True)
        try:
            ser.write((step + "\n").encode())
        except (serial.SerialException, OSError):
            rd.reopen()
            ser.write((step + "\n").encode())
        rd.pump(a.wait)
    rd.pump(0.5)
    ser.close()


if __name__ == "__main__":
    main()
