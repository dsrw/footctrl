# footctrl

Custom firmware patch for the **original M-VAVE Chocolate** MIDI foot controller (USB/firmware name
"FootCtrl", JieLi AC636N; not the Chocolate Plus). It adds **state feedback**: apps like Loopy Pro send a CC
back when a control changes, and the pedal shows it on its 2-digit display.

## What it does

In **Manufacturer Control** mode (CubeSuite), the four switches send fixed CCs on channel 1, 127 on press and
0 on release (stock behaviour):

| Switch | Sends | Lit by incoming CC (value >= 64 = on, < 64 = off) | Segment |
|---|---|---|---|
| 1 | CC 20 | CC 20, channel 1 | upper-left of the left digit |
| 2 | CC 21 | CC 21, channel 1 | upper-right of the left digit |
| 3 | CC 22 | CC 22, channel 1 | upper-left of the right digit |
| 4 | CC 23 | CC 23, channel 1 | upper-right of the right digit |

The expression jack sends CC 7. The mode starts with a blank display; presses don't change the display, only
incoming CCs do. Other modes behave as stock.

Feedback is received over **USB MIDI** only (for now). The switches still send over USB and Bluetooth.

Built from stock firmware 051. Tested over USB with Loopy Pro on iOS and from macOS.

## Build

You need:
- Python 3.
- The stock firmware `FootCtrl_051.fwsc` from M-VAVE: <https://www.cuvave.com/download.html>
  (FootCtrl, Mobile Firmware). The build checks its SHA-256.
- `fwsctool.py` from [dtnprt/chocolate-plus-re](https://github.com/dtnprt/chocolate-plus-re) (`firmware/`), for
  the `.fwsc` container, cipher and CRCs. It is not included here.

```
git clone https://github.com/dtnprt/chocolate-plus-re
python3 -I build.py FootCtrl_051.fwsc --tools chocolate-plus-re/firmware
# -> FootCtrl_101.fwsc
```

`python3 -I build.py FootCtrl_051.fwsc stock --tools ...` rebuilds the stock file unchanged (a byte-identical
check of the pipeline).

The patch bytes are embedded in `build.py`. To change the patch, edit `src/feedback.s` / `src/feedback.ld`,
assemble with JieLi's Linux toolchain (`tools/asm.sh`; x86-64 Linux, e.g. a VM), copy the new bytes into
`build.py` and check them with `python3 -I build.py --check-elf src/feedback.elf`.
`tools/mkelf.py` wraps a decrypted app area in an ELF so JieLi's `objdump` can disassemble it.

## Flash

1. Install **SincoOTA** (M-VAVE, iOS/Android).
2. Copy `FootCtrl_101.fwsc` to the phone (keep the file name; SincoOTA uses it to decode the header).
3. Flash it over Bluetooth with SincoOTA. If the app hangs on "connect back to the device" while the pedal shows
   a dim "-", give it time, or restart the app and Bluetooth; the pedal is in its update loader.
4. Updating resets the pedal's settings. In CubeSuite, select **Manufacturer Control**.

**Back to stock:** flash the original `FootCtrl_051.fwsc` with SincoOTA the same way.

Use at your own risk. This is not affiliated with or endorsed by M-VAVE / Cuvave.

## How it works

- A hook replaces the call from the USB MIDI OUT endpoint handler into the packet parser (`0x1e102e8`).
  In Manufacturer Control mode it scans the USB-MIDI packets for CC 20-23 on channel 1, sets or clears the
  segment bits in the display buffer, then runs the original parser.
- Code space: 38 bytes of unused padding after the data-init image, plus 58 bytes freed by pointing two mode
  start-screen table entries at byte-identical copies (modes 9 -> 7, 11 -> 1) and moving mode 10's start
  screen.
- Manufacturer Control's start screen ("CU") is blanked.
- The version reply becomes `FootCtrl_101`.

Details: [docs/firmware-051.md](docs/firmware-051.md).

## Credits

- [dtnprt/chocolate-plus-re](https://github.com/dtnprt/chocolate-plus-re): `.fwsc`/`.ufw` format, cipher, CRCs
  and the CubeSuite protocol, from the Chocolate Plus work.
- JieLi's pi32v2 toolchain for the disassembly and assembler.

## License

MIT for the code and notes in this repository (see LICENSE). M-VAVE's firmware is not included and remains
theirs.
