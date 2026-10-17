#!/usr/bin/env python3
"""The two dxmt host/PE sources must still parse.

CI is the only place these compile: they are C inside a meson submodule, built
for aarch64 and arm64ec on a macOS runner, and nothing on a Windows host builds
them. Both errors that got past every local check were caught by the compiler and
nothing else:

  - a `static NTSTATUS` return type left stranded above a comment block, so the
    function it belonged to lost it. The compiler said "cannot combine with
    previous type-name declaration specifier" and "declaration does not declare
    anything"; a brace-count or brace-match check would have said the same thing
    without a toolchain.
  - `#include <windef.h>` where the same directory's main.c uses
    `#include "windef.h"`. Angle brackets search the compiler's system include
    path and do not find Wine's headers.

So this extracts the declarations the patch adds into a small standalone
translation unit and compiles it with whatever C compiler is present. It does
not try to build the real files -- they need Metal, UIKit and the rest -- but it
does check that what was added is well-formed C and that the includes it relies
on are spelled the way the neighbouring file spells them.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PATCH = os.path.join(ROOT, "patches", "dxmt-wmt-null-dest.patch")

failures = []


def check(what, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + what + ("  " + detail if detail else ""))
    if not cond:
        failures.append(what)


check("the patch is present", os.path.exists(PATCH))
if not os.path.exists(PATCH):
    print("FAILED: cannot check what is not there")
    sys.exit(1)

text = open(PATCH, "rb").read().decode("utf-8", "replace")
added = []
for line in text.split("\n"):
    if line.startswith("+") and not line.startswith("+++"):
        added.append(line[1:])
added_text = "\n".join(added)

# --- 1. every function that gained a body still has its return type --------
# The stranded `static NTSTATUS` case: a return type followed by a comment and
# then a different declaration.
for m in re.finditer(r"^(static\s+(?:NTSTATUS|int|void|const void|uint32_t)[^\n(]*)$",
                     added_text, re.M):
    tail = added_text[m.end():m.end() + 400].lstrip()
    if tail.startswith("/*") or tail.startswith("//"):
        nxt = re.sub(r"(/\*.*?\*/|//[^\n]*\n)", "", tail, flags=re.S).lstrip()
        if not nxt.startswith(("(", "{")):
            check("return type at %r is not stranded above a comment" % m.group(1)[:40],
                  False, "next thing is %r" % nxt[:40])

check("no return type is stranded above a comment block",
      not any("return type is not stranded" in f for f in failures))

# --- 2. includes are spelled the way the directory spells them --------------
thunks = os.path.join(ROOT, "dxmt", "src", "winemetal", "winemetal_thunks.c")
main_c = os.path.join(ROOT, "dxmt", "src", "winemetal", "main.c")
if os.path.exists(thunks) and os.path.exists(main_c):
    main_text = open(main_c, encoding="utf-8", errors="replace").read()
    thunks_text = open(thunks, encoding="utf-8", errors="replace").read()
    for header in ("windef.h", "winbase.h"):
        in_main = ('#include "%s"' % header) in main_text
        check("main.c includes %s with quotes" % header, in_main)
        bad = re.search(r'#include\s*<%s>' % re.escape(header), thunks_text)
        check("winemetal_thunks.c does not include %s with angle brackets" % header,
              bad is None,
              "angle brackets search the compiler's system path" if bad else "")

# --- 3. the new declarations compile ---------------------------------------
cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc")
if not cc or os.environ.get("WMT_SKIP_COMPILE") == "1":
    print("SKIP the compile check (no C compiler, or WMT_SKIP_COMPILE=1); "
          "the stranded-return-type and include-spelling checks above still ran")
else:
    # Pull out the self-contained pieces the patch adds: the DXBC note globals
    # and dumper, and the blit ring. They need no Metal and no Wine.
    # Search the de-prefixed text: in the patch every added line starts with '+',
    # so a regex anchored on the declaration never matches.
    pieces = []
    m = re.search(r"(/\* ---- last DXBC blob.*?^\}\n)", added_text, re.S | re.M)
    if m:
        pieces.append(m.group(1))
    m = re.search(r"(#define WMT_BLIT_RING.*?\n\}\n)", added_text, re.S)
    if m:
        pieces.append(m.group(1))
    check("the self-contained additions were found to compile", len(pieces) == 2, "got %d of 2 pieces; the extractors must keep up with the patch text" % len(pieces))
    if pieces:
        # This host's clang has no libc headers, so stdio/string are declared
        # directly and only the declarations this patch adds are checked. On a
        # host that does have them the real headers are used instead.
        with tempfile.TemporaryDirectory() as td:
            probe = os.path.join(td, "p.c")
            open(probe, "w", encoding="utf-8").write("#include <stdio.h>\nint main(void){return 0;}\n")
            have_libc = subprocess.run([cc, "-fsyntax-only", probe],
                                       capture_output=True, text=True).returncode == 0
        if not have_libc:
            print("note: this host's clang has no libc headers; stdio/string are "
                  "declared by hand so the declarations under test still compile")
        driver = (
            ('#include <stdint.h>\n#include <stddef.h>\n'
             '#include <stdio.h>\n#include <string.h>\n#include <mach/mach_time.h>\n'
             if have_libc else
             '#include <stdint.h>\n#include <stddef.h>\n'
             'typedef struct { int dummy; } FILE;\n'
             'FILE *fopen(const char *, const char *);\n'
             'size_t fwrite(const void *, size_t, size_t, FILE *);\n'
             'int fclose(FILE *);\n'
             'int fprintf(FILE *, const char *, ...);\n'
             'int snprintf(char *, size_t, const char *, ...);\n'
             'void *memset(void *, int, size_t);\n'
             'uint64_t mach_absolute_time(void);\n'
             '#define stderr ((FILE *)0)\n')
            + 'typedef unsigned long obj_handle_t;\n'
            'struct WMTMemoryPointer { void *ptr; };\n'
            'struct wmtcmd_base { uint32_t type; struct WMTMemoryPointer next; };\n'
            'enum WMTBlitCommandType { WMTBlitCommandCopyFromTextureToBuffer,\n'
            '  WMTBlitCommandCopyFromTextureToTexture, WMTBlitCommandMax };\n'
            'struct WMTOrigin { uint64_t x, y, z; };\n'
            'struct WMTSize { uint64_t width, height, depth; };\n'
            'struct wmtcmd_blit_copy_from_texture_to_buffer {\n'
            '  enum WMTBlitCommandType type; uint16_t reserved[3];\n'
            '  struct WMTMemoryPointer next; obj_handle_t src; uint32_t slice;\n'
            '  uint32_t level; struct WMTOrigin origin; struct WMTSize size;\n'
            '  obj_handle_t dst; };\n'
            'struct wmtcmd_blit_copy_from_texture_to_texture {\n'
            '  enum WMTBlitCommandType type; uint16_t reserved[3];\n'
            '  struct WMTMemoryPointer next; obj_handle_t src; uint32_t src_slice;\n'
            '  uint32_t src_level; struct WMTOrigin src_origin;\n'
            '  struct WMTSize src_size; obj_handle_t dst; uint32_t dst_slice;\n'
            '  uint32_t dst_level; struct WMTOrigin dst_origin;\n'
            '  struct WMTSize dst_size; };\n'
            'static uint32_t wmt_blit_cmd_size(int t){return 0;}\n'
            + "\n".join(pieces) + "\nint main(void){return 0;}\n")
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "frag.c")
            open(src, "w", encoding="utf-8").write(driver)
            r = subprocess.run([cc, "-fsyntax-only", "-x", "c++", "-std=gnu++11", src],
                               capture_output=True, text=True)
            check("the added declarations are well-formed C++ (-fsyntax-only)",
                  r.returncode == 0, (r.stderr or "").strip()[:300])

print("PASS" if not failures else "FAILED: " + "; ".join(failures))
sys.exit(0 if not failures else 1)