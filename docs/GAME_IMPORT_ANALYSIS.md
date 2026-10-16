# Game import analysis (2026-10-16) — static only, no execution

Method: `llvm-readobj --file-headers --coff-load-config --coff-imports` and
`llvm-strings -n 4/-n 5` over each executable and its DLLs. Nothing was
executed, nothing was patched, no DRM component was analysed. Paths are the
user's own installations.

Neither binary was run, so **no status below is a WinePhone test result.** The
rows record which Wine and DXMT code paths a title will reach, and therefore
what the runtime must have before the title is worth a device run.

## CONTROL Resonant — `E:\Games\CONTROL Resonant\CONTROLResonant.exe`

- **Architecture:** `IMAGE_FILE_MACHINE_AMD64`, PE32+ (`Magic 0x20B`),
  `IMAGE_SUBSYSTEM_WINDOWS_GUI`, `ImageBase 0x140000000`, subsystem 6.0.
  Security-relevant flags present: `DYNAMIC_BASE`, `HIGH_ENTROPY_VA`,
  `NX_COMPAT`, and **Control Flow Guard** (`GuardCFCheckFunction` and
  `GuardCFCheckDispatch` both non-zero).
- **Imports:** 52 DLLs, 1054 symbols. Largest: `KERNEL32` 190, **`MSVCP140`
  169**, `USER32` 82, `cohtml.WindowsDesktop` 74, CRT api-sets ~150 across 12
  DLLs, `PhysX_64` 45, `PhysXFoundation_64` 39, `bink2w64` 24, `VCRUNTIME140`
  20, `steam_api64` 11, `HID.DLL` 11, `AVIFIL32` 11, `PhysXCommon_64` 11,
  `XINPUT1_4` 1, `MFPlat` 8.
- **Graphics: D3D12 only.** No DLL references `d3d11.dll` as an entry point.
  The Agility SDK is present and referenced: `D3D12Core.dll` (4.9 MB) has 6
  `d3d12` and 1 `dxgi` reference, `d3d12SDKLayers.dll` 5. Surrounding
  D3D12-era dependencies: `nvngx_dlss`/`nvngx_dlssd`/`nvngx_dlssg` (DLSS),
  `amd_fidelityfx_framegeneration_dx12` and `amd_fidelityfx_upscaler_dx12`
  (FSR), `NRD.dll` (denoiser), `NRI.dll` (NVIDIA Rendering Interface),
  `PhysX`. RTTI identifies the engine as Remedy Northlight: `rend::W4GIQuality`,
  `rend::W4PTQuality`, `rend::W4RTReSTIRQuality`, `rend::W4SSAAMethod@rend`.
- **Consequence for WinePhone:** D3D12 is deliberately not provided. The D3D12
  path is excluded from this tree for licensing, and `scripts/build-ipa.sh`
  fails the build if an IPA contains `d3d12core.dll`, `madeira_d3d12` or
  `libmetaliconverter`. **Verdict: out of scope for Track A on a graphics-API
  gap, not a DRM one.** Re-open only if a D3D12→Metal layer lands.
- **Non-graphics load:** CEF (`cohtml.WindowsDesktop` + `cohtml_icuuc` +
  `MediaDecoders.WindowsDesktop` + a 23 MB `v8.dll` JavaScript engine) for the
  in-game browser/UI; PhysX for physics; Bink2 for video; `XINPUT1_4` and
  `HID.DLL` for input.

## Rise of the Tomb Raider — `D:\Rise of the Tomb Raider\ROTTR.exe`

- **Architecture:** `IMAGE_FILE_MACHINE_AMD64`, PE32+ (`0x20B`),
  `IMAGE_SUBSYSTEM_WINDOWS_GUI`, `ImageBase 0x140000000`, subsystem 6.0, same
  flag set including **Control Flow Guard**.
- **Imports:** 37 DLLs, 912 symbols. Largest: `KERNEL32` 173, **`MSVCP140`
  134**, **`EOSSDK-Win64-Shipping` 102**, `USER32` 101, CRT api-sets ~130,
  `WINMM` 31, `WS2_32` 29, `VCRUNTIME140` 20, `ADVAPI32` 17, `bink2w64` 17,
  `GDI32` 16, `steam_api64` 13, `HID.DLL` 12, `dbghelp` 12,
  `stream_engine` 9, `openvr_api` 7, `MSACM32` 6, `faultrep` 1.
- **Graphics: D3D11 primary, D3D12 opt-in.** The executable itself carries
  4 `d3d11.dll`, 2 `dxgi.dll`, 2 `d3dcompiler_` and 1 `d3d12.dll` reference.
  RTTI shows a complete D3D11 class hierarchy in the binary
  (`PCDX11DeviceManager`, `PCDX11CommandList`, `PCDX11ComputeShader`,
  `PCDX11DefaultRenderTarget`, `PCDX11DeferredContextPool`, `PCDX11BitmapTexture`,
  `PCDX11DepthBuffer`, `PCDX11ConstantBuffer`, `PCDX11DomainShader`) alongside a
  single `PCDX12PooledAlloc`, and it ships `d3dcompiler_47.dll` (4.1 MB) so
  DXBC is compiled at run time — exactly the path DXMT implements. The token
  `DX12` exists as a standalone string while `DX11` does not, which reads as
  "D3D11 by default, D3D12 as an opt-in argument".
- **Launch rule this implies:** the per-game profile must **not** pass `DX12`.
  Anything that makes the game choose D3D12 lands on an unsupported path.
  VERIFY by running with `WINEDEBUG=+loaddll,+module` and confirming
  `d3d11.dll` loads and `d3d12.dll` does not.
- **Good news on the runtime DLLs:** this installation ships `msvcp140.dll`
  (551 KB), `vcruntime140.dll` (94 KB) and `vcruntime140_1.dll` (36 KB) in its
  own folder, so it does not depend on the user supplying the Microsoft
  redistributable. CONTROL Resonant does not ship them and would rely on Wine's
  own LGPL `msvcp140`/`vcruntime140` builtins in the DLL farm.
- **Consequence for WinePhone:** this is the stronger Track A candidate of the
  two, because its primary renderer is the one DXMT translates.

## DRM position (rule 3)

Neither binary was checked for DRM beyond counting what it imports. Both are
Steam builds (`steam_api64.dll`; ROTTR also ships `steamclient64.dll` and
`GameOverlayRenderer64.dll`). No Denuvo, Easy Anti-Cheat or BattlEye marker was
found in either executable by string scan, but a string scan is not proof and
**no DRM component was analysed or bypassed.** Any title whose DRM blocks
execution is reported unsupported rather than worked around; prefer a DRM-free
build of the same title for a compatibility run.

## What this changes in the runtime

1. **Control Flow Guard** is present in both. Record it as a Wine-side
   question rather than assuming support.
2. **`HIGH_ENTROPY_VA`** is requested by both. That is a large-address-space
   request, which interacts with the memory limits on a free Apple ID
   (`com.apple.developer.kernel.extended-virtual-addressing` is unavailable
   there). Treat as a top memory risk before any AAA attempt.
3. **CEF in CONTROL** pulls in a full Chromium engine plus a JavaScript VM.
   That is a heavy unix-side surface for Wine and a second large allocation
   consumer alongside the renderer.
4. **PhysX, DLSS, FSR, NRD, NRI** in CONTROL are vendor libraries with their own
   CPU/GPU entry points; none is a Wine module and each would need either a
   native ARM64 path or a decision to disable the feature.