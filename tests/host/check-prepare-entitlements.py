#!/usr/bin/env python3
"""Host check: scripts/prepare-entitlements.py.

The rule under test is the one that decides whether a memory entitlement is
worth showing as available: only a key the signing profile actually authorises
may be emitted, and asking for anything else has to be reported rather than
glossed over. Synthetic profiles stand in for the three real cases - a free
7-day Apple Account, a paid team holding both capabilities, and a paid team
holding only Extended Virtual Addressing.
"""
import datetime
import os
import plistlib
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(ROOT, "scripts", "prepare-entitlements.py")
APP_ENTS = os.path.join(ROOT, "app", "Madeira", "Madeira.entitlements")

INCREASED_MEMORY = "com.apple.developer.kernel.increased-memory-limit"
EXTENDED_VA = "com.apple.developer.kernel.extended-virtual-addressing"
GET_TASK_ALLOW = "get-task-allow"
ALLOW_JIT = "com.apple.security.cs.allow-jit"

failures = []


def ok(message):
    print("PASS %s" % message)


def bad(message):
    failures.append(message)
    print("FAIL %s" % message)


def make_profile(path, days, memory):
    now = datetime.datetime(2026, 10, 16, 12, 0, 0)
    ents = {
        "application-identifier": "ABCDE12345.com.madeira.emulator",
        GET_TASK_ALLOW: True,
        "keychain-access-groups": ["ABCDE12345.*"],
    }
    if "IM" in memory:
        ents[INCREASED_MEMORY] = True
    if "EVA" in memory:
        ents[EXTENDED_VA] = True
    prof = {
        "Entitlements": ents,
        "TeamName": "Synthetic Test Team",
        "ProvisionedDevices": ["0123456789abcdef"],
        "CreationDate": now,
        "ExpirationDate": now + datetime.timedelta(days=days),
    }
    # A real .mobileprovision is CMS-wrapped; the script strips the wrapper.
    with open(path, "wb") as fh:
        fh.write(b"\x30\x82\xfakecms" + plistlib.dumps(prof))
    return path


def run(profile, *extra):
    return subprocess.run([sys.executable, SCRIPT, profile] + list(extra),
                          capture_output=True, text=True)


def main():
    if not os.path.isfile(SCRIPT):
        bad("scripts/prepare-entitlements.py exists")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        free = make_profile(os.path.join(tmp, "free7.mobileprovision"), 7, "")
        paid = make_profile(os.path.join(tmp, "paid.mobileprovision"),
                            365, "IM+EVA")
        eva_only = make_profile(os.path.join(tmp, "eva.mobileprovision"),
                                365, "EVA")

        # 1. A free 7-day profile carries neither capability, and the script has
        #    to say so and explain that no sideloading tool can change that.
        r = run(free)
        if r.returncode == 0 and "FREE Apple Account" in r.stdout \
                and "NOT granted" in r.stdout:
            ok("a free 7-day profile reports neither memory capability and is "
               "identified as a free Apple Account")
        else:
            bad("free profile handling: rc=%d out=%r" % (r.returncode,
                                                         r.stdout[-400:]))

        # 2. Generation must come from the profile, never from a wish list.
        out = os.path.join(tmp, "free.entitlements")
        r = run(free, "--out", out)
        if r.returncode == 0 and os.path.isfile(out):
            with open(out, "rb") as fh:
                made = plistlib.load(fh)
            if made == {GET_TASK_ALLOW: True}:
                ok("generation from a free profile emits only get-task-allow")
            else:
                bad("free profile generation emitted %r" % (made,))
        else:
            bad("generation from a free profile failed: rc=%d %r"
                % (r.returncode, r.stderr[-300:]))

        # 3. A paid team holding both capabilities gets both emitted.
        out2 = os.path.join(tmp, "paid.entitlements")
        r = run(paid, "--out", out2)
        with open(out2, "rb") as fh:
            made = plistlib.load(fh)
        if r.returncode == 0 and made.get(INCREASED_MEMORY) is True \
                and made.get(EXTENDED_VA) is True:
            ok("a paid profile holding both capabilities emits both")
        else:
            bad("paid profile generation emitted %r" % (made,))

        # 4. Only what the profile grants: a team with EVA alone must not get
        #    the increased-memory-limit key. Generated separately, because the
        #    rule is about the profile in hand, not about the previous run.
        out3 = os.path.join(tmp, "eva.entitlements")
        r = run(eva_only, "--out", out3)
        with open(out3, "rb") as fh:
            made_eva = plistlib.load(fh)
        if r.returncode == 0 and INCREASED_MEMORY not in made_eva \
                and made_eva.get(EXTENDED_VA) is True:
            ok("EVA-only generation emits EVA and does not add "
               "increased-memory-limit")
        else:
            bad("EVA-only generation emitted %r" % (made_eva,))

        # 5. The CI gate: the committed app entitlements must not ask for a key
        #    a free profile cannot authorise.
        r = run(free, "--check", APP_ENTS)
        if r.returncode == 1 and INCREASED_MEMORY in r.stderr:
            ok("--check fails when the app asks for a capability the profile "
               "does not authorise")
        else:
            bad("--check against a free profile: rc=%d stderr=%r"
                % (r.returncode, r.stderr[-300:]))

        # 6. The same file passes when the profile does authorise it. This is
        #    what stops the gate from being permanently red.
        r = run(paid, "--check", APP_ENTS)
        if r.returncode == 0:
            ok("--check passes for a profile that authorises the committed keys")
        else:
            bad("--check against a paid profile: rc=%d stderr=%r"
                % (r.returncode, r.stderr[-300:]))

        # 7. allow-jit is macOS-only; it must be a note, never the failure.
        r = run(paid, "--check", APP_ENTS)
        if "NOTE" in r.stdout and ALLOW_JIT in r.stdout:
            ok("allow-jit is reported as a note rather than a mismatch")
        else:
            bad("allow-jit note missing: %r" % r.stdout[-300:])

        # 8. A missing file is refused rather than treated as "no entitlements".
        r = run(os.path.join(tmp, "nope.mobileprovision"))
        if r.returncode != 0:
            ok("a missing profile is refused instead of silently allowing all")
        else:
            bad("a missing profile was accepted")

    if failures:
        print("\n%d failure(s)" % len(failures))
        return 1
    print("\nall entitlement-preparation checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())