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
echo "=== toolchain cache validation (the pinned sources above are always fetched) ==="
TOOLCHAIN="$ROOT/toolchains/llvm-mingw-${LLVM_MINGW_VERSION}-ucrt-macos-universal"
if [[ -x "$TOOLCHAIN/bin/arm64ec-w64-mingw32-clang" ]]; then
  echo "  reused: toolchains/$(basename "$TOOLCHAIN") ($("$TOOLCHAIN/bin/arm64ec-w64-mingw32-clang" --version 2>/dev/null | head -n 1))"
fi
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
#
# The workflow restores toolchains/ from an exact-key cache and this script is
# the only thing that validates it. A cache is not evidence that the artifacts
# are there, complete or at the pin, so every cached tree is checked for the
# exact file its consumers use:
#   llvm-project     -> .git at $LLVM_PIN and llvm/CMakeLists.txt
#   llvm-host-build  -> bin/llvm-tblgen (build/wine-macos needs it too)
#   llvm-ios-build   -> include/llvm/Config/llvm-config.h (read by
#                       build/madeira-d3d12/build-pe.sh) and lib/*.a (linked by
#                       build/dxmt-ios/build.sh)
# A tree that fails its check is (re)built here; a complete one is reused, which
# is what makes a cache hit cost seconds instead of ~35 minutes. The pinned
# sources are always fetched: the cache holds build products, never sources.
LLVM_PIN=8dfdcc7b7bf66834a761bd8de445840ef68e4d1a
LLVM_SRC="$ROOT/toolchains/llvm-project/llvm"
LLVM_HOST="$ROOT/toolchains/llvm-host-build"
LLVM_IOS="$ROOT/toolchains/llvm-ios-build"
LLVM_TBLGEN="$LLVM_HOST/bin/llvm-tblgen"

LLVM_PINNED=0
if [[ -d "$ROOT/toolchains/llvm-project/.git" ]] && [[ -f "$LLVM_SRC/CMakeLists.txt" ]] \
   && [[ "$(git -C "$ROOT/toolchains/llvm-project" rev-parse HEAD 2>/dev/null)" == "$LLVM_PIN" ]]; then
  LLVM_PINNED=1
  echo "  reused: toolchains/llvm-project @ $LLVM_PIN"
else
  if [[ ! -d "$ROOT/toolchains/llvm-project/.git" ]]; then
    git clone --filter=blob:none --no-checkout \
      https://github.com/llvm/llvm-project.git "$ROOT/toolchains/llvm-project"
  fi
  git -C "$ROOT/toolchains/llvm-project" fetch --depth 1 origin "$LLVM_PIN"
  git -C "$ROOT/toolchains/llvm-project" checkout --detach FETCH_HEAD
  echo "  fetched: toolchains/llvm-project @ $LLVM_PIN (the cached tree was absent or at another revision)"
fi
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

# The host tablegen is only reused for a tree that is at the pin: it is a build
# product of that source, not of whatever revision happens to be checked out.
if [[ "$LLVM_PINNED" == 1 ]] && [[ -x "$LLVM_TBLGEN" ]]; then
  echo "  reused: toolchains/llvm-host-build ($LLVM_TBLGEN)"
else
  cmake -S "$LLVM_SRC" -B "$LLVM_HOST" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD=Native \
    -DLLVM_BUILD_TOOLS=ON -DLLVM_INCLUDE_TESTS=OFF -DLLVM_ENABLE_PROJECTS=""
  cmake --build "$LLVM_HOST" --target llvm-tblgen --parallel 3
  echo "  built: toolchains/llvm-host-build ($LLVM_TBLGEN)"
fi

# Counted through a guarded helper, not `ls ... | wc -l` in a command
# substitution: with `set -o pipefail` an absent lib/ makes that pipeline fail
# and `set -e` would abort the bootstrap right here, on exactly the cache miss
# this validation exists to repair.
llvm_ios_objects() {
  local n=0
  if [[ -d "$LLVM_IOS/lib" ]]; then
    n="$(find "$LLVM_IOS/lib" -maxdepth 1 -name '*.a' | wc -l | tr -d ' ')"
  fi
  printf '%s' "$n"
}
LLVM_IOS_OBJECTS="$(llvm_ios_objects)"
if [[ "$LLVM_PINNED" == 1 ]] && [[ -f "$LLVM_IOS/include/llvm/Config/llvm-config.h" ]] \
   && [[ "$LLVM_IOS_OBJECTS" != 0 ]]; then
  echo "  reused: toolchains/llvm-ios-build ($LLVM_IOS_OBJECTS archives, include/llvm/Config/llvm-config.h)"
else
  cmake -S "$LLVM_SRC" -B "$LLVM_IOS" -G Ninja \
    -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_OSX_ARCHITECTURES=arm64 \
    -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_HOST_TRIPLE=arm64-apple-ios17.0 \
    -DLLVM_DEFAULT_TARGET_TRIPLE=arm64-apple-ios17.0 -DLLVM_TARGET_ARCH=host \
    -DLLVM_TARGETS_TO_BUILD="" -DLLVM_ENABLE_PROJECTS="" \
    -DLLVM_BUILD_TOOLS=OFF -DLLVM_INCLUDE_TOOLS=OFF -DLLVM_BUILD_UTILS=OFF \
    -DLLVM_BUILD_TESTS=OFF -DLLVM_INCLUDE_TESTS=OFF \
    -DLLVM_BUILD_EXAMPLES=OFF -DLLVM_INCLUDE_EXAMPLES=OFF \
    -DLLVM_BUILD_BENCHMARKS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF \
    -DLLVM_INCLUDE_DOCS=OFF -DLLVM_ENABLE_PLUGINS=OFF -DLLVM_ENABLE_ZLIB=OFF \
    -DLLVM_TABLEGEN="$LLVM_TBLGEN"
  cmake --build "$LLVM_IOS" --parallel 3
  echo "  built: toolchains/llvm-ios-build ($(llvm_ios_objects) archives)"
fi

if [[ ! -f "$LLVM_IOS/include/llvm/Config/llvm-config.h" ]] || [[ "$(llvm_ios_objects)" == 0 ]]; then
  echo "error: toolchains/llvm-ios-build has no include/llvm/Config/llvm-config.h or lib/*.a after the build" >&2
  exit 1
fi
echo "Bootstrap complete. Toolchain archive SHA-256 verified; LLVM source is pinned at $LLVM_PIN."


