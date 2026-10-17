# ROTTR: the level-load "Out of memory", and why it is not ours

**Status: open, and outside this tree.** Everything below is measured on a
device run, and the conclusion is that the host never refused anything.

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

The reporter is `0x1403c4d20`, reached only through a vtable. Its arguments are
`rcx = the allocator, rdx = tag, r8 = total free, r9d = allocator index`, and
the wrapper at `0x1403c4e50` passes `r8` straight through.

**`total free` is the game's own counter, not the operating system.** The object
layout, from the constructor at `0x1403c37f0`:

```
+0x28  arena base          +0x2c  arena limit
+0x38  free counter        +0x48  current block pointer
+0x50/51 size + flag       +0x52  ready flag
+0x58  CRITICAL_SECTION    +0x8F0  a second one
+0x80  first subheap       [0]    vtable -> 0x140d437f0
```

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

There are three allocator classes (`vtable` `0x140d43490`, `0x140d436d0`,
`0x140d437f0`) sharing the arena globals `0x141006d40` (base) and
`0x141006d40 + 0x141006d44` (limit). The default instance is the singleton at
`0x141006d80`, referenced 4507 times.

## What is still unknown

**The decision.** The function that decides "I cannot satisfy this" and calls
the reporter was not found. Slot numbers do not transfer between the three
vtables, so a slot histogram over the singleton's call sites
(`tools/pe-slot-histogram.py`: `+0x98` 2760, `+0x90` 1622) ranks the entry
points without naming the failure path.

**The counter has no 64-bit reader.** `0x38` is written with `addq` and set with
`movq %r15, 0x38(%r14)`, and a scan of the whole `.text` finds **no** 64-bit
`movq 0x38(reg), reg` — the 5644 hits are 32-bit `movl` of a different field.
So either the value reaches the reporter through a chain the signature scan does
not follow, or `0x38` is not the field the reporter prints. That is where this
stops.

**What would settle it**, in order of cost:

1. The game's own `VirtualAlloc` arguments at the failing call. The host counts
   successes and failures already; logging the size and flags of the last few
   successes before the game's OOM would say whether the game asked for the
   0.8 MB at all.
2. A read of the live object's `+0x28`, `+0x2c`, `+0x38` at the moment the
   `[guest-log]` line is emitted. The `[guest-log]` path already sees the guest's
   assert; it would need to find the singleton at `0x141006d80` and print three
   fields.

Both are host-side and neither needs the executable.

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