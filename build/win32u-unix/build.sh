#!/bin/bash
# Build Wine's win32u unix side as a static lib for iOS (aarch64).
# Mirrors build/ntdll-unix/build.sh — compiles unpatched upstream .c files
# with iOS clang, per-file overrides go in this dir.
#
# Phase 3D step 1: just get every file compiling. All SONAME_LIB*
# deps (freetype, fontconfig, egl, vulkan) forced undefined for now;
# those code paths fall back to stubs.
set -e

BUILD_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$BUILD_DIR/../.." && pwd)"
WINE_SRC="$REPO_ROOT/wine"
WINE_BUILD="$WINE_SRC/build-macos"
NTDLL_SHIMS="$REPO_ROOT/build/ntdll-unix/shims"
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
OBJ_DIR="$BUILD_DIR/obj"
APP_LIB="$REPO_ROOT/app/Madeira/libwin32u_unix.a"

mkdir -p "$OBJ_DIR"

SUCCEEDED=0
FAILED=0
FAILED_FILES=""

# FreeType, statically: build/freetype-ios/build.sh writes the archive into
# <build>/libfreetype.a and its generated configuration headers into
# <build>/include/freetype/config/{ftconfig.h,ftoption.h}. ft2build.h is a
# source header in the clone, so both roots are named here, generated first
# (same convention as build/ntdll-unix's dwrite_unixlib).
FREETYPE_DIR="$REPO_ROOT/build/freetype-ios"
FREETYPE_LIB="$FREETYPE_DIR/build/libfreetype.a"
FREETYPE_INC_SRC="$REPO_ROOT/research/freetype/include"
FREETYPE_INC_BUILD="$FREETYPE_DIR/build/include"

# freetype_ios.c is the only translation unit here that includes FreeType, and
# without it fonts are disabled silently ("WARNING: no libfreetype.a" below).
# The producer is a separate, cached stage (build/freetype-ios/build.sh), so a
# missing header is reported by name before the compiles, not as a lone FAILED.
MISSING_REQUIRED=""
for h in "$FREETYPE_INC_SRC/ft2build.h" \
         "$FREETYPE_INC_BUILD/freetype/config/ftconfig.h" \
         "$FREETYPE_INC_BUILD/freetype/config/ftoption.h"; do
    [ -e "$h" ] || MISSING_REQUIRED="$MISSING_REQUIRED $h"
done
if [ -n "$MISSING_REQUIRED" ]; then
    echo "error: the win32u-unix stage is missing required FreeType headers:$MISSING_REQUIRED" >&2
    echo "  run build/freetype-ios/build.sh first (the workflow's FreeType step, or its cache)" >&2
    exit 1
fi

compile_one() {
    local src=$1
    local name=$2
    shift 2
    echo -n "  $name... "

    if xcrun -sdk iphoneos clang \
        -arch arm64 -isysroot "$SDK" -miphoneos-version-min=17.0 \
        -O2 -fPIC -fvisibility=hidden -fno-stack-protector -fno-strict-aliasing \
        -Wno-implicit-function-declaration -Wno-int-conversion \
        -include "$BUILD_DIR/config_ios.h" \
        -include "$REPO_ROOT/build/ntdll-unix/shims/wine_ios_exit.h" \
        -I"$BUILD_DIR" \
        -I"$WINE_BUILD/include" \
        -I"$NTDLL_SHIMS" \
        -I"$WINE_BUILD/dlls/win32u" -I"$WINE_SRC/dlls/win32u" \
        -I"$WINE_BUILD/include" -I"$WINE_SRC/include" \
        -D__WINESRC__ -D_WIN32U_ \
        -D_ACRTIMP= -DWINBASEAPI= \
        -DSYSTEMDLLPATH=\"\" \
        -DWINE_UNIX_LIB -DWINE_IOS=1 \
        -D__wine_unix_lib_init=win32u_unix_lib_init \
        -USONAME_LIBFREETYPE \
        -USONAME_LIBFONTCONFIG \
        -USONAME_LIBEGL \
        -USONAME_LIBVULKAN \
        -USONAME_LIBGNUTLS \
        -UHAVE_FT2BUILD_H \
        "$@" \
        -c "$src" -o "$OBJ_DIR/$name.o" 2>"$OBJ_DIR/$name.err"; then
        echo "OK"
        SUCCEEDED=$((SUCCEEDED + 1))
    else
        echo "FAILED"
        FAILED=$((FAILED + 1))
        FAILED_FILES="$FAILED_FILES $name"
    fi
}

echo "=== Building win32u unix (iOS) ==="

# All *.c files except main.c (main.c is the PE side entry — lives in win32u.dll).
# dibdrv/*.c compile as their own translation units.
for src in $WINE_SRC/dlls/win32u/*.c $WINE_SRC/dlls/win32u/dibdrv/*.c; do
    name=$(basename "$src" .c)

    # main.c is PE-side (DllMain, syscall PE wrappers) — skip.
    [ "$name" = "main" ] && continue

    # dibdrv file collisions: prefix them so we don't overwrite dc.o/bitblt.o/objects.o
    if [[ "$src" == *"/dibdrv/"* ]]; then
        name="dibdrv_$name"
    fi

    # Per-file iOS overrides (analogous to ntdll-unix's pattern).
    case "$name" in
        class)
            compile_one "$BUILD_DIR/class_ios.c" "class"
            continue
            ;;
        winstation)
            compile_one "$BUILD_DIR/winstation_ios.c" "winstation"
            continue
            ;;
        sysparams)
            compile_one "$BUILD_DIR/sysparams_ios.c" "sysparams"
            continue
            ;;
        defwnd)
            compile_one "$BUILD_DIR/defwnd_ios.c" "defwnd"
            continue
            ;;
        driver)
            compile_one "$BUILD_DIR/driver_ios.c" "driver"
            continue
            ;;
        message)
            compile_one "$BUILD_DIR/message_ios.c" "message"
            continue
            ;;
        d3dkmt)
            # Wraps upstream d3dkmt.c: the opt-in MADEIRA_KMT_ADAPTER adapter
            # (see the header comment in d3dkmt_ios.c).
            compile_one "$BUILD_DIR/d3dkmt_ios.c" "d3dkmt"
            continue
            ;;
        syscall)
            # Wraps upstream syscall.c and adds win32u_zero_bits(), the
            # allocation ceiling of the calling pseudo-process (see the
            # header comment in syscall_ios.c).
            compile_one "$BUILD_DIR/syscall_ios.c" "syscall"
            continue
            ;;
        freetype)
            # Statically-linked freetype (build/freetype-ios/build/libfreetype.a).
            # The wrapper re-defines HAVE_FT2BUILD_H itself; config_ios.h's
            # #undefs win for every other TU. Generated config first: this TU
            # must see the ftconfig.h the library was compiled with.
            compile_one "$BUILD_DIR/freetype_ios.c" "freetype" \
                -I"$FREETYPE_INC_BUILD" \
                -I"$FREETYPE_INC_SRC"
            continue
            ;;
    esac

    compile_one "$src" "$name"
done

echo ""
echo "Results: $SUCCEEDED succeeded, $FAILED failed"
if [ -n "$FAILED_FILES" ]; then
    echo "Failed:$FAILED_FILES"
fi

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "(not linking — errors in $OBJ_DIR/<name>.err)"
    exit 1
fi

echo ""
echo "=== Building libwin32u_unix.a ==="
ar rcs "$OBJ_DIR/libwin32u_unix.a" "$OBJ_DIR"/*.o

# Merge the static freetype so the app link needs no project changes.
# Not a warning that can be ignored: the stage above required its headers, so an
# absent archive means the two dirs do not belong to the same build.
if [ -f "$FREETYPE_LIB" ]; then
    libtool -static -o "$OBJ_DIR/libwin32u_unix.a" \
        "$OBJ_DIR/libwin32u_unix.a" "$FREETYPE_LIB" 2>/dev/null
    echo "merged $FREETYPE_LIB"
else
    echo "error: $FREETYPE_LIB is missing; rerun build/freetype-ios/build.sh" >&2
    exit 1
fi

echo "Copying to app..."
cp "$OBJ_DIR/libwin32u_unix.a" "$APP_LIB"
echo "libwin32u_unix.a: $(wc -c < "$APP_LIB" | tr -d ' ') bytes"
echo "Done!"
