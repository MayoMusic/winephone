# WinePhone progress

## 2026-10-14 (workspace local date)

### FP0 environment

- Workspace: `J:\GameMode`; initially empty and not a Git repository.
- Host: Windows 10 Pro, OS build `10.0.26200`, x64, about 17.0 GB RAM.
- J: drive: NTFS, about 91.9 GB free at inspection.
- Available: Git `2.55.0.windows.5`, GitHub CLI `2.102.0`, Python `3.10.11`, Clang `21.1.6`, 7-Zip, tar.
- Missing: Xcode, `xcodebuild`, CMake, Ninja, Meson.
- `gh auth status`: not logged into any GitHub host.
- Network: `git ls-remote https://github.com/willfaust/Madeira.git HEAD` succeeded and returned `279fd0f83170425db002fe25d6bd62f6355f497d`.
- Existing sibling checkout `J:\games\wine-ios` has user modifications; left untouched.
- Madeira base (`279fd0f83170425db002fe25d6bd62f6355f497d`), FEX (`f59cab95659e8add0c88f0c76ec1cf483c536dbf`), DXMT (`128b297c6e9a00014408dc68b4c2c2373b5813de`), madeira-dock (`72558e416a390f3669457930f09a389e54f49556`), and Wine (`9129e9684daaeae70da9435e7c6060e59392634e`) match their gitlinks. Wine is a depth-1 exact commit. Required source dependencies are mapped in `docs/SOURCES.md`; FEX test-corpus submodules remain deinitialized. One partial corpus fetch occurred during the interrupted recursive clone; no binary was executed or added to the WinePhone working tree.
- Measured FP0 wall time: approximately 2 minutes to initial source fetch and host inventory; exact stage timing was not instrumented. Source fetch and repair elapsed about 12 minutes, including the abandoned full Wine history fetch; no clean-room timer was running.

### Initial source findings (not build evidence)

- Madeira README identifies Wine 11.4, FEX, DXMT and a single-process wineserver arrangement, and states upstream FEX/Wine/DXMT checkouts do not build for iOS.
- `docs/BUILDING.md` says a clean checkout lacks llvm-mingw and built LLVM/iOS toolchains; the project also referenced an absent Microsoft VC++ runtime folder. WinePhone removes that resource from the Xcode bundle so those DLLs remain user-supplied and undistributed.
- That document identifies a Metal Shader Converter installer and tracked library for the D3D12 research path. WinePhone will omit that path pending licensing review.
- The app build requires Xcode/iOS SDK and cannot run on this Windows host.
- Added pinned macOS bootstrap and unsigned IPA workflow scripts. Static checks passed; no CI run, IPA build, simulator/device run, FPS measurement, or game compatibility test has occurred.
- Persisted the requested user environment settings with Windows `setx` and created the target directories: `CODEX_HOME=J:\codex-home`, `TEMP/TMP=J:\tmp`, `npm_config_cache=J:\npm-cache`, and `PIP_CACHE_DIR=J:\pip-cache`.

### FP1/FP2 source and build preparation

- Submodule pins match the Madeira gitlinks. Build-required FEX/DXMT dependencies are recorded in `docs/SOURCES.md`; binary test-corpus submodules remain uninitialized. The local VIXL submodule worktree is empty due a stale Git lock; clean workflow fetch is unverified.
- Ran `tools/ios_audit.sh`; raw log SHA-256: `7D0470D28A30A39E56A38C62EF4754EAE7C6BDC68D632B9BE023F309564C7932`. Findings and limits are in `docs/STUDY.md`.
- Updated the DXMT build script to create `libdxmt_combined.a` on a clean build. Removed Xcode resource references to the absent user-supplied VC++ runtime folder and to the proprietary converter/custom D3D12 payload. D3D12 support is not claimed.
- Added `scripts/bootstrap.sh`, `scripts/build-ipa.sh`, `.github/workflows/build-ipa.yml`, and a closed release-input validator. Static validation passed: Bash syntax parse, Python bytecode compile, Wine builtin marker scan (29 runtime-named DLLs), JSON parse, text patch reverse-apply check, and `git diff --cached --check` (only Windows LF/CRLF warnings).
- `python tools/validate_release_inputs.py .` correctly reports missing generated archives on this unbuilt Windows host; `--skip-archives` passes the release exclusion/provenance checks. This is expected and is not a build test.
- Winlator app source was inspected at public commit `3981d86efa4f333b2a34a7da8b6521476cd8c8b9` as fallback because parent-pinned app commit `a030f552f452158a2db64fdb32b490fa19c0b48d` could not be checked out. PPSSPP source at `0b557116c29a07f608552c578a209db7bc57a27c` confirms an IR interpreter path. GameHub website timed out; claims remain unverified. No code copied.
- No Mac build, workflow run, IPA SHA-256, device install, or game test. Build-stage durations cannot be measured until CI runs. Approximate prior fetch timings are recorded above and are not precision measurements.

### GitHub publication and license review

- User confirmed `gh auth login`; `gh auth status` reports active account `MayoMusic` with repo/workflow scopes. Created public repository `https://github.com/MayoMusic/winephone`.
- Reviewed root `THIRD-PARTY-NOTICES.md`, `docs/LICENSING.md`, `wine/LICENSE-MADEIRA.md` (as recorded by the provenance audit), and the LGPL dependency inventory. The project itself records unresolved conflict and clean recipient relink/re-sign/install test. Binary release is therefore **not cleared**; no `WINEPHONE_BINARY_RELEASE_CLEARED` variable will be set. Workflow artifact upload remains gated.
- No code or IPA has yet been pushed or built in CI at this point.

### First macOS workflow attempt

- Run `38628817666` failed in 26 seconds at Xcode selection: the runner reported `xcode-select: error: --switch must be run as root`. Checkout succeeded; no dependency or product build was attempted.
- Blocker ladder rung 1: updated the workflow to run `sudo xcode-select -s` and will verify the installed path in the next run.

### Second macOS workflow attempt

- Run `38628969464` passed Xcode selection, Homebrew setup, checksum-toolchain setup, and submodule fetch. It ran 20m 4s, then failed in the iOS LLVM build at `lib/LLVMHello.dylib`: Apple ld rejected `llvm-ios-build/lib/Transforms/Hello/LLVMHello.def` as an unknown file type.
- Blocker ladder rung 1: configure LLVM with examples, tests, benchmarks, docs, plugins and tools disabled for the iOS target. The failing `LLVMHello` target is an example plugin, not a WinePhone runtime dependency.
- The Xcode command reported Xcode 26.6 / iOS SDK 26.5. No Wine, FEX, DXMT or app product build was reached; no IPA exists.

### Third macOS workflow attempt

- Run `38631948290` completed LLVM after 35m 8s, then built GnuTLS and FFmpeg successfully (GnuTLS 279s; FFmpeg 48s). It failed at `=== fex-ios ===`: the pinned FEX `CMakeLists.txt` saw an empty `CMAKE_SYSTEM_PROCESSOR` and aborted with `Unsupported processor type .`.
- Blocker ladder rung 1: set `CMAKE_SYSTEM_PROCESSOR=arm64` explicitly for the iOS cross-configuration and enable FEX's `FEX_IOS_HOST_BUILD` plus its required `FEX_IOS_HOST` C/C++/ASM defines, matching the existing ARM64EC iOS build recipe.
- FEX, Wine, DXMT and app targets were not reached. No IPA exists.

### CI cache improvement (2026-10-15)

- GitHub Actions did not retain a cache after the prior job failed, so LLVM would have rebuilt from source after every downstream failure.
- Updated CI to run bootstrap as its own successful step, explicitly save pinned LLVM/toolchain outputs immediately afterward, then skip duplicate bootstrap inside the IPA packaging script. Cache action save is pinned to `actions/cache` v4.2.4 commit `0400d5f644dc74513175e3cd8d07132dd4860809`.
- This change reduces future iteration cost; cache save and restoration are not yet verified.

### Fourth macOS workflow attempt

- Run `38637082925` completed the cold bootstrap in 27m 38s, saved the LLVM/toolchain cache in 1m 23s, then failed during `fex-ios` CMake configuration. The failure is confirmed by the run log: `aarch64_fit_native.py` could not import `packaging` or `pkg_resources`, `NeedDisabledSVE.py` tried to open `/proc/cpuinfo` on Darwin, and the resulting empty CPU string caused `string(STRIP ...)` to fail.
- Blocker ladder rung 1: set FEX `TUNE_CPU=none` for the generic iOS ARM64 build so configuration does not probe the build host's CPU or Linux `/proc`. This avoids adding a new Python package dependency to a path that does not need host-specific tuning.
- The `actions/cache/save` step completed successfully, so the toolchain cache save is now verified. Cache restoration on a subsequent run remains unverified. No Wine/DXMT/app product link or IPA packaging was reached.
- Next: push this FEX configuration fix and run the cached workflow; inspect its first failure and continue.

### Stage-limited FEX iteration preparation (2026-10-15)

- GitHub's cache listing contains the exact pinned toolchain cache key (1.48 GiB), proving a cache entry was saved. This does **not** prove the runner restores it; restore remains **UNVERIFIED**.
- Added `workflow_dispatch` choice `only_stage=all|fex-ios`. The `fex-ios` path requires the exact-key cache restore to report a hit, skips LLVM/toolchain bootstrap, initializes only FEX and its required nested submodules, skips GnuTLS/FFmpeg and runs only the FEX iOS stage. The normal `all` path is unchanged.
- The IPA upload steps and `WINEPHONE_BINARY_RELEASE_CLEARED` gate were not changed. No release variable was set.
- Pending the one stage-limited run: prove cache restore from the workflow output, capture all FEX compile errors and stage duration. Those results remain **UNVERIFIED**.

### Log-reading capability and run 38727641709 (2026-10-16)

- The previous session could not read Actions logs or dispatch workflows (no `gh`, no token, REST 403). This session has `gh` authenticated as `MayoMusic` with `repo` and `workflow` scopes, so both are now possible. All statements below come from logs this session downloaded, not from a user report.
- Fetched and fast-forwarded 4 commits the local tree was missing (`c4cd4a6`, `62f3269`, `6bde730`, `3daa133`). Local HEAD was `b1f0696`; `origin/main` was `3daa133`. The stashed local `build-ipa.yml` edit (push-marker `[fex-ios]` routing) was dropped as superseded: the workflow now selects stages through `workflow_dispatch` `only_stage`.
- **Cache restore is now VERIFIED.** Run `38727641709` step 6 printed `Pinned toolchain cache exact-key hit: true` and the FreeType step printed `Pinned FreeType cache exact-key hit: true`. This closes the "restore remains UNVERIFIED" note carried since run `38637082925`. Consequence: a full run costs ~13 min instead of ~40, so iteration no longer needs stage-only paths for cost reasons alone.
- **Run `38727641709` (`all`, commit `3daa133`, 11m29s) stage results, from the log:** `gnutls` OK, `ffmpeg` OK, `fex-ios` OK, `fex-arm64ec` OK, `wine-macos` configure OK, widl-generated headers OK, `wine-ntdll-unix` reported `Results: 37 succeeded, 0 failed` and produced `libntdll_unix.a` of 2,373,192 bytes in 22 s, then `wineserver` failed immediately with `ERROR: No base libwineserver.a found`.
- **Therefore B-008, B-009 and B-010 are closed by evidence**, not by assumption: the Wine tree is configured, every prerequisite header prefix resolves, the widl headers are generated, and the ntdll unix side links. The build has advanced past every blocker those entries described.
- The Wine configure "development files not found" lines (EGL, Wayland, Pulse, FFmpeg, GStreamer, SDL2, libvulkan/MoltenVK and the rest) are optional-feature probes in Wine's own `configure`, expected on a device target, and are not the failure. Recorded so they are not re-investigated.
- **New blocker B-011:** `libwineserver.a` is git-ignored by Madeira and produced by nothing, so a clean checkout cannot build `wineserver` — see `BLOCKERS.md`. Fix written: `build/wineserver/build.sh` compiles all 44 `wine/server/*.c` with the existing `CC_FLAGS` and archives them when no base is present, plus a `BASE_SKIP` array for sources proven unbuildable and a new `only_stage=wineserver` path.
- **Also verified against source, not assumed:** `ARCHITECTURE_ANALYSIS.md` and `STEAM_CEF_HANDOFF.md` named in the study brief do not exist in Madeira at `279fd0f` (`docs/` holds BUILDING, CONTROLLERS, JIT, KEYBOARD_MOUSE, LIBRARY, LICENSING, MADEIRA_DOCK, MEDIA, STEAM_CLOUD, STEAM_LIBRARY, STEAM_SIGNIN, WOW64, wine-lgpl-provenance). `scripts/build-ipa.sh` and `scripts/` do not exist upstream either; the root has no `.github/`, so Madeira ships no CI of its own. The Wine fork license conflict resolves to **LGPL-2.1-or-later**: `docs/wine-lgpl-provenance.md` records that the fork's HEAD had applied an irreversible LGPL→GPL-3.0 conversion (commit `0224441925d`) and that branch `madeira-lgpl` is `wine-11.4` plus 51 cherry-picked commits with the conversion skipped. The study brief's JIT-helper URL guess (`0-Blu/StikJIT`) is wrong; `README.md:168-170` credits `StikDebug/StikDebug`, `StikDebug/StikJIT` and `jkcoxson/idevice`.
- Local validation: `bash -n` passes on `build/wineserver/build.sh` and `scripts/build-ipa.sh`; the workflow parses and now offers `['all','fex-ios','wine-ntdll-unix','wineserver']`; the `set -e` empty-`BASE_SKIP` path was checked not to abort; the 44-source failure path was exercised with a stub `xcrun` and reported all 44 sorted. No macOS, no iOS SDK, so nothing about actual iOS compilation is claimed.

### Fifth macOS workflow attempt — FEX passes, wine-ntdll-unix fails (2026-10-14)

- Run `38644632372` (commit `bb733f6`) failed after 11m22s. Reported from its log (this agent still cannot read Actions logs: no `gh`/token, REST API HTTP 403): the `fex-ios` stage **passed**, and `wine-ntdll-unix` failed.
- `wg_parser_apple_ios... OK`; ~37 other translation units (`audio_null_ios`, `madsync`, `gnutls_symtab_ios`, `ws2_32_unixlib`, `bcrypt_unixlib`, `debug`, `env`, `file`, `loader`, `process`, `server`, `signal_*`, `socket`, `sync`, `syscall`, `thread`, `virtual`, ...) printed `FAILED` in 0.2-0.4 s each, with **no compiler text in the log** because `build/ntdll-unix/build.sh` redirects each compile's stderr to `obj/<name>.err` and prints only OK/FAILED.
- Root cause established by reading the tree: `build/ntdll-unix/build.sh` is byte-identical to Madeira's, but every TU except `wg_parser_apple_ios` needs `-include "$WINE_BUILD/include/config.h"` from `wine/build-macos` (`:7,27,65`), a configured Wine tree that Madeira's machine had out of band (`build/dxmt-ios/README.md:47-49`, `tests/host/check-wma-decoder.py:25-27`) and that **no script in WinePhone ever creates**.
- Change made: `build/ntdll-unix/build.sh` now prints each failing compile's exact command line and the first 40 lines of its stderr and exits before `ar`; new `build/wine-macos/configure.sh` configures `wine/build-macos` (`--enable-archs=aarch64 --without-x --disable-tests`), invoked as stage `wine-macos` before `wine-ntdll-unix` and available as `only_stage=wine-ntdll-unix`.
- Also, the earlier `[skip ci]` FEX recipe-alignment change (`c4cd4a6`) was **reverted**: `fex-ios` passes as it was.
- UNVERIFIED: the configure flags, the unix compiles, and whether DXMT additionally needs `wine/build-macos` built (`make tools/winebuild` + aarch64-windows import libs).

### Sixth macOS workflow attempt — wine-ntdll-unix reaches the compilers (2026-10-14)

- Run `38651245572` (`only_stage=wine-ntdll-unix`, commit `62f3269`) reported `31 OK / 6 FAILED`. It is the first time this stage produced a compiler-level result at all, and it confirms the previous fix: **not one** of the six failures was `config.h`, so `wine/build-macos` configures on the runner and every other translation unit found its `-include`.
- The six: `bcrypt_unixlib`/`secur32_unixlib` (`gnutls/gnutls.h`), `crypt32_unixlib` (`gnutls/pkcs12.h`), `winegstreamer_unixlib` (`libavcodec/avcodec.h`), `dwrite_unixlib` (`ft2build.h`), and `server_ios.c:2580` reading `ri_page_wait_time_mach`, which `rusage_info_v6` in the iPhoneOS 26.5 SDK does not declare.
- Root cause for the four headers, read from the tree: the include prefixes in `build/ntdll-unix/build.sh:20-24` are identical in both paths, but the stage-only path ran none of their producers. `scripts/bootstrap.sh` builds only LLVM and the toolchains (`:19-43`, `:66-83`) — no GnuTLS, no FFmpeg, no FreeType — and FreeType (`research/freetype`, git-ignored at `.gitignore:113`) had no producer anywhere; `build/freetype-ios/build.sh` at HEAD required a pre-cloned tree (`:18`).
- Changes: the stage-only path now runs the `gnutls` and `ffmpeg` stages (`scripts/build-ipa.sh:68-69`); FreeType is a separate pinned build with its **own** cache key (`.github/workflows/build-ipa.yml:88-113`) and now clones and verifies the pinned commit itself; the stage prints its full include-path diagnostic (`build/ntdll-unix/build.sh:26-73`), including the toolchain cache-hit value; `server_ios.c` drops `pgw=` and keeps `pin=`.
- Recorded for the next run: the wall after these six is not one of them. `dwrite_unixlib` and `winegstreamer_unixlib` also need the widl-generated `dwrite_3.h`/`d2d1.h`/`mfobjects.h`, which exist only in a *built* Wine tree (makedep writes those rules — `wine/tools/makedep.c:2004-2009` — and widl is itself a build product). `build/wine-macos/configure.sh` now generates them after configure, best-effort and logged (B-010).
- UNVERIFIED: every fix in this list, including the make-based header generation and the `--enable-archs=aarch64` configure flags, the unix compiles, and whether DXMT additionally needs `wine/build-macos` built. The FEX recipe-alignment change stays reverted; `DECISIONS.md` and the artifact release gate are untouched.
