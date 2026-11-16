// footctrl: M-VAVE Chocolate (FootCtrl 051) patch: USB MIDI-in -> display feedback in Manufacturer Control (firmware mode 6).
// Mode 6 sends fixed CC 20..23 on channel 1, momentary. An incoming CC 20+i on channel 1 lights (value >= 64)
// or clears switch i's top segment: 1 = upper-left of left digit (0x8000), 2 = upper-right of left (0x0800),
// 3 = upper-left of right digit (0x0080), 4 = upper-right of right (0x0008). Display content = h[0x13502].
//
// Space: cave A = 40 B of 0xff after the data-init image; region R = 58 B freed by pointing the mode 9 and
// mode 11 screen-init table entries at their byte-identical twins (mode 7 / mode 1) and moving mode 10's init.

    .section .hook,"ax"           // 0x1e102e8, was: call usb_midi_parse (r0 = USB-MIDI packets, r1 = bytes)
    call fb

    .section .m6init,"ax"         // 0x1e11cc2, was: r0 = 'C'; r1 = 'U' -> mode 6 starts blank
    r0 = 0x20
    r1 = 0x20

    .section .cave_a,"ax"
    .globl fb
fb:
    [--sp] = {rets, r7-r4}
    r5_r4 = r1_r0                 // keep the arguments for the tail call
    r3 = 0x13502                  // display content (hi byte = left digit, lo byte = right digit)
    r0 = 0x14a44
    r0 = b[r0+0x0] (u)            // current mode
    r6 = r4                       // packet pointer
    r7 = r5 + r4                  // end
    if (r0 == 0x6) goto L_go
L_out:
    r1_r0 = r5_r4
    {rets, r7-r4} = [sp++]
    goto usb_midi_parse
L_go:
    goto L_pkt

    .section .cave_r,"ax"
L_pkt:
    if (r6 >= r7) goto L_exit
    r0 = b[r6+0x1] (u)            // status
    r1 = b[r6+0x2] (u)            // CC
    r2 = b[r6+0x3] (u)            // value
    r6 += 0x4
    if (r0 != 0xb0) goto L_pkt    // CC, channel 1
    r1 += -0x14
    if (r1 >= 0x4) goto L_pkt     // CC 20..23 only (unsigned)
    r1 = r1 << 0x2
    r0 = 0x8000
    r0 >>= r1
    r1 = h[r3+0x0] (u)
    r1 |= r0
    if (r2 >= 0x40) goto L_st
    r1 ^= r0
L_st:
    h[r3+0x0] = r1
    goto L_pkt
L_exit:
    goto L_out
    .globl m10_init
m10_init:                         // moved, unchanged: show "N4"
    r0 = 0x4e
    r1 = 0x34
    r2 = 0x0
    goto disp2

    .section .tbl,"a"             // 0x1e16b18: screen-init entries for modes 9, 10, 11
    .long 0x1e11ccc               // mode 9 -> mode 7's identical init
    .long m10_init
    .long 0x1e11c86               // mode 11 -> mode 1's identical init
