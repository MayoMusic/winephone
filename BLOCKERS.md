# WinePhone blockers

## B-001: Local iOS build unavailable

- **Evidence:** FP0 found Windows 10 x64 and no `xcodebuild`/Xcode. Madeira's documented final build step is `xcodebuild -project app/Madeira.xcodeproj ...` (`docs/BUILDING.md` at base commit `279fd0f83170425db002fe25d6bd62f6355f497d`).
- **Impact:** IPA build must run on a macOS GitHub runner; this host cannot validate the IPA locally.
- **Next path:** Run the drafted macOS Actions workflow after GitHub authentication. The local platform limitation has a documented CI path.
- **Ladder tried:** (1) diagnosis; (3) use the documented macOS build route. (2) Not needed because source lists the correct platform-specific builder.
- **Status:** Active.

## B-002: GitHub publication requires user authentication

- **Evidence:** `gh auth status` reports no logged-in GitHub host.
- **Impact:** Cannot create the public repository, push changes, start a user-owned workflow, or publish a release.
- **Next path:** Prepare and review local work; then ask the user to run `gh auth login`.
- **Ladder tried:** (1) checked current CLI auth state; credential handling remains user-only by instruction.
- **Status:** Active.

## B-003: Full source history omitted; one local nested checkout has a stale lock

- **Evidence:** Full-history clone exceeded the time box; the Wine fork branch head is the exact gitlink SHA `9129e9684daaeae70da9435e7c6060e59392634e`. FEX `.gitmodules` includes binary test-corpus submodules (`fex-gcc-target-tests-bins`, `fex-gvisor-tests-bins`, `fex-posixtest-bins`).
- **Impact:** Full ancestry and unneeded test binaries are not fetched. `FEX/External/vixl` local worktree is empty although the exact gitlink is recorded; a stale `.git` lock prevented the current checkout from fetching it.
- **Next path:** The bootstrap fetches VIXL at its exact gitlink on the clean runner. Confirm this succeeds in CI.
- **Ladder tried:** (1) checked for an active Git process (none); (2) retained exact pinned gitlink and updated bootstrap to fetch selected nested sources; a stale lock removal was rejected by workspace safety policy. No corpus binary was run or added to the WinePhone tree.
- **Status:** Local worktree issue; clean-run verification pending.

## B-004: Device-side behavior not verified

- **Evidence:** No IPA exists and no device logs were provided. JIT behavior on iOS 27, signing entitlements, jetsam limits, and runtime compatibility remain untested.
- **Impact:** No performance or compatibility claim can be made.
- **Next path:** Build IPA in CI, then user installs/enables JIT and shares logs. User will provide a game name before title-specific analysis.
- **Status:** Active.

## B-006: FEX iOS configure assumes Linux host probes

- **Evidence:** GitHub Actions run `38637082925` completed bootstrap/cache and failed FEX configure after `NeedDisabledSVE.py` attempted `/proc/cpuinfo`; its `aarch64_fit_native.py` import failure left the CPU string empty for CMake `string(STRIP ...)`. The five `HAS_SYSCALL_*` messages are optional compile probes, not by themselves fatal. Exact FEX source pin: `f59cab95659e8add0c88f0c76ec1cf483c536dbf`.
- **Impact:** No Darwin configure, FEXCore compile, IPA link/package, or device test is proven.
- **Next path:** Keep generic `TUNE_CPU=none`; `patches/fex-darwin.patch` is **deleted** and `build/fex-ios/build.sh` no longer defines `FEX_IOS_HOST`/`FEX_IOS_HOST_BUILD`, which are the Windows-PE-module (`fex-wow64`/`fex-arm64ec`) flags, not native `fex-ios` ones (`docs/MADEIRA_RECIPE.md` correction; `FEX/FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:719`). Confirm configure+compile once in the macOS `only_stage=fex-ios` dispatch, then address the first remaining compile error.
- **Status:** The `fex-ios` stage now **passes** (run `38644632372` reached and completed it). `FEX_IOS_HOST`/`FEX_IOS_HOST_BUILD` are the Windows-PE-module flags, but the recipe-alignment change was reverted because the stage works as-is and FEX must not be touched; `TUNE_CPU=none` stays. The failure moved downstream to B-008.

## B-005: License/provenance review needed before public binary release

- **Evidence:** Madeira `docs/LICENSING.md` explicitly leaves LGPL static-link/relink capability and lawyer review open; `LICENSE-EXCEPTION.md` limits its exception to Madeira-authored code and does not cover Wine.
- **Impact:** Do not claim final distribution clearance for a combined IPA until the exact license bundle, notices, and relink route are verified.
- **Next path:** Audit `THIRD-PARTY-NOTICES.md`, submodule license files, converter exclusion, and clean rebuild/relink capability; retain per-component licenses. The workflow requires repository variable `WINEPHONE_BINARY_RELEASE_CLEARED=true` before publishing IPA artifacts.
- **Status:** Active.

## B-007: No-JIT target is not implemented

- **Evidence:** The app uses `JITAllocator.c` and FEX's iOS JIT pool environment variables; no AOT backend or interpreter fallback is wired into the app.
- **Impact:** The Track A sideload output does not meet the separate zero-JIT App-Store-style requirement.
- **Next path:** Track B feasibility study: measure code discoverability, prototype an existing lifter/interpreter integration, or document why it cannot meet the requirement.
- **Status:** Active; explicitly out of scope for the current Track A build.

## B-008: `wine/build-macos` is never configured, so every unix-side compile fails

- **Evidence:** run `38644632372`, stage `wine-ntdll-unix`: `wg_parser_apple_ios... OK` and ~37 other translation units `FAILED` in 0.2-0.4 s each with no compiler text in the log. `build/ntdll-unix/build.sh:27,65` pass `-include "$WINE_BUILD/include/config.h"` with `WINE_BUILD=wine/build-macos` (`:7`); `wg_parser_apple_ios` (`:153-163`) is the only compile that passes no Wine include, and it is the only one that succeeded. `build/ntdll-unix/build.sh` is byte-identical to Madeira's at `279fd0f`. No script in the repository configures `wine/build-macos`; its consumers are `build/ntdll-unix/build.sh`, `build/win32u-unix/build.sh:14`, `build/wineserver/build.sh:28`, `build/d3d11-triangle/build.sh:50`, `tests/dxmt/build.sh:21`, `scripts/build-ipa.sh:84`, and the out-of-band status is documented in `build/dxmt-ios/README.md:47-49` and `tests/host/check-wma-decoder.py:25-27`.
- **Impact:** The whole `wine-ntdll-unix`, `wineserver` and `win32u-unix` chain, DXMT's PE build, and therefore the app link and IPA cannot proceed.
- **Next path:** New `build/wine-macos/configure.sh` (stage `wine-macos` in `scripts/build-ipa.sh`, also reachable with `only_stage=wine-ntdll-unix`) configures the tree with `--enable-archs=aarch64 --without-x --disable-tests`. `build/ntdll-unix/build.sh` now prints each failing compile's exact command line and first 40 lines of stderr, so one run shows the real errors. Whether the tree must additionally be **built** (`make tools/winebuild` + `aarch64-windows` import libs) for DXMT is a further step.
- **Status:** **The configure half is verified.** Run `38651245572` (`only_stage=wine-ntdll-unix`, commit `62f3269`) reported `31 OK / 6 FAILED` and **none** of the six failures was `config.h`: every other translation unit found `-include wine/build-macos/include/config.h`. The six failures were four missing *other* prerequisites and one SDK field, now B-009 and B-010.

## B-009: the stage-only path built none of the header prefixes the stage consumes

- **Evidence:** run `38651245572` (`only_stage=wine-ntdll-unix`): `bcrypt_unixlib` and `secur32_unixlib` failed on `gnutls/gnutls.h` (`wine/dlls/bcrypt/gnutls.c:34`, `wine/dlls/secur32/schannel_gnutls.c:36`), `crypt32_unixlib` on `gnutls/pkcs12.h` (`build/crypto-unix/crypt32_unixlib_ios.c:40`), `winegstreamer_unixlib` on `libavcodec/avcodec.h` (`build/ntdll-unix/winegstreamer_unixlib_ios.c:251`), `dwrite_unixlib` on `ft2build.h` (`wine/dlls/dwrite/freetype.c:31`). `build/ntdll-unix/build.sh` reads those prefixes from `$REPO_ROOT`-relative paths (`:20-24`) that are **identical in both paths** — `toolchains/gnutls-ios`, `toolchains/ffmpeg-ios`, `research/freetype` — but the stage-only path ran none of their producers. `scripts/bootstrap.sh` builds only LLVM/toolchains (`:19-43`, `:66-83`): it never builds GnuTLS, FFmpeg or FreeType, and `research/freetype` is git-ignored (`.gitignore:113`). Madeira's `docs/BUILDING.md` at `279fd0f` has GnuTLS and FFmpeg as its first two steps (`:33-35`, `:38-42`) but its "Inputs that are not in the repository" table (`:17-25`) has no FreeType and no Wine build tree, and `build/freetype-ios/build.sh` at HEAD refused to run without a pre-cloned `research/freetype` (`:18`).
- **Impact:** Four of six failures in the stage; the whole crypto/network, media and text (dwrite) side of `libntdll_unix.a`.
- **Next path:** `scripts/build-ipa.sh:68-69` now runs the `gnutls` and `ffmpeg` stages before `wine-macos`/`wine-ntdll-unix` in the `only_stage=wine-ntdll-unix` path; FreeType is a separate pinned build with its own cache key (`.github/workflows/build-ipa.yml:88-113`, `winephone-freetype-2.13.3-42608f77…`) whose script clones tag `VER-2-13-3` and verifies the annotated tag's **commit** (`42608f77f20749dd6ddc9e0536788eaad70ea4b5`). The toolchain cache key is untouched, so LLVM is not rebuilt.
- **Status:** Fixed, **UNVERIFIED** until the next stage-limited run.

## B-010: two unixlibs need widl-generated headers, which only a *built* Wine tree has

- **Evidence:** `wine/dlls/dwrite/dwrite_private.h:24-25` includes `dwrite_3.h` and `d2d1.h` (`wine/dlls/dwrite/freetype.c:44` includes `dwrite_private.h`), and `wine/dlls/winegstreamer/unixlib.h:32` includes `mfobjects.h`; none of those four headers exists anywhere in the checkout (`find wine -name dwrite_3.h -o -name d2d1.h -o -name mfobjects.h -o -name mftransform.h` is empty — only the `.idl` inputs are tracked). They are widl output and widl is itself a build product, so configure alone cannot create them: `wine/aclocal.m4:293` `wine_fn_config_makefile()` and `wine/configure:24365` `wine_fn_output_makedep()` only *write* the rules (makedep is compiled and run there), and `wine/tools/makedep.c:2004-2009` gives every `include/*.idl` a `.h` target in that directory's Makefile, invoking widl by its literal path (`:4914`). In both pipeline paths `wine-ntdll-unix` (`scripts/build-ipa.sh:71`, `:96`) runs before the first `make` in a Wine tree (`wine-pe-ntdll`, `build/wine-pe/build-ntdll.sh:20`). Run `38651245572` could not show this: `dwrite` stops at `ft2build.h` first and `winegstreamer` at `avcodec.h`.
- **Impact:** Without the headers, `dwrite_unixlib` and `winegstreamer_unixlib` fail as soon as B-009 is fixed, so `libntdll_unix.a` still cannot be linked.
- **Next path:** `build/wine-macos/configure.sh` now generates them in `wine/build-macos/include` — the tree every unix side already includes — with `make -C wine/build-macos/tools/widl` (only when the binary is absent) followed by `make -C wine/build-macos/include`, and prints `present`/`MISSING` for all four headers. It is deliberately best-effort: a failure is printed and the stage continues, so the diagnosis stays with `build/ntdll-unix/build.sh:26-73` and any compile still fails loudly with its command line.
- **Status:** Fix added, **UNVERIFIED**: the make invocations were read out of makedep/configure, not executed (this worktree has no macOS, no bison/flex and no root, so no Wine build tree can be generated); whether `make -C include` needs further generated sources first is unknown.
