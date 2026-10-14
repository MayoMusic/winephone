#!/usr/bin/env bash
# Build and validate a no-signing iOS IPA from the pinned WinePhone tree.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${1:-$ROOT/artifacts}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
start=$SECONDS

run_stage() {
  local label="$1" stage_start="$SECONDS"
  shift
  printf '\n=== %s ===\n' "$label"
  "$@" 2>&1 | tee -a "$OUT/build.log"
  printf '%s duration seconds: %s\n' "$label" "$((SECONDS-stage_start))" \
    | tee -a "$OUT/build-environment.txt"
}

[[ "$(uname -s)" == Darwin ]] || { echo "error: IPA builds require macOS/Xcode" >&2; exit 1; }
xcodebuild -version
xcodebuild -showsdks | grep -q iphoneos || { echo "error: iOS SDK unavailable" >&2; exit 1; }
{
  date -u '+Build start: %Y-%m-%dT%H:%M:%SZ'
  uname -a
  xcodebuild -version
  xcrun --sdk iphoneos --show-sdk-version
} | tee "$OUT/build-environment.txt"
run_stage bootstrap bash "$ROOT/scripts/bootstrap.sh"
{
  cmake --version | head -n 1
  ninja --version
  meson --version
  bison --version | head -n 1
  printf 'WinePhone base: '; git rev-parse HEAD
  printf 'FEX: '; git -C "$ROOT/FEX" rev-parse HEAD
  printf 'Wine: '; git -C "$ROOT/wine" rev-parse HEAD
  printf 'DXMT: '; git -C "$ROOT/dxmt" rev-parse HEAD
  git submodule status --recursive
} | tee -a "$OUT/build-environment.txt"

# Do not silently create an incomplete app. Microsoft redistributables,
# Apple converter binaries and game files are intentionally not build inputs.
run_stage gnutls bash "$ROOT/build/gnutls-ios/build.sh"
run_stage ffmpeg bash "$ROOT/build/ffmpeg/build.sh"
run_stage fex-ios bash "$ROOT/build/fex-ios/build.sh"
run_stage fex-arm64ec bash "$ROOT/build/fex-arm64ec/build.sh"
run_stage wine-ntdll-unix bash "$ROOT/build/ntdll-unix/build.sh"
run_stage wineserver bash "$ROOT/build/wineserver/build.sh"
run_stage win32u-unix bash "$ROOT/build/win32u-unix/build.sh"
run_stage wine-pe-ntdll bash "$ROOT/build/wine-pe/build-ntdll.sh"
run_stage wine-pe-modules bash "$ROOT/build/wine-pe/build-modules.sh"
run_stage dxmt-ios bash "$ROOT/build/dxmt-ios/build.sh"

export PATH="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin:$PATH"
if [[ ! -e "$ROOT/dxmt/toolchains" ]]; then ln -s ../toolchains "$ROOT/dxmt/toolchains"; fi
if [[ ! -f "$ROOT/dxmt/build-arm64ec/build.ninja" ]]; then
  run_stage dxmt-pe-configure env SDKROOT="$(xcrun --sdk macosx --show-sdk-path)" meson setup \
    --cross-file "$ROOT/dxmt/build-aarch64-win.txt" \
    --native-file "$ROOT/dxmt/build-osx.txt" \
    -Dwine_build_path=../../wine/build-macos "$ROOT/dxmt/build-arm64ec"
fi
run_stage dxmt-pe-build env SDKROOT="$(xcrun --sdk macosx --show-sdk-path)" meson compile -C "$ROOT/dxmt/build-arm64ec"
for pair in "d3d11/d3d11.dll:d3d11.dll" "dxgi/dxgi.dll:dxgi.dll" \
            "winemetal/winemetal.dll:winemetal.dll" "d3d10/d3d10core.dll:d3d10core.dll"; do
  src="${pair%%:*}"; dst="${pair##*:}"
  cp "$ROOT/dxmt/build-arm64ec/src/$src" "$ROOT/app/Madeira/arm64ec-windows/$dst"
done
run_stage rppairing-ios bash "$ROOT/build/rppairing-ios/build.sh"
run_stage faultrep bash "$ROOT/build/faultrep/build.sh"

# Check archive references only after every producing build step has run.
python3 "$ROOT/tools/validate_release_inputs.py" "$ROOT"

run_stage xcodebuild xcodebuild -project "$ROOT/app/Madeira.xcodeproj" -scheme Madeira \
  -destination 'generic/platform=iOS' -configuration Debug \
  -derivedDataPath "$ROOT/build/DerivedData" \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY= \
  build

APP="$ROOT/build/DerivedData/Build/Products/Debug-iphoneos/Madeira.app"
[[ -d "$APP" ]] || { echo "error: Xcode did not produce Madeira.app" >&2; exit 3; }
rm -rf "$OUT/Payload"
mkdir -p "$OUT/Payload"
ditto "$APP" "$OUT/Payload/Madeira.app"
IPA="$OUT/WinePhone-unsigned.ipa"
run_stage ipa-package bash -c 'cd "$1" && /usr/bin/zip -qry "$2" Payload' _ "$OUT" "$IPA"

unzip -l "$IPA" | grep -q 'Payload/Madeira.app/Info.plist' || exit 4
unzip -l "$IPA" | grep -q 'Payload/Madeira.app/Madeira$' || exit 4
if unzip -l "$IPA" | grep -Eiq 'libmetalirconverter|d3d12core\.dll|madeira_d3d12|x86_64-vcruntime'; then
  echo "error: forbidden D3D12 converter or Microsoft runtime found in IPA" >&2; exit 5
fi
shasum -a 256 "$IPA" | tee "$OUT/SHA256SUMS"
echo "Build duration: $((SECONDS-start)) seconds"
echo "Build duration seconds: $((SECONDS-start))" >> "$OUT/build-environment.txt"
echo "IPA: $IPA"
