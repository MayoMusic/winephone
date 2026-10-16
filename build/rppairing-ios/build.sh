#!/bin/bash
# Build libmadeira_rppairing.a (on-device remote pairing for Built-in StikJIT,
# app/Madeira/JITPairing.swift) for iOS arm64 and copy it to app/Madeira/,
# where the app target links it. The C interface is app/Madeira/MadeiraRPPairing.h.
#
# Dependencies come from crates.io at the versions in Cargo.lock (idevice is
# MIT, jkcoxson/idevice; see THIRD-PARTY-NOTICES.md). Their licence notices
# are regenerated into app/Madeira/legal/LICENSES-rppairing-crates.txt, which
# the app bundles. Needs rustup with the aarch64-apple-ios target
# (`rustup target add aarch64-apple-ios`) and python3.
set -euo pipefail

BUILD_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$BUILD_DIR/../.." && pwd)"
TARGET=aarch64-apple-ios
export IPHONEOS_DEPLOYMENT_TARGET=17.0

cd "$BUILD_DIR"

# The header above names `rustup target add aarch64-apple-ios` as a prerequisite,
# but the script never performed it, so a runner whose Rust toolchain lacks the
# iOS target failed with E0463 "can't find crate for `core`" - run 38849863774 -
# after cargo had already spent a minute fetching crates. Establish it here
# instead of assuming it, and say which way it went so a silent skip is
# impossible.
echo "=== ensuring the Rust target $TARGET is installed ==="
if command -v rustup >/dev/null 2>&1; then
    if rustup target list --installed 2>/dev/null | grep -qx "$TARGET"; then
        echo "  $TARGET already installed"
    else
        rustup target add "$TARGET"
        echo "  installed $TARGET"
    fi
else
    echo "error: rustup is required to add the $TARGET target." >&2
    echo "  cargo was found at $(command -v cargo 2>/dev/null || echo none)," >&2
    echo "  but no rustup is on PATH, so this Rust toolchain cannot build for iOS." >&2
    exit 1
fi

cargo build --release --locked --target "$TARGET"
cp "target/$TARGET/release/libmadeira_rppairing.a" "$REPO_ROOT/app/Madeira/libmadeira_rppairing.a"
echo "-> app/Madeira/libmadeira_rppairing.a"
python3 "$BUILD_DIR/notices.py" "$REPO_ROOT/app/Madeira/legal/LICENSES-rppairing-crates.txt"
