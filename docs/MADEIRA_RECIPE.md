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

## Evidence limits

The pinned Madeira documentation marks the FEX iOS target UNVERIFIED from a clean checkout (`docs/BUILDING.md:49`). This recipe records source text and exact pins; it does not prove an iOS CMake configure, compilation, or device run. All such outcomes remain **UNVERIFIED** until the stage-limited GitHub Actions run records them.
