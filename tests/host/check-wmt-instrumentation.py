#!/usr/bin/env python3
"""The instrumentation has to be able to reach the log at all.

Two of these checks exist because a diagnostic that silently does not print is
worse than no diagnostic: it reads as a clean run.

PE-side output cannot go to stderr. Run 1's at-terminate check reported the
guest's stderr handle as fd=-1, so fprintf(stderr) from PE code is lost. WARN is
the route that works -- d3d11_swapchain.cpp is also PE code and its WARN lines
appear as "warn: [present] ..." in a device log. This asserts every PE-side
diagnostic uses WARN and that the include is present, because the failure mode
is a build that compiles and prints nothing.

Host-side output may use dprintf(2): the [mach_exc] lines come from exactly
that and appear in the exported log.

Also asserts the debug-layer setting cannot be enabled by the environment,
because a dylib-load constructor runs before WineProcessBridge.m exports the
env.NAME lines from madeira.cfg. Reading the config file is the only route that
works at that point.
"""
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PATCH = os.path.join(ROOT, "patches", "dxmt-wmt-null-dest.patch")
PE = os.path.join(ROOT, "dxmt", "src", "winemetal", "winemetal_thunks.c")
HOST = os.path.join(ROOT, "dxmt", "src", "winemetal", "unix", "winemetal_unix.c")
if not os.path.exists(HOST):
    HOST = PATCH

failures = []


def check(what, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + what + ("  " + detail if detail else ""))
    if not cond:
        failures.append(what)


# The PE file may not exist when dxmt is not checked out -- and it does not exist
# in the host-checks job, which is where this runs. The patch always does, and it
# carries the same text, so fall back to it.
#
# A patch's added lines are prefixed with '+', which is not part of the source.
# Reading them raw makes every line-start assertion fail on a change that is
# present, which is what CI reported: the WARN lines were there, behind a '+'.
FROM_PATCH = not os.path.exists(PE)
if FROM_PATCH:
    PE = PATCH
check("a PE-side source to inspect", os.path.exists(PE),
      "%s (dxmt not checked out, reading the patch instead)" % os.path.basename(PE) if FROM_PATCH else PE)
if not os.path.exists(PE):
    print("FAILED: cannot inspect the PE side")
    sys.exit(1)

pe = open(PE, encoding="utf-8", errors="replace").read()
if FROM_PATCH:
    pe = "\n".join(l[1:] if l.startswith("+") else l for l in pe.split("\n"))
host = open(HOST, encoding="utf-8", errors="replace").read() if os.path.exists(HOST) else ""
if HOST == PATCH:
    host = "\n".join(l[1:] if l.startswith("+") else l for l in host.split("\n"))

# --- PE-side diagnostics must use WARN, not stderr --------------------------
# Strip comments before looking: these tags are named in prose explaining what
# they are for, and the first textual match of [tex-bad-pe] is that comment, not
# the call.
pe_code = re.sub(r"/\*.*?\*/", "", pe, flags=re.S)
pe_code = re.sub(r"//[^\n]*", "", pe_code)

for tag in ("[tex-bad-pe]", "[wmt-fail]"):
    at = pe_code.find(tag)
    check("%s is present in the PE side" % tag, at >= 0)
    if at < 0:
        continue
    line = pe_code[pe_code.rfind("\n", 0, at) + 1: pe_code.find("\n", at)]
    check("%s goes through WARN" % tag, line.lstrip().startswith("WARN("),
          line.strip()[:60])
check("winemetal_thunks.c includes windef.h for WARN",
      re.search(r'#include\s*<windef\.h>', pe) is not None)
check("the PE side has no diagnostic left on fprintf(stderr)",
      re.search(r'fprintf\(stderr,\s*"\[(tex-bad-pe|wmt-fail)\]', pe_code) is None)

# --- the debug layer cannot be read from the environment at load ------------
ctor = re.search(r'wmt_mtl_debug_early.*?\n\}', host, re.S)
check("the load-time constructor exists", ctor is not None)
if ctor:
    body = ctor.group(0)
    # Strip comments first: the constructor explains WHY getenv is wrong, so the
    # word appears in prose. Checking the raw text flagged that explanation as a
    # violation of itself.
    code = re.sub(r"/\*.*?\*/", "", ctor.group(0), flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    check("it reads madeira_cfg, not getenv",
          "madeira_cfg_int" in code
          and not re.search(r'getenv\s*\(\s*"MADEIRA_MTL', code),
          "getenv of the setting would always be empty: WineProcessBridge.m "
          "exports env.NAME lines after this runs")
    check("it reports requested=0 as well as requested=1",
          "requested=0" in body and "requested=1" in body)

# --- and it says whether the layer is actually active -----------------------
check("the active state is reported, not just the setenv",
      re.search(r'validation=%s', host) is not None,
      "a clean run with the layer inert must not read as validation finding nothing")
check("it distinguishes ACTIVE from NOT ACTIVE",
      "ACTIVE" in host and "NOT ACTIVE" in host)
check("it uses the device class as the observable",
      re.search(r'object_getClassName', host) is not None,
      "MTLDebugDevice instead of MTLDevice is what the layer does to the class")

# --- the PE route proves itself, so a missing diagnostic is never ambiguous -
check("a PE self-test line exists", "[wmt-selftest]" in pe)
check("the self-test runs at PE module load, not on first game call",
      re.search(r'__attribute__\(\(constructor\)\)\s*static void\s*wmt_pe_log_selftest', pe)
      is not None,
      "it must fire whether or not the game ever calls an allocator")
check("the self-test uses WARN too",
      re.search(r'WARN\("\[wmt-selftest\]', pe) is not None)

# --- a silent 'not found' must not look like 'layer off' -------------------
if ctor:
    code = re.sub(r"/\*.*?\*/", "", ctor.group(0), flags=re.S)
    check("the load-time constructor reports the config path it read",
          "madeira_cfg__dir" in code and "cfg-dir-source" in code,
          "HOME and the Documents path may both be unresolvable at dylib load")
    check("an unresolved path is reported as its own outcome",
          "UNRESOLVED" in code,
          "an unresolved path and a setting that is off are otherwise identical")
    check("it says whether the file was found", "found=" in code)

# --- NOT ACTIVE must come with a reason ------------------------------------
check("NOT ACTIVE is explained, not just stated",
      re.search(r'MTL_DEBUG_LAYER was set before this device was created', host) is not None)
check("it reports whether the layer was set before creation",
      "setBeforeCreation=" in host)
check("it tells the reader to treat such a run as a baseline",
      "baseline" in host)
# [dxbc-dump] is emitted from airconv, a different file.
AIRCONV = os.path.join(ROOT, "dxmt", "src", "airconv", "dxbc_converter.cpp")
airconv = open(AIRCONV, encoding="utf-8", errors="replace").read() if os.path.exists(AIRCONV) else pe

check("[dxbc-dump] carries a tick", "dxbc-dump t=%llu" in airconv,
      "it is emitted from airconv, not the winemetal host file")
check("[blit-ring] carries a tick", "[blit-ring t=%llu]" in host)
check("both use one clock", host.count("mach_absolute_time()") >= 1
      and airconv.count("mach_absolute_time()") >= 1)

# --- host side may still use dprintf, that route is known to work -----------
check("the host side still reports through stderr",
      "[tex-reject]" in host and "[tex-host]" in host)

print("PASS" if not failures else "FAILED: " + "; ".join(failures))
sys.exit(0 if not failures else 1)