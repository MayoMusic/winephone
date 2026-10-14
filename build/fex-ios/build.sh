#!/bin/bash
# Configure (first time) and build the FEXCore static libraries the app links
# (FEX/build-ios/FEXCore/Source/*.a and External/*). Options mirror the
# development build's CMakeCache.
set -eu
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$R/FEX/build-ios"
PATCH="$R/patches/fex-darwin.patch"
# Keep iOS adaptations as a reviewable WinePhone patch, not edits to the FEX
# submodule checkout. The reverse check makes a repeated local build harmless.
if ! git -C "$R/FEX" apply --reverse --check "$PATCH" >/dev/null 2>&1; then
    git -C "$R/FEX" apply --check "$PATCH"
    git -C "$R/FEX" apply "$PATCH"
fi
if [ ! -f "$B/CMakeCache.txt" ]; then
    cmake -S "$R/FEX" -B "$B" -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_SYSTEM_PROCESSOR=arm64 -DCMAKE_OSX_ARCHITECTURES=arm64 \
        -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 -DCMAKE_BUILD_TYPE=Release \
        -DFEX_IOS_HOST_BUILD=ON -DCMAKE_C_FLAGS=-DFEX_IOS_HOST -DCMAKE_CXX_FLAGS=-DFEX_IOS_HOST -DCMAKE_ASM_FLAGS=-DFEX_IOS_HOST \
        -DTUNE_CPU=none \
        -DBUILD_TESTING=OFF -DBUILD_THUNKS=OFF -DBUILD_FEXCONFIG=OFF -DBUILD_FEX_LINUX_TESTS=OFF \
        -DENABLE_FEX_ALLOCATOR=OFF -DENABLE_ASSERTIONS=OFF -DENABLE_CLANG_THUNKS=ON -DENABLE_CCACHE=ON
fi
set +e
make -k -j"$(sysctl -n hw.ncpu)" -C "$B" FEXCore FEXCore_Base 2>&1 | tee "$B/build.log"
BUILD_STATUS=${PIPESTATUS[0]}
set -e
echo "FEX compiler error summary:"
grep -E "error:" "$B/build.log" | sort | uniq -c || true
if [ "$BUILD_STATUS" -ne 0 ]; then
    exit "$BUILD_STATUS"
fi
ls "$B/FEXCore/Source/"*.a
