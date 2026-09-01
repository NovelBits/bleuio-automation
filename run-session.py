#!/usr/bin/env python3
"""Run an annotated AT-command script against one or two BleuIO dongles and
capture the full transcript to JSON (+ optional markdown terminal blocks).

Built 2026-08-18 for the BleuIO automation content series: every command
sequence that appears in a post must have a captured run behind it. This is
the lightweight, reusable sibling of the BLE Unplugged course's
run-lesson-commands.py harness.

Script format (one command per line; blank lines and # comments ignored):

    [A] ATI
    [B] AT+GAPSTATUS
    [A] AT+GAPSCAN=5 @wait 6
    [B] AT+ADVSTART @expect ADVERTISING
    [B] AT+SPSSEND=hello @expect_not ERROR
    [A] @read 1.5                 # read pending async data (notifications) WITHOUT
                                  # sending anything; accepts @expect/@expect_not too
    @pause 2                      # sleep between commands (seconds)
    @note anything you want       # recorded in the transcript

Per-command directives (after the AT command, space-separated):
    @wait <s>          read window for this command (default 0.6; scans need it)
    @expect <str>      FAIL the step if response lacks <str> (case-insensitive)
    @expect_not <str>  FAIL the step if response contains <str>

[A]/[B] map to --port-a/--port-b. Single-dongle scripts just use [A].

Usage:
    python3 run-session.py demo.txt --port-a /dev/cu.usbmodemX \\
        [--port-b /dev/cu.usbmodemY] [--out capture.json] [--md capture.md]

Exit code: 0 if every @expect passed, 1 otherwise. Ports are opened once and
held for the whole session (required for SPS work; also faster).
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone

try:
    import serial
except ImportError:
    sys.exit("pyserial is required:  pip3 install pyserial")

BAUD = 115200
LINE = re.compile(r"^\[([AB])\]\s+(.*)$")


def clean(raw):
    """Serial response -> display text (strip \r, collapse blank runs)."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip("\n")


def read_response(port, wait, until=None):
    """Accumulate serial output for `wait` seconds. If `until` is given, return
    as soon as that substring appears (up to `wait` as a ceiling) — needed for
    async completion events (e.g. GATTCREAD) whose timing varies vs a fixed window."""
    end = time.time() + wait
    chunks = []
    while time.time() < end:
        n = port.in_waiting
        if n:
            chunks.append(port.read(n))
            if until and until.lower() in b"".join(chunks).decode("utf-8", "replace").lower():
                break
        time.sleep(0.05)
    return b"".join(chunks).decode("utf-8", "replace")


PLACEHOLDER = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


def parse_sets(pairs):
    """['CI=24', 'MAC=AA:BB'] -> {'CI': '24', 'MAC': 'AA:BB'}.

    Only the FIRST '=' separates, because AT syntax uses '=' inside values
    (e.g. --set P=intv_min=30)."""
    out = {}
    for p in pairs or []:
        key, sep, val = p.partition("=")
        if not sep or not key:
            raise ValueError(f"--set expects KEY=VALUE, got: {p!r}")
        out[key] = val
    return out


def substitute(text, values):
    """Replace every {{KEY}} in `text` from `values`.

    Raises if a placeholder has no value, or if a value is never used. Both are
    silent failures otherwise: an unsubstituted {{CI}} would be sent to the dongle
    literally, and a typo'd key would sweep the same value N times while looking
    like it worked."""
    used = set()

    def repl(m):
        key = m.group(1)
        if key not in values:
            raise ValueError(f"{{{{{key}}}}} in the script has no --set {key}=VALUE")
        used.add(key)
        return values[key]          # a function repl is literal; no backslash escapes

    out = PLACEHOLDER.sub(repl, text)
    unused = sorted(set(values) - used)
    if unused:
        raise ValueError(f"--set given but never used in the script: {', '.join(unused)}")
    return out


def parse_directives(rest):
    """Split 'AT+CMD @wait 6 @until FOO @expect FOO BAR' -> (cmd, {wait, until, expect, expect_not})."""
    d = {"wait": 0.6, "until": None, "expect": [], "expect_not": []}
    parts = re.split(r"\s+@(?=wait|until|expect_not|expect)", rest)
    cmd = parts[0].strip()
    for p in parts[1:]:
        key, _, val = p.partition(" ")
        val = val.strip()
        if key == "wait":
            d["wait"] = float(val)
        elif key == "until":
            d["until"] = val
        elif key == "expect":
            d["expect"].append(val)
        elif key == "expect_not":
            d["expect_not"].append(val)
    return cmd, d


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("script")
    ap.add_argument("--port-a", required=True)
    ap.add_argument("--port-b")
    ap.add_argument("--out", help="JSON transcript path")
    ap.add_argument("--md", help="Markdown render path (terminal blocks per step)")
    ap.add_argument("--set", action="append", metavar="KEY=VALUE", dest="sets",
                    help="Substitute {{KEY}} in the script. Repeatable. Sweep by looping "
                         "outside: for ci in 30 50 100; do ... --set CI=$ci --out cap-ci$ci.json; done")
    a = ap.parse_args()

    ports = {"A": serial.Serial(a.port_a, BAUD, timeout=0.2)}
    if a.port_b:
        ports["B"] = serial.Serial(a.port_b, BAUD, timeout=0.2)
    for p in ports.values():
        p.reset_input_buffer()

    try:
        values = parse_sets(a.sets)
        script_text = substitute(open(a.script).read(), values)
    except ValueError as e:
        sys.exit(f"{a.script}: {e}")

    steps, failures = [], 0
    for lineno, line in enumerate(script_text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@pause"):
            time.sleep(float(line.split()[1]))
            continue
        if line.startswith("@note"):
            steps.append({"note": line[5:].strip()})
            continue
        m = LINE.match(line)
        if not m:
            sys.exit(f"{a.script}:{lineno}: cannot parse: {line}")
        dongle, rest = m.group(1), m.group(2)
        if dongle not in ports:
            sys.exit(f"{a.script}:{lineno}: [{dongle}] used but --port-{dongle.lower()} not given")

        port = ports[dongle]
        if rest.startswith("@read"):
            # read pending async output (e.g. incoming notifications); no write, no flush
            m2 = re.match(r"@read\s*([\d.]*)\s*(.*)$", rest)
            wait = float(m2.group(1)) if m2.group(1) else 1.0
            _, d = parse_directives("READ " + m2.group(2))
            cmd = "(read)"
            resp = clean(read_response(port, wait))
        else:
            cmd, d = parse_directives(rest)
            port.reset_input_buffer()
            port.write((cmd + "\r").encode())
            # if @until given, use the first @expect as the sentinel when @until has no value
            resp = clean(read_response(port, d["wait"], until=d["until"]))

        ok = all(e.lower() in resp.lower() for e in d["expect"]) and \
             not any(e.lower() in resp.lower() for e in d["expect_not"])
        if not ok:
            failures += 1
        steps.append({"dongle": dongle, "cmd": cmd, "response": resp,
                      "expect": d["expect"], "expect_not": d["expect_not"], "ok": ok})
        status = "" if ok else "  << EXPECT FAILED"
        print(f"[{dongle}] {cmd}{status}")

    for p in ports.values():
        p.close()

    capture = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": a.script,
        "ports": {k: v for k, v in [("A", a.port_a), ("B", a.port_b)] if v},
        "sets": values,
        "failures": failures,
        "steps": steps,
    }
    if a.out:
        json.dump(capture, open(a.out, "w"), indent=1)
        print(f"\ntranscript -> {a.out}")
    if a.md:
        with open(a.md, "w") as f:
            f.write(f"<!-- captured {capture['captured_at']} from {a.script} -->\n")
            for s in steps:
                if "note" in s:
                    f.write(f"\n> {s['note']}\n")
                    continue
                f.write(f"\n**[{s['dongle']}]**\n```\n{s['response']}\n```\n")
        print(f"markdown   -> {a.md}")

    print(f"\n{len([s for s in steps if 'cmd' in s])} commands, {failures} expect failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
