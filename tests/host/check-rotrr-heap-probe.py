#!/usr/bin/env python3
"""The ROTTR heap probe must exist, read safely, walk every allocator object,
and stay off by default.

ml1221 (docs/ROTTR_HEAP_OOM.md): the 14:11 dialog -- "Out of memory,
"UNKNOWN" requested 112460 bytes (... 1028736280 total free ...)" -- is the
game's own accounting, and the object that printed it is not the singleton.
The reporter asks {+0xd0} for that number and {+0xd0} is literally
"mstate[0x868] - this[0x40] - this[0x38]", while the singleton's mstate[0x868]
is its 768 MB arena and the dialog printed 981.1 MB. So the probe walks the
allocator-object chain ([0x141006d78], linked through this+0x10 at
construction) and prints each object.

ml1222: that chain head is a RELOCATED address on the device -- the 16:39 /
16:53 logs show ROTTR.exe at 0x12c000000 / 0x1246e0000 with entry = base +
0xcc7a70 (the file's entry RVA), i.e. VA = base + RVA.  The probe must
resolve the entry (ios_jit_mappings: pe_base = guest image, jit_base = the
JIT pool copy), read the statics at BOTH candidates, and let the live pointer
decide.  Seven properties matter, each one a real failure mode:

  1. it exists and is called from the warmer tick (a probe that is never
     called reads as a clean run);
  2. every guest read goes through mach_vm_read_overwrite (a dereference of
     the statics before ROTTR.exe is mapped would crash the app -- the same
     mistake virtual_ios.c documents twice at other sites);
  3. it is gated on MADEIRA_ROTRR_HEAP_PROBE and stays silent otherwise (a
     hard-coded guest VA is only correct for this game);
  4. it resolves the module at runtime and reads the chain, not one object:
     singleton pointer RVA 0x1006d80 and head RVA 0x1006d78 at both the image
     and the pool copy, next-previous at this+0x10, bounded so a stale link
     cannot spin;
  5. the addresses it reads stay the traced ones (mstate at this+0x48,
     capacity at mstate+0x868 -- NOT +0x820, which is the 0x10 alloc grain);
  6. the printed name cannot inject format directives ('%' is folded);
  7. no absolute 0x141 static VAs come back (the image is relocated).
"""
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SRC = os.path.join(ROOT, "build", "ntdll-unix", "virtual_ios.c")

failures = []


def check(what, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + what + ("  " + detail if detail else ""))
    if not cond:
        failures.append(what)


if not os.path.exists(SRC):
    print("FAILED: %s is missing" % SRC)
    sys.exit(1)

text = open(SRC, encoding="utf-8", errors="replace").read()

check("the probe is enabled by an environment variable",
      'getenv( "MADEIRA_ROTRR_HEAP_PROBE" )' in text)
check("the probe function exists", "static void ios_rotrr_heap_probe( void )" in text)
check("the per-object printer exists",
      "static void ios_rotrr_probe_object( const char *tag, unsigned long long obj )" in text)
check("the probe refuses to run when not wanted",
      "if (!ios_rotrr_heap_probe_wanted()) return;" in text)
check("the probe is called from the warmer tick",
      "if ((cycle % 5) == 0) ios_rotrr_heap_probe();" in text)
check("the probe resolves ROTTR.exe at runtime (the image is relocated)",
      "static int ios_rotrr_probe_locate(" in text)
check("the resolver walks the host image table and matches the module name",
      "ios_jit_mappings[i].pe_base" in text and 'strstr( n, "ROTTR" )' in text)
check("the resolver reads the PE-view signature through the checked reader",
      "mz != 0x5a4d" in text)
check("the probe reads the singleton pointer RVA at BOTH candidates",
      "img + 0x1006d80ULL" in text and "pool + 0x1006d80ULL" in text)
check("the probe reads the chain-head RVA at BOTH candidates",
      "img + 0x1006d78ULL" in text and "pool + 0x1006d78ULL" in text)
check("no hard-coded absolute statics remain",
      "0x141006d78ULL" not in text and "0x141006d80ULL" not in text)
check("the chain walk goes through this+0x10",
      "cur + 0x10" in text)
check("the chain walk is bounded", "i < 15" in text)
check("the probe reads the mstate capacity block",
      "mstate + 0x818" in text)
check("the capacity field is +0x868, not the +0x820 grain",
      "kbuf + 0x50" in text and "mstate + 0x820" not in text)
check("the name reader folds '%' so a stale link cannot inject a format",
      "nb[i] != '%'" in text)
check("the probe comment points at the doc",
      "docs/ROTTR_HEAP_OOM.md" in text)

# All guest reads must go through the one checked helper. Find the helper and
# assert it uses the kernel copy; then assert the probe bodies never
# dereference a guest address directly (no cast-then-deref, no `*(...*)0x1...`).
helper = text.find("static int ios_rotrr_probe_read(")
check("the read helper exists", helper != -1)
if helper != -1:
    body = text[helper:helper + 700]
    check("the read helper uses mach_vm_read_overwrite",
          "mach_vm_read_overwrite" in body)
    check("the read helper checks the copied size", "got ==" in body)

probe = text.find("static void ios_rotrr_probe_object( const char *tag, unsigned long long obj )")
check("the probe body is findable", probe != -1)
if probe != -1:
    body = text[probe:probe + 8000]
    check("the probe body has no direct dereference of a guest VA",
          not any(t in body for t in ("*( ", "*(volatile", "*(unsigned", "*(unsigned long long *)0x1", "*((unsigned")))
    check("the probe body reads through the helper only",
          "ios_rotrr_probe_read(" in body and "memcpy(" in body)
    check("the probe reports the exact 'free' term the dialog prints",
          "free868=%lld" in body)
    check("the walk is in the same span as the printer",
          "ios_rotrr_probe_object( \"list\", cur )" in body)

if failures:
    print("\nFAILED: %d check(s)" % len(failures))
    sys.exit(1)
print("\nall checks passed")
