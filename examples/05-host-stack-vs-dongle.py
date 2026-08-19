#!/usr/bin/env python3
"""Post 6 experiment: compare what a host Bluetooth stack reports vs what the
dongle's raw scan shows, while an advertiser renames itself.

Shows that the OS stack (macOS CoreBluetooth via bleak here) merges advertising
data + scan response and the scan-response name wins, so a rename in the
advertising data alone is invisible through the host stack.

Requires: two BleuIO dongles + `pip install pyserial bleak`.
Replace the two port paths below (find them with `python3 bleuio.py find --all`).
macOS-tested; run it on your own platform to see how yours behaves.
"""
import asyncio, time, re, serial
from bleak import BleakScanner

ADVERTISER_PORT = "/dev/cu.usbmodemXXXX"   # dongle that advertises (replace)
SCANNER_PORT    = "/dev/cu.usbmodemYYYY"   # dongle that scans raw (replace)

def at(port, cmd, wait=0.8):
    s = serial.Serial(port, 115200, timeout=0.2)
    try:
        s.reset_input_buffer(); s.write((cmd + "\r").encode()); time.sleep(wait)
        return re.sub(r"\r", "", s.read(8000).decode("utf-8", "replace")).strip()
    finally:
        s.close()

async def host_scan(seconds=6.0):
    seen = {}
    def cb(d, adv):
        if {d.name, adv.local_name} & {"SENSOR", "TEMP", "BleuIO"}:
            seen[d.address] = {"name": d.name, "local_name": adv.local_name}
    sc = BleakScanner(detection_callback=cb)
    await sc.start(); await asyncio.sleep(seconds); await sc.stop()
    return list(seen.values())

async def main():
    for name_hex, label in [("07:09:53:45:4E:53:4F:52", "SENSOR"),
                            ("05:09:54:45:4D:50", "TEMP")]:
        at(ADVERTISER_PORT, "AT+ADVSTOP")
        at(ADVERTISER_PORT, f"AT+ADVDATA={name_hex}")
        at(ADVERTISER_PORT, "AT+ADVSTART")
        raw = at(SCANNER_PORT, "AT+GAPSCAN=5", 6.5)
        dongle_names = re.findall(r"\(([A-Za-z0-9 ]+)\)", raw)
        host = await host_scan()
        print(f"\nadvertising data = {label!r}")
        print(f"  dongle raw scan sees: {dongle_names}")
        print(f"  host stack sees:      {host}")
    at(ADVERTISER_PORT, "AT+ADVSTOP")

if __name__ == "__main__":
    asyncio.run(main())
