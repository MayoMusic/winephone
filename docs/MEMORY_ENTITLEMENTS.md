# Memory entitlements: what they are, what they are not, and what they fix

This exists because a bad diagnosis is expensive here. Rise of the Tomb Raider
dies with

```
CDC: Unable to reserve 3072MB of address space.
```

and the natural reaction is to reach for "more RAM". Those are two different
limits, two different entitlements, and only one of them touches this failure.

## The two entitlements are not interchangeable

From Apple's own documentation for each key:

| Entitlement | Apple's wording | What it changes |
|---|---|---|
| `com.apple.developer.kernel.increased-memory-limit` | "may perform better by **exceeding the default app memory limit** on supported devices" | physical RAM ceiling (the Jetsam threshold) |
| `com.apple.developer.kernel.extended-virtual-addressing` | "needs that require a **larger addressable space**. For example, **games that memory map assets to stream to the GPU may benefit** from a larger address space" | virtual address space |

The failing call is `VirtualAlloc(NULL, 0xC0000000, MEM_RESERVE,
PAGE_READWRITE)` - a contiguous **address space** reservation.
`MEM_RESERVE` does not commit physical pages. So raising the RAM ceiling does
nothing for it.

**Extended Virtual Addressing is the one that can address this failure.**
Increased Memory Limit cannot.

## What Apple will and will not grant

Both are restricted capabilities, enabled on the App ID and shipped through the
"Extended Virtual Addressing" / increased-memory-limit capability in the Xcode
project editor. That requires a **paid Apple Developer Program team**.

A **free Apple Account** gets a 7-day profile and cannot hold restricted
capabilities. There is no workflow that changes this: not a sideloading tool,
not an entitlement plist, not a rebuild.

## Why a sideloading tool cannot grant them

SideStore, AltStore and similar tools re-sign the IPA **with your own team's
certificate**. They can place a key into a code signature. They cannot make
Apple authorise a capability your team does not hold, and they cannot enlarge an
address map the kernel did not grant.

`Madeira.entitlements` already carries `increased-memory-limit`. On a free
profile that key is present and unauthorised: it does nothing, and the app now
reports it as amber "signed, not granted" rather than a green tick.

`com.apple.security.cs.allow-jit` is also in that file. It is macOS-only and
iOS never grants it - the app's own code comment says so. It is harmless but
inert.

## About GetMoreRam

`https://github.com/byeCl0ud/GetMoreRam` was checked and **is not reachable**.
The GitHub API returns 404 for the repository and for the user `byeCl0ud`, a
direct HTTPS GET returns 404, and a repository search for `GetMoreRam` returns
nothing. Its contents, dependencies and implementation are therefore unknown
here, and nothing in this tree is derived from it.

What can be said without it: the app's setup guide used to instruct "install
GetMoreRam and run it to inject memory entitlements into your App ID". That
instruction has been corrected, because the part of it that is checkable is
wrong. Injecting a key into an App ID is a Developer Portal operation, it needs
the capability to already be grantable to that team, and a free Apple Account
is not. The guide now describes the capability, the account requirement, and
the signing step, and does not tell the reader to install a tool whose behaviour
this project cannot verify.

## What the app does now

`app/Madeira/MemoryCapability.swift` resolves each capability from three
independent sources and refuses to call one working unless an effect is seen:

1. `SecTaskCopyValueForEntitlement` - what the kernel reports.
2. The embedded `.mobileprovision` - what Apple authorised.
3. `jit_task_map_range` - the address map this process actually received.

A key sitting in a file satisfies none of these on its own. Extended Virtual
Addressing is only reported as working when the profile authorises it **and**
the measured map top is above the non-entitled ceiling of `0xfc0000000` (63 GB).
If the key is set but the map is unchanged, the badge is amber: the entitlement
did nothing.

The badges are three-state (green / amber "signed, not granted" / red
"missing"), and the startup log carries the measured map, the profile kind and
its remaining lifetime, so a log states which account type produced it.

## Preparing the signing workflow

Entitlements have to be right before installation, not at runtime, so the step
belongs to the packaging workflow. `scripts/prepare-entitlements.py` reads the
profile that will sign the build and emits only what that profile authorises:

```sh
# report what a profile allows, change nothing
python3 scripts/prepare-entitlements.py build/embedded.mobileprovision

# regenerate app/Madeira/Madeira.entitlements from that profile
python3 scripts/prepare-entitlements.py build/embedded.mobileprovision \
    --out app/Madeira/Madeira.entitlements

# CI gate: fail if the committed entitlements ask for anything the profile
# does not authorise
python3 scripts/prepare-entitlements.py build/embedded.mobileprovision \
    --check app/Madeira/Madeira.entitlements
```

`tests/host/check-prepare-entitlements.py` runs this against a free 7-day
profile, a paid profile holding both capabilities, and a paid profile holding
only Extended Virtual Addressing.

## The remaining blocker, stated plainly

With a free Apple Account there is no route to Extended Virtual Addressing.
So on the current signing identity the ROTTR failure cannot be fixed from the
emulator side, and the options are:

- **Obtain the capability** - paid Apple Developer Program team, capability
  enabled on the App ID, rebuild signed by that team. Slow, and outside this
  repository's control.
- **Ask less address space** - the game reserves 3072 MB of address space in
  one call, with no fallback. `tools/rotrr-heap-patch.py` lowers that constant.
  `MEM_RESERVE` commits nothing, so a smaller reservation still works for as
  much as the game actually touches, and the failure moves to a clearer
  "out of transient heap space" message if it was genuinely needed.

Nothing here has been run on a device. No capability status has been observed,
no game has been started, and no performance figure exists.