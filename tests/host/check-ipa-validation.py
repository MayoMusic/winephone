#!/usr/bin/env python3
"""tools/validate-ipa.sh against real archives: it must pass a good IPA and refuse each bad one.

The packaging step of scripts/build-ipa.sh hands its result to this script, so
the checks it makes are the ones that decide whether a built IPA is a valid
unsigned device artifact:

  - Payload/<App>.app/Info.plist is in the archive;
  - CFBundleExecutable names a file that exists in the bundle *and* in the
    archive, and is executable;
  - Payload holds exactly one .app;
  - the executable has an arm64 slice (lipo);
  - no forbidden release input (Apple's Metal Shader Converter, the custom
    D3D12 runtime, Microsoft's runtime directory);
  - SHA256SUMS is the sha256 of the packaged IPA and verifies with
    `shasum -a 256 -c`.

Everything but `lipo` is portable, so this runs on Linux and macOS: `lipo` is
stubbed on PATH. Fixtures are real zip archives built with zip(1); the test is
skipped only if zip/unzip are unavailable.
"""
from pathlib import Path
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools/validate-ipa.sh"

failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


for tool in ("zip", "unzip", "shasum"):
    if shutil.which(tool) is None:
        sys.exit("SKIP-FAIL: %s is not available" % tool)
if not VALIDATOR.exists():
    sys.exit("SKIP-FAIL: %s is missing" % VALIDATOR)

WORK = Path(tempfile.mkdtemp(prefix="madeira-ipa-"))


def make_app(root, name="Madeira.app", exec_name="Madeira", extra=(), plist_exec=None):
    """A Payload directory with one bundle, an XML Info.plist and an executable."""
    payload = root / "artifacts" / "Payload"
    bundle = payload / name
    bundle.mkdir(parents=True)
    bundle.joinpath("Info.plist").write_bytes(
        plistlib.dumps({"CFBundleExecutable": plist_exec if plist_exec is not None else exec_name,
                        "CFBundleIdentifier": "app.madeira.winephone",
                        "CFBundleName": "Madeira"}))
    exe = bundle / exec_name
    exe.write_bytes(b"\xcf\xfa\xed\xfe" + b"\0" * 64)   # arm64 Mach-O magic + padding
    exe.chmod(0o755)
    for name_extra, data in extra:
        target = bundle / name_extra
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return payload


def package(root, ipa_name="WinePhone-unsigned.ipa"):
    """Zip the Payload directory, and check that the archive really holds what the tree holds.

    The fixtures are built and zipped while the suite runs checks in parallel,
    and on a loaded host a zip whose listing is short would make a later
    assertion about the *validator* fail for the wrong reason. Verify here, and
    retry the package once rather than testing the validator against an archive
    that was never complete.
    """
    ipa = root / "artifacts" / ipa_name
    on_disk = sorted(str(p.relative_to(root / "artifacts"))
                     for p in (root / "artifacts/Payload").rglob("*") if p.is_file())
    for attempt in (1, 2):
        subprocess.run(["zip", "-qry", str(ipa), "Payload"],
                       cwd=root / "artifacts", check=True)
        listing = subprocess.run(["unzip", "-l", str(ipa)], capture_output=True, text=True).stdout
        missing = [f for f in on_disk if f not in listing]
        if not missing:
            return ipa
        if attempt == 2:
            sys.exit("FAIL: the test fixture archive is missing %s; unzip -l says:\n%s"
                     % (missing, listing))
        ipa.unlink()
    return ipa


def run(root, ipa, archs="arm64", payload=None):
    bin_stub = root / "bin"
    bin_stub.mkdir(exist_ok=True)
    stub = bin_stub / "lipo"
    stub.write_text('#!/bin/sh\nprintf \'%s\\n\' "$LIPO_ARCHS"\n')
    stub.chmod(0o755)
    env = dict(os.environ, PATH=str(bin_stub) + os.pathsep + os.environ.get("PATH", ""),
               LIPO_ARCHS=archs)
    sums = root / "artifacts" / "SHA256SUMS"
    r = subprocess.run(["bash", str(VALIDATOR), str(ipa),
                        str(payload if payload is not None else root / "artifacts/Payload"),
                        str(sums), str(root)],
                       capture_output=True, text=True, env=env)
    return r, sums


def only_one(root):
    """A fresh fixture directory per case, so one case cannot see another's files."""
    d = WORK / ("case%d" % len(list(WORK.iterdir())))
    d.mkdir(parents=True)
    return d


# ------------------------------------------------------------------ accepts a good IPA
root = only_one(WORK)
payload = make_app(root)
ipa = package(root)
r, sums = run(root, ipa)
check(r.returncode == 0, "a well-formed arm64 IPA validates (rc=%d, %s)" % (r.returncode, r.stderr.strip()[:200]))
keys = dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)
check(keys.get("IPA_VALID") == "1" and keys.get("BUNDLE_EXEC") == "Madeira"
      and keys.get("IPA_ARCHS") == "arm64" and keys.get("APP_BUNDLES") == "1",
      "and reports the bundle, its executable and the arch it found: %s" % keys)

# The published hash must be the hash of the published IPA, in verifiable form.
recomputed = subprocess.run(["shasum", "-a", "256", str(ipa)], capture_output=True, text=True,
                            check=True).stdout.split()[0]
check(sums.exists() and sums.read_text().split()[0] == recomputed,
      "SHA256SUMS is the sha256 of the packaged IPA")
check(sums.exists() and sums.read_text().split()[1] == "artifacts/" + ipa.name,
      "and names it relative to the repository root, so 'shasum -c' verifies it")
verified = subprocess.run(["shasum", "-a", "256", "-c", str(sums)],
                          cwd=root, capture_output=True, text=True) if sums.exists() else None
check(verified is not None and verified.returncode == 0, "shasum -a 256 -c accepts the sums file")

# ------------------------------------------------------------------ rejects the bad ones
root = only_one(WORK)
payload = make_app(root, plist_exec="Madeira")
(payload / "Madeira.app/Madeira").unlink()
ipa = package(root)
r, _ = run(root, ipa)
check(r.returncode != 0 and "does not exist" in r.stderr,
      "an IPA whose CFBundleExecutable is missing is refused: %s" % r.stderr.strip()[:160])

root = only_one(WORK)
payload = make_app(root)
make_app(root, name="Stale.app", exec_name="Stale")
ipa = package(root)
r, _ = run(root, ipa)
check(r.returncode != 0 and "expected exactly 1" in r.stderr,
      "a payload with two app bundles is refused: %s" % r.stderr.strip()[:1200])

root = only_one(WORK)
payload = make_app(root)
ipa = package(root)
r, _ = run(root, ipa, archs="x86_64")
check(r.returncode != 0 and "no arm64 slice" in r.stderr,
      "an executable without an arm64 slice is refused: %s" % r.stderr.strip()[:160])

root = only_one(WORK)
payload = make_app(root, extra=[("d3d12core.dll", b"MZ")])
ipa = package(root)
r, _ = run(root, ipa)
# The archive listing is the input to this check, so report it when the check
# does not fire: a missing file and an unreadable listing are different bugs.
diag = ""
if not (r.returncode != 0 and "forbidden" in r.stderr):
    diag = "\n  zip listing:\n%s\n  files under Payload: %s" % (
        "\n".join("  " + l for l in subprocess.run(["unzip", "-l", str(ipa)], capture_output=True,
                                                   text=True).stdout.splitlines()),
        sorted(str(p.relative_to(root)) for p in (root / "artifacts/Payload").rglob("*")))
check(r.returncode != 0 and "forbidden" in r.stderr,
      "a forbidden D3D12/Microsoft runtime file is refused: %s%s" % (r.stderr.strip()[:160], diag))

root = only_one(WORK)
payload = make_app(root)
ipa = package(root)
(payload / "Madeira.app/Info.plist").unlink()
r, _ = run(root, ipa)
check(r.returncode != 0 and "Info.plist" in r.stderr,
      "a bundle without Info.plist is refused: %s" % r.stderr.strip()[:160])

root = only_one(WORK)
make_app(root)
ipa = package(root)
stale = "0" * 64 + "  artifacts/" + ipa.name + "\n"
root.joinpath("artifacts/SHA256SUMS").write_text(stale)
r, sums = run(root, ipa)
real = subprocess.run(["shasum", "-a", "256", str(ipa)], capture_output=True, text=True,
                      check=True).stdout.split()[0]
check(r.returncode == 0 and sums.read_text() != stale and sums.read_text().split()[0] == real,
      "a stale SHA256SUMS is replaced with the hash of this IPA, never trusted as-is")

shutil.rmtree(WORK, ignore_errors=True)

if failures:
    print("FAILED: %d" % len(failures))
    sys.exit(1)
print("OK")
