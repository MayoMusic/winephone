# Madeira FEX iOS build recipe

## Source pins

- Madeira root: `279fd0f83170425db002fe25d6bd62f6355f497d` (the WinePhone base pin in `DECISIONS.md` D-001).
- FEX submodule gitlink at that root: `f59cab95659e8add0c88f0c76ec1cf483c536dbf` (`git ls-tree <Madeira-pin> FEX`).
- The recipe below is reconstructed from those exact trees. Madeira's own `docs/BUILDING.md:49` says the iOS build script mirrors an existing development CMakeCache and marks a clean build UNVERIFIED. Therefore the documented script invocation, not a claim of a reproduced clean build, is the available recipe.

## FEX iOS static-library command

At Madeira `build/fex-ios/build.sh:8-14`, configuration happens only when `FEX/build-ios/CMakeCache.txt` does not exist. No toolchain file or explicit generator is provided. The exact configure command is:

```sh
cmake -S "$R/FEX" -B "$B" \
  -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_SYSROOT=iphoneos \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF \
  -DBUILD_THUNKS=OFF \
  -DBUILD_FEXCONFIG=OFF \
  -DBUILD_FEX_LINUX_TESTS=OFF \
  -DENABLE_FEX_ALLOCATOR=OFF \
  -DENABLE_ASSERTIONS=OFF \
  -DENABLE_CLANG_THUNKS=ON \
  -DENABLE_CCACHE=ON
```

There are no environment-variable exports in that script. It expects `cmake` and `ls` on `PATH`; `cmake --build "$B" --target FEXCore FEXCore_Base` builds the named targets, then `ls "$B/FEXCore/Source/"*.a` checks for archives (`build/fex-ios/build.sh:14-15`). `docs/BUILDING.md:49` describes the expected outputs as the FEXCore/FEXCore_Base/Jemalloc archives plus `External/{cephes,fmt,SoftFloat-3e,xxhash}` archives.

**Toolchain and runner facts explicitly present in Madeira's record:** the FEX iOS target is iOS ARM64 with deployment target 17.0. The script does not pin Xcode, macOS, or SDK versions; it selects the `iphoneos` SDK by name (`build/fex-ios/build.sh:9-10`). Madeira's app build documentation gives `xcodebuild -project app/Madeira.xcodeproj -scheme Madeira -destination 'generic/platform=iOS' -allowProvisioningUpdates build` (`docs/BUILDING.md:68`), but gives no Xcode version there. Exact Xcode/SDK version used for the FEX CMake invocation: **UNVERIFIED** in this source record.

## Host tuning scripts and relevant CMake behavior

- The FEX fork defaults `TUNE_CPU` to `native` (`FEX/CMakeLists.txt:189`). For an ARM64 target, when the compiler version is below the unusually high `999999.0` threshold, the configure path runs `Scripts/aarch64_fit_native.py /proc/cpuinfo <clang-version>`, then `Scripts/NeedDisabledSVE.py` (`FEX/CMakeLists.txt:516-542`). The returned CPU name is passed to `check_cxx_compiler_flag(-mcpu=...)`.
- `aarch64_fit_native.py` first imports `packaging.version.Version`, falling back to `pkg_resources.parse_version` (`FEX/Scripts/aarch64_fit_native.py:4-7`); it opens the path passed as argv[1] (`:111-120`). Neither Madeira's FEX iOS script nor its documented FEX recipe installs Python `packaging` or `setuptools`. Whether the development machine had one available is **UNVERIFIED** by the recipe (`docs/BUILDING.md:49` says the script was not clean-run).
- `NeedDisabledSVE.py` reads `/proc/cpuinfo` in both `GetCPUFeatures` (`FEX/Scripts/NeedDisabledSVE.py:11-14`) and `IsAffectedSnapdragon` (`:39-43`). Those reads only occur through the `TUNE_CPU=native` branch above.
- `FEX/CMakeLists.txt:89-117` lowercases and matches `CMAKE_SYSTEM_PROCESSOR`, then fails if it cannot identify x86-64, ARM64, ARM64EC. Madeira's FEX iOS command does **not** pass `-DCMAKE_SYSTEM_PROCESSOR`; whether its Xcode toolchain/CMake inferred it in the original development cache is **UNVERIFIED**.
- `FEX_IOS_HOST_BUILD` is not passed by the native FEX iOS script. In the same Madeira tree, the distinct ARM64EC module script passes `FEX_IOS_HOST_BUILD=ON`, `TUNE_CPU=cortex-a78`, `MINGW_TRIPLE=arm64ec-w64-mingw32`, and `FEX_IOS_HOST=1` to C/C++/ASM (`build/fex-arm64ec/build.sh:8-21`; recipe summary `docs/BUILDING.md:50`). Those are not native FEXCore iOS invocation flags.
- The iOS build doc gives no `requirements.txt`, venv, or Python package install for this FEX command. Madeira's macOS build broadly requires Homebrew bison 3 for Wine's `tools/wrc` (`docs/BUILDING.md:54`); that is separate from the FEX `packaging` import.

## Invocation chain in WinePhone

The current WinePhone workflow selects Xcode 26.6 and reports the selected Xcode and iPhoneOS SDK (`.github/workflows/build-ipa.yml:24-30`). It runs `scripts/bootstrap.sh`, then `scripts/build-ipa.sh artifacts` with `WINEPHONE_SKIP_BOOTSTRAP=1` (`:47-62`). `scripts/build-ipa.sh:48-50` runs the GnuTLS, FFmpeg and FEX iOS stages in sequence; it invokes `build/fex-ios/build.sh` as a child Bash process. The FEX stage receives the workflow process environment; the FEX build script itself exports no variables.

`bootstrap.sh` checks `xcodebuild`, cmake, Ninja, Meson, and bison, adds Homebrew bison to PATH, downloads the pinned llvm-mingw tarball, and builds host `llvm-tblgen` and LLVM for iOS (`scripts/bootstrap.sh:7-84`). It does not install Python `packaging` or `setuptools`. This LLVM build is not called by the Madeira `build/fex-ios/build.sh`; whether other WinePhone stages need it is outside the FEX iOS recipe.

## Step 2 — Difference from WinePhone's current recipe

| Setting/behavior | Madeira pin | WinePhone current tree | Assessment |
|---|---|---|---|
| `CMAKE_SYSTEM_NAME=iOS` | Present (`build/fex-ios/build.sh:9`) | Present (`build/fex-ios/build.sh:16`) | Same; needed. |
| `CMAKE_SYSTEM_PROCESSOR=arm64` | Omitted | Present (`:16`) | Ours-only; needed for FEX's architecture match (`FEX/CMakeLists.txt:89-117`). Previous configure evidence is in `PROGRESS.md` under the CMake processor failure; Darwin's automatic inference is not assumed. |
| `CMAKE_OSX_ARCHITECTURES=arm64` | Present (`:9`) | Present (`:16`) | Same; needed. |
| `CMAKE_OSX_SYSROOT=iphoneos`, `CMAKE_OSX_DEPLOYMENT_TARGET=17.0`, `CMAKE_BUILD_TYPE=Release` | Present (`:10`) | Present (`:17`) | Same. |
| `FEX_IOS_HOST_BUILD=ON` | Omitted in the native FEXCore script; present in **both** Windows-PE-module scripts (`build/fex-wow64/build.sh:15`, `build/fex-arm64ec/build.sh:22`) | **Removed** (was `build/fex-ios/build.sh:18`) | Wrong for this target. It only turns on the 32-bit guest window, `ENABLE_GUEST_WINDOW` (`FEX/CMakeLists.txt:123-128`), and Madeira's WOW64 comment scopes that to "the aarch64 WOW64 module". The static library the app links is not that module. |
| `FEX_IOS_HOST` on C/C++/ASM | Omitted in native FEXCore recipe; present in both PE-module scripts (`build/fex-wow64/build.sh:15-16`, `build/fex-arm64ec/build.sh:22-23`) | **Removed** (was `build/fex-ios/build.sh:18`) | Wrong for this target; the earlier "needed" verdict is retracted (see the correction below). The native library gets its iOS behaviour from `__APPLE__`, and the app compiles the same headers without the macro. |
| `TUNE_CPU` | Not set; CMake defaults to `native` (`FEX/CMakeLists.txt:189`) | `none` (`build/fex-ios/build.sh:19`) | Ours-only and needed on Darwin. Madeira's native-tuning branch invokes both `/proc/cpuinfo` scripts (`FEX/CMakeLists.txt:516-542`); installing `packaging` alone cannot provide `/proc/cpuinfo` or make `aarch64_fit_native.py` Darwin-aware. Chosen fix: keep `none`, do not add an unused Python dependency/venv. |
| Build options `BUILD_TESTING`, `BUILD_THUNKS`, `BUILD_FEXCONFIG`, `BUILD_FEX_LINUX_TESTS`, `ENABLE_FEX_ALLOCATOR`, `ENABLE_ASSERTIONS`, `ENABLE_CLANG_THUNKS`, `ENABLE_CCACHE` | Same values (`:11-12`) | Same (`:20-21`) | Same. |
| Configure/build commands | Configure on missing cache, then `cmake --build ... --target FEXCore FEXCore_Base` and list archives (`:8-15`) | Same conditional configure; uses `make -k -j$(sysctl -n hw.ncpu)` and prints sorted unique compiler errors (`:15-...`) | Error aggregation is ours-only and required for one-run triage. Assumes CMake's default generator on this runner is Unix Makefiles; verify from runner output. |
| FEX source adaptations | At this FEX pin, `NeedDisabledSVE.py` and `FEXHeaderUtils/CMakeLists.txt` do not contain Darwin guards (`FEX/Scripts/NeedDisabledSVE.py:11-14,39-43`; `FEX/FEXHeaderUtils/CMakeLists.txt:4-57`). | Workflow applies `patches/fex-darwin.patch` before configure (`build/fex-ios/build.sh:8-14`). | See the Step 3 patch audit below. |
| Python dependency setup | No Python package setup is specified for the FEX iOS build (`docs/BUILDING.md:49`; FEX script contains no pip/venv call). `aarch64_fit_native.py` imports `packaging`, then tries `pkg_resources` (`FEX/Scripts/aarch64_fit_native.py:4-7`). | Bootstrap installs no Python package (`scripts/bootstrap.sh:7-84`); FEX stage sets `TUNE_CPU=none`. | `packaging` is an undeclared dependency of the native CPU-tuning branch, but it is not a solution to the Darwin `/proc` failure. The iOS target disables that branch, so do not add a venv just for it. Its availability on the historical Madeira machine remains **UNVERIFIED**. |
| Xcode/SDK | The docs specify `iphoneos` and app build invocation but not a version (`docs/BUILDING.md:68`; FEX script `:9-10`). | Workflow selects Xcode 26.6 and logs `xcodebuild -version` and iPhoneOS SDK (`.github/workflows/build-ipa.yml:24-30`). | Ours-only runner pin; useful reproducibility detail, not a known Madeira requirement. Exact version of Madeira's original FEX build remains **UNVERIFIED**. |
| Toolchain bootstrap/cache | Madeira doc says the FEX clean build is UNVERIFIED (`docs/BUILDING.md:49`); FEX iOS script itself has no toolchain fetch. | Bootstrap builds LLVM 15/iOS tools and fetches llvm-mingw (`scripts/bootstrap.sh:24-84`); workflow caches those paths (`.github/workflows/build-ipa.yml:37-58`). | Ours-only; required by other build stages, but LLVM is not directly invoked by `build/fex-ios/build.sh`. GitHub currently lists a 1.48 GiB cache entry for the configured key; actual runner restore is **UNVERIFIED** until a run reports `cache-hit=true`. |

**Decision on `packaging`:** Do not install it in a venv. The previous failed log (run `38637082925`, summarized in `PROGRESS.md`) recorded missing `packaging` and `pkg_resources`, but this is downstream of `TUNE_CPU=native`. Even with a working version parser, `aarch64_fit_native.py` opens its `/proc/cpuinfo` argument and `NeedDisabledSVE.py` reads `/proc/cpuinfo`; macOS has no Linux procfs. `TUNE_CPU=none` bypasses both scripts and avoids host CPU tuning for an iOS cross-build. This is a Darwin-specific build adaptation, not a claim that Madeira's historical configuration used it.

## Step 3 — Darwin patch redundancy audit

At FEX pin `f59cab95659e8add0c88f0c76ec1cf483c536dbf`, the fork does **not** already guard the SVE `/proc` reads or the CMake syscall checks. However, the FEX iOS command now selects `TUNE_CPU=none`, which bypasses the full `TUNE_CPU=native` branch containing both CPU scripts (`FEX/CMakeLists.txt:516-542`). Therefore the `NeedDisabledSVE.py` hunk was redundant for this target. `aarch64_fit_native.py` also leaves the native branch entirely, so installing `packaging` in a venv is unnecessary for this build.

The syscall feature checks in `FEX/FEXHeaderUtils/CMakeLists.txt:4-57` each run a `check_cxx_source_compiles`; a failed probe only omits a `HAS_SYSCALL_*` definition (`if(HAS_SYSCALL_...)`), and does not call `message(FATAL_ERROR)`. `FEX/FEXHeaderUtils/FEXHeaderUtils/Syscalls.h:61-105` selects Linux syscall wrappers only under `__linux__`, and has an Apple wrapper branch. The probe guard hunk was therefore not required to get through configure and is removed. The Apple wrapper implementations' runtime suitability is **UNVERIFIED**.

The remaining one-hunk patch guards `Arm64.cpp`'s Windows diagnostic under both `FEX_IOS_HOST` and `_WIN32`; `FEX_IOS_HOST` alone is also defined by WinePhone's native iOS FEXCore build, while `VirtualQuery` and the `MEM_*` region types are Windows APIs. This source fix remains necessary and the patch passes `git -C FEX apply --check` against the exact FEX pin. No new stubs are introduced. The Darwin short log line only omits Windows region metadata.

## Correction (2026-10-14, resumed): `FEX_IOS_HOST` is a Windows-PE-module define

The Step 2/3 table above originally kept `FEX_IOS_HOST` and `FEX_IOS_HOST_BUILD` in `build/fex-ios/build.sh` as "ours-only and needed". Re-reading the pinned trees shows that is wrong, and the flags are removed:

- Madeira's `build/fex-ios/build.sh` passes neither flag. Madeira passes them **only** in `build/fex-wow64/build.sh:15-16` and `build/fex-arm64ec/build.sh:22-23`, both Windows PE (`toolchain_mingw.cmake`) builds whose `wow64fex`/`arm64ecfex` targets are shipped as `xtajit.dll` / `xtajit64.dll`.
- The fork says so itself at `FEX/FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:719`: *"VirtualQuery exists only in the FEX_IOS_HOST (Windows module) builds; the native iOS FEXCore build (build/fex-ios) reports without the region."* The Darwin compile error in that block is therefore self-inflicted by the extra define, not a FEX porting gap.
- `FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:340,445,632` (`IosAtomicWritableAlias`) and `Arm64.cpp:2332` are the PE module's guest-PE-image/JIT-pool behaviour; `Arm64.cpp:2332` is explicitly commented "Scoped to the WOW64 module".
- `FEX/FEXCore/include/FEXCore/Utils/DualMap.h:7`, `CodeEmitter/CodeEmitter/Buffer.h:25,120` and `FEXCore/Source/Interface/Core/JIT/JIT.cpp:995,1316` gate on `defined(__APPLE__) || defined(FEX_IOS_HOST)`, so the native iOS build already selects those paths through `__APPLE__`.
- No CMake file defines `FEX_IOS_HOST`; it is command-line only (`FEX/CMakeLists.txt:123` is `FEX_IOS_HOST_BUILD`). The app target compiles the same headers without it (`app/Madeira.xcodeproj/project.pbxproj:831` = `DEBUG=1` only; `app/Madeira/FEXBridge.mm:21-22` includes `AllocatorHooks.h` and `DualMap.h`).

Consequently `patches/fex-darwin.patch` (whose single hunk added `&& defined(_WIN32)` to that one block) is deleted: with the macro gone the block is unreachable in `build/fex-ios`, and it still compiles in the MinGW `fex-arm64ec` build where `_WIN32` is defined. Kept as needed Darwin deviations: `CMAKE_SYSTEM_PROCESSOR=arm64` and `TUNE_CPU=none`. **UNVERIFIED** until the macOS run: that FEXCore then configures and compiles.

**Not adopted (2026-10-14, same day).** Run `38644632372` then showed the `fex-ios` stage **passing** with the flags and the patch in place. This change was therefore reverted: `build/fex-ios/build.sh` and `patches/fex-darwin.patch` are back to their `bb733f6` state and FEX is not touched. The analysis above stands only as a note should the flag ever need revisiting; it is not a change in the tree.

## Evidence limits

The pinned Madeira documentation marks the FEX iOS target UNVERIFIED from a clean checkout (`docs/BUILDING.md:49`). This recipe records source text and exact pins; it does not prove an iOS CMake configure, compilation, or device run. All such outcomes remain **UNVERIFIED** until the stage-limited GitHub Actions run records them.

## Step 6 — `wine-ntdll-unix` failure (run 38644632372, 2026-10-14)

**Evidence (from the user-provided log; this worktree cannot read the run).** Stage `wine-ntdll-unix`: `wg_parser_apple_ios... OK`, and ~37 other translation units (`audio_null_ios`, `madsync`, `gnutls_symtab_ios`, `ws2_32_unixlib`, `bcrypt_unixlib`, `debug`, `env`, `file`, `loader`, `process`, `server`, `signal_*`, `socket`, `sync`, `syscall`, `thread`, `virtual`, ...) printed `FAILED` in 0.2-0.4 s each with **no compiler text in the log**. The `fex-ios` stage passed, so FEX is not touched here.

**A. Why the log had no compiler text.** `build/ntdll-unix/build.sh:18-46` (`compile_one`) and `:57-82` (`compile_unixlib`) send each compile's stderr to `$OBJ_DIR/<name>.err` and print only `OK`/`FAILED`, plus a `Failed:` list at `:202-205`; the `.err` files stay on the runner. Fixed: both now funnel through a `run_compile` helper that, on failure, prints the source, the exact command line (bash `printf %q`) and the first 40 lines of stderr, and the script exits with a message before `ar` if anything failed (the pattern `build/win32u-unix/build.sh:143-144` already uses).

**B. Why `wg_parser_apple_ios` passed and every other file failed.** It is the one compile in the script that passes **no Wine include**: a dedicated inline invocation (`build/ntdll-unix/build.sh:153-163` at HEAD) with no `-include config.h` and no `-I"$WINE_BUILD/..."`. Every other file goes through `compile_one`/`compile_unixlib`, and both use

```sh
-include "$WINE_BUILD/include/config.h"   # build/ntdll-unix/build.sh:27 and :65 at HEAD
```

with `WINE_BUILD="$WINE_SRC/build-macos"` (`:7`) — i.e. **`wine/build-macos`**, a configured Wine **build tree**, not Wine's source tree. An instantly-missing `-include` is exactly a ~0.2-0.4 s fatal error.

**C. Madeira's script is identical.** `git diff 279fd0f:build/ntdll-unix/build.sh build/ntdll-unix/build.sh` is **empty (0 lines)**. So the divergence is not the script: Madeira's development machine had `wine/build-macos` pre-configured out of band, and WinePhone's pipeline never creates it.

- `build/dxmt-ios/README.md:47-49`: "**Wine aarch64-windows static libs** already built in `wine/build-macos/` — see `build/ntdll-unix/build.sh` and the Wine submodule for the original configure."
- `tests/host/check-wma-decoder.py:25-27`: "MADEIRA_WINE_BUILD (a configured Wine build tree whose include/ holds config.h and the widl-generated headers; default: `wine/build-macos`, the tree `build/ntdll-unix/build.sh` uses)."
- Other consumers of the same tree: `build/winserver/build.sh:28` (`-I"$WINE_SRC/build-macos/include"`), `build/win32u-unix/build.sh:14`, `build/d3d11-triangle/build.sh:50`, `tests/dxmt/build.sh:21`, and `scripts/build-ipa.sh:84` (DXMT `-Dwine_build_path=../../wine/build-macos`).
- The **only** Wine configure invocations in the whole repository are `build/wine-pe/build-ntdll.sh:18`, `build/wine-pe/build-modules.sh:104` (both `wine/build-arm64ec`) and `build/wine-i386/build.sh:49` (`wine/build-i386`). **Nothing configures `build-macos`.**

**D. Fix.** New `build/wine-macos/configure.sh`, run by `scripts/build-ipa.sh` as stage `wine-macos` immediately before `wine-ntdll-unix` (and, in the new `only_stage=wine-ntdll-unix` path, before it too). It configures `wine/build-macos` with `--enable-archs=aarch64 --without-x --disable-tests`, derived from:

- `docs/WOW64.md:288-290` — the aarch64 side comes from "a tree configured with `--enable-archs=aarch64`";
- `build/wine-pe/build-ntdll.sh:18` and `build/wine-i386/build.sh:49` — the `--without-x --disable-tests` convention for the sibling trees;
- `dxmt/build-aarch64-win.txt` (aarch64-windows cross file) and `dxmt/src/winemetal/meson.build:18-25` — DXMT needs `libs/winecrt0`, `dlls/winecrt0`, `dlls/ntdll`, `dlls/dbghelp` under `aarch64-windows`, plus `tools/winebuild/winebuild`, from that tree.

**UNVERIFIED:** the exact flags Madeira's development machine used for `build-macos` (not recorded anywhere in the tree); whether configure succeeds on the runner; whether the unix compiles then pass; and DXMT additionally needs that tree **built** (`make tools/winebuild` plus the `aarch64-windows` import libraries), which this increment does not do.

## Step 7 — run 38651245572 (`only_stage=wine-ntdll-unix`, 2026-10-14): 31 OK / 6 FAILED

The run used commit `62f3269`, so it had the `wine-macos` stage (32 of 37 compiles found `config.h`), but not the GnuTLS/FFmpeg/FreeType steps or the diagnostics added in the same working session. The six failures are four missing prerequisite trees plus one SDK field:

| Translation unit | Error | Producing step |
|---|---|---|
| `bcrypt_unixlib`, `secur32_unixlib` | `gnutls/gnutls.h` (`wine/dlls/bcrypt/gnutls.c:34`, `wine/dlls/secur32/schannel_gnutls.c:36`) | `build/gnutls-ios/build.sh` |
| `crypt32_unixlib` | `gnutls/pkcs12.h` (`build/crypto-unix/crypt32_unixlib_ios.c:40`) | `build/gnutls-ios/build.sh` |
| `winegstreamer_unixlib` | `libavcodec/avcodec.h` (`winegstreamer_unixlib_ios.c:251`) | `build/ffmpeg/build.sh` |
| `dwrite_unixlib` | `ft2build.h` (`wine/dlls/dwrite/freetype.c:31`) | `build/freetype-ios/build.sh` |
| `server` | `server_ios.c:2582` reads `ri_page_wait_time_mach`, absent from `rusage_info_v6` in the iPhoneOS 26.5 SDK | n/a (source change) |

### A. Where the include paths come from, and which path exported what

`build/ntdll-unix/build.sh:20-24` defines the four prefixes as plain `$REPO_ROOT`-relative paths (`GNUTLS_PREFIX=toolchains/gnutls-ios`, `FFMPEG_PREFIX=toolchains/ffmpeg-ios`, `FREETYPE_SRC=research/freetype`, `FREETYPE_BUILD=build/freetype-ios/build`) and passes them to exactly the compiles that need them (`:170`, `:173`, `:182`, `:185`, `:216`). Those values are **identical in the full and the stage-only path** — what differed is which producing step had run:

- `scripts/bootstrap.sh` builds **only** LLVM and the toolchains: it fetches the submodules (`:19-24`), downloads and SHA-256-checks llvm-mingw (`:27-43`), then configures/builds `llvm-host-build` and `llvm-ios-build` (`:66-83`). It never builds GnuTLS, FFmpeg or FreeType and never configures a Wine tree, so no bootstrap-produced prefix could exist for the stage-only path to inherit. (The `toolchains/gnutls-ios` and `toolchains/ffmpeg-ios` prefixes come from the `gnutls` and `ffmpeg` *stages*, which the full path runs at `scripts/build-ipa.sh:80-81` and the stage-only path goes straight past.)
- FreeType had no producer anywhere: no script and no workflow step referenced `build/freetype-ios`, `research/freetype` is git-ignored (`.gitignore:113`), and `build/freetype-ios/build.sh` at HEAD refused to run without a pre-cloned tree (`:18` `[ -d "$SRC" ] || { echo "ERROR: clone freetype first (see header)"; exit 1; }`). This is the same machine-state assumption as Step 6.
- Madeira's `docs/BUILDING.md` at `279fd0f` agrees, and shows the gap: its two first steps are GnuTLS (`:33-35`) and FFmpeg (`:38-42`), its "Inputs that are not in the repository" table (`:17-25`) lists the LLVM toolchains and Wine Mono but **no FreeType and no Wine build tree**, and `:52-54` lists the unix side before the PE side (the ordering that hides the widl prerequisite below). Madeira's `wine/build-macos` and `research/freetype` were machine state, not recipe steps.

### B. Diagnostics (in the tree now)

`build/ntdll-unix/build.sh:26-73` prints, before the first compile: the four prefixes and the exact `-I` flags each group of compiles gets, `present`/`MISSING` for `config.h`, the widl-generated headers, `gnutls.h`, `pkcs12.h`, `avcodec.h` (source and build), `ft2build.h` (source and build) and `libfreetype.a`, `ls toolchains`, the state of both Wine build trees, a `find` for the four third-party headers, and the toolchain cache-hit value (passed by the workflow as `WINEPHONE_TOOLCHAIN_CACHE_HIT`, `.github/workflows/build-ipa.yml:115-121`). Each failing compile already printed its source, exact command line and first 40 lines of stderr (Step 6).

### C. Fixes

- The stage-only path now runs the same producers as the full path: `scripts/build-ipa.sh:68-69` (`gnutls`, `ffmpeg`) before `wine-macos`/`wine-ntdll-unix` (`:70-71`).
- FreeType is a separate, pinned build with its **own** cache key (`.github/workflows/build-ipa.yml:88-113`, key `winephone-freetype-2.13.3-…`), so it never invalidates the `~35`-minute LLVM cache (key `winephone-macos26-llvm-…`, `:56`): `build/freetype-ios/build.sh` now clones the tag itself and verifies the **commit** (the tag is annotated: `VER-2-13-3` -> tag object `534ad345…` -> commit `42608f77f20749dd6ddc9e0536788eaad70ea4b5`), which is its checksum step. Its cmake invocation is unchanged from Madeira's, so the existing consumers' paths stay valid (`build/win32u-unix/build.sh:65-70` uses `build/include` + `research/freetype/include`, merges `build/libfreetype.a`).
- `server`: `build/ntdll-unix/server_ios.c:2579-2583` drops `pgw=` from the `[xp]` line instead of reading a member the SDK does not declare; `pin=` (from `ri_pageins`) is kept and the reason is a comment at the site.

### The next wall: the widl-generated headers (not among the six)

Run 38651245572 never reached this, because `wine/dlls/dwrite/freetype.c` fails on `ft2build.h` (`:31`) before `dwrite_private.h` (`:44`) is read. Once FreeType exists, two of the same compiles need headers that exist in **no** source tree:

- `wine/dlls/dwrite/dwrite_private.h:24-25` includes `dwrite_3.h` and `d2d1.h`; `wine/dlls/dwrite/freetype.c:44` includes `dwrite_private.h`.
- `wine/dlls/winegstreamer/unixlib.h:32` includes `mfobjects.h`.
- `find wine -name dwrite_3.h -o -name d2d1.h -o -name mfobjects.h -o -name mftransform.h` finds **nothing**: only the `.idl` inputs are tracked (`wine/include/dwrite_3.idl`, `d2d1.idl`, `mfobjects.idl`, `mftransform.idl`; listed in `wine/include/Makefile.in:302`, `:115-122`, `:467`).
- They are widl output, and **widl is itself a build product**, so configure alone cannot create them: `configure` only *writes* the rules (`wine/aclocal.m4:293` `wine_fn_config_makefile()`, driven per directory from `wine/configure.ac:2443…`), and `wine/configure:24365` `wine_fn_output_makedep()` compiles `tools/makedep.c` and runs makedep with `-i` on each generated Makefile (`:24373`). makedep gives every `include/*.idl` a `.h` target in that directory's Makefile (`wine/tools/makedep.c:2004-2009`) and invokes widl by its literal path (`:4914`), so `make -C <tree>/include` needs no top-level Makefile (this fork has none: `wine/Makefile.in` is not tracked at all).
- Which is why Step 6's reading of `tests/host/check-wma-decoder.py:25-27` ("a **configured** Wine build tree whose include/ holds config.h and the widl-generated headers") is only true of a tree that has also been **built**, and why `build/ntdll-unix/build.sh:158` names `wine/build-arm64ec/include`: in Madeira's own order both trees were already built on the development machine. In the pipeline, `wine-pe-ntdll` (`scripts/build-ipa.sh:99`, the first `make` in a Wine tree in the pipeline, `build/wine-pe/build-ntdll.sh:20`) runs **after** `wine-ntdll-unix` (`:96`) in the full path too.

`build/wine-macos/configure.sh` therefore now also generates them, after configure, in `wine/build-macos/include` — the tree every unix side already includes (`-I"$WINE_BUILD/include"`): `make -C wine/build-macos/tools/widl` (only if the binary is absent) then `make -C wine/build-macos/include`, and a `present`/`MISSING` report for all four headers. It is deliberately best-effort (a failure is printed and the stage continues) only because that keeps the diagnosis in one place: if the headers are still absent, the diagnostic above says so and the affected compile still fails loudly with its command line.

**UNVERIFIED:** whether those two make invocations succeed on the runner (the widl rules, the tool build, and the need for bison/flex in the `include` rule set are read from makedep and configure, not executed — this worktree has no macOS, no bison/flex and no root, so a Wine build tree cannot be generated here); whether `make -C include` needs further generated headers first; and whether FreeType's `ft2build.h` from `research/freetype/include` is enough for `wine/dlls/dwrite/freetype.c` without the CMake build's generated headers.
