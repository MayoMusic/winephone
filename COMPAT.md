# Compatibility status

WinePhone builds and runs. The first recorded device run is Rise of the Tomb
Raider on iPhone18,3 / iOS 27.0.1: it **reaches the main menu** and then, on the
first level load, aborts inside its own allocator. That abort is measured and
ruled out as ours — `docs/ROTTR_HEAP_OOM.md`.

Every other row below is still a **static analysis of the user's own installed
binaries**, not a test result. Do not treat Madeira's title reports or the
project brief's estimates as WinePhone results either.

Machine-readable records and schema live in `compat/catalog.json`. A status other
than **Untested** requires a recorded run with device, OS, build commit,
profile, logs, FPS/frame-time method, and test duration — the ROTTR entry is the
one that has all of them.

Status vocabulary: **Untested** (analysed, never run) · **Unsupported-API**
(needs a graphics API this tree does not provide) · **Unsupported-DRM** (must
not be worked around) · Boots / Menu / Playable / Perfect (require a recorded
device run).

## Titles on the user's disks

Analysis method and full evidence: `docs/GAME_IMPORT_ANALYSIS.md`
(`llvm-readobj` + `llvm-strings`; nothing executed, patched or redistributed).

| Title | Arch | Renderer | Status | Basis |
|---|---|---|---|---|
| Rise of the Tomb Raider | x86-64 PE32+ | **D3D11 primary**, D3D12 opt-in | **Menu** | Recorded run, `compat/catalog.json`. Builds DXMT (Apple A19 GPU, feature level 11_0, BC textures), creates its 1280×720 window and a Metal layer, reaches the main menu. The first level load then aborts in the game's own allocator — not a host refusal, not fragmentation, not RAM: `docs/ROTTR_HEAP_OOM.md`. Static basis: 4 `d3d11.dll` and 2 `dxgi.dll` references, a complete `PCDX11*` hierarchy, and `d3dcompiler_47.dll`, so DXBC is compiled at run time, which is the path DXMT implements. The per-game profile must not pass `DX12`. |
| CONTROL Resonant | x86-64 PE32+ | **D3D12 only** | **Unsupported-API** | No `d3d11.dll` import anywhere, so there is no fallback to the D3D11 path that works: ships the Agility SDK (`D3D12Core.dll` 5,015,624 + `d3d12SDKLayers.dll` 4,959,776) and resolves `D3D12CreateDevice` through `sl.interposer.dll`, with DLSS, FSR, NRD, NRI and PhysX around it. Blocked three ways, which are different facts. **Policy:** Microsoft's D3D12Core and Apple's `libmetalirconverter` are prohibited release inputs — `tools/validate_release_inputs.py` fails the build on them, and `scripts/build-ipa.sh:200` runs it every build. **Incomplete:** Wine's own `d3d12` over vkd3d is not prohibited but has two gaps — the shipped `arm64ec-windows` payload has no `d3d12.dll` at all (`scripts/build-ipa.sh:191` copies only `d3d11`, `dxgi`, `winemetal`, `d3d10core`; the `aarch64-windows` copy is a prebuilt binary this build does not produce), and there is no Vulkan device, the only `vulkan-1.dll` being a deliberate stub answering `VK_ERROR_INCOMPATIBLE_DRIVER` (`tools/build-stub-dlls.py`, built so Vulkan-using titles fall back to D3D — which a D3D12-only title cannot do). An earlier version of this row claimed no such rule existed; it does. Full evidence, and what has **not** been ruled out — chiefly a Vulkan→Metal layer such as MoltenVK, which no rule forbids — is `docs/D3D12_BACKEND.md`; re-derive with `tools/d3d12-backend-probe.py`. |

Both binaries set **Control Flow Guard** and request **HIGH_ENTROPY_VA**. The
second is a large-address-space request and collides with the limits of a free
Apple ID (`com.apple.developer.kernel.extended-virtual-addressing` is not
available there); treat it as the top memory risk before any AAA attempt.

### ROTTR: the 3072 MB address-space reservation, traced

Observed on device: `CDC: Unable to reserve 3072MB of address space.`, then
`ExitProcess`. Traced to a single instruction in the CDC allocator, at RVA
`0x3C3717` (file offset `0x3C2D17`) in a 341-byte function at RVA `0x3C3690`:

```asm
mov  edx, 0xC0000000     ; 3072 MB, a compile-time immediate
mov  r8d, 0x2000          ; MEM_RESERVE
lea  r9d, [rcx+4]         ; PAGE_READWRITE
call [rip+...]            ; VirtualAlloc  -> NULL
test rax, rax
jne  ok                   ; no retry, no smaller fallback anywhere
```

The 3072 is not derived from system memory and is not configurable; the failure
text prints `0xC0000000 >> 20`. Of the 15 `VirtualAlloc` call sites in the
binary this is the only one with a hard-coded size of 32 MB or more - the other
14 take their size from a register. Because `MEM_RESERVE` commits nothing, the
reservation is an address-space problem, not a RAM problem: see
`docs/MEMORY_ENTITLEMENTS.md`. `tools/rotrr-heap-patch.py` lowers the constant.

**Patched and verified on device.** At 768 MB the reservation succeeds:

```
[bigres] tid=007c #1 size=0x30000000 (768 MB) type=0x2000 prot=0x4
[guest-reserve] #1 0x7138010000+0x30000000 hinted=0 running_total=768MB
```

It does not need the 768 MB: the FEX arena's 4 GB already ends at `0x7138010000`
and the band ceiling is `0x7180000000`, so 1152 MB is free above the arena and
the reservation would fit at a much larger size too. `jumbo-mb` should therefore
match the patched request rather than the original 3072.

Two things about it that are worth not re-learning:

- `VirtualAlloc(NULL, ...)` never fails on this device, because `VM_FLAGS_ANYWHERE`
  finds somewhere in the 454 GB map. A game that spreads its arena out is not
  stopped by the ceiling it was told about; it is stopped by fragmentation it
  created itself, which is what the level-load abort turned out to be.
- The 16 `[range-probe]` lines in that run show every slot Wine *preferred*
  (`0x7c…`, `0x74…`) sitting above the task ceiling, which is why the
  allocation fell back to hint 0 and landed inside the FEX arena instead.

The level-load abort that replaced this failure is `docs/ROTTR_HEAP_OOM.md`.

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