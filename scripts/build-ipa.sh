#!/usr/bin/env bash
# Build and validate a no-signing iOS IPA from the pinned WinePhone tree.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${1:-$ROOT/artifacts}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
start=$SECONDS
ONLY_STAGE="${WINEPHONE_ONLY_STAGE:-all}"
case "$ONLY_STAGE" in
  all|fex-ios|wine-ntdll-unix|wineserver) ;;
  *) echo "error: unsupported WINEPHONE_ONLY_STAGE '$ONLY_STAGE' (use all, fex-ios, wine-ntdll-unix or wineserver)" >&2; exit 2 ;;
esac
BASE_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
STAGES=""
STATUS="$OUT/build-status.txt"

# What this run actually produced, for the workflow (and for anyone reading the
# log): a stage-only dispatch builds one stage and produces no IPA, while the
# full path must end with IPA_PRESENT=1 and a hash that verifies against it. A
# green step must not imply an artifact that was never made.
write_status() {
  {
    printf 'STAGE=%s\n' "$ONLY_STAGE"
    printf 'COMMIT=%s\n' "$BASE_COMMIT"
    printf 'STAGES=%s\n' "${STAGES# }"
    printf '%s\n' "$@"
  } > "$STATUS"
}

run_stage() {
  local label="$1" stage_start="$SECONDS"
  shift
  STAGES="$STAGES $label"
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
if [[ "$ONLY_STAGE" == fex-ios ]]; then
  echo "fex-ios-only mode: skipping LLVM/toolchain bootstrap."
  git submodule update --init --depth 1 FEX
  git -C FEX submodule update --init --depth 1 \
    External/vixl External/fmt External/range-v3 External/rpmalloc \
    External/unordered_dense External/xxhash External/jemalloc_glibc \
    Source/Common/cpp-optparse
elif [[ "$ONLY_STAGE" == wine-ntdll-unix || "$ONLY_STAGE" == wineserver ]]; then
  echo "$ONLY_STAGE-only mode: skipping LLVM/toolchain bootstrap."
  git submodule update --init --depth 1 wine
elif [[ "${WINEPHONE_SKIP_BOOTSTRAP:-0}" == 1 ]]; then
  echo "Bootstrap already completed in the workflow."
else
  run_stage bootstrap bash "$ROOT/scripts/bootstrap.sh"
fi
{
  cmake --version | head -n 1
  ninja --version
  meson --version
  bison --version | head -n 1
  printf 'WinePhone base: '; git rev-parse HEAD
  printf 'FEX: '; git -C "$ROOT/FEX" rev-parse HEAD 2>/dev/null || echo "(not initialized)"
  printf 'Wine: '; git -C "$ROOT/wine" rev-parse HEAD 2>/dev/null || echo "(not initialized)"
  printf 'DXMT: '; git -C "$ROOT/dxmt" rev-parse HEAD 2>/dev/null || echo "(not initialized)"
  git submodule status --recursive || true
} | tee -a "$OUT/build-environment.txt"

if [[ "$ONLY_STAGE" == wineserver ]]; then
  # build/wineserver/build.sh compiles the pinned submodule's server/ sources
  # against wine/build-macos/include (the configured tree's config.h and the
  # widl-generated public headers) and links no other stage's output: the iOS
  # shims and the ntsync header it also includes (build/ntdll-unix/shims,
  # build/madsync) are tracked in this repository, not produced by another
  # stage. The configured wine tree is therefore the one prerequisite it has,
  # and a stage-only dispatch runs it — the same stage the full path runs.
  export PATH="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin:$PATH"
  run_stage wine-macos bash "$ROOT/build/wine-macos/configure.sh"
  run_stage wineserver bash "$ROOT/build/wineserver/build.sh"
  echo "stage-only dispatch ($ONLY_STAGE): no IPA is built, validated or published by this run."
  write_status "IPA_PRESENT=0" "NOTE=stage-only dispatch: no IPA is built or validated"
  cat "$STATUS"
  echo "Build duration: $((SECONDS-start)) seconds"
  echo "Build duration seconds: $((SECONDS-start))" >> "$OUT/build-environment.txt"
  exit 0
fi

if [[ "$ONLY_STAGE" == wine-ntdll-unix ]]; then
  export PATH="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin:$PATH"
  # build/ntdll-unix/build.sh compiles bcrypt/secur32/crypt32/winegstreamer
  # against the GnuTLS and FFmpeg prefixes their stages produce
  # (toolchains/gnutls-ios, toolchains/ffmpeg-ios). Those are not part of the
  # LLVM toolchain cache, so the stage-only path must build them too — the same
  # stages the full path runs.
  run_stage gnutls bash "$ROOT/build/gnutls-ios/build.sh"
  run_stage ffmpeg bash "$ROOT/build/ffmpeg/build.sh"
  run_stage wine-macos bash "$ROOT/build/wine-macos/configure.sh"
  run_stage wine-ntdll-unix bash "$ROOT/build/ntdll-unix/build.sh"
  echo "stage-only dispatch ($ONLY_STAGE): no IPA is built, validated or published by this run."
  write_status "IPA_PRESENT=0" "NOTE=stage-only dispatch: no IPA is built or validated"
  cat "$STATUS"
  echo "Build duration: $((SECONDS-start)) seconds"
  echo "Build duration seconds: $((SECONDS-start))" >> "$OUT/build-environment.txt"
  exit 0
fi

# Do not silently create an incomplete app. Microsoft redistributables,
# Apple converter binaries and game files are intentionally not build inputs.
if [[ "$ONLY_STAGE" == all ]]; then
  run_stage gnutls bash "$ROOT/build/gnutls-ios/build.sh"
  run_stage ffmpeg bash "$ROOT/build/ffmpeg/build.sh"
fi
run_stage fex-ios bash "$ROOT/build/fex-ios/build.sh"
if [[ "$ONLY_STAGE" == fex-ios ]]; then
  echo "stage-only dispatch ($ONLY_STAGE): no IPA is built, validated or published by this run."
  write_status "IPA_PRESENT=0" "NOTE=stage-only dispatch: no IPA is built or validated"
  cat "$STATUS"
  echo "Build duration: $((SECONDS-start)) seconds"
  echo "Build duration seconds: $((SECONDS-start))" >> "$OUT/build-environment.txt"
  exit 0
fi
run_stage fex-arm64ec bash "$ROOT/build/fex-arm64ec/build.sh"
# wine/build-macos is the configured Wine tree every unix side (ntdll, win32u,
# wineserver) and DXMT's PE build consume; Madeira treats it as a pre-existing
# out-of-band build and no script created it (build/wine-macos/configure.sh has
# the file references). It must exist before wine-ntdll-unix.
export PATH="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin:$PATH"
run_stage wine-macos bash "$ROOT/build/wine-macos/configure.sh"
run_stage wine-ntdll-unix bash "$ROOT/build/ntdll-unix/build.sh"
run_stage wineserver bash "$ROOT/build/wineserver/build.sh"
run_stage win32u-unix bash "$ROOT/build/win32u-unix/build.sh"
run_stage wine-pe-ntdll bash "$ROOT/build/wine-pe/build-ntdll.sh"
run_stage wine-pe-dxmt-prereqs bash "$ROOT/build/wine-pe/build-dxmt-prereqs.sh"
run_stage wine-pe-modules bash "$ROOT/build/wine-pe/build-modules.sh"
run_stage dxmt-ios bash "$ROOT/build/dxmt-ios/build.sh"

export PATH="$ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin:$PATH"
if [[ ! -e "$ROOT/dxmt/toolchains" ]]; then ln -s ../toolchains "$ROOT/dxmt/toolchains"; fi
if [[ ! -f "$ROOT/dxmt/build-arm64ec/build.ninja" ]]; then
  # meson setup takes [builddir] [sourcedir]. Passing only the build dir leaves
  # meson to take the source directory from the current directory, which is the
  # repository root and has no meson.build, so it reported:
  #   Neither directory '<ROOT>/dxmt/build-arm64ec' nor directory None
  #   contain a build file meson.build.
  # The dxmt source root is dxmt/ itself (its meson.build carries
  # project('dxmt', ...)). Pass both, the way Madeira's own recipe does:
  #   meson setup dxmt/build-arm64ec dxmt ...
  #
  # The cross file must be the ARM64EC one, not build-aarch64-win.txt.
  # dxmt/meson.build:32-38 decides is_arm64ec by compiling "#error not arm64ec"
  # unless __arm64ec__/_M_ARM64EC is defined, and only
  # arm64ec-w64-mingw32-clang defines them. With the aarch64 compiler that check
  # fails - which is the literal "error: not arm64ec" in the log - and
  # meson.build:247-260 then sets windows_builtin_install_dir to
  # 'aarch64-windows' instead of 'arm64ec-windows', so winemetal/meson.build
  # searched a directory the ARM64EC Wine tree never populates and reported
  # "library 'winecrt0' not found". wine_build_path must likewise be the
  # ARM64EC tree. This is Madeira's exact recipe from docs/BUILDING.md.
  run_stage dxmt-pe-configure env SDKROOT="$(xcrun --sdk macosx --show-sdk-path)" meson setup \
    --cross-file "$ROOT/dxmt/build-arm64ec-win.txt" \
    --native-file "$ROOT/dxmt/build-osx.txt" \
    -Dwine_build_path=../../wine/build-arm64ec \
    "$ROOT/dxmt/build-arm64ec" "$ROOT/dxmt"
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

# ---------------------------------------------------------------- validate
# Check the artifact, not the step that produced it: the archive's layout, that
# the bundle's CFBundleExecutable really names the executable inside it, that
# the executable carries the arm64 slice the device needs, that Payload holds
# one app, that no forbidden release input is inside, and that the hash written
# next to the IPA is provably the hash of that IPA. tools/validate-ipa.sh does
# those checks and writes+verifies SHA256SUMS; it is runnable (and is run by
# tests/host/check-ipa-validation.py) without a Mac except for lipo.
IPA_KEYS="$(bash "$ROOT/tools/validate-ipa.sh" "$IPA" "$OUT/Payload" "$OUT/SHA256SUMS" "$ROOT")" \
  || { echo "error: IPA validation failed for $IPA" >&2; exit 4; }
echo "$IPA_KEYS"
APP_COUNT="$(sed -n 's/^APP_BUNDLES=//p' <<<"$IPA_KEYS")"
BUNDLE_EXEC="$(sed -n 's/^BUNDLE_EXEC=//p' <<<"$IPA_KEYS")"
APP_ARCHS="$(sed -n 's/^IPA_ARCHS=//p' <<<"$IPA_KEYS")"
IPA_HASH="$(sed -n 's/^IPA_SHA256=//p' <<<"$IPA_KEYS")"
echo "IPA validated: $APP_COUNT app bundle, $BUNDLE_EXEC ($APP_ARCHS), sha256 $IPA_HASH"

write_status "IPA_PRESENT=1" "IPA_PATH=$IPA" "IPA_SHA256=$IPA_HASH" \
  "IPA_ARCHS=$APP_ARCHS" "IPA_BUNDLE_EXEC=$BUNDLE_EXEC" "SHA256SUMS=$OUT/SHA256SUMS"
cat "$STATUS"
echo "Build duration: $((SECONDS-start)) seconds"
echo "Build duration seconds: $((SECONDS-start))" >> "$OUT/build-environment.txt"
echo "IPA: $IPA"
