#!/usr/bin/env python3
"""scripts/bootstrap.sh against a warm toolchain cache: reuse it, never trust it.

The workflow restores toolchains/ from an exact-key cache and then runs this
script, so the script is the only thing that can tell a complete cache from a
stale, partial or wrongly-pinned one. Its contract:

  - the pinned *sources* are always fetched (the cache holds build products);
  - toolchains/llvm-project is reused only when .git is at the LLVM pin;
  - toolchains/llvm-host-build is reused only when bin/llvm-tblgen is there and
    the source tree is at the pin (the tablegen is a product of that source);
  - toolchains/llvm-ios-build is reused only when include/llvm/Config/llvm-config.h
    and lib/*.a are there (the two artifacts the DXMT and madeira-d3d12 builds
    read) and the source is at the pin;
  - anything else is rebuilt here, so a cache miss or a damaged cache still ends
    with a complete toolchain;
  - the llvm-mingw archive is not downloaded again when its compiler is present.

The test runs the real script in a throwaway "repository" whose compilers are
stubs that log their arguments and materialise the files a real configure+build
would. That is enough to prove which work the script decided to do, without a
35-minute LLVM build.
"""
from pathlib import Path
import os
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/bootstrap.sh"
PIN = "8dfdcc7b7bf66834a761bd8de445840ef68e4d1a"
MINGW = "llvm-mingw-20260421-ucrt-macos-universal"

failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


STUBS = {
    "xcodebuild": "#!/bin/sh\necho \"xcodebuild $*\" >> \"$WP_LOG\"\n",
    "ninja": "#!/bin/sh\nexit 0\n",
    "meson": "#!/bin/sh\nexit 0\n",
    "bison": "#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'bison (GNU Bison) 3.8.2'; fi\n",
    "curl": "#!/bin/sh\necho \"curl $*\" >> \"$WP_LOG\"\nexit 1\n",
    # git: report the revision the fake checkout is at, and log everything else
    "git": """#!/bin/sh
echo "git $*" >> "$WP_LOG"
case "$*" in
  *"rev-parse HEAD"*) printf '%s\\n' "${WP_LLVM_HEAD:-}" ;;
esac
exit 0
""",
    # cmake: log, and materialise what a real configure+build of that tree writes
    "cmake": """#!/bin/sh
echo "cmake $*" >> "$WP_LOG"
if [ "$1" = "-S" ]; then
  echo "cmake-configure $*" >> "$WP_CONFIGURE_LOG"
fi
dir=""
prev=""
for a in "$@"; do
  if [ "$prev" = "-B" ]; then dir="$a"; fi
  prev="$a"
done
case "$dir" in
  *llvm-host-build)
    mkdir -p "$dir/bin"
    printf '#!/bin/sh\\nexit 0\\n' > "$dir/bin/llvm-tblgen"
    chmod +x "$dir/bin/llvm-tblgen" ;;
  *llvm-ios-build)
    mkdir -p "$dir/include/llvm/Config" "$dir/lib"
    : > "$dir/include/llvm/Config/llvm-config.h"
    : > "$dir/lib/libLLVMCore.a" ;;
  "") ;;
  *) echo "unexpected cmake -B $dir" >> "$WP_LOG" ;;
esac
exit 0
""",
}


def make_stub_bin(root):
    bindir = root / "bin"
    bindir.mkdir()
    for name, body in STUBS.items():
        p = bindir / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def make_repo(root, *, pin_head=PIN, mingw=True, host=True, ios=True, ios_lib=True):
    repo = root / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "scripts/bootstrap.sh")
    tc = repo / "toolchains"
    if mingw:
        (tc / MINGW / "bin").mkdir(parents=True)
        clang = tc / MINGW / "bin/arm64ec-w64-mingw32-clang"
        clang.write_text("#!/bin/sh\necho 'clang version 21'\n")
        clang.chmod(0o755)
    (tc / "llvm-project/.git").mkdir(parents=True)
    (tc / "llvm-project/llvm/cmake/modules").mkdir(parents=True)
    (tc / "llvm-project/llvm/CMakeLists.txt").write_text("# llvm\n")
    # already carrying the Darwin|iOS dead-strip edit, so the patch step is a no-op
    (tc / "llvm-project/llvm/cmake/modules/AddLLVM.cmake").write_text(
        'if(NOT LLVM_NO_DEAD_STRIP)\n      if(${CMAKE_SYSTEM_NAME} MATCHES "Darwin|iOS")\n')
    if host:
        (tc / "llvm-host-build/bin").mkdir(parents=True)
        (tc / "llvm-host-build/bin/llvm-tblgen").write_text("#!/bin/sh\nexit 0\n")
        (tc / "llvm-host-build/bin/llvm-tblgen").chmod(0o755)
    if ios:
        (tc / "llvm-ios-build/include/llvm/Config").mkdir(parents=True)
        (tc / "llvm-ios-build/include/llvm/Config/llvm-config.h").write_text("")
        if ios_lib:
            (tc / "llvm-ios-build/lib").mkdir(parents=True)
            (tc / "llvm-ios-build/lib/libLLVMCore.a").write_text("")
    return repo


def run(repo, root, pin_head=PIN):
    make_stub_bin(root)
    log = root / "cmds.log"
    cfg = root / "configure.log"
    log.write_text("")
    cfg.write_text("")
    env = dict(os.environ,
               PATH=str(root / "bin") + os.pathsep + os.environ.get("PATH", ""),
               WP_LOG=str(log), WP_CONFIGURE_LOG=str(cfg), WP_LLVM_HEAD=pin_head)
    r = subprocess.run(["bash", str(repo / "scripts/bootstrap.sh")],
                       capture_output=True, text=True, env=env, cwd=repo, timeout=300)
    return r, log.read_text(), cfg.read_text()


WORK = Path(tempfile.mkdtemp(prefix="madeira-cache-"))

# --------------------------------------------------------------- a complete cache
warm = WORK / "warm"
repo = make_repo(warm, mingw=True, host=True, ios=True, ios_lib=True)
r, cmds, cfg = run(repo, warm)
check(r.returncode == 0, "a complete cached toolchain bootstraps successfully (%s)" % r.stderr.strip()[-300:])
check(r.stdout.count("  reused:") == 4,
      "every cached tree is reported as reused (%s)" % [l for l in r.stdout.splitlines() if "reused" in l])
check("llvm-tblgen" in r.stdout and "toolchains/llvm-mingw" in r.stdout,
      "the reused trees are named with the artifact that proved them")
check("cmake-configure" not in cfg and "cmake --build" not in cmds,
      "no LLVM configure or build runs on a complete cache (the ~35-minute path)")
check("git fetch" not in cmds and "git clone" not in cmds,
      "the pinned source revision is not re-fetched when the tree is already at the pin")
check("curl " not in cmds,
      "the llvm-mingw archive is not downloaded again")

# --------------------------------------------------------------- a damaged cache
damaged = WORK / "damaged"
repo = make_repo(damaged, mingw=True, host=True, ios=True, ios_lib=False)
r, cmds, cfg = run(repo, damaged)
check(r.returncode == 0, "a cache missing the iOS LLVM archives still ends complete (%s)" % r.stderr.strip()[-300:])
check("built: toolchains/llvm-ios-build" in r.stdout,
      "and says it rebuilt that tree")
check("reused: toolchains/llvm-host-build" in r.stdout,
      "while still reusing the trees that are intact")
check("cmake-configure -S" in cfg and "CMAKE_SYSTEM_NAME=iOS" in cfg.replace("\n", " "),
      "the rebuild is the real iOS cross-configuration (%s)" % [l for l in cfg.splitlines() if l.startswith("cmake-configure")][:1])
check((repo / "toolchains/llvm-ios-build/lib/libLLVMCore.a").exists()
      and (repo / "toolchains/llvm-ios-build/include/llvm/Config/llvm-config.h").exists(),
      "and produces both artifacts the consumers read")

# --------------------------------------------------------------- an empty cache
empty = WORK / "empty"
repo = make_repo(empty, mingw=True, host=False, ios=False)
r, cmds, cfg = run(repo, empty)
check(r.returncode == 0, "an empty build cache bootstraps from scratch (%s)" % r.stderr.strip()[-300:])
check("built: toolchains/llvm-host-build" in r.stdout and "built: toolchains/llvm-ios-build" in r.stdout,
      "both LLVM trees are built when neither is cached")
check(cfg.count("cmake-configure") == 2 and cmds.count("cmake --build") == 2,
      "and both are configured and built once each (%d configures, %d builds)"
      % (cfg.count("cmake-configure"), cmds.count("cmake --build")))

# --------------------------------------------------------------- a stale pin
stale = WORK / "stale"
repo = make_repo(stale, mingw=True, host=True, ios=True)
r, cmds, cfg = run(repo, stale, pin_head="0000000000000000000000000000000000000000")
check(r.returncode == 0, "a cache from another revision still bootstraps (%s)" % r.stderr.strip()[-300:])
check("fetched: toolchains/llvm-project" in r.stdout,
      "the tree is re-fetched and checked out at the pin")
check("built: toolchains/llvm-host-build" in r.stdout,
      "and the host tablegen, which belongs to that source, is rebuilt")

shutil.rmtree(WORK, ignore_errors=True)

if failures:
    print("FAILED: %d" % len(failures))
    sys.exit(1)
print("OK")
