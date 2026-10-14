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

The named configure failure has a narrow source-level fix: disable build-host CPU auto-tuning for the generic iOS ARM64 target and make the SVE helper tolerate missing `/proc`, querying `hw.optional.arm.FEAT_SVE` on Darwin when available. The syscall checks are optional feature probes and should be guarded so Darwin records all five Linux syscall capabilities as unavailable instead of attempting Linux-oriented detection. Patch applicability can be tested against the exact submodule commit on this host; actual Darwin configuration and compile behavior require the configured macOS GitHub runner.

**Unverified:** Apple's `hw.optional.arm.FEAT_SVE` availability/value on the selected macOS runner. Verify by running `sysctl -n hw.optional.arm.FEAT_SVE` there; absence is handled as no SVE feature by the patch.

