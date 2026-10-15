#!/bin/bash
# Validate a packaged, unsigned iOS IPA the way the device will meet it.
#
#   tools/validate-ipa.sh <ipa> <payload-dir> <sums-file> [<root>]
#
# Checks, in order, and exits non-zero with a named reason on the first failure:
#
#   1. the archive carries Payload/<App>.app/Info.plist;
#   2. the bundle's CFBundleExecutable names a file that is really there (read
#      with python3's plistlib, so it also works when the plist is binary);
#   3. that executable is inside the archive at the same path;
#   4. Payload holds exactly one .app (a second app in the payload is a signing
#      and install hazard, and it means the packaging step copied a stale tree);
#   5. the executable has an arm64 slice (lipo -archs): the IPA is built for
#      arm64 devices only, and an x86_64/simulator slice means the wrong build
#      configuration was packaged;
#   6. no forbidden release input crept in (Apple's Metal Shader Converter, the
#      custom D3D12 runtime, Microsoft's redistributable runtime directory) --
#      the same exclusions tools/validate_release_inputs.py enforces on the app
#      directory, checked here on the packaged bytes.
#
# It then writes <sums-file> as `shasum -a 256` output for the packaged IPA and
# verifies it back with `shasum -a 256 -c`, so the hash published next to the
# IPA is provably the hash of that IPA (path relative to <root> when the IPA is
# inside it, which is how CI verifies it).
#
# Prints key=value lines for the caller:
#   IPA_VALID=1 APP_BUNDLES=<n> BUNDLE_EXEC=<name> IPA_ARCHS=<archs> IPA_SHA256=<hex>
set -euo pipefail

IPA="${1:?usage: validate-ipa.sh <ipa> <payload-dir> <sums-file> [root]}"
PAYLOAD="${2:?usage: validate-ipa.sh <ipa> <payload-dir> <sums-file> [root]}"
SUMS="${3:?usage: validate-ipa.sh <ipa> <payload-dir> <sums-file> [root]}"
ROOT="${4:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

fail() { echo "error: $*" >&2; exit 1; }

# A membership failure is reported with the listing that did not contain the
# entry: an archive that is empty or unreadable and one that is missing a file
# need different answers.
fail_listing() {
    echo "error: $*" >&2
    echo "--- unzip -l $IPA (rc=$LISTING_RC) ---" >&2
    printf '%s\n' "$LISTING" | head -n 40 >&2
    [ -z "$LISTING_ERR" ] || printf '%s\n' "$LISTING_ERR" | head -n 10 >&2
    exit 1
}

[[ -f "$IPA" ]] || fail "$IPA does not exist"
[[ -d "$PAYLOAD" ]] || fail "$PAYLOAD does not exist"

LISTING_RC=0
LISTING="$(unzip -l "$IPA" 2> "$IPA.unzip-stderr")" || LISTING_RC=$?
LISTING_ERR="$(cat "$IPA.unzip-stderr" 2>/dev/null || true)"
rm -f "$IPA.unzip-stderr"
[[ "$LISTING_RC" = 0 ]] || fail_listing "unzip cannot read $IPA"
[[ -n "$LISTING" ]] || fail_listing "unzip produced no listing for $IPA"

# 1/2. the bundle and its declared executable
APP_BUNDLE=""
for d in "$PAYLOAD"/*.app; do
    [[ -d "$d" ]] || fail "$PAYLOAD holds no .app bundle"
    APP_BUNDLE="$d"
done
[[ -n "$APP_BUNDLE" ]] || fail "$PAYLOAD holds no .app bundle"
APP_NAME="$(basename "$APP_BUNDLE")"
PLIST="$APP_BUNDLE/Info.plist"
[[ -f "$PLIST" ]] || fail "$APP_BUNDLE has no Info.plist"
echo "$LISTING" | grep -q "Payload/$APP_NAME/Info.plist" \
    || fail_listing "$IPA does not contain Payload/$APP_NAME/Info.plist"

BUNDLE_EXEC="$(python3 - "$PLIST" <<'PY'
import plistlib, sys
try:
    with open(sys.argv[1], "rb") as fh:
        print(plistlib.load(fh).get("CFBundleExecutable", ""))
except Exception as exc:                                  # noqa: BLE001 - reported below
    sys.stderr.write("cannot read %s: %s\n" % (sys.argv[1], exc))
PY
)"
[[ -n "$BUNDLE_EXEC" ]] || fail "$PLIST declares no CFBundleExecutable"
APP_EXE="$APP_BUNDLE/$BUNDLE_EXEC"
[[ -f "$APP_EXE" ]] || fail "CFBundleExecutable is '$BUNDLE_EXEC' but $APP_EXE does not exist"
[[ -x "$APP_EXE" ]] || fail "$APP_EXE is not executable"
echo "$LISTING" | grep -q "Payload/$APP_NAME/$BUNDLE_EXEC\$" \
    || fail_listing "$IPA does not contain Payload/$APP_NAME/$BUNDLE_EXEC"

# 3. exactly one app in the payload
APP_COUNT="$(find "$PAYLOAD" -maxdepth 1 -mindepth 1 -name '*.app' | wc -l | tr -d ' ')"
[[ "$APP_COUNT" = 1 ]] || fail "Payload holds $APP_COUNT .app bundles, expected exactly 1"

# 4. the slice the device runs
APP_ARCHS="$(lipo -archs "$APP_EXE" 2>/dev/null || echo '')"
[[ -n "$APP_ARCHS" ]] || fail "lipo cannot read the architectures of $APP_EXE"
case "$APP_ARCHS" in
    *arm64*) ;;
    *) fail "$BUNDLE_EXEC has no arm64 slice (lipo -archs says '$APP_ARCHS')" ;;
esac

# 5. release exclusions, on the packaged bytes
if echo "$LISTING" | grep -Eiq 'libmetalirconverter|d3d12core\.dll|madeira_d3d12|x86_64-vcruntime'; then
    fail "forbidden D3D12 converter or Microsoft runtime found in $IPA"
fi

# 6. the published hash must be the hash of this file, and must verify
if [[ "$IPA" == "$ROOT/"* ]]; then SUMS_PATH="${IPA#"$ROOT/"}"; else SUMS_PATH="$IPA"; fi
IPA_SHA256="$(shasum -a 256 "$IPA" | cut -d' ' -f1)"
printf '%s  %s\n' "$IPA_SHA256" "$SUMS_PATH" > "$SUMS"
( cd "$ROOT" && shasum -a 256 -c "$SUMS" > /dev/null ) \
    || fail "$SUMS does not verify against $IPA"

echo "IPA_VALID=1"
echo "APP_BUNDLES=$APP_COUNT"
echo "BUNDLE_EXEC=$BUNDLE_EXEC"
echo "IPA_ARCHS=$APP_ARCHS"
echo "IPA_SHA256=$IPA_SHA256"
