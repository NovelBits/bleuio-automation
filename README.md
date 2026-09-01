# BleuIO automation

Runnable code for the Novel Bits blog series **Automate your Bluetooth LE testing**. A
[BleuIO](https://www.bleuio.com/) is a USB Bluetooth LE dongle driven by AT commands over a
serial port, which makes it a fast, scriptable, deterministic test peer. Clone this, plug in a
dongle or two, and run the same sequences the posts walk through.

> Novel Bits is a US distributor of the BleuIO dongles. You can get them at
> https://novelbits.io/bleuio/. Nothing here requires buying from us; any BleuIO works.

## Posts in this series

<!-- Add each post's URL here as it publishes. Keep the order the series is meant to be read. -->

| # | Post | Example script |
|---|------|----------------|
| 1 | Testing a Bluetooth LE device without a phone | [`examples/01-scan-advertise-connect.txt`](examples/01-scan-advertise-connect.txt) |
| 2 | A scripted Bluetooth LE test: connect, exchange data, verify | [`examples/02-sps-data-exchange.txt`](examples/02-sps-data-exchange.txt) |
| 3 | An AI agent just ran my Bluetooth LE test | (uses the runner + example 01) |
| 4 | CI for Bluetooth LE: a regression rig on every build | [`examples/03-pairing-bonding-reset.txt`](examples/03-pairing-bonding-reset.txt) |
| 6 | Your Bluetooth LE tests aren't flaky. The stack under them is. | (uses the runner + example 01) |
| 7 | Resetting Bluetooth LE state between tests | [`examples/03-pairing-bonding-reset.txt`](examples/03-pairing-bonding-reset.txt) |
| 8 | A programmable peer in a handful of AT commands | [`examples/04-custom-service.txt`](examples/04-custom-service.txt) |

Post links will be filled in as each one publishes.

## Requirements

- One or two BleuIO dongles (two lets you script both ends of a link).
- Python 3.8+ and `pyserial`:  `pip3 install pyserial`

## Files

- **`bleuio.py`** — find the dongle and send one AT command. Start here.
  ```
  python3 bleuio.py find --all              # list connected BleuIO ports
  python3 bleuio.py info                     # ATI: firmware, role, status
  python3 bleuio.py cmd "AT+GETMAC"          # send any command
  ```
- **`run-session.py`** — run an annotated multi-command script against one or two dongles,
  with `@expect` assertions, exiting nonzero on a miss (so it works as a CI test):
  ```
  python3 run-session.py examples/01-scan-advertise-connect.txt \
      --port-a /dev/cu.usbmodemAAAA --port-b /dev/cu.usbmodemBBBB
  ```
  Script format (one command per line; `#` comments and blank lines ignored):
  ```
  [A] AT+GAPSCAN=5 @wait 6.5 @expect SCAN COMPLETE   # [A]/[B] pick the dongle
  [B] AT+ADVSTART @expect ADVERTISING                 # @expect fails the step if absent
  [A] AT+SPSSEND=hi @expect_not ERROR                 # @expect_not fails if present
  [A] @read 1.5 @expect hello                          # read async data (notifications)
  [A] AT+GATTCREAD=0026 @wait 6 @until Value read      # read until a substring lands
  @pause 2                                              # sleep between commands
  @note anything                                        # recorded in the transcript
  ```
- **`examples/`** — session scripts from the blog posts. Each uses a `<PERIPHERAL_MAC>`
  placeholder: get your peripheral dongle's address with `AT+GETMAC` and substitute it.

## A note on handles

Attribute handles like `000D` or `0026` in the examples are positions in a specific firmware's
GATT table (captured on 2.7.9.78). On other firmware, confirm them with `AT+GETSERVICES`.

## License

MIT. See [LICENSE](LICENSE). "BleuIO" is a product of Smart Sensor Devices; other product names
referenced in code comments belong to their respective owners.

## Sweeping a parameter

`--set KEY=VALUE` substitutes `{{KEY}}` anywhere in a script. It is repeatable, and the values are
recorded in the JSON transcript so a sweep's captures identify themselves.

```bash
for ci in 30 50 100 200; do
  python3 run-session.py examples/06-connection-interval-sweep.txt \
    --port-a "$A" --port-b "$B" \
    --set MAC=40:48:FD:EA:E4:88 --set CI=$ci \
    --out cap-ci${ci}ms.json
done
```

The loop stays in your shell rather than in the runner. One run is one transcript, which is the
granularity you want for comparing timing cases, and it drops into a CI matrix unchanged.

Two things are errors rather than warnings, because both otherwise fail silently: a `{{KEY}}` with no
`--set`, which would send the literal text to the dongle, and a `--set` the script never uses, which
would sweep the same value N times while looking like it worked.

**Which side you are on decides what you can sweep.** The central picks the connection interval from
the range it requests, so a connection-timing sweep has to run from the central. Advertising interval
is set by whichever side is advertising.

**`AT+CONNPARAM` takes milliseconds** (7.5 to 4000) and is set on the central while disconnected; the
parameters apply to the next connection. Its readback reports 1.25 ms units instead, so a request of
30 ms comes back as 24. That asymmetry is the thing people trip over.
