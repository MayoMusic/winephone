# FEX Darwin configure and component audit

## Step 1 — dependency map

**Question:** Which Linux assumptions interfere with configuring or building the pinned FEX iOS target?

**Source:** FEX submodule commit `f59cab95659e8add0c88f0c76ec1cf483c536dbf` (WinePhone parent before this note: `10ef48c`). This is the exact commit requested. `git -C FEX rev-parse HEAD` returned the same hash.

**Method:** Read the relevant CMake and Python sources and searched FEX with `rg` for `/proc`, `/sys`, `syscall`, `SYS_*`, `ptrace`, futex, clone, `MAP_32BIT`, signalfd, Linux headers, rseq and perf events. This Windows host has no Xcode/iOS SDK, so Darwin CMake configure and compilation cannot be reproduced locally. Do not treat the source audit as a build test.

### Configure-time host assumptions

| Location | Use | Classification |
|---|---|---|
| `FEX/CMakeLists.txt:516-537` | `TUNE_CPU=native` invokes `aarch64_fit_native.py` with `/proc/cpuinfo`, strips its output into a `-mcpu=` argument, and runs `NeedDisabledSVE.py`, which also reads `/proc/cpuinfo`. | Configure-time; this is the fatal path observed in the prior run. |
| `FEX/Scripts/NeedDisabledSVE.py:11-52` | Reads `/proc/cpuinfo` for feature and MIDR data. | Configure-time helper; uncaught missing-file errors on Darwin. |
| `FEX/FEXHeaderUtils/CMakeLists.txt:5-56` | `check_cxx_source_compiles` probes getcpu, gettid, tgkill, statx, renameat2. | Configure-time feature checks. A failed optional check is not itself a CMake fatal error; on Darwin the wrappers in `FEX/FEXHeaderUtils/FEXHeaderUtils/Syscalls.h:60-86` select Apple implementations for getcpu/gettid/tgkill. |
| `FEX/CMakeLists.txt:560-602` | Runs `nproc` only when tests are enabled and resolves source metadata through Git. | Configure-time, but tests are disabled in the iOS build; Git metadata is available after checkout. |

### Compile-time and runtime host assumptions

| Location | Use | Classification and target impact |
|---|---|---|
| `FEX/CMakeLists.txt:581-596` | Skips `Source/` entirely when CMake reports `APPLE`. | Target exclusion: Linux tools, guest ELF process loader and Linux syscall-emulation executable are not built in the Apple configuration. |
| `FEX/Source/Tools/LinuxEmulation/LinuxSyscalls/` (for example `x64/Thread.cpp:23,210-222` and `x32/Thread.cpp:23,210-222`) | Linux syscall translation, futex, ptrace, signalfd, rseq and perf syscall tables, Linux UAPI headers, and host `syscall()` calls. | Compile-time if `Source/` is enabled; the Apple CMake guard excludes it. |
| `FEX/Source/Tools/FEXInterpreter/ELFCodeLoader.h:763-769` and `FEX/Source/Tools/FEXInterpreter/CMakeLists.txt:79-98` | ELF guest loading and Linux binfmt_misc integration use `/proc` and `/proc/sys/fs/binfmt_misc`. | Compile/runtime Linux-only launcher path; the Apple CMake guard excludes `Source/`. |
| `FEX/FEXCore/include/FEXCore/Utils/InterruptableConditionVariable.h:8-15,58-100` | Selects Linux futex or Apple `os_unfair_lock`/pthread condition-variable implementation by platform macro. | Compile-time conditional; Apple implementation exists. |
| `FEX/FEXCore/include/FEXCore/Utils/WritePriorityMutex.h:5-17` | Selects Linux futex definitions or Apple lock headers. | Compile-time conditional; Apple path exists, but runtime semantics need a test. |
| `FEX/FEXCore/include/FEXCore/Utils/SignalScopeGuards.h:164-184` | Uses Linux `SYS_rt_sigprocmask` only under `__linux__`, and POSIX signal APIs under `__APPLE__`. | Compile-time conditional; Apple path exists. |
| `FEX/FEXCore/Source/Interface/Core/CPUBackend.cpp:14-16` and `FEX/FEXCore/include/FEXCore/Utils/PrctlUtils.h:4-30` | Linux prctl headers/operations are conditionally compiled; the header has a non-Linux branch. | Compile-time conditional; audit confirms a fallback branch, not its runtime completeness. |
| `FEX/FEXCore/Source/Utils/Allocator.cpp:231-233` | `StealMemoryRegion` parses `/proc/self/maps`. | Runtime Linux-specific function; source audit alone does not prove the iOS path avoids it. |
| `FEX/FEXCore/Source/Interface/Core/JIT/MiscOps.cpp:10-16,275-281` | Emits the guest ARM64 Linux `getcpu` syscall instruction/number for translated guest behavior. | Compile-time guest-instruction generation, not a host `syscall()` probe. Whether this is appropriate for the Wine iOS syscall callback needs integration testing. |
| `FEX/Source/Common/HostFeatures.cpp:21-36` and `FEX/Source/Common/CPUInfo.cpp:12-20` | Linux host feature detection reads `/sys/devices/system/cpu`; the iOS fork has comments/adaptation for missing sysfs. | Source/ host layer is excluded by the Apple guard; not part of the selected FEXCore static target. |
| `FEX/Source/Tools/FEXBash/FEXBash.cpp:58`, `FEX/Source/Tools/FEXServer/ProcessPipe.cpp:69-88`, and `FEX/Source/Common/FDUtils.h:7-14` | Linux tools use `/proc/self/exe`, `/proc/self/fd`, or Linux limits headers. | Tool/runtime paths; `Source/` is excluded for Apple. |

### Scope boundary and stubs

The iOS build script requests only the static `FEXCore` and `FEXCore_Base` targets; FEX's root CMake guard excludes `Source/` on Apple, and `BUILD_THUNKS=OFF` excludes thunks. This means the configure-only patch below does not bring in the Linux syscall emulator or ELF launcher.

No new stub implementation has been added. In particular, WinePhone's Darwin/Wine callback for guest syscalls, Linux `statx`/`renameat2` equivalents, and the FEXCore allocator's `/proc/self/maps` path are not proven stubbed by this audit. These are explicit integration gaps, not silently treated as supported. A Darwin JIT smoke test and iOS debugger-attached JIT test are also not run here.

### Result

The named configure failure has a narrow source-level fix: the iOS build command disables build-host CPU auto-tuning with `-DTUNE_CPU=none` (`build/fex-ios/build.sh:16`, parent commit `10ef48c`), and the WinePhone patch below makes the SVE helper tolerate missing `/proc`, querying `hw.optional.arm.FEAT_SVE` on Darwin when available. The syscall checks are optional feature probes; the patch guards them so Darwin records all five Linux syscall capabilities as unavailable instead of attempting Linux-oriented detection. Patch applicability can be tested against the exact submodule commit on this host; actual Darwin configuration and compile behavior require the configured macOS GitHub runner.

**Unverified:** Apple's `hw.optional.arm.FEAT_SVE` availability/value on the selected macOS runner. Verify by running `sysctl -n hw.optional.arm.FEAT_SVE` there; absence is handled as no SVE feature by the patch.

## Step 2 — Darwin configure patch

**Change:** `patches/fex-darwin.patch` is applied to the pinned FEX checkout by `build/fex-ios/build.sh` before CMake runs. It is a patch series artifact outside the submodule; no vendored FEX source is committed as an in-place edit. The script checks whether the patch is already applied so repeated local invocations remain safe.

**Patch behavior:**

- `NeedDisabledSVE.py` catches missing `/proc/cpuinfo`; on Darwin it queries `sysctl -n hw.optional.arm.FEAT_SVE`. Missing/unsupported sysctl returns an empty feature list, and absent `/proc` means no Snapdragon MIDR table match.
- `FEXHeaderUtils/CMakeLists.txt` runs getcpu/gettid/tgkill/statx/renameat2 feature probes only for `CMAKE_SYSTEM_NAME=Linux`. Other systems define all five `HAS_SYSCALL_*` values as false; the Apple-specific pthread wrappers are already selected by `Syscalls.h`.
- The iOS FEX build passes `TUNE_CPU=none`, avoiding both Linux `/proc/cpuinfo` scripts and host-specific CPU tuning during an ARM64 cross-build.

**Verification on this Windows host:** `git -C FEX apply --check ../patches/fex-darwin.patch` passed against FEX commit `f59cab95659e8add0c88f0c76ec1cf483c536dbf`. The patch was temporarily applied and reversed to run the helper with mocked Darwin/sysctl results; positive SVE, negative SVE, and missing-proc paths passed. This does not prove CMake configures or FEXCore compiles on Darwin. A local Xcode/iOS SDK is unavailable.

## Step 3 — static FEXCore boundary and outstanding stubs

The existing `build/fex-ios/build.sh` requests static targets `FEXCore` and `FEXCore_Base` only. The pinned root `FEX/CMakeLists.txt:581-596` excludes `Source/` for Apple, which excludes the Linux syscall-emulation executable, its Linux host syscalls, and the FEX ELF guest loader. `BUILD_THUNKS=OFF` excludes Wine/Windows thunks. The chosen static target includes x86 decode/IR/JIT code and its base utilities; the FEX header/IR generators and support libraries remain required dependencies.

**Stub inventory:** no new FEX stub bodies are added in this step. The excluded Linux syscall emulator and ELF loader are omitted rather than replaced; FEXCore is a library and is not a standalone guest runner. Guest syscall delivery must be supplied by the Wine integration callback. Linux-specific facilities still referenced by FEXCore utilities include `/proc/self/maps` in `FEX/FEXCore/Source/Utils/Allocator.cpp:231-233` and Linux syscall-number emission for guest `getcpu` in `FEX/FEXCore/Source/Interface/Core/JIT/MiscOps.cpp:275-281`; whether iOS avoids or replaces those paths is not yet demonstrated. These are next compile/integration blockers, not claimed stubs.

**Unverified:** the FEXCore-only target completes on the selected macOS/iOS SDK. The active CI run from parent commit `10ef48c` predates patch application and is not used as evidence for this step. No Fibonacci execution test or iOS debugger-attached JIT test has been run. The latter remains explicitly unverified; verify on the iPhone 17 with the selected iOS and sideload debugger tooling after an IPA exists.

## Step 4 — Darwin FEXCore compile audit and compile-error collection

**Source/pin:** FEX `f59cab95659e8add0c88f0c76ec1cf483c536dbf`; WinePhone main before this fix `d218a37`. This is a static source audit on Windows; no Darwin compiler is available locally. Line references below are relative to the pinned FEX tree.

**Compile hazard fixed in `patches/fex-darwin.patch`:** `FEX/FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:707-712` selected `VirtualQuery`, `MEMORY_BASIC_INFORMATION`, and `MEM_IMAGE`/`MEM_MAPPED`/`MEM_PRIVATE` under `FEX_IOS_HOST` alone. The iOS static FEXCore build also defines `FEX_IOS_HOST`, but is not a Windows PE build. The condition now requires both `FEX_IOS_HOST` and `_WIN32`; Darwin uses the adjacent short diagnostic that does not query Windows region metadata. The diagnostic is nonfunctional metadata only; no memory-management behavior is stubbed.

**Scan inventory (Darwin compile-time status):**

| Location | Finding | Classification |
|---|---|---|
| `FEX/FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:707-712` | Windows `VirtualQuery` and `MEM_*` identifiers used in the iOS diagnostic branch. | Compile-time failure on Darwin; fixed by the patch above. |
| `FEX/FEXCore/include/FEXCore/Utils/AllocatorHooks.h:7-196` | Windows allocation constants/APIs (`MEM_*`, `VirtualAlloc*`, `VirtualQuery`) occur in the `_WIN32` implementation branch. | Platform-conditional; not selected by Darwin. Confirmed source branch only; Darwin compiler still needs to verify. |
| `FEX/FEXCore/include/FEXCore/Utils/File.h:12,27-...` | `<windows.h>` and Win32 file APIs are in the `_WIN32` branch. | Platform-conditional; POSIX file implementation selected on Darwin. |
| `FEX/FEXCore/Source/Utils/Allocator.cpp:23-26,38-310` | Linux headers and `/proc/self/maps` (`:231-232`) are within the `__linux__` implementation. | Compile-time excluded on Apple; Apple implementation begins at `:311`. |
| `FEX/FEXCore/Source/Utils/Allocator.cpp:319-352` | Apple allocator reports `StealMemoryRegion` unsupported (`return {}`), `Setup48BitAllocatorIfExists` empty, `VirtualName` no-op, and fork hooks empty. | Existing compile-time Darwin stubs; no new stub introduced. 48-bit VA reservation is intentionally unavailable on Apple. Runtime suitability remains UNVERIFIED. |
| `FEX/FEXCore/include/FEXCore/Utils/PrctlUtils.h:4-...` | `<linux/prctl.h>` and Linux operations are under `__linux__`; Apple branch defines compatibility constants and `prctl(...) { return -1; }`. | Existing Darwin stub; callers must tolerate unsupported `prctl` operations. This audit does not prove each caller does. |
| `FEX/FEXCore/include/FEXCore/Utils/InterruptableConditionVariable.h:8-15,40,70,74-...` | Linux futex header and `syscall(SYS_futex, ...)` vs Apple pthread/lock path. | Linux calls compile only in `__linux__` branch; Apple implementation exists. Runtime behavior UNVERIFIED. |
| `FEX/FEXCore/include/FEXCore/Utils/WritePriorityMutex.h:6-11,351-...` | Linux futex/syscall branch and Apple lock/spin implementation. | Platform-conditional; Apple implementation exists. Runtime behavior UNVERIFIED. |
| `FEX/FEXCore/include/FEXCore/Utils/SignalScopeGuards.h:164-184` | Linux `SYS_rt_sigprocmask` vs Apple POSIX signal calls. | Platform-conditional; Linux syscall code is excluded on Apple. |
| `FEX/FEXCore/Source/Interface/Core/CPUBackend.cpp:14-16` | Linux `prctl` header. | `__linux__` conditional include. |
| `FEX/FEXCore/Source/Utils/Profiler.cpp:5` | Linux magic header. | `__linux__` conditional include. |
| `FEX/FEXCore/Source/Interface/Core/JIT/MiscOps.cpp:12-13,275-281` | `SYS_getcpu` numeric constant emitted for the translated guest operation. | Guest syscall instruction/number generation, not a Darwin host syscall dependency. Wine guest-syscall integration remains UNVERIFIED. |
| `FEX/FEXCore/unittests/APITests/FileLoading.cpp:14,21` | Unit test reads `/proc/self/maps`. | Test-only Linux assumption; `BUILD_TESTING=OFF`, so excluded from this target. |
| `FEX/FEXCore/Source/Interface/Core/Dispatcher/Dispatcher.cpp:876-888`; `.../JIT/JIT.cpp:540,560,669,691,1405` | `sys_icache_invalidate` in Apple branches, with separate FEX iOS / PE paths nearby. | Conditional/platform path; source audit indicates Apple-native calls are guarded by `__APPLE__`, but mixed target macro behavior needs Darwin compilation. UNVERIFIED. |

The remaining `rg` hits for `syscall`, `<linux/...>`, `/proc`, `MEM_*`, `VirtualQuery`, and `<windows.h>` are accounted for above. FEX root CMake also excludes its Linux `Source/` launcher/syscall emulation when `APPLE` is true (existing `docs/RE_NOTES.md` Step 1); this build asks for `FEXCore` and `FEXCore_Base`, not the Linux ELF loader or Linux syscall emulator. That is evidence of the intended target boundary, not proof that the full iOS app integration is complete.

**Existing stubs to preserve/document:** (1) Apple `prctl` returns `-1` in `PrctlUtils.h`; (2) Apple allocator VA-stealing returns an empty region list and its VA-name/fork hooks are no-ops in `Allocator.cpp`; (3) Apple syscall-feature probes are defined false by `patches/fex-darwin.patch`. The last item is a feature-probe fallback, not an implementation of Linux syscalls. The new `Arm64.cpp` short diagnostic only omits Windows region metadata; it is not a behavior stub.

**Build diagnostics change:** `build/fex-ios/build.sh` now invokes `make -k -j"$(sysctl -n hw.ncpu)"` for the two static targets, saves output to `FEX/build-ios/build.log`, prints `grep -E "error:" ... | sort | uniq -c`, then returns Make's status. This is intended to collect independent compile errors in one runner execution. It has not yet been exercised on macOS.

**Verification status:** `git -C FEX apply --check ../patches/fex-darwin.patch` passes against the pinned submodule. Darwin compile, complete error inventory, static-library output, the requested x86-64 Fibonacci JIT execution, macOS `MAP_JIT` behavior, and iOS debugger-attached JIT are all **UNVERIFIED**. The active workflow run `38643156359` was observed once as `in_progress`; per instruction it was not polled and no result is claimed.

## Step 5 — retraction: `FEX_IOS_HOST` is the Windows-PE-module define; patch deleted

**Source/pin:** FEX `f59cab95659e8add0c88f0c76ec1cf483c536dbf`; Madeira root `279fd0f83170425db002fe25d6bd62f6355f497d`. The local FEX submodule was checked out at the pin for this reading (`git -C FEX rev-parse HEAD` = the pin).

**Corrected finding.** Step 4's "the iOS static FEXCore build also defines `FEX_IOS_HOST`" premise is wrong. `FEX_IOS_HOST` (and `FEX_IOS_HOST_BUILD`) is the Windows-PE-module flavour of the iOS host:

- Madeira defines them only in `build/fex-wow64/build.sh:15-16` and `build/fex-arm64ec/build.sh:22-23` (both `toolchain_mingw.cmake` / MinGW builds). Madeira's `build/fex-ios/build.sh` defines neither.
- `FEX/FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:719` (pinned, unmodified) says: *"VirtualQuery exists only in the FEX_IOS_HOST (Windows module) builds; the native iOS FEXCore build (build/fex-ios) reports without the region."* So the block guarded by `#ifdef FEX_IOS_HOST` at `:707` is **not** part of the native library, and WinePhone's `-DFEX_IOS_HOST` is what pulled `MEMORY_BASIC_INFORMATION`/`VirtualQuery`/`MEM_*` into a Darwin compile.
- No `CMakeLists.txt`/`*.cmake` in the pin defines the macro; `FEX/CMakeLists.txt:123` is `FEX_IOS_HOST_BUILD`, which only selects `ENABLE_GUEST_WINDOW` (`:124-128`).
- The native library's iOS behaviour comes from `__APPLE__`: `FEXCore/include/FEXCore/Utils/DualMap.h:7`, `CodeEmitter/CodeEmitter/Buffer.h:25,120`, `FEXCore/Source/Interface/Core/JIT/JIT.cpp:995,1316` all read `defined(__APPLE__) || defined(FEX_IOS_HOST)`.
- The app compiles the same headers without the macro — `app/Madeira.xcodeproj/project.pbxproj:831` is `GCC_PREPROCESSOR_DEFINITIONS = ("DEBUG=1","$(inherited)")`, and `app/Madeira/FEXBridge.mm:21-22` includes `AllocatorHooks.h` and `DualMap.h` — so defining the macro in the library is also a macro/ODR mismatch with its consumer.

**Action:** `build/fex-ios/build.sh` drops `FEX_IOS_HOST_BUILD=ON` and `-DFEX_IOS_HOST` from the C/C++/ASM flags, matching Madeira. `patches/fex-darwin.patch` is **deleted** (its single hunk is unreachable without the macro and unnecessary in the MinGW build where `_WIN32` is defined). No source guard is added, because the recipe needs none once the flag is removed. `TUNE_CPU=none`, `CMAKE_SYSTEM_PROCESSOR=arm64`, `make -k` and the sorted `error:` summary are unchanged.

**UNVERIFIED:** Darwin configure/compile with the corrected flags; the failed log of run `38644632372`, which this worktree could not read (no `gh`, no token, REST API HTTP 403 rate-limited). The fix is recipe-derived, not log-confirmed.

