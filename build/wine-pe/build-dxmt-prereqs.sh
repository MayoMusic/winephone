#!/bin/bash
# Build the Wine PE-side artefacts that DXMT's winemetal meson.build resolves
# out of wine_build_path.
#
# Run 38836941062 failed in dxmt-pe-configure with two symptoms that share one
# cause:
#   dxmt/src/winemetal/meson.build:18:20: ERROR: C shared or static library
#     'winecrt0' not found
#   meson-private/tmp*/testfile.cpp:2:2: error: not arm64ec
#
# dxmt/meson.build:32-38 decides is_arm64ec by compiling
#   #if !defined(__arm64ec__) && !defined(_M_ARM64EC)
#   #error not arm64ec
#   #endif
# and only a true ARM64EC compiler defines those macros, so it is the compiler
# in the cross file that fails. scripts/build-ipa.sh was passing
# dxmt/build-aarch64-win.txt, which selects aarch64-w64-mingw32-clang. With
# is_arm64ec false, meson.build:247-260 picks windows_builtin_install_dir =
# 'aarch64-windows' instead of 'arm64ec-windows', so every find_library() below
# searched a directory the ARM64EC Wine tree never populates. The build-ipa.sh
# change to build-arm64ec-win.txt plus -Dwine_build_path=../../wine/build-arm64ec
# is what fixes that; this script supplies the files it then looks for.
#
# winemetal/meson.build:18-25 needs, under wine_build_path:
#   libs/winecrt0/<install-dir>/libwinecrt0.a   (configure.ac:3522 puts the
#       library at libs/winecrt0; there is no dlls/winecrt0 at this pin)
#   dlls/ntdll/<install-dir>/libntdll.a          (built by build-ntdll.sh)
#   dlls/dbghelp/<install-dir>/libdbghelp.a
#   tools/winebuild/winebuild
# Build the DLL by file target, not "make -C dlls/<name>", for the same reason
# build-modules.sh does it: the directory target also tries the module's .so.
set -euo pipefail

R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TC="$R/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
export PATH="$TC:$PATH"
B="$R/wine/build-arm64ec"

if [ ! -f "$B/config.status" ]; then
    mkdir -p "$B" && cd "$B" && ../configure --enable-archs=arm64ec --without-x --disable-tests --enable-winegstreamer
fi

JOBS="$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"
INSTALL_DIR=arm64ec-windows

echo "=== winebuild (winemetal/meson.build:25 needs the binary) ==="
make -C "$B" -j"$JOBS" tools/winebuild

echo "=== winecrt0 (winemetal/meson.build:18-20) ==="
make -C "$B" -j"$JOBS" libs/winecrt0

echo "=== dbghelp (winemetal/meson.build:24) ==="
# The import library is a separate make target from the DLL and is not a
# prerequisite of it, so building only the DLL file target links fine and still
# leaves no libdbghelp.a - which is what run 38838887708 did.
#
# Do not guess the archive's target name. Wine 11 generates its makefiles with
# tools/makedep (configure.ac:2435, "creating Makefile rules..."), so there is
# no template to read a target name from: "dlls/dbghelp/libdbghelp.a" is not a
# rule and run 38840357642 failed with "No rule to make target". The module
# *directory* target is known to exist - docs/BUILDING.md and
# build/wine-pe/build-modules.sh both use "make -C dlls/<name>" - so build that
# to let Wine produce the import library itself.
make -C "$B" -j"$JOBS" "dlls/dbghelp/$INSTALL_DIR/dbghelp.dll"
if [ ! -f "$B/dlls/dbghelp/$INSTALL_DIR/libdbghelp.a" ]; then
    make -C "$B" -j"$JOBS" dlls/dbghelp
fi
# Still absent after the directory target too (run 38841949430). The reason is
# Wine's, not ours: a PE module's import library is only built when some other
# module links against it. libntdll.a exists because every module links ntdll;
# nothing links dbghelp, so its archive is never produced - which is why the
# directory target did not create it either.
#
# So ask winebuild for it directly. tools/winebuild/main.c:233 has
# LONG_OPT_IMPLIB, and wine/dlls/dbghelp/dbghelp.spec is the export list, so this
# is the same tool and the same spec the build would have used - it just does not
# depend on a generated make target name, which makedep does not expose.
WB="$B/tools/winebuild/winebuild"
SPEC="$B/dlls/dbghelp/dbghelp.spec"
if [ ! -f "$B/dlls/dbghelp/$INSTALL_DIR/libdbghelp.a" ] && [ -x "$WB" ] && [ -f "$SPEC" ]; then
    "$WB" --dll-name dbghelp --implib \
        -o "$B/dlls/dbghelp/$INSTALL_DIR/libdbghelp.a" "$SPEC"
    echo "  winebuild --implib wrote libdbghelp.a"
fi
# winemetal/meson.build:24 searches only
# join_paths(wine_build_path, 'dlls/dbghelp', windows_builtin_install_dir), so
# put the archive where meson will look rather than changing dxmt.
if [ ! -f "$B/dlls/dbghelp/$INSTALL_DIR/libdbghelp.a" ]; then
    cand=$(find "$B/dlls/dbghelp" -maxdepth 2 -name 'libdbghelp.a' | head -n 1)
    if [ -n "$cand" ]; then
        cp "$cand" "$B/dlls/dbghelp/$INSTALL_DIR/libdbghelp.a"
        echo "  placed libdbghelp.a from $cand into $INSTALL_DIR"
    fi
fi

echo "=== resolving what winemetal/meson.build will look for ==="
missing=0
for f in \
    "libs/winecrt0/$INSTALL_DIR/libwinecrt0.a" \
    "dlls/ntdll/$INSTALL_DIR/libntdll.a" \
    "dlls/dbghelp/$INSTALL_DIR/libdbghelp.a" \
    "tools/winebuild/winebuild"
do
    if [ -f "$B/$f" ]; then
        printf '  present  %10s bytes  %s\n' "$(wc -c < "$B/$f" | tr -d ' ')" "$f"
    else
        printf '  MISSING  %s\n' "$f"
        missing=$((missing+1))
    fi
done
if [ "$missing" -ne 0 ]; then
    echo "error: $missing prerequisite(s) absent; winemetal cannot configure" >&2
    exit 1
fi
echo "Wine PE prerequisites complete for $INSTALL_DIR."