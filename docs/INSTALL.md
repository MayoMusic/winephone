# Install notes (not yet tested)

There is no IPA to install yet. The GitHub workflow is intended to produce an
unsigned artifact. It will need to be signed for your device with your Apple
ID using SideStore, AltStore, or another signing tool. The signing flow and
entitlements must be checked on the actual iPhone 17/iOS 27 before claiming
installation support.

The pinned Madeira JIT guide (`docs/JIT.md`, base commit
`279fd0f83170425db002fe25d6bd62f6355f497d`) describes built-in StikJIT pairing
from iOS 27: pair the app through **Settings → Privacy & Security → Developer
Mode → Pair with Madeira**, continue the in-app pairing/JIT flow, and keep the
debugger-assisted JIT protocol active while the app requests executable
memory. The exact prompts and entitlement behavior must be verified on your
device. A successful app install alone does not prove JIT is enabled.

Free Apple ID provisioning is time-limited. Apple currently documents a
7-day expiration for free provisioning profiles; after expiry the app must be
refreshed/reinstalled. See [Apple's developer account help](https://developer.apple.com/help/account/basics/about-your-developer-account/).
**VERIFY:** confirm the exact SideStore/AltStore refresh steps and what app
container data survives on the installed version you use.

Do not add Microsoft Visual C++ runtime DLLs to the IPA or repository. If a
game needs Microsoft's redistributable rather than Wine's built-in
implementation, supply it yourself under Microsoft's terms. DRM, anti-cheat,
and anti-tamper titles are unsupported; no circumvention is provided.
