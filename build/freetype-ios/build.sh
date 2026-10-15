#!/bin/bash
# Build freetype static for iOS arm64 — consumed by build/win32u-unix/build.sh
# and build/ntdll-unix/build.sh (whose dwrite override includes Wine's
# dlls/dwrite/freetype.c). Those compile against research/freetype/include
# (ft2build.h and the rest of the public tree) plus this script's generated
# build/include (freetype/config/{ftconfig.h,ftoption.h}, named first on their
# command lines), and merge build/libfreetype.a into libwin32u_unix.a (no Xcode
# project changes). The two roots' contents are verified at the end of this
# script.
#
# Source: freetype, shallow-cloned at tag VER-2-13-3 into research/freetype.
# That is Madeira's recipe (the original header here said
#   git clone --depth 1 --branch VER-2-13-3 ... research/freetype
# and research/freetype is a build tree, not tracked). The checkout is then
# verified against the pinned commit, which is the checksum step:
#
#   tag ref VER-2-13-3 -> tag OBJECT 534ad3456055ee1f65ecde3bcf22a656a31514d1
#                      -> commit     42608f77f20749dd6ddc9e0536788eaad70ea4b5
#
# (The tag is annotated: `git ls-remote --tags` prints the tag object, and a
# `git clone --branch VER-2-13-3` checks out the commit above. Verify the
# commit, never the tag-object sha.)
#
# All optional deps disabled — fonts are plain TTFs from wine/fonts/.
set -euo pipefail

BUILD_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$BUILD_DIR/../.." && pwd)"
SRC="$REPO_ROOT/research/freetype"

FREETYPE_TAG=VER-2-13-3
FREETYPE_COMMIT=42608f77f20749dd6ddc9e0536788eaad70ea4b5
FREETYPE_URL=https://github.com/freetype/freetype.git

if [ ! -d "$SRC/.git" ]; then
    echo "=== cloning freetype $FREETYPE_TAG ==="
    git clone --depth 1 --branch "$FREETYPE_TAG" "$FREETYPE_URL" "$SRC"
fi

GOT="$(git -C "$SRC" rev-parse HEAD)"
if [ "$GOT" != "$FREETYPE_COMMIT" ]; then
    echo "ERROR: research/freetype HEAD is $GOT, expected pinned commit $FREETYPE_COMMIT" >&2
    exit 1
fi
echo "freetype source verified at $GOT"

BUILD="$BUILD_DIR/build"
FREETYPE_LIB="$BUILD/libfreetype.a"

cmake -S "$SRC" -B "$BUILD" -G "Unix Makefiles" \
  -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 \
  -DCMAKE_OSX_SYSROOT="$(xcrun --sdk iphoneos --show-sdk-path)" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF \
  -DFT_DISABLE_ZLIB=ON -DFT_DISABLE_BZIP2=ON -DFT_DISABLE_PNG=ON \
  -DFT_DISABLE_HARFBUZZ=ON -DFT_DISABLE_BROTLI=ON \
  -DCMAKE_C_FLAGS="-fno-stack-protector"

cmake --build "$BUILD" -j8

# ---------------------------------------------------------------- artifacts
# FreeType's CMake build installs nothing, and it does NOT create
# <build>/include/ft2build.h: ft2build.h is a tracked source header. What it
# does create are the generated configuration headers under
# <build>/include/freetype/config/ (freetype/CMakeLists.txt points
# FTCONFIG_H_NAME/FTOPTION_H_NAME at ${PROJECT_BINARY_DIR}/include), and those
# are load-bearing: the consumers put <build>/include before
# research/freetype/include (build/ntdll-unix's dwrite_unixlib,
# build/win32u-unix's freetype_ios) so the ftconfig.h generated from
# builds/unix/ftconfig.h.in wins over the ANSI copy in the source tree. Verify
# both halves here, so a partial or stale cached tree is rejected by name now
# instead of as a compile failure in a later stage.
FREETYPE_CONFIG_H="$BUILD/include/freetype/config/ftconfig.h"
FREETYPE_OPTION_H="$BUILD/include/freetype/config/ftoption.h"
FREETYPE_FT2BUILD_H="$SRC/include/ft2build.h"
MISSING_REQUIRED=""
for f in "$FREETYPE_LIB" "$FREETYPE_CONFIG_H" "$FREETYPE_OPTION_H" "$FREETYPE_FT2BUILD_H"; do
    [ -e "$f" ] || MISSING_REQUIRED="$MISSING_REQUIRED $f"
done
if [ -n "$MISSING_REQUIRED" ]; then
    echo "error: the FreeType build did not produce:$MISSING_REQUIRED" >&2
    exit 1
fi
ARCHS="$(lipo -archs "$FREETYPE_LIB" 2>/dev/null || echo unknown)"
case "$ARCHS" in
    *arm64*) ;;
    *) echo "error: $FREETYPE_LIB has no arm64 slice (lipo -archs says '$ARCHS')" >&2; exit 1 ;;
esac
echo "=== freetype iOS artifacts ==="
echo "  source commit     = $GOT"
echo "  static library    = $FREETYPE_LIB ($(wc -c < "$FREETYPE_LIB" | tr -d ' ') bytes, lipo: $ARCHS)"
echo "  generated headers = $FREETYPE_CONFIG_H"
echo "                      $FREETYPE_OPTION_H (consumed with -I$BUILD/include)"
echo "  source header     = $FREETYPE_FT2BUILD_H (consumed with -I$SRC/include)"
echo "Done: $FREETYPE_LIB"
