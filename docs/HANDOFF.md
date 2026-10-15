# WinePhone handoff — FEX Darwin configure blocker

## Current goal

Continue the existing WinePhone Track A sideload/JIT build: use Madeira as the pinned base, build on the GitHub macOS runner, and advance toward an unsigned IPA. The repo is public at <https://github.com/MayoMusic/winephone>. No IPA or device/game test is proven.

## Fixed so far

- `10ef48c` — sets `TUNE_CPU=none` for the generic ARM64 iOS FEX build, avoiding host-native tuning and its Linux `/proc/cpuinfo`/Python version helper path.
- `92329ec` — records the pinned FEX Darwin dependency audit in `docs/RE_NOTES.md`.
- `d218a37` — adds `patches/fex-darwin.patch` and applies it from `build/fex-ios/build.sh` before FEX CMake configuration. The patch tolerates missing `/proc/cpuinfo` in `NeedDisabledSVE.py`, queries `sysctl -n hw.optional.arm.FEAT_SVE` on Darwin, and runs the five `HAS_SYSCALL_*` configure probes only on Linux, setting them false on other systems.
- Patch applicability was checked against FEX `f59cab95659e8add0c88f0c76ec1cf483c536dbf`. A local mocked helper check passed positive SVE, negative SVE, and missing-proc paths. These are source/patch checks, not a Darwin configure/build test.

## Last confirmed blocker

The last completed failing run is [38637082925](https://github.com/MayoMusic/winephone/actions/runs/38637082925), built from parent commit `bb447fb7580279bf82f048877e6a23d2d23b6c1b`. Its first real failure was:

```text
FileNotFoundError: [Errno 2] No such file or directory: '/proc/cpuinfo'
  FEX/Scripts/NeedDisabledSVE.py, GetCPUFeatures(), line 12
During handling of the above exception, another exception occurred:
  FEX/Scripts/NeedDisabledSVE.py, line 42, also opened /proc/cpuinfo
CMake Error at FEX/CMakeLists.txt:529 (string):
  string sub-command STRIP requires two arguments.
```

The same configure log also reported missing Python `packaging` and `pkg_resources` imports in `FEX/Scripts/aarch64_fit_native.py`. The five `HAS_SYSCALL_GETCPU/GETTID/TGKILL/STATX/RENAMEAT2` probes reported `Failed`; source inspection shows these are optional `check_cxx_source_compiles` probes, not independently fatal configure errors (`FEX/FEXHeaderUtils/CMakeLists.txt:5-56`).

**Additional reported compile error (UNVERIFIED):** `FEX/FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:711` references `MEM_IMAGE`, `MEM_MAPPED`, and `MEM_PRIVATE` inside an `#ifdef FEX_IOS_HOST` block at line 707. Those are Windows `VirtualQuery` constants. The pinned source has no `_WIN32` guard around this diagnostic block, while `build/fex-ios/build.sh` defines `FEX_IOS_HOST` for the native iOS target. The report says Darwin compilation rejects these identifiers; run `38643156359` was still in progress at last observation, so its log has not confirmed this error.

## Tried and ruled out

- Re-running the same source without changing the configure path does not address Darwin's missing `/proc`; the previous failing run is evidence.
- Adding Python `packaging` would not provide Linux `/proc/cpuinfo` and would leave the host/target CPU detection mismatch. The iOS build now uses `TUNE_CPU=none` instead.
- The `HAS_SYSCALL_*` probe messages alone do not explain CMake's fatal `string(STRIP)` error. The patch sets these Linux-only feature flags to false on Darwin and relies on the existing Apple wrapper selection in `FEX/FEXHeaderUtils/FEXHeaderUtils/Syscalls.h`.
- Earlier unrelated blockers are recorded in `PROGRESS.md`: Xcode selection privileges, LLVM's disabled example plugin, and an empty FEX `CMAKE_SYSTEM_PROCESSOR`. Those were addressed before the latest confirmed configure failure.

## Not verified

- The workflow for `d218a37` is the single permitted confirmation run, [38643156359](https://github.com/MayoMusic/winephone/actions/runs/38643156359). At last observation it had reached **Build and package unsigned IPA**; final logs/result were not yet available. Do not claim the patch fixed Darwin configure until this run completes and its logs show the FEX step.
- No FEXCore static library build, Fibonacci JIT unit test, IPA package validation, iPhone install, debugger-attached JIT test, or game launch is recorded.
- No new stubs were added. The Apple CMake path excludes the Linux syscall-emulation `Source/` tree and ELF launcher; excluded behavior is not a tested replacement. `docs/RE_NOTES.md` lists the remaining `/proc/self/maps` allocator and guest-syscall integration questions.
- The `hw.optional.arm.FEAT_SVE` sysctl behavior is mocked locally only. **UNVERIFIED:** availability and value on the macOS runner; verify with `sysctl -n hw.optional.arm.FEAT_SVE` in that runner's log.
- The FEXCore-only split may compile, but compile-time dependencies and the requested JIT Fibonacci execution test remain open.

## Single next step

Fetch the completed log for run `38643156359` once and inspect the first FEX configure/build error. If the same `/proc/cpuinfo`/`string(STRIP)` failure recurs after `d218a37`, stop and report it without another CI attempt. If FEX configuration advances, record the next compile error and ask for no new run until a code change targets that exact error.

## Current continuation (2026-10-15)

**Goal:** Continue the existing Madeira-based Track A build toward a locally validated unsigned IPA on the macOS GitHub runner. Keep `WINEPHONE_BINARY_RELEASE_CLEARED` unset and IPA artifact publication gated; leave DECISIONS.md D-001 through D-008 unchanged.

**Step 0:** Checked run `38644632372` exactly once. Result: `status=in_progress`, empty conclusion. No poll or log fetch was made.

**Done:** `bb733f6` pushed the Arm64.cpp Windows diagnostic guard, FEX compiler-error summary command, and source audit. The new run above corresponds to that commit. Previous pin/source work includes Madeira `279fd0f83170425db002fe25d6bd62f6355f497d` and FEX `f59cab95659e8add0c88f0c76ec1cf483c536dbf`.

**Current blocker:** The Darwin FEXCore build result for `bb733f6` is not known because its workflow remains in progress and the instruction prohibits polling. The prior checked run `38643156359` was also in progress at its single check.

**UNVERIFIED:** Darwin CMake/build success; restored toolchain cache effectiveness; full FEX compiler error list; `packaging` as the cause vs workaround for the earlier configure failure; macOS or iOS JIT execution; IPA validation and device/game launch.

**Next step:** Read Madeira's exact pinned `docs/BUILDING.md` recipe and every directly invoked FEX iOS build script at commit `279fd0f83170425db002fe25d6bd62f6355f497d`; compare it with WinePhone's current bootstrap/build/workflow, then write the sourced recipe/diff before any new CI run.

### Step 1 complete

**Done:** `dc95674` adds `docs/MADEIRA_RECIPE.md`, using root pin `279fd0f83170425db002fe25d6bd62f6355f497d` and FEX pin `f59cab95659e8add0c88f0c76ec1cf483c536dbf`. It records the configure/build command, CMake tuning branch, Python imports and CPU-info reads, processor handling, host-option distinction, dependency evidence, and verification limits with file/line references.

**Current blocker:** The report for run `38644632372` remains `in_progress` at its single allowed observation. FEX on macOS remains **UNVERIFIED**.

**UNVERIFIED:** Madeira's clean FEX iOS build and original CMakeCache values; actual presence of `packaging`/`pkg_resources` on the historical development machine; Xcode/SDK version used for Madeira's documented FEX build; FEXCore compilation on the current macOS runner.

**Next step:** Compare the pinned recipe with WinePhone's FEX build script, bootstrap, and workflow; decide which differences are needed on Darwin and whether Python dependency installation addresses the reported failure.

### Step 2 complete

**Done:** `77477ca` adds the line-by-line recipe comparison to `docs/MADEIRA_RECIPE.md`. The chosen CPU fix is `TUNE_CPU=none`: adding `packaging` to a venv would address only Python's version parser import, while the native-tuning scripts still open Linux `/proc/cpuinfo`. FEX iOS configure requires an explicit ARM64 processor based on `FEX/CMakeLists.txt:89-117`; the iOS host macros/options are identified as WinePhone integration choices, with `FEX_IOS_HOST_BUILD` necessity for the static-only target left **UNVERIFIED**.

**Cache evidence:** GitHub reports a 1.48 GiB cache entry for the configured key. This confirms a saved entry exists, not that the runner restores it; cache restore remains **UNVERIFIED**.

**Current blocker:** Darwin FEXCore compilation has not been confirmed. Run `38644632372` remains at `in_progress` from its single status check.

**Next step:** Remove the no-longer-reached SVE and nonfatal syscall-probe hunks from `patches/fex-darwin.patch`, retaining the Windows-only Arm64 diagnostic guard; record exact remaining behavior.

### Step 3 complete

**Done:** `6b9351f` reduced `patches/fex-darwin.patch` from three hunks to one. `TUNE_CPU=none` bypasses both native tuning scripts. The five syscall probes are nonfatal `check_cxx_source_compiles` checks, and the API wrapper selects its Apple branch; their Darwin runtime behavior remains **UNVERIFIED**. The retained `Arm64.cpp` guard is required because `FEX_IOS_HOST` is used in native iOS compilation while that diagnostic names Windows APIs. `git -C FEX apply --check ../patches/fex-darwin.patch` passed.

**Stubs:** no new stubs were introduced. The log fallback only omits Windows memory-region metadata.

**Current blocker:** FEXCore has not yet been confirmed compiling on Darwin; run `38644632372` remains unknown beyond its one `in_progress` observation.

**Next step:** Add stage-only dispatch for `fex-ios`, explicitly report cache restore hit/miss, and make the stage-only path require a restored toolchain cache without running the LLVM bootstrap. Preserve the existing artifact publication gate.

### Step 4 complete

**Done:** Commit `712e358` adds `workflow_dispatch.only_stage` (`all` or `fex-ios`), cache restore hit reporting with an exact-hit requirement for the FEX-only dispatch, and a `scripts/build-ipa.sh` branch that initializes only FEX sources, skips LLVM bootstrap and unrelated build stages, then exits after FEX iOS. The existing `make -k -j$(sysctl -n hw.ncpu)` plus sorted unique compiler error report stays in `build/fex-ios/build.sh`. Updated `PROGRESS.md`; its cache restore status remains **UNVERIFIED** until runner output.

**Gate:** The artifact upload conditions and `WINEPHONE_BINARY_RELEASE_CLEARED` value were left unchanged. `DECISIONS.md` was not modified.

**Validation limits:** Git diff checks pass. This host lacks Bash and PyYAML, so shell syntax and local workflow YAML parsing are **UNVERIFIED**. Workflow dispatch semantics, exact cache restore, FEX source fetch, and stage behavior also remain **UNVERIFIED** until CI.

**Current blocker:** FEXCore Darwin configure/compile result is unknown. Run `38644632372` had one observed `in_progress` status and was not polled.

**Next step:** Commit and push the complete stage-limited FEX fix as the single non-`[skip ci]` change, launch one `fex-ios` dispatch, and inspect that run once.

### Resumed in the cloud worktree (2026-10-14)

**Step 0 — done.** Fetched `handoff/fex-darwin-configure` (branch HEAD `39e6c03`). Its `docs/HANDOFF.md` is a strict subset of main's: `git diff HEAD origin/handoff/fex-darwin-configure -- docs/HANDOFF.md` shows 42 deletions and **0 insertions** main→branch, so the "copy HANDOFF.md onto main" requirement is already satisfied and no content is lost. The handoff branch diverged at `d218a37`; main carries nine commits it does not (`dc95674`..`b1f0696`).

**Step 1 — BLOCKED; the failed log could not be read from this worktree.** Run `38644632372` (commit `bb733f6`) failed after 11m22s, but:

- `gh` is not installed here and there is no GitHub token in the environment;
- the unauthenticated REST API returns `HTTP 403 {"message":"API rate limit exceeded ..."}` for IP `208.72.218.131` (core `60/60` used, reset `22:48:03Z`);
- GitHub's Actions log download endpoint requires authentication regardless.

**No log has been read, and no first error or `error:` list is recorded yet.** Requested from the user: `gh run view 38644632372 --repo MayoMusic/winephone --log-failed` (or the `FEX compiler error summary:` block plus the first `error:` line). This is the decisive input for Step 4 and is not guessed here.

**Step 2/3 finding — `FEX_IOS_HOST` should not be defined for the native `fex-ios` build.** Read locally at the exact pins (FEX `f59cab95659e8add0c88f0c76ec1cf483c536dbf`, Madeira root `279fd0f83170425db002fe25d6bd62f6355f497d`):

1. Madeira's own `build/fex-ios/build.sh` (the tree WinePhone is forked from) passes **neither** `FEX_IOS_HOST_BUILD` nor `FEX_IOS_HOST` — only `CMAKE_SYSTEM_NAME=iOS`, `CMAKE_OSX_ARCHITECTURES=arm64`, the SDK/target/build-type, the `BUILD_*`/`ENABLE_*` options, and `cmake --build ... --target FEXCore FEXCore_Base`.
2. Madeira passes those two flags **only** in the two Windows-PE-module scripts: `build/fex-wow64/build.sh:15-16` (comment: "The options are the iOS host build's") and `build/fex-arm64ec/build.sh:22-23`.
3. The fork's own comment at `FEX/FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:719` states the intent outright: *"VirtualQuery exists only in the FEX_IOS_HOST (Windows module) builds; the native iOS FEXCore build (build/fex-ios) reports without the region."* That is exactly the `#ifdef FEX_IOS_HOST` block whose `MEM_IMAGE`/`MEM_MAPPED`/`MEM_PRIVATE`/`VirtualQuery` use is a Darwin compile error — a parse error that only exists because WinePhone (unlike Madeira) defined the macro here.
4. No CMake file in the pinned FEX tree defines `FEX_IOS_HOST`; it is purely a command-line define (`grep` over every `CMakeLists.txt`/`*.cmake` returns only `FEX_IOS_HOST_BUILD` at `FEX/CMakeLists.txt:123`).
5. The app target compiles the same FEXCore headers **without** the macro: `app/Madeira.xcodeproj/project.pbxproj:831` sets `GCC_PREPROCESSOR_DEFINITIONS = ("DEBUG=1", "$(inherited)")`, and `app/Madeira/FEXBridge.mm:21-22` includes `<FEXCore/Utils/AllocatorHooks.h>` and `<FEXCore/Utils/DualMap.h>`, both `FEX_IOS_HOST`-sensitive. Building `libFEXCore.a` with the macro while the app compiles those headers without it is a macro/ODR mismatch.

**Fix applied (intermediate commit, `[skip ci]`).** `build/fex-ios/build.sh` no longer passes `FEX_IOS_HOST_BUILD=ON` or `-DFEX_IOS_HOST` on C/C++/ASM, matching Madeira's recipe; `patches/fex-darwin.patch` is deleted because its only hunk guarded a Windows-API diagnostic that is no longer reached. Kept: `CMAKE_SYSTEM_PROCESSOR=arm64` (the runner's CMake otherwise leaves it empty → "Unsupported processor type .") and `TUNE_CPU=none` (Madeira's ARM64EC script sets `TUNE_CPU` for the same reason), plus `make -k` and the sorted `error:` summary.

**Reverted.** Run `38644632372` then showed the `fex-ios` stage **passing** with the flags and patch in place, so this change is reverted: `build/fex-ios/build.sh` and `patches/fex-darwin.patch` are back to the `bb733f6` state and FEX is not touched. The recipe finding is kept as a note in `docs/MADEIRA_RECIPE.md`, not as a change.

**Step 1 (still) — the log was not read.** The user supplied the stage and failure summary instead (see below); this worktree still cannot fetch Actions logs (no `gh`/token). Recorded from their report, not from a log this agent read.

**UNVERIFIED:** the actual failing error for `bb733f6` (log not read); whether removing `FEX_IOS_HOST` lets FEXCore configure and compile on Darwin; cache restore; IPA/device behaviour.

**Next step:** user pastes the failed log; record its first error and full `error:` list here, then commit the fix as the single non-`[skip ci]` change and read the one resulting run.

### Run 38651245572 recorded (2026-10-14)

**Input:** the user reported run `38651245572` (`only_stage=wine-ntdll-unix`, commit `62f3269`) as `31 OK / 6 FAILED` — four missing prerequisite trees plus one SDK field. This agent still cannot read Actions logs (no `gh`/token, REST 403) or dispatch a workflow, so these are their report, not a log this agent read.

**Done in this change set (`[skip ci]`, one commit):**

- the `only_stage=wine-ntdll-unix` path runs the `gnutls` and `ffmpeg` stages before `wine-macos`/`wine-ntdll-unix` (`scripts/build-ipa.sh:68-69`), so `toolchains/gnutls-ios` and `toolchains/ffmpeg-ios` exist like they do in the full path;
- FreeType is a separate, pinned build with its **own** cache key (`.github/workflows/build-ipa.yml:88-113`) — `build/freetype-ios/build.sh` clones tag `VER-2-13-3` and verifies the annotated tag's commit `42608f77f20749dd6ddc9e0536788eaad70ea4b5` — leaving the `winephone-macos26-llvm-…` cache key (and the `~35`-minute LLVM build) untouched;
- `build/ntdll-unix/build.sh:26-73` prints the full include-path diagnostic before compiling, including the toolchain cache-hit value (`WINEPHONE_TOOLCHAIN_CACHE_HIT`, passed by the workflow);
- `server_ios.c` no longer reads `ri_page_wait_time_mach` (absent from `rusage_info_v6` in the iPhoneOS 26.5 SDK): the statistic is dropped from the `[xp]` line and `pin=` is kept;
- the wall after these six is recorded as B-010: `dwrite_unixlib` and `winegstreamer_unixlib` need the widl-generated `dwrite_3.h`/`d2d1.h`/`mfobjects.h`, which exist only in a *built* Wine tree (`wine/tools/makedep.c:2004-2009`; widl is a build product), and `build/wine-macos/configure.sh` now generates them after configure — best-effort and logged;
- `docs/MADEIRA_RECIPE.md` Step 7 records the comparison with Madeira's `docs/BUILDING.md` at `279fd0f` (which has GnuTLS and FFmpeg as its first two steps at `:33-42` but no FreeType and no Wine build tree among its inputs at `:17-25`), plus `BLOCKERS.md` B-008/B-009/B-010 and `PROGRESS.md`.

**Not touched:** FEX (`build/fex-ios/build.sh`, `patches/fex-darwin.patch` stay at `bb733f6`), `DECISIONS.md`, the `WINEPHONE_BINARY_RELEASE_CLEARED` release gate.

**Current blocker:** the stage cannot be re-run from this worktree (no dispatch, no logs), and the new make-based header generation plus the unix compiles are **UNVERIFIED**.

**Next step:** dispatch `only_stage=wine-ntdll-unix` once more and paste (a) the `ntdll unix header diagnostic` block, (b) the `widl-generated public headers` block (or the `make -C include` failure tail), and (c) the `Results:`/`Failed:` line. Those three decide whether the generation works and whether the compiles then pass.

### Resumed with log access (2026-10-16)

**Capability change:** `gh` is authenticated as `MayoMusic` (`repo`, `workflow`). Logs can now be read directly and workflows dispatched, which the previous session could not do. Everything below comes from downloaded logs, not a user report.

**Answered:** `cache restore` is **VERIFIED** — run `38727641709` printed `Pinned toolchain cache exact-key hit: true` and `Pinned FreeType cache exact-key hit: true`. A full run is ~13 min.

**B-008/B-009/B-010 closed by evidence.** Run `38727641709` reached and passed `gnutls`, `ffmpeg`, `fex-ios`, `fex-arm64ec`, `wine-macos` configure and widl header generation; `wine-ntdll-unix` reported `Results: 37 succeeded, 0 failed` and produced `libntdll_unix.a` (2,373,192 bytes). It failed on the next stage's first line. The Wine configure "development files not found" lines are optional-feature probes, not the failure.

**Current blocker: B-011.** `ERROR: No base libwineserver.a found`. `app/Madeira/libwineserver.a` is git-ignored by Madeira (`.gitignore:33`) and produced by nothing — `wine/server/Makefile.in` builds only the `wineserver` program, and `git grep libwineserver` over all of Madeira at `279fd0f` hits only `build/wineserver/build.sh`, `.gitignore` and three `app/` references. Madeira's own clean checkout cannot pass this step either.

**Done in this change set:** `build/wineserver/build.sh` builds the base from all 44 `wine/server/*.c` with the existing `CC_FLAGS` when no base exists, with a `BASE_SKIP` array and an all-failures-at-once failure path; `.gitignore` ignores `build/wineserver/base/`; `scripts/build-ipa.sh` and the workflow gain an `only_stage=wineserver` path (wine submodule + `wine-macos` configure + wineserver only).

**Not verified:** whether all 44 sources compile for iOS. `BASE_SKIP` is expected to need at least one entry. Local checks only: `bash -n` on both scripts, workflow YAML parse, the `set -e` empty-array path, and the 44-source failure path under a stub `xcrun`.

**Next step:** dispatch `only_stage=wineserver` once. If it reports `ERROR: base libwineserver.a incomplete`, add exactly those names to `BASE_SKIP` with their compiler errors — do not guess the list. If the stage passes, the next unproven stage is `win32u-unix`.
