#!/bin/bash
# Prepare the Wine macOS host tree, wine/build-macos: configure it and generate
# the widl-generated public headers under its include/.
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
#
# The second half (widl-generated headers) is UNVERIFIED as well: it is the
# mechanism upstream Wine uses, applied here because the two modules that need
# those headers are compiled from this tree. Run 38651245572 never reached it —
# see the note in the widl block below.
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
else
    mkdir -p "$B"
    cd "$B"
    echo "=== Configure wine/build-macos (host macOS + aarch64-windows PE) ==="
    "$R/wine/configure" \
        --enable-archs=aarch64 \
        --without-x \
        --disable-tests

    echo "wine/build-macos configured; config.h: $(test -f "$B/include/config.h" && echo present || echo MISSING)"
fi

# ---------------------------------------------------------------- widl headers
#
# include/config.h comes from configure, but the headers generated from
# include/*.idl do not: widl is itself a build product. configure only *writes*
# the rules that produce them (wine/aclocal.m4:293 wine_fn_config_makefile, and
# wine/configure:24365 wine_fn_output_makedep, which compiles tools/makedep.c and
# runs makedep with -i on each generated Makefile), and makedep gives every
# include/*.idl a .h target in that directory's Makefile
# (wine/tools/makedep.c:2004-2009), invoking widl by its literal path
# (wine/tools/makedep.c:4914, so `make -C include` needs no top-level Makefile).
#
# Two translation units in build/ntdll-unix/build.sh need those headers and
# therefore cannot compile without this step:
#   dwrite_unixlib        wine/dlls/dwrite/dwrite_private.h:24-25 includes
#                         dwrite_3.h and d2d1.h, which exist only here (the
#                         arm64ec include dir build/ntdll-unix/build.sh:158 names
#                         is empty until *that* tree is built — wine-pe-ntdll
#                         runs after this stage in scripts/build-ipa.sh)
#   winegstreamer_unixlib wine/dlls/winegstreamer/unixlib.h:32 includes
#                         mfobjects.h
# Run 38651245572 failed these two earlier (on ft2build.h and avcodec.h), so
# this condition was not visible in that log.
#
# Best effort, deliberately: if widl or the include rules do not work as
# described, this prints what happened and carries on, because
# build/ntdll-unix/build.sh reports which headers exist and names the exact
# command line of any compile that still fails. A silent no-op here would be
# worse than a logged failure.
WIDL_HEADERS="dwrite_3.h d2d1.h mfobjects.h mftransform.h"
missing=""
for h in $WIDL_HEADERS; do
    [ -f "$B/include/$h" ] || missing="$missing $h"
done

if [ -n "$missing" ]; then
    echo "=== Generating the widl public headers (missing:$missing) ==="
    if [ ! -x "$B/tools/widl/widl" ]; then
        echo "  building tools/widl (widl is the generator; it needs bison + flex)"
        if ! make -C "$B/tools/widl" > "$B/widl-build.log" 2>&1; then
            echo "  note: make -C tools/widl failed; last lines of $B/widl-build.log:"
            tail -n 10 "$B/widl-build.log" | sed 's/^/    /'
        fi
    fi
    if ! make -C "$B/include" > "$B/widl-headers.log" 2>&1; then
        echo "  note: make -C include failed; last lines of $B/widl-headers.log:"
        tail -n 15 "$B/widl-headers.log" | sed 's/^/    /'
    fi
fi

echo "=== widl-generated public headers in $B/include ==="
for h in $WIDL_HEADERS; do
    if [ -f "$B/include/$h" ]; then
        echo "  present: $B/include/$h"
    else
        echo "  MISSING: $B/include/$h"
    fi
done
