#!/bin/bash
# Configure the Wine macOS host tree, wine/build-macos.
#
# Every unix-side stage compiles against this tree, not against Wine's source
# tree: build/ntdll-unix/build.sh:7,34 and build/win32u-unix/build.sh:12 read
#   -include "$WINE_BUILD/include/config.h"
# and the widl-generated headers under "$WINE_BUILD/include"; build/wineserver/
# build.sh adds -I"$WINE_SRC/build-macos/include"; DXMT and build/d3d11-triangle
# read its tools/winebuild/winebuild (build/d3d11-triangle/build.sh:50,
# tests/dxmt/build.sh:21) and its aarch64-windows import libs
# (dxmt/src/winemetal/meson.build:19-25).
#
# Madeira treats this tree as a pre-existing, out-of-band build ("Wine
# aarch64-windows static libs already built in wine/build-macos/" —
# build/dxmt-ios/README.md:47-49; "a configured Wine build tree whose include/
# holds config.h and the widl-generated headers; default: wine/build-macos" —
# tests/host/check-wma-decoder.py:25-27). No script in the repository ever
# created it, and the WinePhone pipeline never did either, so every
# compile_one/compile_unixlib in build/ntdll-unix/build.sh failed instantly on
# the missing -include config.h while wg_parser_apple_ios (the one translation
# unit that passes no Wine include) compiled. This stage creates it.
#
# Flags follow the sibling Wine tree scripts, whose conventions are recorded:
#   build/wine-pe/build-ntdll.sh:18  --enable-archs=arm64ec --without-x --disable-tests --enable-winegstreamer
#   build/wine-i386/build.sh:49      --enable-archs=i386   --without-x --without-vulkan --without-freetype --without-gnutls --disable-tests --enable-winegstreamer
# and docs/WOW64.md:288-290 records the aarch64 tree as
#   "--enable-archs=aarch64".
# The exact flags Madeira's development machine used for build-macos are NOT
# recorded anywhere in the tree (UNVERIFIED); if configure fails, the log shows
# which option the runner rejects.
set -eu

R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$R/wine/build-macos"
TC="$R/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"

# --enable-archs needs an arm64 Windows cross compiler on PATH for the PE half
# (Wine looks for aarch64-w64-mingw32-gcc; llvm-mingw ships it).
if [ -x "$TC/aarch64-w64-mingw32-clang" ]; then
    export PATH="$TC:$PATH"
fi

if [ -f "$B/config.status" ]; then
    echo "wine/build-macos is already configured."
    exit 0
fi

mkdir -p "$B"
cd "$B"
echo "=== Configure wine/build-macos (host macOS + aarch64-windows PE) ==="
"$R/wine/configure" \
    --enable-archs=aarch64 \
    --without-x \
    --disable-tests

echo "wine/build-macos configured; config.h: $(test -f "$B/include/config.h" && echo present || echo MISSING)"
