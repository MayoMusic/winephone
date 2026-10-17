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
    # And the reverse of what this file asserted until the build contradicted
    # it: the PE side cannot have windef.h at all. Wineunixlib.h resolves because
    # the toolchain has winternl.h; windef.h is Wine's name and is absent, which
    # is why the logging route is implemented in the file instead of included.
    check("winemetal_thunks.c does not try to include Wine's windef.h",
          re.search(r'#include\s*[<"]windef\.h[>"]', thunks_text) is None,
          "the LLVM-mingw toolchain headers do not have it; the build said so twice")

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
    # The PE-side logging route. This one was missing while three errors in the
    # PE file got through to a build: windef.h, and then, after that was
    # "fixed" wrongly, an include the toolchain does not have. It is compiled
    # here too, and needs no Wine header -- it declares what it uses.
    m = re.search(r"(extern void \*GetModuleHandleA.*?"
                  r"#define WARN\(\.\.\.\) wmt_pe_warn\(__VA_ARGS__\))",
                  added_text, re.S)
    if m:
        pieces.append(m.group(1))
    else:
        # A named failure, not a silent empty string. An empty piece keeps the
        # count right and compiles less, which is exactly the shape of check
        # that passes while inspecting nothing.
        check("the PE logging block was found to compile", False,
              "no match for GetModuleHandleA .. #define WARN in the added lines; "
              "the extractors have fallen behind the patch")
        pieces.append("")

    # The UNIX_CALL macro, compiled at a call site. Every diagnostic in this file
    # rides on it, and it names a kernel32 function that windef.h used to
    # declare: removing that include took the declaration with it and the build
    # reported four undeclared calls. Nothing else here would have caught it --
    # the macro is neither an added line nor near a hunk, so it is not in the
    # patch at all.
    #
    # Read from the real source when dxmt is here; otherwise a stand-in carrying
    # the same dependency, which says so. Either way GetCurrentThreadId is not
    # stubbed: the declaration has to come from the added lines, and that is the
    # thing being checked.
    unix_call = ""
    unix_call_from = ""
    _src_file = os.path.join(ROOT, "dxmt", "src", "winemetal", "winemetal_thunks.c")
    _haystacks = []
    if os.path.exists(_src_file):
        _haystacks.append(open(_src_file, encoding="utf-8", errors="replace").read())
    else:
        _haystacks.append(text)   # may not contain it; the stand-in covers it
    for _h in _haystacks:
        _pos = _h.find("#define UNIX_CALL")
        while _pos >= 0:
            _end = _h.find("\n", _pos)
            while _h[_end - 1:_end].rstrip() == "\\" or _h[max(0, _end - 2):_end].endswith("\\\n"):
                _nxt = _h.find("\n", _end + 1)
                if _nxt < 0:
                    _end = len(_h)
                    break
                _end = _nxt
            _body = _h[_pos:_end]
            if "GetCurrentThreadId" in _body:
                unix_call = _body
                break
            _pos = _h.find("#define UNIX_CALL", _pos + 1)
        if unix_call:
            break
    if not unix_call:
        unix_call_from = "stand-in"
        unix_call = (
            '#define UNIX_CALL(code, params) \\\n'
            '  wmt_pe_warn("[wmt-fail] status=0x%08x api=%s(%u) tid=%04x", 0, \\\n'
            '             (code < WMT_API_COUNT ? wmt_api_names[code] : "?"), \\\n'
            '             (unsigned)(code), (unsigned)GetCurrentThreadId())\n')
    elif os.path.exists(_src_file):
        unix_call_from = "dxmt/src/winemetal/winemetal_thunks.c"
    else:
        unix_call_from = "the patch (unlikely; assert if this surprises you)"
    check("the UNIX_CALL macro is compiled at a call site", unix_call != "",
          "from %s; it is context, not an added line, so no piece contains it"
          % unix_call_from)
    # What the macro needs around its kernel32 call. GetCurrentThreadId is
    # deliberately absent: if nothing declares it, the compile below fails, which
    # is the entire reason the macro is here.
    unix_call_stubs = (
        '\ntypedef long NTSTATUS;\n'
        '#define WINE_UNIX_CALL(code, params) ((NTSTATUS)0)\n'
        '#define WMT_API_COUNT 1\n'
        'static const char *wmt_api_names[1] = { "?" };\n'
        'static void wmt_api_census_note(unsigned) {}\n'
        # assert is the macro's own use, from the <assert.h> the file includes.
        # Stubbed to a no-op because what is under test is what the names
        # resolve to, not whether the assert fires.
        '#define assert(x) ((void)0)\n'
        'static void wmt_probe_unix_call(void *o) { UNIX_CALL(0, &o); }\n')
    check("the self-contained additions were found to compile", len(pieces) == 3, "got %d of 3 pieces; the extractors must keep up with the patch text" % len(pieces))
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
        # mach/mach_time.h needs the SDK on macOS. Probe for it the same way
        # stdio is probed: if the header is not usable here, declare
        # mach_absolute_time and carry on, because what is under test is the
        # declarations this patch adds and not the SDK.
        with tempfile.TemporaryDirectory() as td:
            mprobe = os.path.join(td, "m.c")
            open(mprobe, "w", encoding="utf-8").write(
                "#include <mach/mach_time.h>\nuint64_t f(void){return mach_absolute_time();}\n")
            margs = [cc, "-fsyntax-only"]
            if shutil.which("xcrun"):
                sdk0 = subprocess.run(["xcrun", "--sdk", "macosx", "--show-sdk-path"],
                                      capture_output=True, text=True)
                if sdk0.returncode == 0 and sdk0.stdout.strip():
                    margs += ["-isysroot", sdk0.stdout.strip()]
            have_mach = subprocess.run(margs + [mprobe],
                                       capture_output=True, text=True).returncode == 0
        if not have_mach:
            print("note: mach/mach_time.h is not usable on this host, so "
                  "mach_absolute_time is declared by hand")

        # The struct shapes must come from the header, not from what this file
        # believes they are. It believed a dst_size member existed; it does not,
        # and the build caught it. Reading the real declaration means a rename
        # upstream is a rename here too.
        real_hdr = os.path.join(ROOT, "dxmt", "src", "winemetal", "winemetal.h")
        real_decls = ""
        if os.path.exists(real_hdr):
            h = open(real_hdr, encoding="utf-8", errors="replace").read()
            for name in ("WMTMemoryPointer", "WMTOrigin", "WMTSize",
                         "wmtcmd_blit_copy_from_texture_to_buffer",
                         "wmtcmd_blit_copy_from_texture_to_texture"):
                # Balanced brace scan: the real structs contain other structs, so
                # a non-greedy [^}]* stops at the first closing brace and yields
                # a truncated declaration that then compiles as something else.
                m0 = re.search(r"struct\s+%s\s*\{" % re.escape(name), h)
                decl = None
                if m0:
                    depth, j = 0, h.find("{", m0.start())
                    k = j
                    while k < len(h):
                        if h[k] == "{":
                            depth += 1
                        elif h[k] == "}":
                            depth -= 1
                            if depth == 0:
                                decl = h[m0.start():k + 1]
                                break
                        k += 1
                check("the real %s is readable from winemetal.h" % name, decl is not None)
                if decl:
                    # C++ needs the terminating semicolon; the header omits it
                    # because C does not.
                    real_decls += decl.rstrip() + ";\n"
        else:
            # Without the submodule there is nothing to compare against; the
            # header shapes are then the ones the patch expects, which is a
            # weaker check and says so.
            print("note: dxmt is not checked out, so the struct shapes cannot be "
                  "compared against the real header")
            # A stand-in with the same shape, so the compile still says something
            # about the declarations rather than dying on a missing type. This is
            # the weaker check and the note above says so.
            real_decls = (
                'struct WMTMemoryPointer { void *ptr; };\n'
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
                '  uint32_t dst_level; struct WMTOrigin dst_origin; };\n')

        # Two translation units, because the sources this patch touches are two
        # languages. winemetal_unix.c and winemetal_thunks.c are C;
        # dxbc_converter.cpp is C++. Compiling all three pieces as C++ is what
        # let `extern "C" void` through in the .c file -- valid C++, a syntax
        # error in a .c -- and the build is where that was found.
        # Both languages need the terminating semicolon here, not just C++: the
        # header omits it because there the struct is a member of another one,
        # and once extracted standalone it needs one. Stripping it for C made
        # the C unit fail with "expected ';' after struct".
        real_decls_c = real_decls

        hdrs_common = ('#include <stdint.h>\n#include <stddef.h>\n'
                       '#include <stdarg.h>\n')
        stub_c = (
            'typedef struct { int dummy; } FILE;\n'
            'typedef __SIZE_TYPE__ wmt_size_t;\n'
            'FILE *fopen(const char *, const char *);\n'
            'size_t fwrite(const void *, size_t, size_t, FILE *);\n'
            'int fclose(FILE *);\n'
            'int fprintf(FILE *, const char *, ...);\n'
            'int snprintf(char *, size_t, const char *, ...);\n'
            'int vsnprintf(char *, size_t, const char *, va_list);\n'
            'void *memset(void *, int, size_t);\n'
            'void *memcpy(void *, const void *, size_t);\n'
            'size_t strlen(const char *);\n'
            'uint64_t mach_absolute_time(void);\n'
            '#define stderr ((FILE *)0)\n')
        # NULL is not redefined: stddef.h is compiler-provided and resolves
        # without libc, so it already has one. Defining it collided with
        # __stddef_null.h.

        tu_c = (
            (hdrs_common + '#include <stdio.h>\n#include <string.h>\n'
             if have_libc else hdrs_common + stub_c)
            + 'typedef unsigned long obj_handle_t;\n'
            'enum WMTBlitCommandType { WMTBlitCommandCopyFromTextureToBuffer,\n'
            '  WMTBlitCommandCopyFromTextureToTexture, WMTBlitCommandMax };\n'
            + real_decls_c
            + 'struct wmtcmd_base { uint32_t type; struct WMTMemoryPointer next; };\n'
            'static uint32_t wmt_blit_cmd_size(int t){return 0;}\n'
            + pieces[1] + "\n" + pieces[2] + "\n" + unix_call + unix_call_stubs
            + "\nint main(void){return 0;}\n")

        tu_cxx = (
            (hdrs_common + '#include <stdio.h>\n#include <string.h>\n'
             + ('#include <mach/mach_time.h>\n' if have_mach else '')
             if have_libc else
             hdrs_common + stub_c
             + ('' if have_mach else 'uint64_t mach_absolute_time(void);\n'))
            + "\n".join([pieces[0]]) + "\nint main(void){return 0;}\n")

        # On macOS the SDK has to be named or mach/ is not found at all. xcrun
        # does not exist elsewhere, so its absence is not a failure.
        sdk_args = []
        if shutil.which("xcrun"):
            sdk = subprocess.run(["xcrun", "--sdk", "macosx", "--show-sdk-path"],
                                 capture_output=True, text=True)
            if sdk.returncode == 0 and sdk.stdout.strip():
                sdk_args = ["-isysroot", sdk.stdout.strip()]

        with tempfile.TemporaryDirectory() as td:
            # Asserted on the generated source, which is what actually gets
            # compiled, rather than on a count of strings in this file. Both
            # units need va_start from <stdarg.h>; adding it to one branch and
            # not the other passes here -- this host has no libc headers, so only
            # the fallback is ever built -- and fails on the macOS runner.
            check("both translation units include <stdarg.h>",
                  "#include <stdarg.h>" in tu_c and "#include <stdarg.h>" in tu_cxx,
                  "UNIX_CALL expands to va_start/va_end; without it the unit does "
                  "not compile")

            c_src = os.path.join(td, "frag.c")
            open(c_src, "w", encoding="utf-8").write(tu_c)
            # The language mode and warning set the real build uses for a C unit
            # (build/dxmt-ios/build.sh: COMMON_FLAGS -std=c11 -Wall plus the
            # MADEIRA_WARNINGS suppressions), minus the target. Matching -std is
            # the part that matters: several of the errors that reached a build
            # were language-mode errors, and C99-versus-C11 and gnu11-versus-c11
            # differ on exactly the implicit-declaration rule that let
            # GetCurrentThreadId through.
            #
            # What this is NOT: a build for arm64 against the iPhoneOS SDK. That
            # needs the macOS runner and happens in the dxmt-ios stage; this
            # stands in for it only for the declarations the patch adds.
            cflags = [cc, "-fsyntax-only", "-x", "c", "-std=c11", "-Wall",
                      "-Werror=implicit-function-declaration",
                      "-Wno-unused-parameter", "-Wno-missing-field-initializers",
                      "-Wno-missing-braces"]
            r = subprocess.run(cflags + sdk_args + [c_src],
                               capture_output=True, text=True)
            check("the C additions are well-formed C (-std=c11 -fsyntax-only)",
                  r.returncode == 0, (r.stderr or "").strip()[:400])

            cxx_src = os.path.join(td, "frag.cpp")
            open(cxx_src, "w", encoding="utf-8").write(tu_cxx)
            r2 = subprocess.run([cc, "-fsyntax-only", "-x", "c++", "-std=gnu++11"]
                                + sdk_args + [cxx_src],
                                capture_output=True, text=True)
            check("the C++ additions are well-formed C++ (-fsyntax-only)",
                  r2.returncode == 0, (r2.stderr or "").strip()[:400])

# --- 4. a .c file never carries a C++ linkage specifier ---------------------
# The build's last error: winemetal_unix.c:2416 "expected identifier or '('",
# at `extern "C" void`. That is legal in the .cpp in the same patch and a syntax
# error in the .c. Asserted per file, from the patch, so it holds in CI where
# dxmt is not checked out.
for _chunk in re.split(r"(?m)^diff --git ", text):
    if not _chunk.strip():
        continue
    _m = re.search(r"^\+\+\+ b/(\S+)", _chunk, re.M)
    if not _m:
        continue
    _path = _m.group(1)
    _added = "\n".join(l[1:] for l in _chunk.split("\n")
                       if l.startswith("+") and not l.startswith("+++"))
    # Comments are stripped: the fix for this error is a comment explaining that
    # `extern "C" void` is the C++ form, and a check that matched its own
    # explanation would fail forever against the record of the fix.
    _code = re.sub(r"/\*.*?\*/", "", _added, flags=re.S)
    _code = re.sub(r"//[^\n]*", "", _code)
    if _path.endswith(".c"):
        check("%s adds no C++ linkage specifier" % _path,
              'extern "C"' not in _code,
              "a .c is compiled as C; `extern \"C\"` is a syntax error there and "
              "the build cannot see it until it compiles the file")
    elif _path.endswith(".cpp"):
        check("%s is the C++ side, as compiled" % _path, True)

print("PASS" if not failures else "FAILED: " + "; ".join(failures))
sys.exit(0 if not failures else 1)