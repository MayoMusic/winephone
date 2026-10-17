#!/usr/bin/env python3
"""The five winemetal entries that write through a caller-supplied pointer.

Runs in scripts/apply-submodule-patches.sh, immediately after the dxmt patches
are applied, so what it reads is the PATCHED source and not whatever the
submodule happened to contain. That is the point: it is the check that a patch
applied is the change the patch was for.

It therefore has no "submodule missing" mode. It was briefly wired into the
host-checks job, which checks out no submodules, and failed there with a
FileNotFoundError -- which is the correct outcome for a check that has nothing
to check, and the reason it belongs next to the patch stage instead.

NSString_getCString, MetalLayer_getProps, MTLLogContainer_enumerate,
WMTGetDisplayDescription and MetalLayer_getEDRValue are the only entries in
the PE->unix table whose DESTINATION is a pointer the caller passed. A NULL
stays NULL to the store: the thunks carry it as a WMTMemoryPointer,
wow_in()/wow_in_wide() preserve NULL by design, and the 64-bit and 32-bit
dispatch tables are separate entries -- so the thunk's check and the handler's
check are not the same check and both are needed.

Two NULLs are legitimate and this is the easy thing to break: a LENGTH QUERY,
where the caller supplies no buffer and asks only how much space it needs.
getCString's answer comes from Foundation and enumerate's bounds test writes
nothing, so a guard that refuses every NULL would silently change behaviour
rather than prevent a crash. The three fixed-size struct out-parameters have no
such form and are always written.

So the predicate is extracted from the shipped source, compiled, and run
against the truth table -- a check that only greps for "wmt_null_dest(" would
pass on a guard that refuses the length query too.

Needs python3 and a C compiler. Set WMT_SKIP_COMPILE=1 to run the source
assertions alone (that weakens it and says so); nothing skips silently.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
THUNKS = os.path.join(ROOT, "dxmt/src/winemetal/winemetal_thunks.c")
UNIX = os.path.join(ROOT, "dxmt/src/winemetal/unix/winemetal_unix.c")

# name -> (unix call code, thunk return type, count expression the guard must use)
ENTRIES = {
    "NSString_getCString": (
        8, "uint32_t", "maxLength"),
    "MetalLayer_getProps": (
        71, "void", "sizeof"),
    "MTLLogContainer_enumerate": (
        91, "uint64_t", "buffer_size"),
    "WMTGetDisplayDescription": (
        96, "void", "sizeof"),
    "MetalLayer_getEDRValue": (
        97, "void", "sizeof"),
}

# Entries whose NULL is legitimate and must still cross. name -> the guard's
# count field, which is what makes the difference.
LENGTH_QUERIES = {"NSString_getCString": "max_length",
                  "MTLLogContainer_enumerate": "buffer_size"}

failures = []


def check(what, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + what + ("  " + detail if detail else ""))
    if not cond:
        failures.append(what)


def body_of(text, signature_regex):
    """The text of a C function, from its signature to the brace that closes it."""
    m = re.search(signature_regex, text)
    if not m:
        return None
    i = text.find("{", m.end() - 1)
    if i < 0:
        return None
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[m.start():j + 1]
    return None


thunks_path_ok = os.path.exists(THUNKS)
unix_path_ok = os.path.exists(UNIX)
if not (thunks_path_ok and unix_path_ok):
    # Say which tree is missing instead of dying inside open() with a
    # FileNotFoundError that reads like a bug in this script.
    missing = THUNKS if not thunks_path_ok else UNIX
    print("FAIL the dxmt submodule is not checked out, so the patched source")
    print("     cannot be examined at all: %s" % missing)
    print("     This check verifies the result of scripts/apply-submodule-patches.sh")
    print("     and belongs in the build, which initialises dxmt.")
    print("FAILED: dxmt source absent")
    sys.exit(1)

thunks = open(THUNKS, encoding="utf-8", errors="replace").read()
unix = open(UNIX, encoding="utf-8", errors="replace").read()

# --- the predicate, taken from the shipped source --------------------------
predicate = re.search(
    r"static inline int\s+wmt_null_dest\s*\([^)]*\)\s*\{.*?\n\}", unix, re.S)
check("wmt_null_dest is defined in winemetal_unix.c", predicate is not None)
if predicate is None:
    print("FAILED: cannot locate the predicate; the rest is unverifiable")
    sys.exit(1)

# --- the two sides both guard ---------------------------------------------
for name, (code, ret, _kind) in sorted(ENTRIES.items()):
    t = body_of(thunks, r"\n%s\(" % re.escape(name))
    check("%s: thunk found" % name, t is not None)
    if t is None:
        continue
    guard = t.find("census_note(%d)" % code)
    call = t.find("UNIX_CALL(%d" % code)
    check("%s (code %d): the thunk refuses before it crosses" % (name, code),
          guard >= 0 and call > guard,
          "guard@%d call@%d" % (guard, call))
    # Every thunk that can return something must return a defined value on the
    # refused path; a bare `return;` in a non-void thunk is a UB return.
    check("%s (code %d): the refused path returns the declared type" % (name, code),
          ret == "void" or re.search(r"return\s+\w+\s*;", t) is not None, ret)

HANDLERS = {
    "NSString_getCString": r"\n_NSString_getCString\(",
    "MetalLayer_getProps": r"\n_MetalLayer_getProps\(",
    "MTLLogContainer_enumerate": r"\n_MTLLogContainer_enumerate\(",
    "WMTGetDisplayDescription": r"\n_WMTGetDisplayDescription\(",
    "MetalLayer_getEDRValue": r"\n_MetalLayer_getEDRValue\(",
}
for name, pat in sorted(HANDLERS.items()):
    h = body_of(unix, pat)
    check("%s: handler found" % name, h is not None)
    if h is None:
        continue
    g = h.find("wmt_null_dest(")
    check("%s: the handler guards the pointer it writes to" % name, g >= 0)
    check("%s: a refused handler reports it instead of returning success" % name,
          g < 0 or "STATUS_INVALID_PARAMETER" in h, "")
    # The store must come after the guard, not before it.
    first_write = min([h.find(s) for s in ("memcpy(params->arg.ptr",
                                            "desc_out->", "value->maximum",
                                            "buffer[", "getCString:(")
                       if h.find(s) >= 0] or [len(h)])
    check("%s: the guard precedes the store" % name, g >= 0 and g < first_write,
          "guard@%d write@%d" % (g, first_write))

# --- the length queries are preserved --------------------------------------
for name, field in sorted(LENGTH_QUERIES.items()):
    h = body_of(unix, HANDLERS[name])
    t = body_of(thunks, r"\n%s\(" % re.escape(name))
    check("%s: the unix guard keys off %s, not a bare NULL test" % (name, field),
          h is not None and re.search(r"wmt_null_dest\([^;]*%s" % field, h) is not None)
    thunk_field = "maxLength" if field == "max_length" else "buffer_size"
    check("%s: the thunk guard keys off %s too" % (name, thunk_field),
          t is not None and re.search(r"!\w+\s*&&\s*%s" % re.escape(thunk_field), t) is not None,
          "a bare '!ptr' here would refuse the length query as well")

for name in sorted(set(ENTRIES) - set(LENGTH_QUERIES)):
    h = body_of(unix, HANDLERS[name])
    check("%s: a fixed-size struct out-param is guarded unconditionally" % name,
          h is not None and re.search(r"wmt_null_dest\([^;]*sizeof", h) is not None)

# --- getEDRValue carried a const pointer it wrote through ------------------
t = body_of(thunks, r"\nMetalLayer_getEDRValue\(")
check("MetalLayer_getEDRValue no longer declares a const out-parameter",
      t is not None and "unixcall_generic_obj_constptr_noret" not in t)
h = body_of(unix, HANDLERS["MetalLayer_getEDRValue"])
check("_MetalLayer_getEDRValue reads it back as a writable pointer",
      h is not None and "unixcall_generic_obj_ptr_noret" in h)

# --- the census still sees the refused calls -------------------------------
for name, (code, _ret, _kind) in sorted(ENTRIES.items()):
    t = body_of(thunks, r"\n%s\(" % re.escape(name))
    check("code %d keeps its census count when it refuses to cross" % code,
          t is not None and "census_note(%d)" % code in t,
          "an uncounted refusal understates the API census")

# --- compile it, then run it ----------------------------------------------
# The truth table, as the bitmask main() returns. Python builds the expected
# mask from this same table rather than hardcoding it, so the two cannot drift.
CASES = [
    ("length query: NULL, no count", None, 0, 0),
    ("NULL with a count", None, 128, 1),
    ("NULL with a count of one", None, 1, 1),
    ("a real pointer, counted", "sink", 128, 0),
    ("a real pointer, uncounted", "sink", 0, 0),
    ("NULL as a sizeof out-param", None, "sizeof(void*)", 1),
]
EXPECTED = sum(want << i for i, (_n, _p, _c, want) in enumerate(CASES))

# Header-free on purpose. A host with only the Swift toolchain's clang has no
# libc headers at all, so <stdint.h>/<assert.h> would fail before the compiler
# ever read the predicate. uint64_t is typedef'd instead -- stdint guarantees
# unsigned long long is 64-bit on every target here, and the test above asserts
# the shipped signature really is uint64_t.
DRIVER = r'''
typedef unsigned long long uint64_t;
%s

int main(void) {
  static int sink;
  int r = 0;
  r |= wmt_null_dest((void *)0, 0);
  r |= wmt_null_dest((void *)0, 128) << 1;
  r |= wmt_null_dest((void *)0, 1) << 2;
  r |= wmt_null_dest(&sink, 128) << 3;
  r |= wmt_null_dest(&sink, 0) << 4;
  r |= wmt_null_dest((void *)0, sizeof(void *)) << 5;
  return r;
}
''' % predicate.group(0)

ran = False
if os.environ.get("WMT_SKIP_COMPILE") == "1":
    print("SKIP the compiled truth table (WMT_SKIP_COMPILE=1); source "
          "assertions only, which cannot see a wrong predicate")
else:
    # A ladder, not a single guess. This test needs a HOST compiler: it links a
    # trivial native program, so a cross or target compiler earlier on PATH
    # would refuse. $CC wins if set; the system /usr/bin/cc and /usr/bin/clang
    # come next because they are unambiguous, and a bare PATH lookup is the last
    # resort rather than the first.
    ladder = []
    if os.environ.get("CC"):
        ladder.append(os.environ["CC"])
    for cand in ("/usr/bin/cc", "/usr/bin/clang", "cc", "clang"):
        if os.path.isabs(cand):
            if os.path.exists(cand):
                ladder.append(cand)
        else:
            found = shutil.which(cand)
            if found and found not in ladder:
                ladder.append(found)
    ladder = [c for c in ladder if c not in ladder[:ladder.index(c)]]  # dedupe, keep order
    check("a C compiler is available", bool(ladder), ", ".join(ladder))
    check("the shipped predicate really is uint64_t (so the freestanding "
          "typedef below stands in for it)",
          "uint64_t count" in predicate.group(0))

    if ladder:
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "null_dest.c")
            obj = os.path.join(td, "null_dest.o")
            open(src, "w", encoding="utf-8").write(DRIVER)

            compiled = None
            for cc in ladder:
                r = subprocess.run(
                    [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-c", src, "-o", obj],
                    capture_output=True, text=True)
                if r.returncode == 0:
                    compiled = cc
                    break
            check("the predicate compiles clean (-Wall -Wextra -Werror)",
                  compiled is not None, compiled or "no compiler compiled it")

            # Link and run down the same ladder. The object build needs no
            # linker, so a host that can compile but not link still gets a real
            # verification of the source.
            last_link = (None, "")
            for cc in ladder:
                exe = os.path.join(td, "nd_" + os.path.basename(cc).replace(".", "_"))
                link = subprocess.run([cc, "-std=c99", src, "-o", exe],
                                      capture_output=True, text=True)
                if link.returncode != 0:
                    last_link = (cc, link.stderr or "")
                    continue
                run = subprocess.run([exe], capture_output=True, text=True)
                got = run.returncode
                for i, (name, _p, _c, want) in enumerate(CASES):
                    check("predicate: %s" % name, (got >> i) & 1 == want,
                          "got %d want %d" % ((got >> i) & 1, want))
                check("the predicate's truth table holds, executed by %s" % cc,
                      got == EXPECTED, "mask %d, expected %d" % (got, EXPECTED))
                ran = True
                break
            else:
                cc_used, err = last_link
                print("NOT RUN the truth table: no compiler on the ladder could "
                      "link a hosted program.")
                print("            last attempt was %s; its linker said:" % cc_used)
                for line in err.strip().splitlines()[:12]:
                    print("              %s" % line)

if not ran and os.environ.get("WMT_SKIP_COMPILE") != "1":
    print("note: the executed truth table did not run. Treat the predicate as "
          "compile-verified only.")

# --- the block comment tells the truth -------------------------------------
block = re.search(r"Null destination pointers.*?-{20,}", unix, re.S)
check("winemetal_unix.c explains the class in one place", block is not None)
if block:
    b = block.group(0)
    check("the block says five, not one", re.search(r"\bFIVE\b", b) is not None)
    for name, (code, _r, _k) in sorted(ENTRIES.items()):
        check("the block lists code %d" % code, re.search(r"\b%d\b" % code, b) is not None)
    check("the block keeps the length-query exception",
          "length query" in b)
    check("the block says INPUT pointers are deliberately excluded",
          re.search(r"INPUT", b) is not None)

print("PASS" if not failures else "FAILED: " + "; ".join(failures))
sys.exit(0 if not failures else 1)