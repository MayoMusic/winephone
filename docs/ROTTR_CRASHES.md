# ROTTR crashes in the 15:32–15:40 device runs

**Status: OPEN. Three distinct host-side crashes, all ours, none of them the
game's own allocator.**

This corrects an earlier reading of the same four logs, which said the game
reached its main menu and exited cleanly. That was wrong: the search looked for
the game's `Out of memory` assert, did not find it, and treated "no assert" as
"no crash". The failures are Mach exceptions with entirely different text, and
they are in DXMT and winemetal rather than in the game.

Verified in the logs, not inferred:

| Run | Time | Fault | Confirmed text |
|---|---|---|---|
| 1 | 15:33 | Metal texture validation | `MTLTextureDescriptor has height (2147484416) greater than the maximum allowed size of 32768` |
| 2 | 15:35 | dangling Objective-C object inside AGX | `pc=libobjc objc_retain+0x10 lr=AGXMetalG18P`, from `_MTLBlitCommandEncoder_encodeCommands` |
| 3 | 15:38 | NULL destination `memmove` | `x0=0 (dst) x1=0x178ef0040 x2=0x3bb0`, from `dxmt::dxbc::read_control_flow` |

All three pass through `__wine_unix_call_dispatcher`, so all three are on the
PE-to-host boundary this project owns.

The `explorer.exe` log is a healthy desktop start and contains no fault.

## What this changes

The game's own `Default Heap Allocator` assert did **not** occur in any of these
runs. `docs/ROTTR_HEAP_OOM.md` describes a separate, earlier failure and stays
open on its own terms; nothing here confirms or refutes it. What these runs show
is that the game cannot reach a level because the host aborts first, in three
different places.

That makes the allocator RE a side quest rather than the blocker, and it moves
the work into `dxmt/` and `madeira-d3d12/`, where a fix is possible at all.

## Issue A — a texture height with bit 31 set

`2147484416 = 0x80000300 = 0x80000000 + 768`. The configured resolution is
1408x648, and 768 is not any configured dimension.

The back-buffer descriptor is a straight copy of the guest's own
`DXGI_SWAP_CHAIN_DESC`:

```cpp
backbuffer_desc_ = D3D11_TEXTURE2D_DESC1 {
  .Width = desc_.Width,
  .Height = desc_.Height,
  ...
```

So `0x80000300` reached DXMT from the guest. The fault happens immediately after
`MakeWindowAssociation: Ignoring flags 3` and `[present] commitBeforePresent=1`,
so it is one of the first textures of the first frame. The dying thread had made
`unix_calls=41`.

Where bit 31 comes from is not established. Two candidates worth separating by
instrumentation rather than argument: a field read at a shifted offset in a
struct crossing the thunk boundary, and a float-to-int conversion that produces
`INT_MIN` on a non-finite or out-of-range input and is then combined with a real
value.

## Issue B — a freed Metal handle used by a blit command

`objc_retain` was called on a pointer outside the JIT pool, from inside the AGX
driver, reached through `_MTLBlitCommandEncoder_encodeCommands`. The
`[mem-census]` just before it shows live memory falling from about 2417 MB to
about 498 MB in one burst, and live buffers from 1034 to 605.

`_wassert(!status && "unix call failed")` at `winemetal_thunks.c:425` fires
afterwards. It is a consequence: the host fault became a guest failure status.
The assertion dialog the user sees is not the fault.

## Issue C — an unchecked allocation in the shader parser

`read_control_flow` copied 15280 bytes to address 0. Metal's `memmove` was
entered with a NULL destination, so either the destination was never allocated
or an allocation returned NULL and the result was used without a check. Run 3
was at `phys=2723 MB (peak 2754)` against a 3354 MB ceiling, with `errno=12`
repeating in `[va-scan]` and the 16 GB and 8 GB FEX arena reservations failing
with `kr=3`.

Memory pressure and a parser bug are both consistent with this and the logs do
not separate them yet.

## Order of work

1. **Stop the abort, then find the cause.** Reject a degenerate descriptor in
   DXMT and return `E_INVALIDARG` instead of letting Metal raise, so the failure
   is a return value rather than a process kill.
2. **Log the descriptor on both sides of the boundary** — guest values and host
   values for the same call. Sane on one side and not the other means a
   marshalling bug; wrong on both means it is born earlier.
3. **`static_assert` every struct crossing the dispatcher**, compiled for the PE
   target and the host target, so a layout difference fails the build instead of
   the game.
4. **Make `read_control_flow`'s allocation failure explicit**: a NULL from the
   container growth returns a shader-compile error instead of being copied into.
5. **Handle lifetime for blit commands**: a resource referenced by a recorded
   command is released when that command's sequence retires, not when the D3D11
   object is released.

## Honest limits of this document

No disassembly was done. `ROTTR.exe`, `Madeira.debug.dylib` and the DXMT sources
were not available to the analysis, so every offset above is read from a log line
and nothing has been confirmed in code. The guest-side leads in Run 1
(`ROTTR.exe+0xe305e0`, `+0xe39d68`, `+0xe32848`) come from a stack scan whose
unwinder reported `<no module>`; they are starting points, not conclusions.

The game's own allocator RE is a separate thread and is still open: the
allocation entry point is `0x1403c4ed0`, reached through vtable slot `+0xf0`, and
it calls `0x1403c6a60` directly. See the end of `docs/ROTTR_HEAP_OOM.md`.