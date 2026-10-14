#!/bin/bash
# Configure (first time) and build the FEXCore static libraries the app links
# (FEX/build-ios/FEXCore/Source/*.a and External/*). Options mirror the
# development build's CMakeCache, as in Madeira's own build/fex-ios/build.sh.
#
# FEX_IOS_HOST / FEX_IOS_HOST_BUILD are NOT part of this build. They are the
# Windows-PE-module flavour of the iOS host: Madeira passes them only in
# build/fex-wow64/build.sh and build/fex-arm64ec/build.sh, and the FEX fork's
# own comment at FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:719 says
# "VirtualQuery exists only in the FEX_IOS_HOST (Windows module) builds; the
# native iOS FEXCore build (build/fex-ios) reports without the region."
# The native library gets its iOS behaviour from __APPLE__; the app target
# (app/Madeira.xcodeproj, GCC_PREPROCESSOR_DEFINITIONS = DEBUG=1) also compiles
# the FEXCore headers (AllocatorHooks.h, DualMap.h) without FEX_IOS_HOST, so
# defining it here would mismatch the app's view of those headers.
#
# Two Darwin-only deviations from Madeira's script are retained:
#   - CMAKE_SYSTEM_PROCESSOR=arm64: the runner's CMake leaves it empty for this
#     iOS cross-configuration, and FEX aborts with "Unsupported processor type .".
#   - TUNE_CPU=none: FEX's default "native" runs Scripts/aarch64_fit_native.py
#     and Scripts/NeedDisabledSVE.py against Linux /proc/cpuinfo, which does not
#     exist on macOS. Madeira's ARM64EC script sets TUNE_CPU for the same reason
#     ("FEX's default, "native", probes the build host and aborts the configure
#     on macOS").
set -eu
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$R/FEX/build-ios"
if [ ! -f "$B/CMakeCache.txt" ]; then
    cmake -S "$R/FEX" -B "$B" -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_SYSTEM_PROCESSOR=arm64 -DCMAKE_OSX_ARCHITECTURES=arm64 \
        -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 -DCMAKE_BUILD_TYPE=Release \
        -DTUNE_CPU=none \
        -DBUILD_TESTING=OFF -DBUILD_THUNKS=OFF -DBUILD_FEXCONFIG=OFF -DBUILD_FEX_LINUX_TESTS=OFF \
        -DENABLE_FEX_ALLOCATOR=OFF -DENABLE_ASSERTIONS=OFF -DENABLE_CLANG_THUNKS=ON -DENABLE_CCACHE=ON
fi
# -k + the sorted summary make one runner execution report every independent
# compile error instead of only the first.
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
