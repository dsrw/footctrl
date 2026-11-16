SECTIONS {
  .hook   0x1e102e8 : { *(.hook) }
  .m6init 0x1e11cc2 : { *(.m6init) }
  .cave_r 0x1e11cf2 : { *(.cave_r) }
  .cave_a 0x1e23e14 : { *(.cave_a) }
  .tbl    0x1e16b18 : { *(.tbl) }
}
usb_midi_parse = 0x1e10028;
disp2          = 0x1e11106;
