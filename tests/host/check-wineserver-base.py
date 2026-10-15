#!/usr/bin/env python3
"""build/wineserver must produce its own base libwineserver.a.

Root cause (recorded failure, run at 3daa133):
`=== wineserver ===` / `ERROR: No base libwineserver.a found`. The stage
patched a "base" archive that had to exist at app/Madeira/libwineserver.a or
build/wineserver/obj/libwineserver.a first — a git-ignored file that was never
committed (no git history) and had no producer anywhere in the repository. It
existed only on the original developer's machine, so every clean checkout,
i.e. every CI run, died at this stage.

The repair: build_base_from_source() compiles every .c in the pinned wine
submodule's server/Makefile.in SOURCES for iOS arm64 with the stage's own
CC_FLAGS, under the natural member names (foo.c -> foo.o), so the existing
PATCHED_FILES/REPLACEMENTS swap still works object-by-object. Priority is
preserved for local builds: an existing obj/ archive, then a developer's
app/Madeira/libwineserver.a, else the source build.

This check is source-level plus a functional dry run: a sandbox repo with
stub `xcrun`/`ar`/`llvm-objcopy` executes the real script end to end, so the
archive member set, the object swap, the symbol-rename sweep and the failure
diagnostics are all exercised without macOS or the wine submodule.
"""
from pathlib import Path
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
WS = ROOT / "build/wineserver/build.sh"
TEXT = WS.read_text(encoding="utf-8")

failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


def parse_list(var):
    """Entries of NAME=( "..." ... ) in the script text."""
    m = re.search(re.escape(var) + r"=\(\n(.*?)\n\)", TEXT, re.S)
    if not m:
        return []
    return re.findall(r'"([^"\n]+)"', m.group(1))


PATCHED = [e.split(":") for e in parse_list("PATCHED_FILES")]
REPLACEMENTS = [e.split(":") for e in parse_list("REPLACEMENTS")]

# ---------------------------------------------------------------- static contract
check("build_base_from_source" in TEXT and "ensure_base_archive" in TEXT,
      "the script has a base-archive producer and resolver")
check('SERVER_MAKEFILE="$WINE_SRC/server/Makefile.in"' in TEXT,
      "the source list is the submodule's own server/Makefile.in, not a copy here")
check(re.search(r"refusing to build\s*\S*\s*an empty libwineserver\.a", TEXT) is not None
      or "refusing to build" in TEXT,
      "an unparseable SOURCES list fails instead of producing an empty archive")
check("git submodule update --init wine" in TEXT,
      "the missing-submodule diagnostic names the true producer/prerequisite")
check(re.search(r"\$\{src%\.c\}\.o", TEXT) is not None,
      "base objects keep their natural member name (foo.c -> foo.o) for the swap")
check("existing local artifact" in TEXT and "elif [ -f \"$APP_LIB\" ]" in TEXT,
      "a developer's pre-existing app/Madeira/libwineserver.a is still honoured")
check(re.search(r'^\s*echo "ERROR: No base', TEXT, re.M) is None,
      "the stage no longer hard-fails on a clean checkout")
check("base|all|request|main|mach|unicode" in TEXT,
      "the usage documents the base producer mode")


# ---------------------------------------------------------------- sandbox harness
XCRUN = """#!/usr/bin/env python3
import os, pathlib, sys
args = sys.argv[1:]
if "--show-sdk-path" in args:
    print("/fake/iphoneos.sdk")
    sys.exit(0)
try:
    src = args[args.index("-c") + 1]
    out = args[args.index("-o") + 1]
except (ValueError, IndexError):
    sys.stderr.write("xcrun stub: expected -c SRC -o OUT\\n")
    sys.exit(2)
if not pathlib.Path(src).is_file():
    sys.stderr.write("xcrun stub: source missing: %s\\n" % src)
    sys.exit(1)
n = 0
counter = os.environ.get("XCRUN_COUNTER")
if counter:
    cf = pathlib.Path(counter)
    n = int(cf.read_text()) + 1 if cf.exists() else 1
    cf.write_text(str(n))
pathlib.Path(out).write_text("OBJ src=%s n=%d\\n" % (src, n))
"""

AR = """#!/usr/bin/env python3
import io, os, pathlib, sys, tarfile
args = sys.argv[1:]
flags, rest = args[0], args[1:]
archive = pathlib.Path(rest[0])
members = rest[1:]


def read():
    data = {}
    if archive.is_file():
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                if m.isfile():
                    data[m.name] = t.extractfile(m).read()
    return data


def write(data):
    with tarfile.open(archive, "w") as t:
        for name in sorted(data):
            info = tarfile.TarInfo(name)
            info.size = len(data[name])
            t.addfile(info, io.BytesIO(data[name]))


if "x" in flags:
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            if m.isfile():
                pathlib.Path(m.name).write_bytes(t.extractfile(m).read())
elif "d" in flags:
    data = read()
    for name in members:
        data.pop(name, None)
    write(data)
else:  # r / rcs: add, replacing same-named members like real ar does
    data = read()
    for f in members:
        data[pathlib.Path(f).name] = pathlib.Path(f).read_bytes()
    write(data)
"""

OBJCOPY = """#!/usr/bin/env python3
import pathlib, sys
args = sys.argv[1:]
f = pathlib.Path(args[-1])
f.write_text(f.read_text()
             + "RENAME " + ",".join(a for a in args if a.startswith("--redefine-sym")) + "\\n")
"""

SYN_MAKEFILE = """PROGRAMS = wineserver

SOURCES = \\
\talpha.c \\
\tmain.c \\
\tobject.c \\
\trequest.c \\
\tsock.c \\
\tbeta.c \\
\tsecurity.h \\
\twineserver.man.in

UNIX_CFLAGS = nothing
"""
SYN_SOURCES = ["alpha.c", "main.c", "object.c", "request.c", "sock.c", "beta.c"]


def sandbox(tag, makefile=None, legacy=None):
    tmp = Path(tempfile.mkdtemp(prefix="wsbase-%s-" % tag))
    sb = tmp / "repo"
    shutil.copytree(ROOT / "build/wineserver", sb / "build/wineserver")
    shutil.rmtree(sb / "build/wineserver/obj", ignore_errors=True)
    for d in ("build/ntdll-unix/shims", "build/madsync", "build/hidpad",
              "app/Madeira", "wine/server"):
        (sb / d).mkdir(parents=True, exist_ok=True)
    # Every upstream source PATCHED_FILES names must exist in the sandbox wine tree.
    for name, src, _old in PATCHED:
        if src.startswith("$WINE_SRC/"):
            p = sb / "wine" / src[len("$WINE_SRC/"):]
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text("/* stub %s */\n" % p.name)
        elif src.startswith("$REPO_ROOT/"):
            p = sb / src[len("$REPO_ROOT/"):]
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text("/* stub %s */\n" % p.name)
    if makefile is not None:
        (sb / "wine/server/Makefile.in").write_text(makefile)
        for src in SYN_SOURCES:
            p = sb / "wine/server" / src
            if not p.exists():
                p.write_text("/* stub %s */\n" % src)
    bindir = tmp / "bin"
    bindir.mkdir()
    for name, body in (("xcrun", XCRUN), ("ar", AR), ("llvm-objcopy", OBJCOPY)):
        p = bindir / name
        p.write_text(body)
        p.chmod(0o755)
    if legacy is not None:
        with tarfile.open(sb / "app/Madeira/libwineserver.a", "w") as t:
            for name, content in legacy.items():
                info = tarfile.TarInfo(name)
                raw = content.encode()
                info.size = len(raw)
                t.addfile(info, io.BytesIO(raw))
    env = dict(os.environ)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["XCRUN_COUNTER"] = str(tmp / "counter")
    return sb, env, tmp


def run(sb, env, mode, label="", expect_fail=False):
    r = subprocess.run(["bash", str(sb / "build/wineserver/build.sh"), mode],
                       cwd=str(sb), env=env, capture_output=True,
                       text=True, timeout=300)
    if r.returncode != 0 and not expect_fail:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-6:]
        print("  [%s rc=%d] %s" % (label or mode, r.returncode, " | ".join(tail)))
    return r


def members_of(archive):
    out = {}
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            if m.isfile():
                out[m.name] = t.extractfile(m).read().decode(errors="replace")
    return out


def compile_n(content):
    m = re.search(r"n=(\d+)", content)
    return int(m.group(1)) if m else -1


# ---------------------------------------------------------------- 1. `base` mode
sb, env, tmp = sandbox("base", makefile=SYN_MAKEFILE)
r = run(sb, env, "base")
check(r.returncode == 0, "`base` mode exits 0 on a clean tree (was: hard failure)")
check("=== Building base libwineserver.a" in r.stdout,
      "`base` mode builds from wine/server/Makefile.in")
archive = sb / "build/wineserver/obj/libwineserver.a"
check(archive.is_file(), "`base` mode writes obj/libwineserver.a")
if archive.is_file():
    got = set(members_of(archive))
    expect = {s[:-2] + ".o" for s in SYN_SOURCES}
    check(got == expect,
          "the archive holds exactly the Makefile.in .c sources as members "
          "(%s)" % ", ".join(sorted(got)))
    content = members_of(archive).get("alpha.o", "")
    check("wine/server/alpha.c" in content,
          "each member was compiled from its own submodule source")
    check(compile_n(content) == 1,
          "base compiles run before anything else in the stage")

# ---------------------------------------------------------------- 2. missing submodule
sb, env, tmp = sandbox("nosub")
r = run(sb, env, "base", expect_fail=True)
check(r.returncode != 0, "`base` fails when the wine submodule is absent")
check("git submodule update --init wine" in r.stderr,
      "and its diagnostic names the submodule fetch as the prerequisite")

# ---------------------------------------------------------------- 3. empty SOURCES guard
sb, env, tmp = sandbox("empty",
                       makefile="PROGRAMS = wineserver\n\nSOURCES = \\\n\tsecurity.h\n")
r = run(sb, env, "base", expect_fail=True)
check(r.returncode != 0, "`base` fails when SOURCES has no compilable source")
check("refusing to build" in r.stderr,
      "and says it refuses to build an empty archive")

# ---------------------------------------------------------------- 4. full `all` run
sb, env, tmp = sandbox("all", makefile=SYN_MAKEFILE)
r = run(sb, env, "all")
check(r.returncode == 0, "`all` mode completes end to end on a clean tree")
obj_archive = sb / "build/wineserver/obj/libwineserver.a"
app_lib = sb / "app/Madeira/libwineserver.a"
check(app_lib.is_file(), "the patched archive is copied to app/Madeira/libwineserver.a")
if obj_archive.is_file() and app_lib.is_file():
    final = members_of(obj_archive)
    base_names = {s[:-2] + ".o" for s in SYN_SOURCES}
    olds = {old for _new, old in REPLACEMENTS}
    news = {new for new, _old in REPLACEMENTS}
    expect = (base_names - olds) | news
    check(set(final) == expect,
          "final members = (base - replaced) + patched objects, no duplicates")
    check("request.o" not in final and "request_ios.o" in final,
          "a replaced object is swapped, not duplicated (the symbol-collision trap)")
    if "object.o" in final and "alpha.o" in final:
        check(compile_n(final["object.o"]) > compile_n(final["alpha.o"]),
              "the surviving object.o is the PATCHED compile, not the base one")
    check(all("RENAME" in body for body in final.values()),
          "the symbol-rename sweep touched every member, base and patched alike")
    check(app_lib.read_bytes() == obj_archive.read_bytes(),
          "the app archive is byte-identical to the stage's archive")
check("=== Building base libwineserver.a" in r.stdout,
      "the full run produced its base rather than expecting a prebuilt one")

# ---------------------------------------------------------------- 5. legacy local archive
sb, env, tmp = sandbox("legacy", makefile=SYN_MAKEFILE,
                       legacy={"legacy_marker.o": "LEGACY\n", "request.o": "OLDREQ\n"})
r = run(sb, env, "all")
check(r.returncode == 0, "`all` still works with a developer's prebuilt archive")
check("existing local artifact" in r.stdout and
      "=== Building base libwineserver.a" not in r.stdout,
      "and reuses it instead of rebuilding the base")
if (sb / "app/Madeira/libwineserver.a").is_file():
    final = members_of(sb / "app/Madeira/libwineserver.a")
    check(final.get("legacy_marker.o", "").startswith("LEGACY"),
          "the prebuilt archive's objects survive into the patched archive")
    check("request.o" not in final and "request_ios.o" in final,
          "and the patched swap still applies to it")

if failures:
    print("FAILED: %d" % len(failures))
    sys.exit(1)
print("OK")
