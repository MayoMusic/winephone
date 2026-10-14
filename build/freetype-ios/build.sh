#!/bin/bash
# Build freetype static for iOS arm64 — consumed by build/win32u-unix/build.sh
# and build/ntdll-unix/build.sh (whose dwrite override includes Wine's
# dlls/dwrite/freetype.c). Those compile against these headers and merge
# build/libfreetype.a into libwin32u_unix.a (no Xcode project changes).
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

cmake -S "$SRC" -B "$BUILD_DIR/build" -G "Unix Makefiles" \
  -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 \
  -DCMAKE_OSX_SYSROOT="$(xcrun --sdk iphoneos --show-sdk-path)" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF \
  -DFT_DISABLE_ZLIB=ON -DFT_DISABLE_BZIP2=ON -DFT_DISABLE_PNG=ON \
  -DFT_DISABLE_HARFBUZZ=ON -DFT_DISABLE_BROTLI=ON \
  -DCMAKE_C_FLAGS="-fno-stack-protector"

cmake --build "$BUILD_DIR/build" -j8
echo "Done: $BUILD_DIR/build/libfreetype.a"
