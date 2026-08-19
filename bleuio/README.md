# BleuIO automation

Code for the Novel Bits "Automate your Bluetooth LE testing" blog series. A
[BleuIO](https://www.bleuio.com/) is a USB Bluetooth LE dongle driven by AT commands over a
serial port, which makes it a fast, scriptable, deterministic test peer.

> Novel Bits is a US distributor of the BleuIO dongles. You can get them at
> https://novelbits.io/bleuio/. Nothing here requires buying from us; any BleuIO works.

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
  with `@expect` assertions, and exit nonzero on a miss (so it works as a CI test):
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
