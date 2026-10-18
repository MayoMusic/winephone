#!/usr/bin/env python3
r"""
ROTTR.exe - retune the hard-coded 3 GB transient-heap reservation.

WinePhone on iOS
================
What this patches
-----------------
Rise of the Tomb Raider's CDC allocator reserves one arena at start-up with

    VirtualAlloc(NULL, 0xC0000000, MEM_RESERVE, PAGE_READWRITE)

That is 3072 MB of *address space*, fixed at compile time. On an iPhone the
process VA ceiling leaves no contiguous 3 GB gap, the call returns NULL, and the
game does this (RVA 0x3C3717, inside a 341-byte function at RVA 0x3C3690):

    mov edx, 0xC0000000        ; the size, hard-coded
    ...
    call qword ptr [rip+...]   ; -> VirtualAlloc
    test rax, rax
    jne  ok
    mov  r8, [rbx+0x868]
    lea  rdx, [rip+...]       ; "Unable to reserve %uMB of address space."
    shr  r8, 20                ; 0xC0000000 >> 20 = 3072
    call 0x14004b9c0           ; snprintf
    lea  r8, [rip+...]        ; "CDC"  (the dialog title)
    call qword ptr [rip+...]   ; -> MessageBoxA
    or   ecx, -1
    call qword ptr [rip+...]   ; -> ExitProcess

There is no retry and no smaller fallback anywhere in that function: it is one
shot, then it exits. This is the only hard-coded reservation >= 32 MB in the
whole binary - all 14 other VirtualAlloc call sites take their size from a
register at run time. (A full Ghidra pass over the stock exe, 2026-10-18, sees
15 call sites, this the only one with a fixed large size. The same
`mov edx, imm32` also becomes the arena cap: the store below keeps the
register, so one immediate governs both.)

The patch changes the immediate from 3072 MB to a size that fits. MEM_RESERVE
alone does not commit physical pages, so the arena still commits on demand; only
the address-space claim shrinks.

--restore puts the stock 3072 MB back. That value only works on iOS together
with the host's boot jumbo holdback: with `jumbo-mb = 3072` in madeira.cfg the
host carves a 3 GB hole at start-up and hands it to the first guest
reservation the kernel cannot place, which is this one. Keep the two
together. The 768 MB setting is the workaround that ran out for real during
the level load (ml1222: commit cursor 0x2FFBD000 of 0x30000000, then the
game's own OOM report), so lowering is for retuning, restoring is for fixing.
docs/ROTTR_HEAP_OOM.md has the whole trace.

What this does NOT fix
----------------------
If the arena really does need more than the patched size, the failure moves
later into the level load and the game reports it itself -- on device the
message is `ERROR: Out of memory, "UNKNOWN" requested ... (<N> total free
...)` while the commit cursor sits at the arena's end. That is what 768 MB
did; the way out is --restore (with the holdback), not a smaller --mb.

Usage
-----
    python rotrr-heap-patch.py "D:\Rise of the Tomb Raider\ROTTR.exe"
    python rotrr-heap-patch.py "D:\Rise of the Tomb Raider\ROTTR.exe" --mb 512
    python rotrr-heap-patch.py "D:\Rise of the Tomb Raider\ROTTR.exe" --restore

A timestamped .bak is written next to the exe before anything is modified.
Re-running is safe: it finds its own patch and can retune the size.
--restore is the shorthand for the stock 3072 MB (STOCK_MB below).
"""
import os
import re
import shutil
import struct
import sys
import time

# The instruction stream around the immediate:
#   BA <imm32>              mov edx, imm32      <- the size we change
#   48 89 03                mov [rbx], rax
#   44 8D 49 04             lea r9d, [rcx+4]    (PAGE_READWRITE)
#   48 89 93 68 08 00 00    mov [rbx+0x868], rdx (store the arena size)
#   41 B8 00 20 00 00       mov r8d, 0x2000     (MEM_RESERVE)
# The four immediate bytes are a wildcard, so the patch is found whatever the
# current size is, and re-running retunes instead of failing.
HEAD = bytes.fromhex("BA")
TAIL = bytes.fromhex(
    "488903" "448D4904" "48899368080000" "41B800200000"
)
IMM_AT = 1
IMM_LEN = 4
PATTERN = re.compile(re.escape(HEAD) + b"...." + re.escape(TAIL), re.S)
EXPECTED_OFF = 0x3C2D17
ALLOWED_MB = (256, 384, 512, 768, 1024, 1536, 2048, 3072)
STOCK_MB = 3072


def fail(msg):
    print("ERROR: %s" % msg)
    return 2


def main() -> int:
    argv = sys.argv[1:]
    path = None
    mb = 768
    mb_set = False
    restore = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--mb":
            i += 1
            if i >= len(argv):
                return fail("--mb needs a number, e.g. --mb 512")
            try:
                mb = int(argv[i])
            except ValueError:
                return fail("--mb needs a number, got %r" % argv[i])
            mb_set = True
        elif a.startswith("--mb="):
            try:
                mb = int(a.split("=", 1)[1])
            except ValueError:
                return fail("--mb needs a number, got %r" % a)
            mb_set = True
        elif a == "--restore":
            restore = True
        elif a.startswith("-"):
            return fail("unknown option %r" % a)
        else:
            if path is not None:
                return fail("give exactly one path to ROTTR.exe "
                            "(got %r and %r)" % (path, a))
            path = a
        i += 1
    if path is None:
        print(__doc__)
        return fail("give exactly one path to ROTTR.exe")
    if restore and mb_set:
        return fail("--restore sets the stock %d MB; do not combine it with "
                    "--mb" % STOCK_MB)
    if restore:
        mb = STOCK_MB
    if mb not in ALLOWED_MB:
        return fail("--mb must be one of %s" % (ALLOWED_MB,))
    if not os.path.isfile(path):
        return fail("no such file: %s" % path)

    with open(path, "rb") as fh:
        data = bytearray(fh.read())
    original_size = len(data)

    hits = [m.start() for m in PATTERN.finditer(bytes(data))]

    if len(hits) == 0:
        print("REFUSING TO PATCH: found 0 matches.")
        print("  The instruction stream this patch looks for is not in the")
        print("  file. Either this is a different build of ROTTR.exe, or the")
        print("  bytes were changed by something else. Nothing was written.")
        return 1
    if len(hits) > 1:
        print("REFUSING TO PATCH: found %d matches, at:" % len(hits))
        for h in hits:
            print("  0x%X" % h)
        print("  Refusing, because patching an unknown one could corrupt a")
        print("  different code path. Nothing was written.")
        return 1

    off = hits[0]
    cur = struct.unpack_from("<I", data, off + IMM_AT)[0]
    target = mb << 20
    print("file    : %s" % path)
    print("size    : %d bytes" % original_size)
    print("match   : 0x%X (expected 0x%X) - exactly 1, good"
          % (off, EXPECTED_OFF))
    print("opcode  : %s  (mov edx, imm32)"
          % data[off:off + 1].hex(" ").upper())
    print("before  : edx = 0x%08X  (%d MB)" % (cur, cur // (1 << 20)))
    print("after   : edx = 0x%08X  (%d MB)" % (target, mb))

    if cur == target:
        print("no change needed - the file is already set to %d MB." % mb)
        return 0
    if cur % (1 << 20) != 0:
        print("NOTE: the current value is not a whole number of MB.")

    bak = "%s.bak.%s" % (path, time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(path, bak)
    print("backup  : %s" % bak)

    new = bytearray(data)
    struct.pack_into("<I", new, off + IMM_AT, target)
    with open(path, "wb") as fh:
        fh.write(new)

    # verify by reading the file back
    with open(path, "rb") as fh:
        verify = bytearray(fh.read())
    if len(verify) != original_size:
        print("FAILED: file size changed; restore from the backup.")
        return 1
    reread = [m.start() for m in PATTERN.finditer(bytes(verify))]
    if len(reread) != 1 or reread[0] != off:
        print("FAILED: signature did not survive the write; restore backup.")
        return 1
    now = struct.unpack_from("<I", verify, off + IMM_AT)[0]
    if now != target:
        print("FAILED: reads back as 0x%08X; restore backup." % now)
        return 1
    touched = [i for i in range(original_size) if verify[i] != data[i]]
    allowed = set(range(off + IMM_AT, off + IMM_AT + IMM_LEN))
    if not set(touched) <= allowed:
        print("FAILED: bytes changed outside the immediate (%r); "
              "restore backup." % sorted(set(touched) - allowed))
        return 1
    print("verified: size unchanged, %d byte(s) differ, all inside the "
          "4-byte immediate, signature intact" % len(touched))
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())