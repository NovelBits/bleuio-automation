#!/usr/bin/env python3
"""Minimal BleuIO dongle control over its USB-serial AT interface.

BleuIO (Smart Sensor Devices, DA14683) is a scriptable Bluetooth LE USB dongle
driven by AT commands over a CDC-ACM serial port. This wrapper finds the dongle
and sends commands, so an agent never has to re-derive the serial plumbing.

Usage:
  bleuio.py find                      # print the BleuIO's AT serial port
  bleuio.py info                      # ATI (firmware, role, connection status)
  bleuio.py cmd "AT+ADVSTART"         # send one AT command, print the response
  bleuio.py cmd "AT+GAPSTATUS" --port /dev/cu.usbmodemXXXX --wait 0.6

Notes:
  - The dongle may expose more than one usbmodem/ttyACM port; `find` probes each
    with ATI and picks the one that answers "BleuIO", so it won't grab a sniffer
    or some other serial device by mistake.
  - Commands are terminated with CR (\\r). Echo is ON by default, so the response
    text starts with the command echoed back.
"""
import sys
import glob
import time
import argparse

try:
    import serial  # pyserial
except ImportError:
    sys.exit("pyserial is required:  pip3 install pyserial")

BAUD = 115200
PORT_GLOBS = ("/dev/cu.usbmodem*", "/dev/ttyACM*")  # macOS, Linux


def _ports():
    seen = []
    for g in PORT_GLOBS:
        seen.extend(sorted(glob.glob(g)))
    return seen


def _probe(port, timeout=0.6):
    try:
        s = serial.Serial(port, BAUD, timeout=timeout)
    except Exception:
        return None
    try:
        s.reset_input_buffer()
        s.write(b"ATI\r")
        time.sleep(0.4)
        return s.read(400).decode("utf-8", "replace")
    except Exception:
        return None
    finally:
        s.close()


def find_port():
    for p in _ports():
        r = _probe(p)
        if r and "BleuIO" in r:
            return p
    return None


def find_all_ports():
    """All ports that answer ATI with 'BleuIO' (multi-dongle rigs)."""
    return [p for p in _ports() if (r := _probe(p)) and "BleuIO" in r]


def send(port, cmd, wait=0.5, nbytes=4000):
    s = serial.Serial(port, BAUD, timeout=0.8)
    try:
        s.reset_input_buffer()
        s.write((cmd + "\r").encode())
        time.sleep(wait)
        return s.read(nbytes).decode("utf-8", "replace")
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(description="Control a BleuIO dongle over serial.")
    ap.add_argument("action", choices=["find", "info", "cmd"])
    ap.add_argument("command", nargs="?", help="AT command (for 'cmd')")
    ap.add_argument("--port", help="Serial port (default: auto-detect via ATI)")
    ap.add_argument("--all", action="store_true",
                    help="With 'find': list every BleuIO port (multi-dongle rigs)")
    ap.add_argument("--wait", type=float, default=0.5,
                    help="Seconds to wait for the response (raise for scans)")
    a = ap.parse_args()

    if a.action == "find" and a.all:
        ports = find_all_ports()
        if not ports:
            sys.exit("No BleuIO found on serial.")
        print("\n".join(ports))
        return

    port = a.port or find_port()
    if not port:
        sys.exit("No BleuIO found on serial. Is it plugged in? "
                 "(looked at /dev/cu.usbmodem* and /dev/ttyACM*)")

    if a.action == "find":
        print(port)
    elif a.action == "info":
        print(send(port, "ATI").strip())
    elif a.action == "cmd":
        if not a.command:
            sys.exit("'cmd' needs a command string, e.g. cmd \"AT+ADVSTART\"")
        print(send(port, a.command, wait=a.wait).strip())


if __name__ == "__main__":
    main()
