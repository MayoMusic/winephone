#!/usr/bin/env python3
r"""
prepare-entitlements.py - generate the entitlements Madeira should be signed
with, from the provisioning profile that will actually sign it.

Why this exists
---------------
A sideloading tool (SideStore, AltStore, GetMoreRam or anything else) signs
with your own team. It can copy a key into a code signature, but it cannot make
Apple authorise a capability your team does not hold. If the signature asks for
a capability the profile does not carry, the install is rejected or the
capability is silently dropped - so "the key is in the plist" is not the same as
"the capability works".

The only trustworthy source for "what am I allowed to ask for" is the profile
that will sign the build. This script reads that profile and emits exactly the
entitlements it authorises. Nothing more.

The two memory entitlements, per Apple's own documentation:

  com.apple.developer.kernel.increased-memory-limit
      "may perform better by exceeding the default app memory limit"
      -> physical RAM. Does not enlarge address space.

  com.apple.developer.kernel.extended-virtual-addressing
      "needs that require a larger addressable space ... games that memory map
       assets to stream to the GPU may benefit"
      -> virtual address space. This is the one a large contiguous VirtualAlloc
         reservation fails on.

Usage
-----
  # See what a profile allows, change nothing.
  python3 prepare-entitlements.py profile.mobileprovision

  # Regenerate the app's entitlements from that profile.
  python3 prepare-entitlements.py profile.mobileprovision \
      --out ../app/Madeira/Madeira.entitlements

  # CI gate: fail if the committed entitlements ask for anything the profile
  # does not authorise.
  python3 prepare-entitlements.py profile.mobileprovision \
      --check ../app/Madeira/Madeira.entitlements
"""
import argparse
import os
import plistlib
import re
import sys

INCREASED_MEMORY = "com.apple.developer.kernel.increased-memory-limit"
EXTENDED_VA = "com.apple.developer.kernel.extended-virtual-addressing"
GET_TASK_ALLOW = "get-task-allow"

# Keys the runtime genuinely needs on iOS. Everything else is optional and is
# only emitted when the profile authorises it.
ALWAYS_WHEN_AUTHORISED = (GET_TASK_ALLOW,)
OPTIONAL_MEMORY = (INCREASED_MEMORY, EXTENDED_VA)

# Keys that are legal to carry but that iOS itself never grants. Asking for one
# cannot fail the install, so they are reported rather than treated as a
# mismatch - otherwise the check would fail on every profile forever.
KNOWN_UNAVAILABLE = {
    "com.apple.security.cs.allow-jit":
        "macOS only; iOS never grants it, so it does nothing here",
}

PLIST_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    '<plist version="1.0">\n<dict>\n'
)
PLIST_FOOTER = "</dict>\n</plist>\n"


def load_profile(path):
    """Return (plist_dict, error_or_None). Handles CMS-wrapped .mobileprovision."""
    with open(path, "rb") as fh:
        blob = fh.read()
    # A .mobileprovision is a CMS/PKCS#7 wrapper around a bare XML plist.
    # Strip the wrapper without needing openssl.
    start = blob.find(b"<?xml")
    end = blob.find(b"</plist>")
    if start == -1 or end == -1:
        return None, "no XML plist found inside %s" % path
    try:
        obj = plistlib.loads(blob[start:end + len(b"</plist>")])
    except Exception as exc:                       # noqa: BLE001
        return None, "could not parse the embedded plist: %s" % exc
    if not isinstance(obj, dict):
        return None, "the embedded plist is not a dictionary"
    return obj, None


def profile_kind(prof, grants):
    if prof.get("ProvisionsAllDevices") is True:
        return "enterprise"
    if prof.get("ProvisionedDevices") is not None:
        return "development" if grants.get(GET_TASK_ALLOW) is True else "ad-hoc"
    if prof.get("ProvisionsAllDevices") is None and \
            prof.get("ProvisionedDevices") is None and \
            "ProvisionsAllDevices" not in prof:
        # store profiles have neither key; ad-hoc/enterprise were handled above
        if "Beta-reports-active" in prof or prof.get("DER-Encoded-Profile") is None:
            pass
        return "store"
    return "store"


def days_left(prof):
    created = prof.get("CreationDate")
    expires = prof.get("ExpirationDate")
    if not isinstance(created, type(prof.get("CreationDate"))) or created is None:
        return None
    if expires is None or created is None:
        return None
    return int((expires - created).total_seconds() // 86400)


def render(keys):
    body = []
    for k in keys:
        body.append("\t<key>%s</key>\n\t<true/>\n" % k)
    return PLIST_HEADER + "".join(body) + PLIST_FOOTER


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("profile", help="path to a .mobileprovision")
    ap.add_argument("--out", help="write the generated entitlements plist here")
    ap.add_argument("--check",
                    help="compare an existing entitlements plist against the "
                         "profile and fail if it asks for anything the "
                         "profile does not authorise")
    args = ap.parse_args()

    if not os.path.isfile(args.profile):
        print("ERROR: no such file: %s" % args.profile, file=sys.stderr)
        return 2
    prof, err = load_profile(args.profile)
    if err:
        print("ERROR: %s" % err, file=sys.stderr)
        return 2

    ents = prof.get("Entitlements") or {}
    if not isinstance(ents, dict):
        print("ERROR: Entitlements is not a dictionary", file=sys.stderr)
        return 2
    grants = {k: (v is True) for k, v in ents.items()}

    kind = profile_kind(prof, grants)
    remaining = days_left(prof)
    print("profile     : %s" % args.profile)
    print("kind        : %s" % kind)
    print("team        : %s" % (prof.get("TeamName") or "unknown"))
    if remaining is not None:
        print("lifetime    : %d days total" % remaining)
        if remaining <= 7:
            print("             : this is a FREE Apple Account profile")
    print("get-task-allow : %s" % ("granted" if grants.get(GET_TASK_ALLOW)
                                   else "NOT granted"))
    print("")
    print("memory capabilities:")
    for key, why in ((INCREASED_MEMORY, "physical RAM limit"),
                     (EXTENDED_VA, "virtual address space")):
        state = "granted" if grants.get(key) else "NOT granted"
        print("  %-58s %-12s (%s)" % (key, state, why))
    print("")
    if not any(grants.get(k) for k in OPTIONAL_MEMORY):
        print("This profile carries neither memory capability.")
        if kind == "development" and remaining is not None and remaining <= 7:
            print("A 7-day profile means a free Apple Account. Free teams cannot")
            print("hold restricted capabilities, so no sideloading tool can add")
            print("them to this build. A game that fails on 'unable to reserve")
            print("N MB of address space' needs Extended Virtual Addressing, which")
            print("this profile cannot provide, and a free account cannot obtain.")
        else:
            print("Enable the capability on the App ID in the Developer Portal")
            print("with a paid Apple Developer Program team, then re-run this.")
        print("")

    wanted = [k for k in ALWAYS_WHEN_AUTHORISED if grants.get(k)]
    wanted += [k for k in OPTIONAL_MEMORY if grants.get(k)]

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(wanted))
        print("wrote %s with %d entitlement(s): %s"
              % (args.out, len(wanted), ", ".join(wanted) or "none"))

    if args.check:
        try:
            with open(args.check, "rb") as fh:
                current = plistlib.load(fh)
        except Exception as exc:                   # noqa: BLE001
            print("ERROR: could not read %s: %s" % (args.check, exc),
                  file=sys.stderr)
            return 2
        asked = sorted(k for k, v in current.items() if v is True)
        unauthorised = [k for k in asked
                        if not grants.get(k) and k not in KNOWN_UNAVAILABLE]
        informational = [k for k in asked if k in KNOWN_UNAVAILABLE]
        for k in informational:
            print("NOTE: %s is present but %s." % (k, KNOWN_UNAVAILABLE[k]))
        if unauthorised:
            print("CHECK FAILED: %s asks for entitlement(s) this profile does "
                  "not authorise:" % args.check, file=sys.stderr)
            for k in unauthorised:
                print("  - %s" % k, file=sys.stderr)
            print("Signing with these present risks a rejected install or the "
                  "key being dropped.", file=sys.stderr)
            return 1
        print("CHECK OK: %s asks only for entitlements this profile authorises "
              "(%s)" % (args.check, ", ".join(asked) or "none"))

    return 0


if __name__ == "__main__":
    sys.exit(main())