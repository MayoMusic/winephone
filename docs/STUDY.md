# Madeira source study (initial audit)

Status: partial. Source evidence refers to Madeira commit
`279fd0f83170425db002fe25d6bd62f6355f497d`; submodule evidence is pinned in
`docs/SOURCES.md`. This is not a runtime test report.

## Architecture confirmed from the base README

The stated stack is FEX x86/x86-64-to-ARM64 translation, ARM64EC Wine 11.4,
DXMT for D3D9/10/11 to Metal, and an in-process wineserver thread. The README
also identifies a separate Madeira D3D12 implementation. WinePhone's current
plan excludes that D3D12 path because its documented build uses Apple's Metal
Shader Converter and needs separate license review.

## Build and source observations

- `README.md` says Madeira's Wine/FEX/DXMT submodules are project forks and
  upstream checkouts do not build for iOS.
- `.gitmodules` pins the FEX, Wine, DXMT, and madeira-dock repositories; the
  exact commit IDs are recorded in `docs/SOURCES.md`.
- `docs/BUILDING.md` documents separate iOS unix-side and ARM64EC PE build
  chains, a final Xcode project build, missing toolchain inputs, and several
  steps not reproduced from a clean checkout.
- `docs/LICENSING.md` records static LGPL libraries and an unverified
  clean-machine relink path. This is a release gate, not a resolved claim.
- `tools/fetch-vcruntime.md` explicitly requires the user to supply Microsoft
  runtime DLLs; WinePhone will not add them to source or artifacts.

## Missing reference material

The requested `ARCHITECTURE_ANALYSIS.md` and `STEAM_CEF_HANDOFF.md` do not
exist in this checkout at the base commit. The current equivalent source is
the README, `docs/BUILDING.md`, `docs/JIT.md`, `docs/MADEIRA_DOCK.md`, and the
component build scripts. No undocumented estimates from the supplied project
brief are treated as measurements.

## Source paths inspected

- `build/ntdll-unix/process_ios.c` has an iOS-specific child-thread entry and
  `pthread_create` path under `WINE_IOS`; the ordinary fork/exec path is in the
  alternate branch. `__wine_unix_spawnvp` reports unsupported on iOS.
- `build/wineserver/main_ios.c` wraps Wine's server main, removes the idle
  timeout, and enters the request loop from the app-created thread.
  `app/Madeira/WineServerBridge.m` passes `--foreground`, which makes
  `build/wineserver/request_ios.c` skip its fork branch. This confirms the
  intended source path, not that all child-process use cases work.
- `app/Madeira/JITAllocator.c` requests one Mach memory entry and maps separate
  RW/RX aliases. It requests `VM_LEDGER_FLAG_NO_FOOTPRINT` and logs failure as
  non-fatal; source comments do not prove that iOS grants the behavior.
- `app/Madeira/FEXBridge.mm` passes the JIT pool aliases; FEX's ARM64EC module
  reads `WINE_IOS_JIT_RX`, `WINE_IOS_JIT_SIZE`, and `WINE_IOS_JIT_RW` in
  `FEX/Source/Windows/ARM64EC/Module.cpp`.
- `app/Madeira/IOSDisplayShim.m` exports a `macdrv_functions` bridge backed by
  `CAMetalLayer`; DXMT's `dxmt/src/winemetal/unix/winemetal_unix.c` uses
  `MTLCreateSystemDefaultDevice()` and iOS conditionals.
- `app/Madeira.xcodeproj/project.pbxproj` referenced an absent VC++ runtime
  folder and copied the D3D12 directory. WinePhone removes those resource
  inputs; custom D3D12 binaries were removed from the ARM64EC farm.

These findings are source-level only. The Madeira/app paths above are at
`279fd0f83170425db002fe25d6bd62f6355f497d`; FEX is
`f59cab95659e8add0c88f0c76ec1cf483c536dbf`; DXMT is
`128b297c6e9a00014408dc68b4c2c2373b5813de`.

## Not yet audited or tested

FEX exception handling beyond the initial grep; full Wine Unix-call behavior;
DXMT feature matrix and shader translation; app lifecycle, input and audio;
Steam helper behavior; complete PE System32 inventory; Winlator/GameHub/PPSSPP
reference studies; macOS clean build; any game binary or on-device behavior.

## Ranked build/runtime gaps (initial)

1. **Build reproducibility:** cold LLVM and all component builds are untested;
   the runner must prove the recipe and available disk/time.
2. **iOS 27 JIT:** pairing, debugger protocol, signing entitlements, and code
   memory behavior are source-described only. **VERIFY:** device run.
3. **License/relink:** parent Wine notices conflict with the fork's LGPL file;
   static LGPL relinking has not been reproduced.
4. **Game compatibility:** no title name or PE/import corpus was provided; no
   DRM screening or game-specific trace exists.
5. **D3D12 and no-JIT:** custom D3D12 is excluded; AOT/no-JIT Track B is only a
   research proposal and has no prototype.
