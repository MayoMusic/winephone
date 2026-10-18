#!/usr/bin/env python3
"""The ROTTR heap patch tool must keep its traced signature, offset and the
way back to the stock 3072 MB arena.

docs/ROTTR_HEAP_OOM.md: the tool retunes one imm32 -- `mov edx, 0xC0000000`
at file offset 0x3C2D17 -- that both sizes the reservation and becomes the
arena cap (the constructor stores the same register at mstate+0x868, so one
immediate governs both; the Ghidra pass over the stock exe sees 15
VirtualAlloc call sites and this the only large fixed size). The 768 MB
workaround demonstrably exhausts in-game (ml1222: commit cursor 0x2FFBD000 of
0x30000000 when the refusal happened at 0x1403C6F37), so the tool must offer
the stock value: 3072 in the allow-list and a --restore alias.

This check fails if the tool loses the offsets, the signature, the stock size
or the restore path. It also RUNS the tool end to end against synthetic
files: a patched-to-768 copy must restore to 0xC0000000 with a backup
written; a file without the signature must be refused and left untouched;
--mb combined with --restore must be a usage error.
"""
import importlib.util
import os
import shutil
import struct
import sys
import tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
TOOL = os.path.join(ROOT, "tools", "rotrr-heap-patch.py")

failures = []


def check(what, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + what + ("  " + detail if detail else ""))
    if not cond:
        failures.append(what)


if not os.path.isfile(TOOL):
    print("FAILED: %s is missing" % TOOL)
    sys.exit(1)

src = open(TOOL, encoding="utf-8", errors="replace").read()
check("the tool points at the doc", "docs/ROTTR_HEAP_OOM.md" in src)
check("the docstring names the holdback fix", "jumbo-mb" in src)

spec = importlib.util.spec_from_file_location("rotrr_heap_patch", TOOL)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

check("the traced file offset is unchanged", mod.EXPECTED_OFF == 0x3C2D17)
check("the opcode is the traced mov edx", mod.HEAD == b"\xBA")
check("the immediate is the 4 bytes after the opcode",
      mod.IMM_AT == 1 and mod.IMM_LEN == 4)
check("the signature tail is the traced instruction stream",
      mod.TAIL == bytes.fromhex("488903" "448D4904" "48899368080000" "41B800200000"))
check("the stock size is 3072 MB", mod.STOCK_MB == 3072 and 3072 in mod.ALLOWED_MB)
check("768 (the exhausted setting) stays retunable", 768 in mod.ALLOWED_MB)
check("every allowed size is a positive whole number of MB",
      all(isinstance(m, int) and m > 0 for m in mod.ALLOWED_MB))

stock = bytes.fromhex("BA") + struct.pack("<I", 0xC0000000) + mod.TAIL
hits = [m.start() for m in mod.PATTERN.finditer(stock)]
check("the pattern matches the stock stream exactly once", hits == [0])
if hits == [0]:
    imm = struct.unpack_from("<I", stock, hits[0] + mod.IMM_AT)[0]
    check("the match lands on the 0xC0000000 immediate", imm == 0xC0000000)

tmp = tempfile.mkdtemp(prefix="rotrr-heap-patch-")
argv = sys.argv


def run(args):
    sys.argv = ["rotrr-heap-patch.py"] + args
    try:
        return mod.main()
    finally:
        sys.argv = argv


try:
    patched = os.path.join(tmp, "ROTTR.exe")
    with open(patched, "wb") as fh:
        fh.write(b"\x90" * 0x100)
        fh.write(bytes.fromhex("BA") + struct.pack("<I", 768 << 20) + mod.TAIL)
        fh.write(b"\x90" * 0x100)

    rc = run([patched, "--restore"])
    check("--restore exits 0 on a 768 MB synthetic copy", rc == 0)
    with open(patched, "rb") as fh:
        data = fh.read()
    got = struct.unpack_from("<I", data, 0x100 + mod.IMM_AT)[0]
    check("--restore wrote 0xC0000000", got == 0xC0000000)
    check("a timestamped backup was written",
          any(n.startswith("ROTTR.exe.bak.") for n in os.listdir(tmp)))

    bad = os.path.join(tmp, "NOPE.exe")
    with open(bad, "wb") as fh:
        fh.write(b"\x90" * 0x80)
    before = open(bad, "rb").read()
    rc = run([bad, "--restore"])
    check("a file without the signature is refused", rc == 1)
    check("...and is left untouched", open(bad, "rb").read() == before)

    rc = run([patched, "--mb", "512", "--restore"])
    check("--mb together with --restore is a usage error", rc == 2)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if failures:
    print("\nFAILED: %d check(s)" % len(failures))
    sys.exit(1)
print("\nall checks passed")
