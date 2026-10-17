# D3D12 on iOS: what this build provides, and what it does not

**Status: UNRESOLVED. Neither gap is closed, and the policy prohibition stands.**
The D3D12 backend is incomplete here, by two independent gaps. This is a
statement about *this* graphics path, not about D3D12 in general. What has *not*
been ruled out is listed at the end.

Everything below is re-derived by `tools/d3d12-backend-probe.py`, which exits
non-zero while either gap is open. Run it before repeating any of it.

## The claim this replaces

`COMPAT.md` recorded CONTROL as **Unsupported-API** on two grounds, and this
document has to correct the record twice over.

The first version of this document said `scripts/build-ipa.sh` had no D3D12 rule
and therefore none existed. That grep was literally true and materially
misleading: **the rule exists, enforced in code, fail-closed** —
`tools/validate_release_inputs.py`, which `scripts/build-ipa.sh:200` runs on
every build:

```python
for forbidden in ("x86_64-vcruntime", "libmetalirconverter", "d3d12"):
    if forbidden.casefold() in project.casefold():
        raise SystemExit(f"forbidden app resource reference remains: {forbidden}")

for name in ("libmetalirconverter.dylib", "d3d12core.dll", "madeira_d3d12.dll"):
    matches = [p for p in app.rglob(name) if p.is_file()]
    if matches:
        raise SystemExit("prohibited D3D12 release inputs remain: ...")
```

So Microsoft's D3D12Core / Agility SDK and Apple's Metal Shader Converter are
**prohibited release inputs**, and a build that ships either fails. That is a
project decision with teeth, not a gap.

What `scripts/build-ipa.sh` really does is *copy only four dxmt modules* — see
Gap 1. Those are different facts and the second version of this document
conflated them.

Wine's own `d3d12.dll` is **not** on the forbidden list, which is why the
`aarch64-windows` copy sits in the repo and passes validation. So the position
is narrower than "D3D12 is banned":

| D3D12 implementation | status here |
|---|---|
| Microsoft D3D12Core / Agility SDK (`d3d12core.dll`) | **prohibited**, enforced by the validator |
| Apple Metal Shader Converter (`libmetalirconverter.dylib`) | **prohibited**, enforced by the validator |
| Wine `d3d12.dll` over vkd3d | not prohibited, but **incomplete** — the two gaps below |

CONTROL Resonant ships the first. So it is blocked by policy *and* would not
work if the policy allowed it.

## Gap 1 — the shipped payload has no `d3d12.dll` at all

`scripts/build-ipa.sh:191` copies exactly four dxmt modules into the payload:

```sh
for pair in "d3d11/d3d11.dll:d3d11.dll" "dxgi/dxgi.dll:dxgi.dll" \
            "winemetal/winemetal.dll:winemetal.dll" "d3d10/d3d10core.dll:d3d10core.dll"; do
  cp "$ROOT/dxmt/build-arm64ec/src/$src" "$ROOT/app/Madeira/arm64ec-windows/$dst"
done
```

`d3d12` is not in that list, and the dxmt PE build is configured for
`build-arm64ec` only. The `aarch64-windows` copy is a prebuilt binary committed
to the repo, not something this build produces:

| payload | `d3d12.dll` | `wined3d.dll` | shipped? |
|---|---|---|---|
| `aarch64-windows` | 458,752 | 3,211,264 | no |
| `arm64ec-windows` | **absent** | 3,670,016 | **yes** |

So a guest that imports `D3D12CreateDevice` does not get a broken driver — it
gets `STATUS_DLL_NOT_FOUND` in the loader, before any instruction runs.

## Gap 2 — `d3d12` is a vkd3d front end, and there is no Vulkan device

Given the DLL, it still would not work. `d3d12.dll`'s imports are the answer:

```
dxgi.dll!CreateDXGIFactory2
wined3d.dll!vkd3d_create_device
wined3d.dll!vkd3d_create_instance
wined3d.dll!vkd3d_create_root_signature_deserializer
wined3d.dll!vkd3d_serialize_root_signature
...
```

Wine's D3D12 speaks D3D12 to the guest and **Vulkan** to whatever is underneath.
So the backend is complete or not depending entirely on a Vulkan device at run
time.

There is none, and that is a decision rather than an oversight.
`tools/build-stub-dlls.py` builds a stand-in `vulkan-1.dll` — 122,880 bytes, 24
imports, all of them the C runtime and `kernel32`:

> vulkan-1.dll: Wine's forwards everything to winevulkan, which needs a host
> Vulkan driver iOS does not have. Here it answers like the Khronos loader on a
> PC without a Vulkan driver, **so games fall back to D3D**: the global commands
> work (`vkEnumerateInstanceVersion` reports 1.3, the instance extension and
> layer lists are empty), `vkCreateInstance` and every other call report
> `VK_ERROR_INCOMPATIBLE_DRIVER`, and `vkGetInstanceProcAddr` hands out only the
> global commands.

The stub exists because a game whose import table names a missing DLL dies in the
loader even if it would never call it — Crysis Remastered names `d3d10.dll`,
`avifil32.dll` and `vulkan-1.dll` that way (log 2026-09-30 18:42). So the stub
buys the *fallback*, and it works for a Vulkan-using D3D11 title. It cannot work
for a D3D12-only title, because D3D12 is not something you can fall back *from*.

Corroborating the absence of a driver, three ways:

| evidence | result |
|---|---|
| ICD manifest (`*.json`) anywhere under `app/` | none |
| `Vulkan\Drivers` / `SOFTWARE\Khronos` set anywhere in the tree | never set |
| MoltenVK, SwiftShader, lavapipe, any translation or software driver | none |
| `winevulkan.dll` in the payload | absent, so `vulkan-1.dll` is the only branch |

`wine/dlls/wined3d/adapter_vk.c:96-99` tries `winevulkan.dll`, then
`vulkan-1.dll`, then:

```c
WARN("Failed to load vulkan-1.dll.\n");
```

That is the expected line for a D3D12 title on this build. No Vulkan adapter is
created.

Note the trap worth not repeating: `vulkan-1.dll` being **present** is not
support. A loader with no driver is exactly what makes the absence hard to see
— an import resolves, and then `vkCreateInstance` fails.

## Why D3D11 does not rescue it

A D3D12 title has to fall back to D3D11 on its own. CONTROL Resonant
(`E:\Games\CONTROL Resonant`) does not: it ships the Agility SDK and has no
`d3d11.dll` import at all.

```
D3D12Core.dll            5,015,624
d3d12SDKLayers.dll       4,959,776
amd_fidelityfx_*_dx12.dll          (FSR, D3D12 only)
nvngx_dlss*.dll, sl.dlss*.dll     (DLSS, D3D12)
NRD.dll, NRI.dll                  (D3D12)
CONTROLResonant.exe    99,470,256
```

It also resolves `D3D12CreateDevice` through `sl.interposer.dll` (Streamline)
rather than from `d3d12.dll` directly, so the SDK's Agility runtime is on the
critical path too and is a third thing that would need handling.

## What has NOT been ruled out

Stating this narrowly matters, because "D3D12 is impossible on iOS" is not what
the evidence shows.

**Not ruled out, and the obvious one: a real Vulkan→Metal translation layer.**
This is what closes Gap 2, and nothing in the project's constraints forbids it
— MoltenVK is MIT-licensed, not Apple's `libmetalirconverter.dylib`, and not on
the validator's forbidden list. It is absent, and it is a substantial dependency
(a new runtime in the IPA, a licensing entry in `THIRD-PARTY-NOTICES.md`, and
DXIL shader paths that would need checking against DXMT's). **It has not been
tried and no claim is made about whether it would work.**

**Not ruled out: shipping `d3d12.dll` for arm64ec.** Closing Gap 1 is a `meson`
target and one more line in the `build-ipa.sh` loop. That alone still leaves
Gap 2 — it turns `STATUS_DLL_NOT_FOUND` into `VK_ERROR_INCOMPATIBLE_DRIVER`.

**Not ruled out: a D3D12→D3D11 translation layer** (Microsoft's D3D12 mapping
layer, or an equivalent). Does not exist in this tree. It is the route that
would actually give a D3D12-only title a fallback, at the cost of feature
coverage — ray tracing, resource binding tier 1 and enhanced barriers do not
map.

**Prohibited by project policy, with the rule enforced in code:** Microsoft's
D3D12Core / Agility SDK and Apple's Metal Shader Converter. CONTROL Resonant
needs the first. Their feasibility was never evaluated and this document makes
no claim about it — they are excluded by `tools/validate_release_inputs.py`, and
that is the whole of the reason.

**Settled:** a Vulkan-using title with a D3D11 fallback works today, which is
what the stub was built for and what the ROTTR main menu demonstrates.

## Re-checking

```
python3 tools/d3d12-backend-probe.py
```

Prints the payload contents, what `d3d12.dll` imports, whether any driver or ICD
setup exists, and the two gaps. Exit status is 1 while either is open, so it can
gate a claim instead of being re-argued.