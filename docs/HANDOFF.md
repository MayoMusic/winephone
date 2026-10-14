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
