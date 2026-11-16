#!/usr/bin/env python3
"""
Build patched firmware for the original M-VAVE Chocolate (FootCtrl, JieLi AC636N) from the stock
M-VAVE firmware FootCtrl_051.fwsc.

    python3 -I build.py FootCtrl_051.fwsc [variant] [-o outdir] [--version NNN] [--tools DIR]

Variants:
    feedback  (default) Manufacturer Control mode lights a top display segment per switch when the matching
              CC (20-23, channel 1) comes back over USB MIDI. See README.md.
    stock     rebuild with no patches; the output must be byte-identical to the input (checks the pipeline)
    segtest   diagnostic: Custom Control mode starts with test segments (0x0880) instead of "00"

The container/cipher/CRC helpers come from fwsctool.py in https://github.com/dtnprt/chocolate-plus-re
(firmware/fwsctool.py). Pass its folder with --tools or $FWSCTOOL_DIR.

--check-elf FILE compares the embedded patch bytes with an assembled ELF (see tools/asm.sh).
"""
import sys, os, struct, hashlib, argparse

STOCK_SHA256 = 'b0ab5dbfa8630e0fb7acca238f83cb1110750c2b69d1c33e8ad3871fa72e39c1'   # FootCtrl_051.fwsc, 488020 B
STOCK_URL = 'https://www.cuvave.com/download.html  (FootCtrl, Mobile Firmware, FootCtrl_051)'
KEY, POS, UBOOT, VBASE = 0x180f, 0x20000, 0x1000, 0x01e00000   # app-area cipher params, uboot header, vaddr base
IDENT_ADDR, IDENT_SLOT = 0x1e16a12, 27                          # "FootCtrl_051" + NULs: name/version reply

DEFAULT_VERSION = {'stock': 51, 'feedback': 101, 'segtest': 901}

def a(v): return v - VBASE

# (vaddr, stock bytes, new bytes, ELF section)
VARIANTS = {
    'stock': [],
    'segtest': [
        (0x1e11cd2, bytes.fromhex('c1ffcfcf0000'), bytes.fromhex('c1ff80080000'), None),  # mode 7 init: r1 = 0x0880
    ],
    # src/feedback.s + src/feedback.ld
    'feedback': [
        (0x1e102e8, bytes.fromhex('bfea9efe'), bytes.fromhex('80ea949d'), '.hook'),
        (0x1e11cc2, bytes.fromhex('50235135'), bytes.fromhex('48204920'), '.m6init'),
        (0x1e11cf2,
         bytes.fromhex('c0ffc0340100c1ffcfcf000050ed0314412052ee061152ee07118000'
                       '502e49344220ffeaf7f9c0ff2432010041208940483049304220ffeaedf9'),
         bytes.fromhex('07e91460684169426a436e8490f8f861f92c01f9f50911a260e0000c'
                       '901a3960011902f901800919b960f78ac0ea8690502e49344220ffeaedf9'), '.cave_r'),
        (0x1e23e14, b'\xff' * 38,
         bytes.fromhex('77040415c3ff02350100c0ff444a010008404616571d00f8040c40'
                       '153704ffeaf960ffea5c6f'), '.cave_a'),
        (0x1e16b18, bytes.fromhex('f21ce1010e1de101181de101'), bytes.fromhex('cc1ce101221de101861ce101'), '.tbl'),
    ],
}

def rebuild_area_crcs(d, crc16):
    """app.bin entry @0x20, area head @0x00 (both: u16 head_crc, u16 data_crc, u32 addr, u32 len ...)."""
    app_addr, app_len = struct.unpack_from('<II', d, 0x24)
    struct.pack_into('<H', d, 0x22, crc16(d[app_addr:app_addr + app_len]))
    struct.pack_into('<H', d, 0x20, crc16(d[0x22:0x40]))
    area_len = struct.unpack_from('<I', d, 0x08)[0]
    struct.pack_into('<H', d, 0x02, crc16(d[0x20:area_len]))
    struct.pack_into('<H', d, 0x00, crc16(d[0x02:0x20]))

def elf_sections(path):
    e = open(path, 'rb').read()
    shoff, = struct.unpack_from('<I', e, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', e, 0x2e)
    sh = [struct.unpack_from('<IIIIIIIIII', e, shoff + i * shentsize) for i in range(shnum)]
    names = e[sh[shstrndx][4]:sh[shstrndx][4] + sh[shstrndx][5]]
    out = {}
    for s in sh:
        name = names[s[0]:names.index(b'\0', s[0])].decode()
        if s[1] == 1 and s[3]:                       # PROGBITS with an address
            out[name] = (s[3], e[s[4]:s[4] + s[5]])
    return out

def check_elf(variant, path):
    secs = elf_sections(path)
    ok = True
    for vaddr, _, new, sec in VARIANTS[variant]:
        if sec is None: continue
        addr, data = secs[sec]
        same = (addr == vaddr and data == new)
        ok &= same
        print(f'{sec:8s} {vaddr:#x} {"OK" if same else "DIFFERS"}')
    return ok

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stock', nargs='?')
    ap.add_argument('variant', nargs='?', default='feedback', choices=sorted(VARIANTS))
    ap.add_argument('-o', '--out', default='.')
    ap.add_argument('--version', type=int)
    ap.add_argument('--tools', default=os.environ.get('FWSCTOOL_DIR'))
    ap.add_argument('--check-elf')
    args = ap.parse_args()

    if args.check_elf:
        sys.exit(0 if check_elf(args.variant, args.check_elf) else 1)
    if not args.stock:
        ap.error('the stock FootCtrl_051.fwsc is required')
    if not args.tools or not os.path.isfile(os.path.join(args.tools, 'fwsctool.py')):
        sys.exit('fwsctool.py not found: pass --tools <chocolate-plus-re/firmware> or set $FWSCTOOL_DIR')
    sys.path.insert(0, args.tools)
    from fwsctool import xcode_block, crc16, member_decrypt, fwsc_wrap, fwsc_unwrap, fix_header_crc, decode_header

    raw = open(args.stock, 'rb').read()
    if hashlib.sha256(raw).hexdigest() != STOCK_SHA256:
        sys.exit(f'{args.stock} is not the stock FootCtrl_051.fwsc (SHA-256 mismatch).\nDownload: {STOCK_URL}')
    ufw = bytearray(fwsc_unwrap(raw, ''))
    assert fwsc_wrap(bytes(ufw), 'FootCtrl', 51) == raw, 'fwsc round-trip failed'

    version = args.version if args.version is not None else DEFAULT_VERSION[args.variant]
    assert 0 <= version <= 999
    patches = [(v, o, n) for v, o, n, _ in VARIANTS[args.variant]]
    if version != 51:
        patches.append((IDENT_ADDR, b'FootCtrl_051'.ljust(IDENT_SLOT, b'\0'),
                        f'FootCtrl_{version:03d}'.encode().ljust(IDENT_SLOT, b'\0')))

    count = decode_header(ufw)['count']
    def rd(i): return bytearray(xcode_block(bytes(ufw[0x40 + i * 0x50:0x40 + (i + 1) * 0x50])))
    def wr(i, e): ufw[0x40 + i * 0x50:0x40 + (i + 1) * 0x50] = xcode_block(bytes(e))
    done = set()
    for i in range(count):
        e = rd(i)
        name = bytes(e[0x40:0x50]).split(b'\0')[0]
        if name not in (b'flash.bin', b'flash2.bin'):      # two copies of the app (both get the same patches)
            continue
        off, size = struct.unpack_from('<II', e, 0x08)
        member = bytes(ufw[off:off + size])
        assert struct.unpack_from('<H', e, 4)[0] == crc16(member), f'{name}: stock chunk CRC mismatch'
        d = bytearray(member_decrypt(member[UBOOT:], KEY, POS))
        assert d[0x30:0x37] == b'app.bin', 'unexpected app-area layout'
        t = bytearray(d); rebuild_area_crcs(t, crc16)
        assert t == d, 'CRC chain self-test failed'
        for vaddr, old, new in patches:
            o = a(vaddr)
            assert len(old) == len(new), f'{vaddr:#x}: length mismatch'
            assert d[o:o + len(old)] == old, f'{vaddr:#x}: unexpected stock bytes {d[o:o + len(old)].hex()}'
            d[o:o + len(new)] = new
        rebuild_area_crcs(d, crc16)
        new_member = member[:UBOOT] + member_decrypt(bytes(d), KEY, POS)
        assert len(new_member) == len(member)
        ufw[off:off + size] = new_member
        struct.pack_into('<H', e, 4, crc16(new_member)); wr(i, e)
        done.add(name)
    assert done == {b'flash.bin', b'flash2.bin'}, done
    ufw = fix_header_crc(bytes(ufw))
    h = decode_header(ufw)
    assert h['stored_crc'] == h['calc_crc']
    out = fwsc_wrap(ufw, 'FootCtrl', version)
    os.makedirs(args.out, exist_ok=True)
    # SincoOTA descrambles the metadata using the file name, so it must stay FootCtrl_NNN.fwsc
    path = os.path.join(args.out, f'FootCtrl_{version:03d}.fwsc')
    open(path, 'wb').write(out)
    print(f'{args.variant}: wrote {path}  sha256={hashlib.sha256(out).hexdigest()}')
    if args.variant == 'stock' and version == 51:
        print('identical to the stock input:', out == raw)

if __name__ == '__main__':
    main()
