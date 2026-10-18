# ROTTR: the level-load "Out of memory", and why it is not ours

**Status: UNRESOLVED. Not fixed, and not fixable from this tree.** The game
still aborts on the first level load. Everything below is measured on a device
run, and the conclusion is that the host never refused anything.

**No claim is made that the level load now works.** Nothing in this repository
changes the outcome: the refusal is inside the game's own allocator, and no
setting, entitlement or host allocation change reaches it. What follows
establishes *that* it is not ours, which is a different thing from fixing it.

**Update 2026-10-18 14:11 (build `20261018T1055Z-4ba6df1e4e87`).** The failure
has a second, *soft* surface, and on this build the fatal one did not appear.
The run reached ~11 minutes with the host refusing nothing (`[alloc-fail]` 0,
`[map-fail]` 0, `[map-rate]` `fail=0` in the last sample) and then the game put
up its own message box:

```
ERROR: Out of memory, "UNKNOWN" requested 112460 bytes (109.8 KB 0.1 MB)
(1028736280 total free (1004625.3 KB 981.1 MB))
```

No `[guest-log]` assert, no `int3`, no `[term]`: the process stayed alive. The
message's *format* (`0x140d43d50`, no allocator name) names the route: the
**fast** allocation slot (`{+0x90}` -> `0x1403c4b20` -> `{+0xf0}` ->
`0x1403c4ed0`). The runs that died (`01:15`/`06:32`/`07:53`) used the other
format (`0x140d43dc0`, `ERROR: %s: ...`), the growing route (`{+0xf8}` ->
`0x1403c4d20` -> `0x1403c6f80`). Two refusals, two routes; the "total free"
number is the same computed value in both. That number is now traced to its
last bit: `mstate[0x868] - this[0x40] - this[0x38]`, with `mstate[0x868]` an
arena size fixed at construction -- 768 MB on this build's default heap. 981.1
MB is larger than that whole arena, so the object that printed this dialog was
*not* the default heap. The refusal itself is traced end to end below, and
ml1221 (`[rotrr-heap]`, `MADEIRA_ROTRR_HEAP_PROBE=1`) walks *every* allocator
object and prints each one's arena size and the exact "free" the message would
print.


## The failure

Reproduced on iPhone18,3 / iOS 27.0.1 with `MADEIRA_CPU_COUNT=2`, `pool=512`:

```
[guest-log] tid 0038 > [ASSERT] Fatal error: ERROR: Default Heap Allocator:
  Out of memory, "UNKNOWN" requested 870240 bytes (849.8 kB 0.8 MB)
  (999488844 total free (976063.3 kB 953.2 MB))
```

then the game's own `int3`. Three runs, three different swap/VRAM settings:

| run | swap | vram | footprint | requested | total free |
|---|---|---|---|---|---|
| 01:15 | classic / 2048 | 2048 | 2536 MB | 870240 | 1 006 569 688 |
| 06:32 | broad / 1024 | 1024 | 1960 MB | 870240 | 1 003 266 420 |
| 07:53 | broad / 1024 | 1024 | 1905 MB | 870240 | 999 488 844 |

The **requested size is identical in all three**; the free total moves by about
7 MB. A pool with 953 MB free does not fail an 0.8 MB request.

### The configuration of record

Where each device setting lives, and the run it is proven from. The 14:11 log --
the one that echoed `madeira.cfg:` and the `[wmt]` lines -- is not on disk any
more, so what is not listed here was never proven for that build; the probe run
starts from the values below.

Game details for `ROTTR.exe` (device-side, not in madeira.cfg):

| setting | value | proven from |
|---|---|---|
| Compatibility & performance > CPU cores reported | 2 | 2026-10-17 15:38: `[madeira] ml1122 cpu-count override: reporting 2 processors (host 6)` |
| > Report an NVIDIA GPU | on | `[bcd] ... nvidia=1`; this is where `dxgi.customDeviceId=2544` comes from |
| > Wine's C++ runtime | on | `[bcd] ... wine-vcrt=1` (2026-10-17 15:38; it was `0` in the 15:33 run) |
| > AVX and AVX2 | off | `[bcd] ... avx=0` |
| Advanced > This game's config | `env.MADEIRA_EC_HOOK_TRACE=0` | `[game-cfg] env.MADEIRA_EC_HOOK_TRACE=0` |
| Aspect & scaling | stretch (fit in the 15:33 run) | `[display-shape] resolution=1408x648 mode=stretch` |

`Documents/madeira.cfg` -- the `madeira.cfg:` line echoes the whole file, so a
key absent from this list was not set:

- The 01:15/06:32/07:53 runs of the table above: `MADEIRA_CPU_COUNT=2`,
  `pool = 512`, and the per-run swap and `vram-mb` values (from those runs'
  logs, since deleted).
- 2026-10-17 15:33-15:38: only `env.MADEIRA_JIT_SHORTCUT=1`. No `pool`,
  `swap-mb` or `vram-mb` key: pool default 896 MB (`Allocating 896MB JIT
  pool`), swap off (no `[swap] ml1077 ... tier ON` line), the video budget
  automatic (`[wmt] ml1042 video memory budget = 1024 MB`).
- 2026-10-18: `map-trace = 1`; ml1221 adds `env.MADEIRA_ROTRR_HEAP_PROBE = 1`.
- 2026-10-18 runs, as echoed by both logs (16:39 and 16:53): `eco = 1`,
  `env.MADEIRA_SWAP_COVERAGE = blocks`, `map-trace = 1`, `pool = 512`,
  `swap-mb = 2048`, `vram-mb = 2048`; the game's own config (`[game-cfg]`) is
  exactly `env.MADEIRA_EC_HOOK_TRACE=0 env.MADEIRA_ROTRR_HEAP_PROBE=1`, and
  `[bcd] library launch ROTTR.exe: avx=0 wine-vcrt=0 nvidia=1 game-config=1`
  (wine-vcrt is back to 0 in these runs). `pool = 512` is the value the
  17-10 morning fatal runs used; the 17-10 evening 896 MB default no longer
  applies.

The patched `ROTTR.exe` is part of the configuration too: the 14:11 run is the
768 MB one (`[guest-reserve] #1 0x713d900000+0x30000000 ... running_total=768MB`),
and the 16:53 run repeats it at a different address
(`#1 0x713cbf0000+0x30000000 ... running_total=768MB`).

## What the host did: nothing wrong

`f8c3f8d` added the instrumentation that makes this a measurement rather than a
reading of the log:

```
[map-fail]        0     every failing NtMapViewOfSection / NtMapViewOfSectionEx
[alloc-fail]      0     every failing NtAllocateVirtualMemory
[alloc-fail-ex]   0     every failing NtAllocateVirtualMemoryEx (the one FEX uses)
[map-rate] last 23.30s: alloc ok=1 fail=0
```

`[map-rate]` counts successes and failures once a second on all four guest
allocation entry points. The last sample before the game died is **23 seconds
long and contains one successful allocation**: the game had stopped asking the
kernel entirely before it declared itself out of memory.

`[footprint] phys=1905 MB (peak 2029)` against a jetsam limit of ~3376 MB.
**1.47 GB spare.**

## What the address space did: nothing wrong

`MADEIRA_BAND_CENSUS=1` prints a census per minute plus, since `81cdb1b`, a
`[band-owner]` breakdown attributing every region in `[0x7000000000,0x7180000000)`
to an owner. The last two censuses of the 07:53 run:

```
[band] census #5 07:57:44  37754 regions, largest gap 4 MB
[band-owner] fex-arena     regions=3862    mapped=4096 MB   grew 0
[band-owner] swap          regions=13      mapped= 807 MB   grew 0
[band-owner] other         regions=565     mapped= 659 MB   grew 0
[band-owner] jit-pool      regions=32768   mapped= 512 MB   grew 0
[band-owner] ~teb-tls      regions=542     mapped=  28 MB   grew 0
[band-owner] ~fex-callret  regions=3       mapped=  24 MB   grew 0
[band-owner] ~fex-lookup   regions=1       mapped=   2 MB   grew 0
```

**Every owner grew 0 MB and gained 0 regions** across the last two censuses,
and the band was frozen through the assert. The timeline says it reached that
fixed point a minute before the game died:

| census | regions | largest gap |
|---|---|---|
| #1 | 32 806 | 1149 MB |
| #2 | 33 680 | 268 MB |
| #3 | 37 547 | **1 MB** (worst) |
| #4 | 37 754 | 4 MB |
| #5 | **37 754** | **4 MB** |

Three readings the log looks like but is not:

- **The 32 768 `jit-pool` regions are not fragmentation.** 512 MB of JIT pool in
  16 KB carves: `512 MB / 16 KB = 32768`. They are present at census #1 and never
  grow.
- **The per-thread costs are not in the band.** `~fex-callret` (8 MB per thread),
  `~fex-lookup` (2 MB per thread) and `~teb-tls` total **54 MB**, all of it
  inside the flat 4096 MB `fex-arena`.
- **6 GB is not the usable address space.** It is the census window, chosen
  because RDR2 wanted 8960 MB inside it. The real map is
  `[0x100f9c000, 0x7180000000)` — `[va-profile] ml749 post-limit
  TASK_VM_INFO.max_address=0x7180000000 (454.0 GB)` — and the largest free gap
  the placement walk ever reports across it is `0x27fff0000`, **10 GB**.

## What the game's allocator is

Traced in `ROTTR.exe` (27 MB, x86-64). Tools in `tools/`, each one small and
each one documented in its own header.

The message strings:

```
.rdata 0x140d43ad0   Default Heap Allocator
.rdata 0x140d43dc0   ERROR: %s: Out of memory, "%s" requested %Iu bytes
                     (...) (%Id total free (...))
```

The reporter is a pair of near-identical wrappers, `0x1403c4b20` and
`0x1403c4d20`, reached only through the vtable (`+0x90` and `+0xf8` of the
class's table at `0x140d437f0`). Their arguments are `rcx = the allocator`,
`rdx = the requested size`, `r8d = a small tag index` -- the name table at
`0x141006da0`, "UNKNOWN" when the index is `>= 0x800` or the entry is NULL --
and the `ERROR: %s: ...` format's `%s` is the allocator's own name string at
`this+0x8`. **`total free` is not an argument**: each reporter calls
`vtable+0xd0` and prints what it returns.

The object layout, from the constructor at `0x1403c37f0` (`this+0x8` is the
name string; `this+0x10` and `this+0x18` link the objects into one chain, see
*The objects* below):

```
+0x28  arena base (32-bit) +0x2c  arena limit (32-bit)
+0x30  outstanding allocs  +0x38  IN-USE bytes (free() subtracts)
+0x40  the second free term +0x48 the dlmalloc mstate (arg to 0x1403c6a60)
+0x50/51 size + flag       +0x52  ready/report flag
+0x58  CRITICAL_SECTION    +0x8F0  a second one (the big lock)
+0x80  first subheap       [0]    vtable -> 0x140d437f0
```

`[0x141006d80]` is a **pointer** to the default instance, not the object.

And the `free` the message prints is computed, by `vtable+0xd0`
(`0x1403c5d20`):

```
free = mstate->vtable[+0x8](mstate) - this[0x40] - this[0x38]
```

(`vtable+0xc8` forwards to that mstate method; `vtable+0xe8` is literally
`mov 0x38(%rcx),%rax`; and the mstate's own `{+0x8}` is `0x1403c7270`, which is
`mov 0x868(%rcx),%rax; ret` -- so the first term is `mstate[0x868]`.) Three
terms, one report -- and none of them is a measurement of the bins.

`mstate[0x868]` is written in exactly two places, both constructors, and never
extended at runtime: `0x1403c356c` (instances, from the size argument) and
`0x1403c3723` (the default heap, from the same immediate that reserves the
arena at `RVA 0x3C3717`). On this build's default heap it is `0x30000000`
(768 MB) -- so a default-heap "total free" above 768 MB cannot exist, and the
14:11 dialog's 981.1 MB cannot have come from that object.

And the imports inside the allocator's own code, `0x1403c3700..0x1403c9000`:

```
KERNEL32.dll!VirtualAlloc                 x2
KERNEL32.dll!VirtualFree                  x2
KERNEL32.dll!EnterCriticalSection         x13
KERNEL32.dll!LeaveCriticalSection         x14
KERNEL32.dll!RaiseException               x1     <- the int3
```

**No `HeapAlloc`. No `HeapCreate`. No `GetProcessHeap`. No
`RtlAllocateHeap`.** "Default Heap Allocator" is the game's own allocator built
directly on `VirtualAlloc`. Its `VirtualAlloc` failing is an
`NtAllocateVirtualMemory` failing, and that has never happened.

The counter is adjusted **before** the work call and before the NULL check, at
`0x1403c774e`: `addq %rax, 0x38(%rbx)`.

### The objects

The class vtables -- `0x140d43490` (the base), `0x140d435b0`, `0x140d436d0`,
`0x140d437f0` -- share the arena globals `0x141006d40` (base) and
`0x141006d40 + 0x141006d44` (limit) and the reporter slots: `{+0x90}` ->
`0x1403c4b20` (the no-name format) and `{+0xf8}` -> `0x1403c4d20` (the named
format); class `0x140d436d0` wraps both in the big lock (`0x1403c4cc0`,
`0x1403c4e50`). The default instance is the singleton at `0x141006d80` (the
pointer is also stored at `0x141006d88`), referenced 4507 times.

The mstate at `this+0x80` has its own vtable, and two of its slots decide what
"grow" can mean:

| mstate vtable | built by | `{+0x8}` (the "free" base) | `{+0x10}` (extend the arena) |
|---|---|---|---|
| `0x140d43350` | `0x1403c3690`, the default heap | `mstate[0x868]` | `0x1403c73a0`: page-aligned end vs `base + mstate[0x868]` -> `-1` **before** `VirtualAlloc`; otherwise `VirtualAlloc(MEM_COMMIT)` inside the reservation |
| `0x140d43330` | `0x1403c34d0`, the instances | `mstate[0x868]` | `0x1403c7340`: a cursor bump inside the block the object was handed; `cursor + delta > base + mstate[0x868]` -> `-1`, no host call on any path |

So an OOM is reachable with the kernel refusing nothing: both flavours compare
against the arena's own size first, and the instance flavour never asks the
host at all.

The objects, in construction order (the once-init at `0x1403c61c0`):

| global | name (`this+0x8`) | class | arena |
|---|---|---|---|
| `0x141006d80` / `0x141006d88` | "Default Heap Allocator" | V4 `0x140d437f0` (ctor `0x1403c37f0`) | 768 MB, reserved by its own mstate constructor |
| `0x141006d90` | "ThreadSafeMemHeapAllocator" | V3 `0x140d436d0` (ctor `0x1403c3990`) | 1 MB (`mstate[0x868] = 0x100000`), over a 1 MB block from the default heap |
| on demand | "MemHeapAllocator" | V2 `0x140d435b0` (ctor `0x1403c35c0`) | a computed block from the default heap; `mstate[0x868] =` the `r8` argument |
| `0x1402dc486` | "cdcRenderer Internal Heap" | V3 `0x140d436d0` (ctor `0x1403c3990`) | 4 MB, on an embedded buffer |

The grain at `mstate[0x820]` (the rounding unit inside `0x1403c6a60`) is `0x10`
on the default heap and on ThreadSafe, but a per-instance argument elsewhere
(the "MemHeapAllocator" created at `0x1403a7586` passes `0x800`).

Every allocator object links itself in the shared constructor prologue
(`0x1403c3460`): `this+0x10` = the previously built object, `this+0x18` = the
next, and `[0x141006d78]` is the newest. That chain is what the probe walks --
newest first, the default heap last.

Note on the three fatal runs: their format prints the singleton's own name
(`this+0x8`), but their `total free` (953.2-960.9 MB) is also above 768 MB.
Either those binaries carried a larger arena constant (the patch tool accepts
256-2048 MB values), or the value position in the format is not what it looks
like; the probe's live `k868` line settles which. The 14:11 build is the
patched-to-768 MB one (`[guest-reserve] ... running_total=768MB`), and the
16:53 run of 2026-10-18 repeats both facts: named fatal form, `requested
870240` (the same size the 17-10 fatal runs asked), `total free 1004119216`
(`0x3bd9a4b0`, 957.6 MB -- again above 768 MB).

### The probe, revised once (ml1222)

ml1221 read the statics at the absolute VA `0x141006d78` -- the address they
have in a *not-relocated* image. On the device the image is relocated: the
16:39 and 16:53 logs show ROTTR.exe at `0x12c000000` / `0x1246e0000` with
entry `base + 0xcc7a70` (the file's entry RVA), and the .text range
(`[iOS-xins] ... sec=base+0x1000 .. base+0xd012be`) confirms **VA = base +
RVA**. `0x141006d78` fell inside the host's reserved 128 MB executable window
("ml977: executable window [0x140000000,0x148000000) is reserved"), so the
only `[rotrr-heap]` line both runs printed is the one-time "no allocator
object yet".

The host already records each image twice, in `ios_jit_mappings[]`:
`pe_base` (the guest image mapping, where relocated absolute references land)
and `jit_base` (the JIT pool copy FEX executes). The `[data-align]` +0x2000
shift is already inside the recorded pool address (the copy's `.data` lands
16K-aligned with it: pool ≡ 0x2000 mod 0x4000 and `.data` RVA 0xfb2000 ≡
0x2000 mod 0x4000). ml1222 resolves ROTTR.exe by module name at runtime and
reads the statics (RVA `0x1006d78` head, `0x1006d80` singleton pointer) at
**both** candidates, printing one `found` line with all four raw values and
which side won:

```
[rotrr-heap] rev=ml1222 ROTTR.exe img=0x1246e0000 pool=0x149836000 (ROTTR.exe)
  cand img: sing=… head=… | cand pool: sing=… head=… -> live via=img|pool
```

From there the object/chain lines are unchanged. Whichever mapping is live is
decided by the next run's log, not by assumption.

## What is still unknown

**The decision is no longer unknown: it is `0x1403c6a60`, traced end to end
below. What is unknown is which term of the "free" number lied.** With the
arena size a constant, if the refusing object was the default heap then at the
14:11 refusal `this[0x40] + this[0x38]` was low by at least
`1028736280 - 805306368 = 223429912` bytes; if it was an instance, its arena
was simply the size the instance was built with. The probe's per-object lines
decide which. The old slot histogram (`tools/pe-slot-histogram.py`: `+0x98`
2760, `+0x90` 1622) is retired: `+0x98` is `free()`, not a reporter, and the
reporter slots are named above.

**The counter has no 64-bit reader — this was wrong, and it stopped the search.**
`0x38` is written with `addq` and set with `movq`, and a scan of the whole
`.text` finds no 64-bit `movq 0x38(reg), reg`. That looked conclusive and it
sent several rounds down the wrong road. It is an artefact of the **width**: the
reporter takes the value 32-bit, `movl %r8d, %ebp` at `0x1403c4b3a`, and the
`movl 0x38(%reg), %r8d` hits a scanner found are the same width, not a different
field. Searching only for `movq` found nothing because nothing is 64-bit.

Two more corrections from the same round:

- **The vtable has 39 entries, not 30.** It was read as ending at slot `+0xe8`,
  which made slot `+0xf0` look out of bounds. It exists, and it is the one that
  matters.
- **`pe-dataval-refs.py` skipped `FF 15` and `FF 25`**, so every indirect call
  through an IAT slot was invisible to it. It reported "0 references" for a slot
  the disassembly shows being called. That is the third time a tool here
  returned a confident zero and the zero was the bug.

## The path to the refusal, traced end to end

The reporters are reached only through the vtable, and every slot is now
named -- the first revision of this document had `+0x98` for the reporter;
`+0x98` is `free()` (`0x1403c5840`), and the fast route's reporter is `+0x90`:

```
{+0x90} -> 0x1403c4b20   fast report (format 0x140d43d50, no allocator name)
              mov (%rcx),%rax
              call *0xf0(%rax)             -> 0x1403c4ed0, the direct allocator
              test %rax,%rax ; jne done
              cmpb $0, this+0x52 ; je done     (not "live" yet: no message)
              call *0xd0(this)                 the "total free" number
              print            (the 14:11 dialog)

{+0xf0} -> 0x1403c4ed0   the direct allocator (class 0x140d436d0's {+0xf0} =
                         0x1403c4f30 is the same call under the big lock)
              cmpb $0, this+0x51           lock bypass flag
              EnterCriticalSection(this+0x58)
              movq this+0x48,%rcx          the mstate
              call 0x1403c6a60             <- the decision
              LeaveCriticalSection

{+0xf8} -> 0x1403c4d20   growing report (format 0x140d43dc0, %s = this+0x8)
              ...same gates, then:
              call 0x1403c6f80             -> (small) 0x1403c6a60
                                           -> (large) 0x1403c6fc3
              print            (the 01:15/06:32/07:53 asserts)
```

`0x1403c6a60` is the allocator, end to end: the request is rounded by the
grain at `mstate[0x820]` (`0x10` on the default heap) plus a header, with a
0x20 floor; a negative
size is NULL at entry; the small bins go by the bitmap at `mstate[0x10]`, then
the larger bins, then the top chunk: carve it if it fits, else
`call 0x1403c8f70`. That call reads the top chunk (`mstate[0x18]`) and asks the
**mstate's own `{+0x10}`** to extend the arena (`call *0x10(%rax)`); on a `-1`
return the caller re-reads the top chunk and, if it still cannot satisfy,
`xor %eax,%eax` at `0x1403c6f37` -- the refusal. It never reserves a new region
itself, and the two grow flavours above (commit-with-a-cap vs pure bump) are
why the refusal can happen with the kernel asked nothing at all.

A last consequence of the same tracing: the "total free" the reporters print
is arithmetic on `mstate[0x868]`, `this+0x40` and `this+0x38`. The bins are not
walked, so the number can read 981 MB while no single free chunk holds 0.8 MB.

Two consequences worth keeping: the report is **suppressible** — `this+0x52`
being clear makes the reporter return without asserting, which is a real patch
lever and also says the allocator asserts only once it believes it is live — and
the refusal is reached through a **non-virtual** call, so it has ordinary direct
call sites that a signature scan can find.

**What would settle it**, in order of cost:

1. The game's own `VirtualAlloc` arguments at the failing call. The host counts
   successes and failures already; logging the size and flags of the last few
   successes before the game's OOM would say whether the game asked for the
   0.8 MB at all.
2. **Implemented** (ml1221, `[rotrr-heap]`, off unless
   `MADEIRA_ROTRR_HEAP_PROBE=1`): a host-side read of the live allocator
   objects. It walks the chain at `[0x141006d78]` (via `this+0x10`, bounded)
   and prints per object: `base/limit/allocs/used/x40`, the name, the mstate
   vtable, `k818/k820/k828/k830/k838/k858/k860/k868`, and `free868` -- the
   exact number the dialog prints. Whichever object's line reproduces
   `1028736280` is the one that refused; its `k858`/`k860` then say how much of
   its arena was really consumed. (The first version, ml1220, read only the
   singleton -- which this build's 768 MB cap rules out for the 14:11 dialog;
   hence the chain walk. ml1222 repaired the other half: the image is
   relocated, so the statics are resolved from `ios_jit_mappings[]` at
   runtime -- `pe_base` and `jit_base` -- instead of the file's `0x141...`
   addresses.)

All of these are host-side and none needs the executable.

## What is explicitly ruled out

| hypothesis | verdict | evidence |
|---|---|---|
| RAM / jetsam | out | 1905 MB of 3376 MB; `[footprint]` flat |
| the 3072 MB reservation | fixed | `[guest-reserve] #1 ... running_total=768MB` |
| FEX arena exhaustion | out | 4096 MB, flat; `[fex-headroom]` 87% at worst |
| address-space fragmentation | out | band frozen, every owner `grew 0` |
| the swap tier | out | `[swap] ... refused 0`, `disk-full refusals 0` |
| the video-budget trim | out | `[wmt] ml1075 video budget now 2048 MB (base 2048, footprint 1025 of 3376)` — never moved |
| a misleading `ullTotalVirtual` | out | 512 GB reported, 454 GB real, and the real map has 10 GB free gaps. **Already implemented**: `ios_clamp_user_space_limit()` (ml990) clamps to the measured `host_addr_space_limit`; `MADEIRA_WIDE_USER_VA=1` disables it |

## The 3072 MB reservation, resolved

`COMPAT.md` records it as unpatched and untested. Both are now settled: see
`tools/rotrr-heap-patch.py` and the on-device result above. The constant at RVA
`0x3C3717` is lowered to 768 MB and the reservation succeeds.