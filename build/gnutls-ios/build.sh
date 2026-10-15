#!/bin/bash
# Cross-compile the GnuTLS stack (GMP -> nettle/hogweed -> GnuTLS) as
# static libraries for iOS arm64. Output prefix: toolchains/gnutls-ios/.
#
# Consumers: Wine's bcrypt/secur32(schannel)/crypt32 unixlibs, compiled
# into libntdll_unix.a. Those normally dlopen libgnutls at runtime; on
# iOS we link these .a files into Madeira.app and resolve symbols through
# a generated table (see build/crypto-unix/).
#
# Notes:
#  - GMP: --disable-assembly (iOS-safe; crypto here isn't hot-path enough
#    to chase hand-tuned asm through Apple's assembler quirks).
#  - GnuTLS: bundled libtasn1 + unistring, no p11-kit (PKCS#11 is
#    meaningless on iOS), no tools/tests/docs.
#  - Stage markers make re-runs skip completed stages; delete
#    obj/<stage>.done to force a rebuild.
set -e

BUILD_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$BUILD_DIR/../.." && pwd)"
SRC_DIR="$BUILD_DIR/src"
OBJ_DIR="$BUILD_DIR/obj"
PREFIX="$REPO_ROOT/toolchains/gnutls-ios"

GMP_VER=6.3.0
NETTLE_VER=3.10.1
GNUTLS_VER=3.8.9

SDK=$(xcrun --sdk iphoneos --show-sdk-path)
CLANG=$(xcrun -f clang)
HOSTFLAGS="-arch arm64 -isysroot $SDK -miphoneos-version-min=17.0"

export CC="$CLANG $HOSTFLAGS"
export CXX="$(xcrun -f clang++) $HOSTFLAGS"
export CFLAGS="-O2"
export AR=$(xcrun -sdk iphoneos -f ar)
export RANLIB=$(xcrun -sdk iphoneos -f ranlib)
export STRIP=$(xcrun -sdk iphoneos -f strip)
export CC_FOR_BUILD="$CLANG -isysroot $(xcrun --sdk macosx --show-sdk-path)"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
# Configure probes must not find Homebrew libs meant for macOS.
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"

HOST=aarch64-apple-darwin
JOBS=$(sysctl -n hw.ncpu)

mkdir -p "$OBJ_DIR" "$PREFIX"

extract() { # tarball, dirname
    if [ ! -d "$OBJ_DIR/$2" ]; then
        echo "=== extracting $2 ==="
        tar -C "$OBJ_DIR" -xf "$SRC_DIR/$1"
    fi
}

# ---------------- GMP ----------------
if [ ! -f "$OBJ_DIR/gmp.done" ]; then
    extract "gmp-$GMP_VER.tar.xz" "gmp-$GMP_VER"
    echo "=== configuring GMP ==="
    cd "$OBJ_DIR/gmp-$GMP_VER"
    ./configure --host=$HOST --prefix="$PREFIX" \
        --enable-static --disable-shared --disable-assembly --with-pic \
        > "$OBJ_DIR/gmp-configure.log" 2>&1
    echo "=== building GMP ==="
    make -j$JOBS > "$OBJ_DIR/gmp-make.log" 2>&1
    make install >> "$OBJ_DIR/gmp-make.log" 2>&1
    touch "$OBJ_DIR/gmp.done"
fi
echo "GMP ok"

# ---------------- nettle ----------------
if [ ! -f "$OBJ_DIR/nettle.done" ]; then
    extract "nettle-$NETTLE_VER.tar.gz" "nettle-$NETTLE_VER"
    echo "=== configuring nettle ==="
    cd "$OBJ_DIR/nettle-$NETTLE_VER"
    ./configure --host=$HOST --prefix="$PREFIX" \
        --enable-static --disable-shared --disable-documentation \
        --with-include-path="$PREFIX/include" --with-lib-path="$PREFIX/lib" \
        > "$OBJ_DIR/nettle-configure.log" 2>&1
    echo "=== building nettle ==="
    make -j$JOBS > "$OBJ_DIR/nettle-make.log" 2>&1
    make install >> "$OBJ_DIR/nettle-make.log" 2>&1
    touch "$OBJ_DIR/nettle.done"
fi
echo "nettle ok"

# ---------------- GnuTLS ----------------
if [ ! -f "$OBJ_DIR/gnutls.done" ]; then
    extract "gnutls-$GNUTLS_VER.tar.xz" "gnutls-$GNUTLS_VER"
    echo "=== configuring GnuTLS ==="
    cd "$OBJ_DIR/gnutls-$GNUTLS_VER"
    ./configure --host=$HOST --prefix="$PREFIX" \
        --enable-static --disable-shared \
        --with-included-libtasn1 --with-included-unistring \
        --without-p11-kit --without-tpm --without-tpm2 \
        --without-idn --without-brotli --without-zstd \
        --disable-doc --disable-tests --disable-tools --disable-cxx \
        --disable-libdane --disable-nls --disable-guile \
        --with-nettle-mini=no \
        NETTLE_CFLAGS="-I$PREFIX/include" NETTLE_LIBS="-L$PREFIX/lib -lnettle" \
        HOGWEED_CFLAGS="-I$PREFIX/include" HOGWEED_LIBS="-L$PREFIX/lib -lhogweed -lgmp" \
        GMP_CFLAGS="-I$PREFIX/include" GMP_LIBS="-L$PREFIX/lib -lgmp" \
        > "$OBJ_DIR/gnutls-configure.log" 2>&1
    echo "=== building GnuTLS ==="
    make -j$JOBS > "$OBJ_DIR/gnutls-make.log" 2>&1
    make install >> "$OBJ_DIR/gnutls-make.log" 2>&1
    touch "$OBJ_DIR/gnutls.done"
fi
echo "GnuTLS ok"

# ------------------------------------------------------------------ install
# The app target links these four from app/Madeira/ (git-ignored, like
# libntdll_unix.a / libwin32u_unix.a / the FFmpeg archives), in dependency
# order gmp -> nettle+hogweed -> gnutls. The Xcode file references are bare
# names resolved against app/Madeira — the same base
# tools/validate_release_inputs.py uses before xcodebuild — so a GnuTLS tree
# left only in $PREFIX/lib is a linked archive that does not exist, which that
# validator reports as "Missing linked archives" and the link would fail on.
APP_DIR="$REPO_ROOT/app/Madeira"
GNUTLS_LIBS=(libgmp libnettle libhogweed libgnutls)
for lib in "${GNUTLS_LIBS[@]}"; do
    src="$PREFIX/lib/$lib.a"
    [ -f "$src" ] || { echo "error: $src was not installed by the build" >&2; exit 1; }
    cp "$src" "$APP_DIR/$lib.a"
done

echo
echo "=== static libs in $PREFIX/lib ==="
ls -la "$PREFIX/lib/"*.a
lipo -info "$PREFIX/lib/libgnutls.a" 2>/dev/null || true

# Verify what the link will actually read: the file is there and it is the iOS
# arm64 slice the target links (a macOS or simulator archive would link and
# then fail at load time, which is exactly what must not be shipped).
echo "=== linked into the app from app/Madeira ==="
for lib in "${GNUTLS_LIBS[@]}"; do
    dst="$APP_DIR/$lib.a"
    [ -f "$dst" ] || { echo "error: $dst is absent after install" >&2; exit 1; }
    archs="$(lipo -archs "$dst" 2>/dev/null || true)"
    case "$archs" in
        *arm64*) ;;
        *) echo "error: $dst carries no arm64 slice (lipo -archs: '${archs:-none}')" >&2; exit 1 ;;
    esac
    printf '  app/Madeira/%s.a (%s)\n' "$lib" "$archs"
done
