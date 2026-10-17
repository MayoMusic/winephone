#!/usr/bin/env python3
"""patches/ must be bytes git can read, and must carry what it claims to.

Two separate failures, both silent until CI.

The first was encoding. Both patch files were UTF-16LE -- a BOM, then every
character with a zero byte after it -- because they were written with a shell
redirect on a host whose shell encodes redirected text that way, rather than
with `git diff --output=`, which writes the bytes git produced. git apply cannot
read that: it reports "No valid patches in input", which reads like a malformed
file and sends you looking at the diff hunks when the content is fine. Reading
it back with a text API hides it completely, because the API decodes the BOM and
every line looks correct.

The second is a patch that applies but does not contain the change it is named
for. The instrumentation in dxmt-wmt-null-dest.patch is the only reason anyone is
running this build, so the markers it adds are asserted here by name: a patch
that lost them to a bad regeneration would otherwise apply cleanly, compile, and
produce an IPA with no diagnostics in it.

This does not verify that the patches apply; scripts/apply-submodule-patches.sh
does that against the real submodule in the build. This is the cheap check that
runs before that, and it names the patch that is wrong.
"""
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PATCH_DIR = os.path.join(ROOT, "patches")

# Patch -> the strings it must contain. Each is a tag the change exists to emit,
# so its absence means the build would not produce the evidence it was made for.
EXPECTED = {
    "dxmt-winemetal-static-implibs.patch": ["static: true", "lib_winecrt0", "lib_dbghelp"],
    "dxmt-wmt-null-dest.patch": [
        "[tex-reject]", "[tex-host]", "[tex-bad-pe]", "[wmt-fail]", "[wmt-selftest]",
        "blit-ring", "dxbc-dump", "wmt_airconv_note_dxbc", "mtl-debug",
        "wmt_null_dest", "MTL_DEBUG_LAYER", "UNRESOLVED",
    ],
}

failures = []


def check(what, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + what + ("  " + detail if detail else ""))
    if not cond:
        failures.append(what)


if not os.path.isdir(PATCH_DIR):
    print("FAIL no patches directory")
    sys.exit(1)

present = sorted(f for f in os.listdir(PATCH_DIR) if f.endswith(".patch"))
check("patches exist at all", bool(present), ", ".join(present))

for name in present:
    path = os.path.join(PATCH_DIR, name)
    raw = open(path, "rb").read()

    check("%s is not empty" % name, len(raw) > 0, "%d bytes" % len(raw))

    # The encoding trap. A BOM of FF FE or FE FF, or any NUL byte, means git
    # apply will reject it whatever the diff says.
    check("%s has no UTF BOM" % name, not raw.startswith(b"\xef\xbb\xbf")
          and not raw.startswith(b"\xff\xfe") and not raw.startswith(b"\xfe\xff"),
          "starts with %s" % raw[:2].hex())
    check("%s has no NUL bytes" % name, b"\x00" not in raw,
          "a NUL means it was written as UTF-16")
    check("%s starts with a diff header" % name, raw.startswith(b"diff --git "),
          repr(raw[:12]))
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        check("%s is pure ASCII" % name, False, str(exc)[:70])
        text = raw.decode("utf-8", "replace")
    else:
        check("%s is pure ASCII" % name, True)
    check("%s names files it changes" % name, "+++ b/" in text)

for name, markers in sorted(EXPECTED.items()):
    path = os.path.join(PATCH_DIR, name)
    if not os.path.exists(path):
        check("%s is present" % name, False, os.path.relpath(path, ROOT))
        continue
    text = open(path, "rb").read().decode("utf-8", "replace")
    missing = [m for m in markers if m not in text]
    check("%s carries everything it is for" % name, not missing,
          "missing: " + ", ".join(missing) if missing else
          "%d markers" % len(markers))

# The two dxmt patches must together cover every file they claim to touch, and
# the instrumentation must be in the same patch as the code that emits it.
null_dest = os.path.join(PATCH_DIR, "dxmt-wmt-null-dest.patch")
if os.path.exists(null_dest):
    text = open(null_dest, "rb").read().decode("utf-8", "replace")
    for f in ("src/winemetal/winemetal_thunks.c",
              "src/winemetal/unix/winemetal_unix.c",
              "src/airconv/dxbc_converter.cpp"):
        check("null-dest patch covers %s" % f, f in text)
    check("the PE self-test ships in the same patch as the PE WARN change",
          "[wmt-selftest]" in text and "[wmt-fail]" in text,
          "splitting them would leave a build where one prints and the other cannot")

print("PASS" if not failures else "FAILED: " + "; ".join(failures))
sys.exit(0 if not failures else 1)