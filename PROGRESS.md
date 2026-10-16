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

### freebuff branch found and merged; host suite run locally (2026-10-16)

- **A second line of work existed and was not on `main`.** `origin/freebuff/7e55aade9baf2c42744e7ccd` holds four commits on top of `3daa133` (`92fad32`, `b2a99cb`, `423687c`, `2df2ad0`) that `main` lacked. Its first commit fixes the **same** blocker as the change this session had just written, and does it better: it derives the base source list from the submodule's `wine/server/Makefile.in` `SOURCES` rather than globbing `server/*.c`, adds a `$0 base` producer-only mode, names the true cause on both failure paths, and ships `tests/host/check-wineserver-base.py` (320 lines) which runs the real script end to end against stub `xcrun`/`ar`/`llvm-objcopy`. Those commits also add `tools/validate-ipa.sh`, IPA artifact validation, toolchain-cache validation in `scripts/bootstrap.sh`, cache-save-on-miss, labelled Xcode/SDK reporting, a `host-checks` workflow job, and `BLOCKERS.md` B-011..B-015.
- **Merged** as `f204a66`, resolving `.github/workflows/build-ipa.yml`, `BLOCKERS.md`, `build/wineserver/build.sh` and `scripts/build-ipa.sh` in freebuff's favour. Their `BLOCKERS.md` is taken whole, so this session's duplicate `B-011` is dropped for their `B-013`, which documents the same root cause with more evidence. `PROGRESS.md` and `docs/HANDOFF.md` auto-merged and keep this session's log-reading findings. The superseded run `38824851060` (which was building this session's version) was cancelled.
- **Host suite executed locally on Windows, results as measured:**
  - `check-wineserver-base.py` — **31 PASS, 0 FAIL, exit 0.** This is real end-to-end verification of the merged wineserver base producer, not an inspection: it asserts the source list comes from `Makefile.in`, that base members keep natural `foo.c -> foo.o` names, that a replaced object is swapped and not duplicated, that the symbol-rename sweep touches base and patched members alike, and that `all` mode completes on a clean tree.
  - `check-ipa-build-graph.py` — **PASS, exit 0** (7 checks: the functional wineserver check is wired in, wineserver is dispatchable alone, full-vs-stage-only is one predicate, no step keys off a named stage, Xcode and SDK versions are labelled with their producing commands).
  - `check-ipa-validation.py` — **SKIP-FAIL: `zip` is not available** on this Windows host. Environmental; the runner has `zip`.
  - `check-toolchain-cache.py` — **14 FAIL.** All fourteen trace to one environmental cause on this host: the stub `git` shim the test installs on `PATH` does not intercept, so the real `git` runs in the sandbox and returns `fatal: not a git repository (or any of the parent directories): .git`; every downstream assertion then reports `[]` or `0 configures, 0 builds`. The checks that do not need the sandbox repository do pass (no LLVM configure on a complete cache, the pinned revision is not re-fetched, the llvm-mingw archive is not downloaded again). **Not claimed as passing.** The merged run's `host-checks` job runs the same four scripts on a POSIX runner and is the authority.
- **Repository visibility changed from private to public**, as requested. Audited first: no credential patterns in tracked files, no `.env`/certificates/provisioning profiles/`p12`, no Microsoft redistributables. The `vcruntime140.dll`, `msvcp140*.dll` and `concrt140.dll` files under `app/Madeira/*-windows/` were checked rather than assumed — each has a matching `wine/dlls/` source directory and all are present in Madeira base `279fd0f`, so they are Wine's own LGPL builtins, not Microsoft's runtime. The Microsoft x86_64 runtime stays user-supplied and absent per rule E3. `LICENSE-EXCEPTION.md` reads `Adopted on: 2026-09-24`, so it is not a draft.
- Run `38825221685` (merge `f204a66`) is the next build attempt and carries the `host-checks` job for the first time.

### Host regression suite passes in CI; ABI constraint read out of the fork (2026-10-16)

- **`Host regression checks` completed SUCCESS, 112 of 112 steps**, in run `38825221685`. That is the whole `tests/host` regression suite (151 check scripts, plus fixture steps) running on a POSIX runner. It closes the questions left open by the local Windows attempt: `check-toolchain-cache.py`, which failed locally with 14 errors all traced to the stub `git` shim not intercepting on Windows, **passes on the runner**; `check-ipa-validation.py`, which skipped locally for a missing `zip`, passes there too.
- **Portability finding, from reading the fork rather than assuming.** A per-file scan of the 44 `wine/server/*.c` at wine `9129e968` for Linux-only constructs (`/proc`, `prctl`, `SYS_*`, `signalfd`, `epoll`, `inotify`, `dl_iterate_phdr`, `__linux__`, ...) gives 30 files with **zero** markers. The 14 that hit are largely properly ported: `fd.c` (55 hits) carries `#elif defined(HAVE_KQUEUE)` and `#elif defined(__APPLE__)` branches, `change.c` (45) uses `F_GETPATH`, which is the BSD/macOS path, and `ptrace.c` (16) guards with `#ifdef __linux__` / `#elif defined(__FreeBSD__)`. So Wine's server is genuinely Darwin-capable and "Linux-only sources" is the wrong hypothesis for whatever `wineserver` hits next. The real exposure is narrower and different: `wine/build-macos` is configured with a **macOS** SDK while the objects are compiled against the **iPhoneOS** SDK, so the expected failures are macOS-only APIs and frameworks that do not exist in the iOS SDK, not Linux idioms. VERIFY against the run's per-file compiler output rather than pre-seeding `BASE_SKIP` from this prediction.
- **`server/Makefile.in` `SOURCES` holds exactly 44 `.c` entries**, counted from the pinned file, with no file on disk missing from the list.
- **ABI hazard found and recorded against B-013.** `wine/server/thread.h:147-148` asserts `offsetof(struct thread, completion_wait) == 640` and `offsetof(struct thread, token) == 600` under `WINE_IOS`, and the comment at `:135-146` explains the contract: the archive is expected to carry 27 objects that `build.sh` never recompiles, they read `struct thread` at the offsets they were compiled with, and inserting a field mid-struct moved `completion_wait` 640 -> 648 and made `cleanup_thread_completion()` dereference garbage on every thread teardown — fault `0x110e5e0007b5`, 19 and 17 native faults in two runs, zero before, and undetected because the `objcopy` repack refreshes each member's mtime so the archive looked freshly built. The stated remedy is "rebuild every object in the archive from these headers", which is what rebuilding all 44 from one flag set does, so the repair removes a latent mixed-ABI hazard rather than inheriting it. The "27 prebuilt objects" wording at `thread.h:103` and `:137` becomes stale once the stage passes and must be corrected with the real count. VERIFY the two `C_ASSERT` values on arm64 iOS: `offsetof` is target-ABI dependent, so this x86-64 host proves nothing about them.

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

### Build-path, cache and packaging repairs (2026-10-15, cloud worktree)

Scope: the two header paths the earlier diagnostic reported, the toolchain cache
validation, the packaged-artifact checks and the workflow conditions that decide
what a run publishes. No FEX, Wine or DXMT source was touched; `DECISIONS.md` and
the `WINEPHONE_BINARY_RELEASE_CLEARED` gate are unchanged.

- **The two "missing" paths were not dependencies.** `wine/build-arm64ec/include/dwrite_3.h`
  cannot exist while `wine-ntdll-unix` runs (`wine-pe-ntdll` builds that tree
  later, `scripts/build-ipa.sh`), and `build/freetype-ios/build/include/ft2build.h`
  is never created by any FreeType configuration: `ft2build.h` is a *source*
  header (`research/freetype/include`) while the build tree contributes the
  generated `include/freetype/config/{ftconfig.h,ftoption.h}`. Verified by
  reading freetype `42608f77f2`'s `CMakeLists.txt` (FTCONFIG_H_NAME/FTOPTION_H_NAME
  under `${PROJECT_BINARY_DIR}`, `file(GLOB PUBLIC_HEADERS "include/ft2build.h")`)
  and comparing both `ftconfig.h` files: the UNIX one adds only
  `#undef HAVE_UNISTD_H`/`#undef HAVE_FCNTL_H`. `dwrite_unixlib` now takes
  `-I"$FREETYPE_INC_BUILD" -I"$FREETYPE_INC_SRC"` (build dir first, the order
  `build/win32u-unix/build.sh` already used instead of the dead arm64ec path).
- **The diagnostic now distinguishes required from informational**, and a missing
  required header stops the stage by name before the compiles. The FreeType
  producer verifies its own outputs (pinned commit, `libfreetype.a` + arm64
  slice, both generated headers, source `ft2build.h`); win32u refuses to build
  the font unit without them.
- **Toolchain cache:** `scripts/bootstrap.sh` now validates each restored tree
  against the artifact its consumers use (checkout at the LLVM pin, `bin/llvm-tblgen`,
  `include/llvm/Config/llvm-config.h` + `lib/*.a`) and rebuilds only what is
  absent or at another revision; the pinned sources are always fetched. The
  workflow saves the cache only on a miss (`actions/cache/save` cannot reserve an
  existing key). Writing this surfaced a real bug in the first version of the new
  check: `LLVM_IOS_OBJECTS="$(ls ... | wc -l)"` aborts under `set -euo pipefail`
  when `lib/` is absent — i.e. on exactly the cache miss it was written for.
- **IPA packaging:** `tools/validate-ipa.sh` checks the archive
  (`Payload/<App>.app/Info.plist`, `CFBundleExecutable` names a file present in
  the bundle *and* the archive, exactly one `.app`, an arm64 slice, no forbidden
  converter/Microsoft runtime) and writes+verifies `SHA256SUMS` with
  `shasum -a 256 -c`. `scripts/build-ipa.sh` records what it produced in
  `artifacts/build-status.txt` (`IPA_PRESENT=1` with path/arch/hash, or `0` for a
  stage-only dispatch), and the workflow prints it, verifies the hash of the exact
  file it uploads, uploads the IPA **and** its hash, and says plainly that a
  stage-only dispatch produces no IPA.
- **Xcode and SDK are two different numbers:** the workflow selects the pinned
  `Xcode_26.6.app` (failing with the list of installed Xcodes when it is
  absent) and then **verifies** what it selected — `xcodebuild -version` must
  report Xcode 26.6, the `xcrun --sdk iphoneos --show-sdk-path` must exist, and
  the SDK major version must be ≥ the 17.0 every stage compiles against. The
  two numbers the logs show (`Xcode 26.6` / `Build version 17F113` and the SDK
  `26.5`) are the same installation: the macOS 26 runner image's inventory maps
  `iphoneos26.5` to both Xcode 26.5 and 26.6.
- **CI coverage:** a `host-checks` job now runs the 106 `tests/host` checks that
  need no submodule and no Swift toolchain; until now nothing ran them, and ten
  of them assert their own presence in the workflow.
- **Tests added:** `tests/host/check-ipa-build-graph.py` (the header/flag/upload
  contract, 0/29 passing before the change), `tests/host/check-ipa-validation.py`
  (real zip fixtures plus a stubbed `lipo`: a good IPA passes, and a missing
  executable slice, a second `.app`, a missing plist, a forbidden runtime file and
  a stale `SHA256SUMS` are each refused), `tests/host/check-toolchain-cache.py`
  (complete cache, cache missing the iOS archives, empty cache, cache at another
  revision). Suite result here: **105 passing / 44 failing** (was 94/52), no
  previously passing check regressed; the 44 need the wine/DXMT/FEX submodules
  (uninitialised in this worktree), `swiftc`/`xcrun`, or are the two workflow-step
  checks recorded in B-012.
- **UNVERIFIED, and why:** nothing in this change set has run on macOS or a
  device. No Xcode, no Wine build tree and no submodules exist in this worktree,
  so the compile-level behaviour of the changed include paths and the two `make`
  invocations in `build/wine-macos/configure.sh` remain unexecuted; the new tests
  are source/contract level except the IPA validator and bootstrap, which are
  executed against real archives and a stubbed toolchain.

### wineserver stage: the base archive now has a producer (2026-10-15)

- The full-path run at `3daa133` got past every stage the previous sessions
  repaired (gnutls, ffmpeg, fex-ios, fex-arm64ec, wine-macos + widl headers,
  wine-ntdll-unix 37/37) and stopped at `=== wineserver ===` with
  `ERROR: No base libwineserver.a found` — the first time the pipeline reached
  this stage at all.
- Root cause (B-013): the stage patched a "base" archive that had to pre-exist
  at `app/Madeira/libwineserver.a` — git-ignored, never committed, produced by
  no script in the repository. It was an out-of-band artifact of the original
  dev machine, so a clean checkout could never pass this stage.
- Repair: `build/wineserver/build.sh` builds the base from the pinned
  submodule's `server/Makefile.in` `SOURCES` with the stage's own flags, keeps
  the natural object names so the existing patched-object swap and symbol
  rename still work, and still honours a pre-existing local archive. `$0 base`
  is a new producer-only mode; both failure paths (missing submodule, empty
  source list) name the true cause instead of the old blanket error.
- Tests: `tests/host/check-wineserver-base.py` (new, wired into the workflow's
  host-checks job and into `check-ipa-build-graph.py`) executes the real script
  in a sandbox with stub compilers/archiver: base member set, object swap,
  rename-sweep coverage, legacy-archive reuse and both diagnostics. Suite
  status for the touched surface: wineserver-base, ipa-build-graph,
  toolchain-cache, ipa-validation and every workflow-reading check pass;
  `check-vcruntime-mfc.py`/`check-shader-pack.py` still fail exactly as at HEAD
  (inherited step expectations recorded in B-012, not run in CI).
- The source list is 44 `.c` files, not 43: the pinned
  `server/Makefile.in` at wine `9129e968` lists 44 `.c` (plus `security.h` and
  the three man pages, which are not compiled), and the stage's `awk` parser
  was run against that file here — every one of the 44 exists at the pin
  (`raw.githubusercontent.com/willfaust/wine/9129e968/...`, HTTP 200 for all),
  as do all 13 `$WINE_SRC/server/*.c` sources named in `PATCHED_FILES`.
- `only_stage=wineserver` is now dispatchable: the stage-only path fetches the
  wine submodule and runs `build/wine-macos/configure.sh` (its one
  prerequisite — the iOS shims and the ntsync header it also includes are
  tracked in this repository, and it links no other stage's output) before
  `build/wineserver/build.sh`, so the repaired stage can be verified without
  the fex-ios/fex-arm64ec legs of the full path.
- UNVERIFIED: the 44 real iOS `server/*.c` compiles and everything after this
  stage (win32u-unix, wine-pe, DXMT, xcodebuild, IPA) — one full workflow run
  away.

### CI evidence read back from the GitHub API (2026-10-15)

This worktree has network access to `raw.githubusercontent.com` and the
unauthenticated REST API (run *logs* need admin rights — `403 Must have admin
rights to Repository` — so the step-level conclusions below are the evidence,
not log text). Three runs exist past the 6bde730/3daa133 repairs:

| run | commit | dispatch | conclusion | step that failed | skipped, and why |
| --- | --- | --- | --- | --- | --- |
| 14 (38655974280) | `3daa1338` | stage-only | **success** | — | 7/8 bootstrap+save, 14/15 IPA upload+evidence, 16 gate |
| 15 (38664461063) | `3daa1338` | `only_stage=all` | failure | 13 Build and package unsigned IPA | 11/12 FreeType build+save (cache hit), 14/15/16 |
| 16 (38686578495) | `3daa1338` | `only_stage=all` | failure | 13 Build and package unsigned IPA | 11/12 FreeType build+save (cache hit), 14/15/16 |

- The two `all` runs stop inside `Build and package unsigned IPA` — the
  `=== wineserver ===` / `ERROR: No base libwineserver.a found` failure B-013
  describes (the run the user quoted). FreeType is skipped because its own
  cache key is an exact hit, which is the designed behaviour
  (`build/freetype-ios/build.sh` verifies the restored tree itself).
- Run 14 is green with **no IPA**: bootstrap, the IPA upload and the evidence
  upload are all skipped. That is the documented stage-only shape, and it is
  why the workflow's "Report build result" step reads
  `artifacts/build-status.txt` (`IPA_PRESENT=0`) instead of treating a green
  build step as an artifact — a step-level conclusion alone cannot tell the two
  apart, which is the finding Critical Issue A asks for.
- Runs 14/15/16 all predate `92fad32`, which carries the wineserver repair, the
  workflow fixes and the `host-checks` job: none of them ran `tests/host`
  (`total jobs 1` in each), so B-012 stands for every run on `main` so far.
- **The Xcode 26.6 / 26.5 discrepancy is not a discrepancy.** The macOS 26
  runner image's published inventory (`actions/runner-images`,
  `images/macos/macos-26-Readme.md`) lists Xcode 26.6 (build **17F113**, the
  default) *and* Xcode 26.5 (17F42), and its SDK table maps **iOS 26.5**
  (`iphoneos26.5`) to *both* Xcode 26.5 and 26.6. So `Xcode 26.6` /
  `Build version 17F113` from `xcodebuild -version` and `26.5` from
  `xcrun --sdk iphoneos --show-sdk-version` are the same installation reporting
  two different things: the Xcode version and the iPhoneOS SDK it ships. The
  selection step now asserts the pair (Xcode exactly 26.6, SDK path present,
  SDK major ≥ the `-miphoneos-version-min=17.0` the stages compile with)
  instead of printing them, and fails by name when a future image moves.
- **The next blocker in the same class (B-015):** the Xcode target links 20
  archives; 13 of them are bare names that
  `tools/validate_release_inputs.py` resolves against `app/Madeira` before
  `xcodebuild`, and the GnuTLS stage was the one producer that left its four
  (`libgnutls`, `libhogweed`, `libnettle`, `libgmp`) only in
  `toolchains/gnutls-ios/lib`. That validator would have exited 2 with
  `Missing linked archives` on the first run that got that far — the same
  producer/consumer defect as B-013, one stage later, invisible until the
  wineserver stage stopped killing the run. The stage now installs them into
  `app/Madeira/` in dependency order and verifies each is the iOS arm64 slice;
  `check-ipa-build-graph.py` derives the bare-name set from the project file
  itself and requires a placing producer for every entry, so this class cannot
  come back silently.
- The workflow's full-vs-stage-only conditions are now one predicate
  (`(inputs.only_stage || 'all')`), so no step keys off a named stage and the
  `push` event (unset input) cannot be mistaken for a stage-only run;
  `tests/host/check-ipa-build-graph.py` pins that.

### Clean-build chain advanced to the DXMT PE link (2026-10-16)

Six consecutive runs each removed one blocker, in this order, with every claim
taken from a downloaded log rather than a report:

1. `38727641709` — cache restore proved: `exact-key hit: true` for both the
   toolchain and FreeType. B-008/B-009/B-010 close on evidence; `libntdll_unix.a`
   produced, 37/37.
2. `38727641709` stopped at the first line of `wineserver`:
   `ERROR: No base libwineserver.a found`. B-013. The base archive is git-ignored
   by Madeira and produced by nothing — Wine's `server/Makefile.in` builds only
   the `wineserver` program. A clean Madeira checkout fails here too. Fixed by
   building the base from the submodule's own `SOURCES`.
3. `38825815420` — **wineserver built for the first time**: 44 sources compiled
   for iOS in 12 s, then `libwin32u_unix.a`. No `BASE_SKIP` entry was needed,
   which contradicted the earlier "Linux-only sources" hypothesis.
4. `38825815420` / `38828999867` — `wine-pe-ntdll`: building the whole
   `dlls/ntdll` directory also built the host `ntdll.so`, whose unix link needs
   `_ios_avail_phys` — defined only in `build/ntdll-unix/virtual_ios.c`, which
   belongs to `libntdll_unix.a`. `system.c`'s comment blames
   `tools/patch-wine-avail-phys.py`, which is not in the repository. The `.so` is
   never shipped and the PE module does not link it, so build the PE target only.
5. `38830824987` — that target's path is relative to the build root;
   `-C arm64ec-windows` fails with "No rule to make target". `wine-pe-ntdll` and
   `wine-pe-modules` then cleared.
6. `38832880011` — `dxmt-ios`: 82 of 83 units passed, `airconv_context` failed on
   `air_msad.h`. Reading the file showed it is 165 lines and uses those three
   Apple AIR headers for nothing but three optional intrinsic blobs;
   `initializeModule()` never touches them. B-016 records the licensing decision
   to stub them rather than ship licence-bound headers.
7. `38835000672` — **dxmt-ios 83/83**, `libdxmt_unix.a` and `libdxmt_combined.a`
   created. `meson setup` then failed because only the build directory was
   passed, leaving meson to take the source from the repository root, which has
   no `meson.build`.
8. `38836941062` — meson configured and exposed the real cause: the cross file
   was `build-aarch64-win.txt`. `dxmt/meson.build:32-38` decides `is_arm64ec` by
   compiling `#error not arm64ec` unless `__arm64ec__`/`_M_ARM64EC` is defined,
   so the aarch64 compiler failed that probe and `meson.build:247-260` then chose
   `aarch64-windows` over `arm64ec-windows`. That produced both the literal
   "not arm64ec" error and the bogus `winecrt0` lookup, and would have shipped
   plain-AArch64 PE modules instead of the hybrid ARM64EC images the design
   depends on. Switched to `build-arm64ec-win.txt` with
   `-Dwine_build_path=../../wine/build-arm64ec`, which is Madeira's own recipe.
9. `38838887708` — a new prerequisite stage found three of the four artefacts
   `winemetal/meson.build:18-25` resolves, with sizes, and named the fourth:
   `MISSING dlls/dbghelp/arm64ec-windows/libdbghelp.a`.
10. `38843362962` / `38844655658` — resolving that took three attempts, each of
    which added information rather than guessing: the archive target is not
    readable from source because Wine 11 generates makefiles with `tools/makedep`
    (`configure.ac:2435`); the module directory target does not produce it
    either; and the build log shows Wine never invokes `winebuild --implib` for
    dbghelp at all, only for kernelbase, kernel32, ntdll and ucrtbase — Wine
    builds a module's import library only when something links against it, and
    nothing links dbghelp. The fix reuses Wine's own argument form, copied from
    the log rather than invented, and an earlier silent skip was removed by
    printing every guard condition.

**Method note.** Two of these ten were fixed by reading a guard expression in
the source (`is_arm64ec`, `initializeModule`) rather than by trying a build
variant, and two were fixed by adding verification that names the cause instead
of the symptom. Both approaches paid for themselves immediately; guessing a
generated make target name cost two full CI cycles.

**Still unproven:** no unsigned IPA has been produced, nothing has been linked
into an app binary, and nothing has run on a device. The ARM64EC `winemetal`
and `d3d11` modules, the `xcodebuild` link and the packaging step have not
completed in any run.
