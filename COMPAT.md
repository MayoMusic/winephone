# Compatibility status

No game has been run by WinePhone. No IPA has been built. Every row below is a
**static analysis of the user's own installed binaries**, not a test result.
Do not treat Madeira's title reports or the project brief's estimates as
WinePhone results either.

Machine-readable placeholder records and schema live in `compat/catalog.json`.
All statuses remain untested until a run is recorded with device, OS, build
commit, profile, logs, FPS/frame-time method, and test duration.

Status vocabulary: **Untested** (analysed, never run) · **Unsupported-API**
(needs a graphics API this tree does not provide) · **Unsupported-DRM** (must
not be worked around) · Boots / Menu / Playable / Perfect (require a recorded
device run).

## Titles on the user's disks

Analysis method and full evidence: `docs/GAME_IMPORT_ANALYSIS.md`
(`llvm-readobj` + `llvm-strings`; nothing executed, patched or redistributed).

| Title | Arch | Renderer | Status | Basis |
|---|---|---|---|---|
| Rise of the Tomb Raider | x86-64 PE32+ | **D3D11 primary**, D3D12 opt-in | **Untested — recommended first test** | Executable carries 4 `d3d11.dll` and 2 `dxgi.dll` references and a complete `PCDX11*` class hierarchy; ships `d3dcompiler_47.dll`, so DXBC is compiled at run time, which is the path DXMT implements. `DX12` exists as a standalone token while `DX11` does not, reading as D3D11-by-default with D3D12 opt-in, so the per-game profile must not pass `DX12`. |
| CONTROL Resonant | x86-64 PE32+ | **D3D12 only** | **Unsupported-API** | Ships the Agility SDK (`D3D12Core.dll`, 6 `d3d12` references) and **no** component references `d3d11.dll`, with DLSS, FSR, NRD, NRI and PhysX around it. D3D12 is excluded from this tree for licensing and `scripts/build-ipa.sh` rejects an IPA containing the converter. |

Both binaries set **Control Flow Guard** and request **HIGH_ENTROPY_VA**. The
second is a large-address-space request and collides with the limits of a free
Apple ID (`com.apple.developer.kernel.extended-virtual-addressing` is not
available there); treat it as the top memory risk before any AAA attempt.

Rise of the Tomb Raider ships its own `msvcp140.dll`, `vcruntime140.dll` and
`vcruntime140_1.dll`, so it needs no user-supplied Microsoft redistributable.
CONTROL Resonant does not ship them and would rely on Wine's own LGPL builtins.

## DRM position

Both are Steam builds (`steam_api64.dll`; ROTTR also ships `steamclient64.dll`
and `GameOverlayRenderer64.dll`). No Denuvo, Easy Anti-Cheat or BattlEye marker
was found by string scan — a scan is not proof, and **no DRM component was
analysed or bypassed**. A title whose DRM blocks execution is to be reported
`Unsupported-DRM` and left alone; prefer a DRM-free build for compatibility runs.

## Known graphics limits carried by the build itself

`BLOCKERS.md` B-016: `dxmt-ios` is built without Apple's licensed Metal Shader
Converter headers, so the MSAD, sample-position and tessellation intrinsic
libraries are not linked. A shader using one will fail in the Metal compiler at
run time. Any title relying on tessellation is expected to need the licensed
converter; that trade-off is a recorded decision, not an oversight.