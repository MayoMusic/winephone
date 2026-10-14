# Modification catalog

Paths are in the WinePhone checkout; source commit IDs identify the audited
source version. A source match or static artifact check is not runtime proof.

| ID | Area | Type | Change | Source/evidence | Validation/status |
|---|---|---|---|---|---|
| M-001 | Identity/license | BUILD/POLICY | Establish WinePhone description, GPL choice explanation, and release gates | Madeira base `279fd0f83170425db002fe25d6bd62f6355f497d`; `README.md`, `LICENSE`, `docs/LICENSING.md` | Drafted locally; GitHub auth still required |
| M-002 | CI/toolchain | BUILD | Pin macOS build sources; create combined DXMT archive on a clean build; package unsigned IPA | `scripts/bootstrap.sh`, `scripts/build-ipa.sh`, `.github/workflows/build-ipa.yml`; base `279fd0f83170425db002fe25d6bd62f6355f497d`, LLVM `8dfdcc7b7bf66834a761bd8de445840ef68e4d1a` | Shell syntax/artifact gates pending; no macOS run |
| M-003 | D3D12 | BUILD/POLICY | Exclude Metal Shader Converter and custom Madeira D3D12 release binaries; retain Wine builtin stub | `build/dxmt-ios/build.sh`, `app/Madeira.xcodeproj/project.pbxproj`, removed farm binaries; base `279fd0f83170425db002fe25d6bd62f6355f497d` | Changes staged/local; IPA not built; D3D12 unsupported |
| M-004 | Microsoft runtime | BUILD/POLICY | Remove absent user-supplied x86_64 runtime folder from Xcode resources; verify similarly named farm files are Wine builtins | `app/Madeira.xcodeproj/project.pbxproj`; ARM64/ARM64EC DLL farms; base `279fd0f83170425db002fe25d6bd62f6355f497d` | Static marker check observed; package gate added; clean CI pending |
| M-005 | Process/server | ARCH/RESEARCH | Reuse iOS thread-backed process creation and in-process foreground wineserver | `build/ntdll-unix/process_ios.c`, `build/wineserver/main_ios.c`, `app/Madeira/WineServerBridge.m`; base commit | Source confirmed; runtime startup/child launch untested |
| M-006 | FEX JIT | PATCH/POLICY | Reuse app-owned dual-map JIT pool and FEX RX/RW aliases; verify debugger/TXM behavior on target | `app/Madeira/JITAllocator.c`, `app/Madeira/FEXBridge.mm`, `FEX/Source/Windows/ARM64EC/Module.cpp`; FEX `f59cab95659e8add0c88f0c76ec1cf483c536dbf` | Source-only; OS enforcement/device behavior VERIFY |
| M-007 | Display/graphics | ARCH | Reuse UIKit/CAMetalLayer bridge and DXMT iOS Metal device path | `app/Madeira/IOSDisplayShim.m`, `dxmt/src/winemetal/unix/winemetal_unix.c`; DXMT `128b297c6e9a00014408dc68b4c2c2373b5813de` | Source-only; no graphics test |

## Audit rules

- A search hit is a lead, not proof that a call is reachable on iOS.
- Record file, function/line, pinned source revision, evidence, risk, change,
  and a reproducible test for every future patch.
- Do not upstream AI-authored changes to FEX or DXMT; see `DECISIONS.md` D-007.
- No IPA build or device test has passed.
