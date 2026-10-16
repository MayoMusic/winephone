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

**Correction.** An earlier version of this file said the repository was
unreachable. That was wrong, and the cause is worth recording: the repository
search that would have found it failed silently, and "the search returned
nothing" was read as "the repository does not exist". The URL in the request,
`github.com/byeCl0ud/GetMoreRam`, does 404 - the user `byeCl0ud` does not exist -
but the project lives at **`github.com/hugeBlack/GetMoreRam`** (389 stars,
Swift, created 2025-03-15). Searching, not guessing, is what finds a moved
project.

Its mechanism is one line of code, in `GetMoreRam/AppIDViewModel.swift`:

```swift
let cool = try await AppleAPI.shared.updateAppID(
    appID, capabilities: ["INCREASED_MEMORY_LIMIT"], team: team, session: session)
```

It is a **StosSign wrapper** (the signing service behind SideStore/AltStore). It
signs into the Apple Developer Portal with your own Apple ID - Anisette data
fetching is taken from SideStore - lists your team's App IDs, and calls
`updateAppID` to enable a capability on one. You then reinstall from
SideStore/AltStore, which re-signs against a profile that now carries the
entitlement.

So it does not add an entitlement to a binary. It changes the App ID in the
Developer Portal, and the entitlement arrives later because Apple then issues a
profile containing it.

**What it can and cannot do, checked against the repository:**

| Query | Hits |
|---|---|
| `INCREASED_MEMORY_LIMIT` | 1 (`AppIDViewModel.swift`) |
| `EXTENDED_VIRTUAL_ADDRESSING` | **0** |
| `extended-virtual` | **0** |

It enables exactly one capability and has no code path for the other. It also
requires portal access to a team that already holds the capability, so it is not
a route around the paid-account requirement.

**Therefore it cannot fix the ROTTR failure.** It grants the RAM-limit
entitlement, and the ROTTR failure is an address-space reservation. This is the
same conclusion the Apple documentation gives, now corroborated by the tool's
own source rather than by inference.

## What Winlator does differently, and what transfers

`github.com/brunodev85/winlator` (19,484 stars) is the Android equivalent: Wine
plus Box64 running x86 Windows games on ARM. It faces the same guest, and AAA
titles do start there. Two things are worth separating.

**What does not transfer: the large reservation itself.** Box64 maps the guest's
x86_64 address space into the host's. An Android 64-bit process has a far larger
address space than an iOS process without Extended Virtual Addressing, so a
3 GB contiguous `VirtualAlloc` simply has somewhere to land. There is no trick
in Box64 that manufactures contiguous address space - the difference is the
platform's ceiling. Nothing here makes iOS more like Android in that respect.

**What does transfer: the strong memory model.** Winlator's
`app/src/main/assets/box64/default.box64rc` sets
`BOX64_DYNAREC_STRONGMEM=1` for exactly the titles that stress threading -
witcher3, Dishonored, MassEffect, FalloutNV, Borderlands, Resident Evil 2 and
3, Just Cause 3 and 4 - and `BOX64_DYNAREC_WEAKBARRIER=1` for Resident Evil 2,
Resident Evil 3 and Just Cause. The option is documented as "emulation of x86
strong memory model", levels 0 to 4, and the box64 trackers describe it as
fixing memory-barrier-dependent behaviour at a CPU speed cost.

x86 is a strongly ordered architecture and ARM is weakly ordered. Wine on
ARM64EC has to impose x86's ordering on translated code, and a game that
misses it does not fail with a clear diagnostic - it fails as an intermittent
crash in threaded code, long after start-up, which is exactly the kind of
problem that is expensive to chase later.

**This has not been audited in this tree.** It is recorded as an investigation
item, not as a finding: no Wine or FEX source has been read for memory-barrier
handling, and no threaded game has been run.

Winlator's per-game `.box64rc` profile - one file of overrides keyed by
executable name - is the same shape as this project's per-game profile system,
which is a point in favour of that design rather than evidence about anything.

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