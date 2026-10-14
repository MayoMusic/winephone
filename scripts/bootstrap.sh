#!/usr/bin/env bash
# Reproducible macOS source/toolchain bootstrap for WinePhone.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v xcodebuild >/dev/null || { echo "error: Xcode is required (run on macOS)" >&2; exit 1; }
command -v cmake >/dev/null || { echo "error: cmake is required" >&2; exit 1; }
command -v ninja >/dev/null || { echo "error: ninja is required" >&2; exit 1; }
command -v meson >/dev/null || { echo "error: meson is required" >&2; exit 1; }
command -v bison >/dev/null || { echo "error: bison 3.x is required" >&2; exit 1; }
if command -v brew >/dev/null; then
  export PATH="$(brew --prefix bison)/bin:$PATH"
fi
xcodebuild -downloadComponent MetalToolchain

# Fetch only runtime/build source dependencies. FEX's three binary test corpus
# submodules are deliberately excluded from the release build.
git submodule update --init --depth 1 FEX wine dxmt madeira-dock
git -C FEX submodule update --init --depth 1 \
  External/vixl External/fmt External/range-v3 External/rpmalloc \
  External/unordered_dense External/xxhash External/jemalloc_glibc \
  Source/Common/cpp-optparse
git -C dxmt submodule update --init --depth 1 external/nvapi include/native/directx

LLVM_MINGW_VERSION=20260421
LLVM_MINGW_ARCHIVE="llvm-mingw-${LLVM_MINGW_VERSION}-ucrt-macos-universal.tar.xz"
LLVM_MINGW_SHA256=bd85a3975723815cef28dbbd2ca2cb0c926f6b348a12a0453f39f7af273cb3f7
TOOLCHAIN="$ROOT/toolchains/llvm-mingw-${LLVM_MINGW_VERSION}-ucrt-macos-universal"
if [[ ! -x "$TOOLCHAIN/bin/arm64ec-w64-mingw32-clang" ]]; then
  DOWNLOAD_TMP="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
  mkdir -p "$ROOT/toolchains" "$DOWNLOAD_TMP/winephone-downloads"
  ARCHIVE="$DOWNLOAD_TMP/winephone-downloads/$LLVM_MINGW_ARCHIVE"
  curl --fail --location --retry 3 \
    "https://github.com/mstorsjo/llvm-mingw/releases/download/${LLVM_MINGW_VERSION}/${LLVM_MINGW_ARCHIVE}" \
    --output "$ARCHIVE"
  echo "$LLVM_MINGW_SHA256  $ARCHIVE" | shasum -a 256 --check
  tar -xJf "$ARCHIVE" -C "$ROOT/toolchains"
fi
export PATH="$TOOLCHAIN/bin:$PATH"

# Madeira's DXMT unix build requires LLVM 15 built for iOS plus a host
# llvm-tblgen. The pin and one small Apple-linker compatibility edit are
# documented in docs/BUILDING.md. Cache the build directories between CI runs.
LLVM_PIN=8dfdcc7b7bf66834a761bd8de445840ef68e4d1a
if [[ ! -d "$ROOT/toolchains/llvm-project/.git" ]]; then
  git clone --filter=blob:none --no-checkout \
    https://github.com/llvm/llvm-project.git "$ROOT/toolchains/llvm-project"
fi
git -C "$ROOT/toolchains/llvm-project" fetch --depth 1 origin "$LLVM_PIN"
git -C "$ROOT/toolchains/llvm-project" checkout --detach FETCH_HEAD
LLVM_SRC="$ROOT/toolchains/llvm-project/llvm"
if ! grep -q 'if(\${CMAKE_SYSTEM_NAME} MATCHES "Darwin|iOS")' "$LLVM_SRC/cmake/modules/AddLLVM.cmake"; then
  python3 - "$LLVM_SRC/cmake/modules/AddLLVM.cmake" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old = 'if(NOT LLVM_NO_DEAD_STRIP)\n      if(${CMAKE_SYSTEM_NAME} MATCHES "Darwin")'
new = 'if(NOT LLVM_NO_DEAD_STRIP)\n      if(${CMAKE_SYSTEM_NAME} MATCHES "Darwin|iOS")'
assert s.count(old) == 1, "unexpected pinned LLVM dead-strip block"
p.write_text(s.replace(old, new))
PY
fi

cmake -S "$LLVM_SRC" -B "$ROOT/toolchains/llvm-host-build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD=Native \
  -DLLVM_BUILD_TOOLS=ON -DLLVM_INCLUDE_TESTS=OFF -DLLVM_ENABLE_PROJECTS=""
cmake --build "$ROOT/toolchains/llvm-host-build" --target llvm-tblgen --parallel 3

cmake -S "$LLVM_SRC" -B "$ROOT/toolchains/llvm-ios-build" -G Ninja \
  -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_HOST_TRIPLE=arm64-apple-ios17.0 \
  -DLLVM_DEFAULT_TARGET_TRIPLE=arm64-apple-ios17.0 -DLLVM_TARGET_ARCH=host \
  -DLLVM_TARGETS_TO_BUILD="" -DLLVM_ENABLE_PROJECTS="" \
  -DLLVM_BUILD_TOOLS=OFF -DLLVM_BUILD_UTILS=OFF \
  -DLLVM_INCLUDE_TESTS=OFF -DLLVM_ENABLE_ZLIB=OFF \
  -DLLVM_TABLEGEN="$ROOT/toolchains/llvm-host-build/bin/llvm-tblgen"
cmake --build "$ROOT/toolchains/llvm-ios-build" --parallel 3

echo "Bootstrap complete. Toolchain archive SHA-256 verified; LLVM source is pinned at $LLVM_PIN."

