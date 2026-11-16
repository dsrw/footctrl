"""Wrap a raw pi32v2 code blob as a minimal ELF32 (ET_EXEC, e_machine 0xF1) for JieLi objdump."""
import struct, sys
src, dst, base, skip = sys.argv[1], sys.argv[2], int(sys.argv[3], 0), int(sys.argv[4], 0)
code = open(src, 'rb').read()[skip:]
shstr = b'\0.text\0.shstrtab\0'
ehsz, phsz, shsz = 52, 32, 40
code_off = ehsz + phsz
shstr_off = code_off + len(code)
sh_off = (shstr_off + len(shstr) + 3) & ~3
eh = b'\x7fELF\x01\x01\x01' + bytes(9) + struct.pack('<HHIIIIIHHHHHH', 2, 0xF1, 1, base + skip, ehsz, sh_off, 0, ehsz, phsz, 1, shsz, 3, 2)
ph = struct.pack('<IIIIIIII', 1, code_off, base + skip, base + skip, len(code), len(code), 5, 4)
sh = bytes(shsz)
sh += struct.pack('<IIIIIIIIII', 1, 1, 6, base + skip, code_off, len(code), 0, 0, 2, 0)
sh += struct.pack('<IIIIIIIIII', 7, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)
out = eh + ph + code + shstr
out += bytes(sh_off - len(out)) + sh
open(dst, 'wb').write(out)
