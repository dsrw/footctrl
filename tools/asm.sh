#!/bin/bash
# Assemble src/<name>.s with JieLi's pi32v2 toolchain (Linux x86_64; https://pkgman.jieliapp.com/s/linux-toolchain)
# and print the disassembly. Usage: tools/asm.sh [name]   (default: feedback)
#   JL_TOOLCHAIN = toolchain root (default ~/jltc/jieli-linux-toolchains-20260730.1)
set -e
NAME=${1:-feedback}
TC="${JL_TOOLCHAIN:-$HOME/jltc/jieli-linux-toolchains-20260730.1}/pi32v2/bin"
cd "$(dirname "$0")/../src"
"$TC/clang" -target pi32v2 -c "$NAME.s" -o "/tmp/$NAME.o"
"$TC/ld" -T "$NAME.ld" "/tmp/$NAME.o" -o "$NAME.elf"
"$TC/objdump" -d -print-imm-hex "$NAME.elf"
"$TC/objdump" -h "$NAME.elf"
