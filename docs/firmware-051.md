# FootCtrl 051 firmware notes

Notes on the stock M-VAVE Chocolate (original, non-Plus) firmware `FootCtrl_051.fwsc`
(SHA-256 `b0ab5dbfa8630e0fb7acca238f83cb1110750c2b69d1c33e8ad3871fa72e39c1`). Addresses are virtual addresses;
app-area offset 0 = `0x01e00000`, code starts at `0x01e00120`.

## Hardware / USB
- MCU: JieLi AC636N (pi32v2 core). The `.ufw` header says `chip=AC636N`, the same as the Chocolate Plus.
- USB: `4353:4B4D`, manufacturer "Jieli Technology", product "SINCO", full speed.
  - Interface 0: HID (keyboard, mouse, consumer, digitizer; used by the page-turner modes).
  - Interfaces 1/2: class-compliant USB MIDI, bulk IN `0x84` / OUT `0x04`.
- BLE GATT: BLE-MIDI characteristic value handle `0x0072`; Sinco control `ae41` = `0x0062`; JieLi OTA `ae01` = `0x0082`.

## Image layout
- `.fwsc` = Sinco wrapper around a JieLi `.ufw` (see `fwsctool.py` in dtnprt/chocolate-plus-re).
- Members: `flash.bin`, `isd_config.ini`, `ota.bin`, `script.ver`, `flash2.bin`, `blimit.bin`, `tail.bin`.
  `flash.bin` and `flash2.bin` hold the same app code; only their area-head CRCs differ.
- App area = `member_decrypt(flash.bin[0x1000:], key=0x180f, pos=0x20000)`; `app.bin` at `0x120`, length `0x23d1c`.
- Startup copies the data-init images `0x1e21a74`(0xd5c) -> RAM `0x11200` and `0x1e227d0`(0x1644) -> RAM `0x15f80`.
  They end at `0x1e23e14`; the 40 bytes of `0xff` after that (to `0x1e23e3c`) are unused.
- Name/version reply: `"FootCtrl_051"` + NULs, 27-byte slot at `0x1e16a12`. SincoOTA/CubeSuite show this.

## Display
- 2-digit 7-segment display, multiplexed by `0x1e10c16` (registered at `0x1e124fa` as a 5 ms timer).
  It drives a shift register (data GPIO 22, clock GPIO 21; digit select GPIO 17 / 23).
- Content: halfword `0x13502`; the copy actually shown is `0x13504` (blanked during blink-off).
  Blink control bytes `0x134d6`/`0x134d7`; 0 = steady.
- High byte = left digit, low byte = right digit. Bits: a=6 b=3 c=2 d=0 e=1 f=7 g=4 dp=5.
- Digit font `0x1e16784` (`cf0c5b5d9cd5d74cdfdd`, same encoding as the Chocolate Plus).
- `disp2(c0, c1, r2)` at `0x1e11106`: two ASCII characters (space, or anything not in the font, = blank).

## Switches
- The same 5 ms timer scans the 4 switches. State per switch at RAM `0x13694 + 2*i` (counter, state).
- Press = 4 consecutive "down" polls (about 15-20 ms). Release = 4 "up" polls. Long press = 200 polls (1 s).
  A+B and C+D combos are detected when both are already down (no pending window).
  There is no extra press delay like the ~95 ms in Chocolate Plus 012: in a tap test, 10/10 taps of 90-120 ms
  all arrived.
- Events go to the current mode's switch handler: `handler(index, event)`. index 0-3 = switch, 4/5 = combos,
  128 = expression jack. event 1 = press, 0 = release, 2 = long press, 3 = release after long press.

## Modes
Table at `0x1e16af4`: 12 screen-init functions, then 12 switch handlers (index = mode).
Current mode = byte `0x14a44`.

| idx | start screen | handler | notes |
|---|---|---|---|
| 0 | "1A" | 0x1e112fe | |
| 1 | "00" | 0x1e113c0 | |
| 2 | "Tu" | 0x1e114aa | |
| 3 | "N1" | 0x1e114fa | HID keyboard |
| 4 | "N2" | 0x1e11554 | HID keyboard |
| 5 | "N3" | 0x1e115ae | HID keyboard |
| 6 | "CU" | 0x1e11612 | **Manufacturer Control**: CC 20+i ch 1, 127 press / 0 release; expression -> CC 7; never draws |
| 7 | 0xcfcf "00" | 0x1e11664 | **Custom Control**: config below; "--" on press, "00" on release |
| 8 | "AD" | 0x1e11862 | |
| 9 | 0xcfcf "00" | 0x1e11ad8 | init is byte-identical to mode 7's |
| 10 | "N4" | 0x1e11b5c | |
| 11 | "00" | 0x1e11bc2 | init is identical to mode 1's (same branch target) |

The order of CubeSuite's mode list does not match these indices.

Custom Control config (RAM `0x14a44`, the CubeSuite `FootCtrl` struct): +0 mode, +1 channel (0-based),
+2+2i `usr[i]` (low byte = CC; high byte = "Visual Behavior" = toggle). Toggle states: bytes `0x13220 + i`.

## MIDI paths
- USB: EP setup `0x1e0fb70`; OUT handler `0x1e101ce` reads the FIFO, then `call 0x1e10028` at `0x1e102e8`
  (r0 = USB-MIDI packets, r1 = byte count). `0x1e10028` handles the vendor protocol (`00 59 ...`) inside SysEx
  and turns packets into MIDI bytes (running status compressed, last status at `0x13758`).
- BLE-MIDI: write callback case `handle == 0x72` -> parser `0x1e0eda2` (r0 = data, r1 = length); last status at
  `0x13768`.
- Both hand their MIDI bytes to the ring-buffer write `0x1e0ed5a(cbuf, data, len)`: USB uses cbuf `0x1374c`,
  BLE uses `0x1375c`. It then posts event 128 to the `midi_route` task. Other callers (`0x1e108d8`,
  `0x1e11e64`, `0x1e12296`) use other buffers (e.g. `0x1373c`); not yet identified.
- Send: `0x1e1089c(msg, len)`.

## Pitfalls
- Data words and rodata are reached through a base register plus offsets, so a missing absolute reference does
  not prove a constant or function is unused.
- `switch` statements use relative jump tables, so code with no visible callers can still be live.
- A firmware update resets the pedal's settings (mode and CCs must be set again in CubeSuite).
