# WinePhone decisions

## D-001: Base repository

- **Choice:** Madeira (Option 1), pinned at `279fd0f83170425db002fe25d6bd62f6355f497d`.
- **Reason:** It already carries the iOS Wine/FEX/DXMT adaptations required by the project. The README explicitly says the upstream checkouts do not build for iOS.
- **Evidence:** `README.md`, `docs/BUILDING.md`, and `.gitmodules` at that commit.
- **Status:** Pinned checkout is present locally. Clean clone reproduction remains a CI acceptance item.

## D-002: License for WinePhone-authored code

- **Choice:** GPL-3.0-or-later, with no Madeira Converter Exception claimed for WinePhone-authored code.
- **Reason:** This matches the Madeira base's main license and keeps the project copyleft. The exception in the base is limited to Madeira-author code and cannot be extended by this project to upstream Wine or other contributors' code. We will not include or build the Apple Metal Shader Converter / Madeira D3D12 path in WinePhone's IPA pipeline unless a separate legal review establishes a compatible route.
- **Evidence:** `LICENSE`, `LICENSE-EXCEPTION.md`, `docs/LICENSING.md`, `docs/BUILDING.md`, all at base commit `279fd0f83170425db002fe25d6bd62f6355f497d`.
- **Meaning:** GPL is a free-software license that permits use, modification, and redistribution, while requiring source and the same freedoms when distributing covered modified/combined software. Component-specific licenses and notices remain in force; this choice does not relicense upstream code.
- **Status:** Engineering choice, not legal advice. Public distribution remains blocked on a component-by-component provenance review and review of LGPL static-link/relink obligations.

## D-003: Build target

- **Choice:** Build an unsigned IPA on a macOS GitHub Actions runner; do not attempt a local iOS build on this Windows host.
- **Reason:** No Mac/Xcode is available locally. Madeira's documented build invokes `xcodebuild` and requires iOS SDKs.
- **Evidence:** `docs/BUILDING.md` at base commit `279fd0f83170425db002fe25d6bd62f6355f497d`; FP0 host check (2026-10-14 local time).
- **Status:** No workflow has been run; runner availability and all clean-build inputs remain to be verified.

## D-004: Device/JIT track

- **Choice:** Track A (debugger-enabled sideload build) for the iPhone 17 on iOS 27; free Apple ID signing.
- **Reason:** The user selected this device and account. No-JIT Track B remains research only.
- **Evidence:** User-provided device context; Madeira `README.md` and `docs/JIT.md` require verification against source and device behavior.
- **Status:** No device test has occurred.

## D-005: Game test selection

- **Choice:** Defer selecting a title until the user provides its name; meanwhile use only repository-hosted test programs and build checks.
- **Reason:** The game is user-owned and on-device, but its identity and DRM status are not yet known.
- **Status:** No game binary has been inspected or run.

## D-006: GitHub publication

- **Choice:** Prepare local project changes for a new public repository named `winephone`; create/push only after the user runs `gh auth login`.
- **Reason:** GitHub CLI is installed but unauthenticated. No credentials will be requested or handled here.
- **Status:** Awaiting user-only authentication action after the repository contents are reviewable.

## D-007: Keep AI-authored changes out of upstream contributions

- **Choice:** Publish changes only in the separate WinePhone repository; do not push or submit patches to Madeira, Wine, FEX, or DXMT upstream.
- **Reason:** Madeira `CONTRIBUTING.md` at base commit `279fd0f83170425db002fe25d6bd62f6355f497d` says AI must not generate code contributions to Madeira. FEX and DXMT upstream policies also prohibit AI-authored code contributions.
- **Evidence:** FEX upstream `CONTRIBUTING.md` at `5285020de0b30dbdae7b44d0d83541af2d13d002`; DXMT upstream `CONTRIBUTING.md` at `186a2327f1ec76376f6bc1ef64636f08b0728567`; see `docs/SOURCES.md`.
- **Status:** Applied; `origin` still points to Madeira and must never be used for push.

## D-008: Label the current artifact as Track A only

- **Choice:** The workflow builds the existing debugger-enabled sideload app. It does not claim to provide the required no-JIT/App-Store-style target.
- **Reason:** The pinned integration wires FEX through the JIT code pool; no AOT or fast-interpreter x86 backend has been implemented.
- **Evidence:** `app/Madeira/JITAllocator.c`, `app/Madeira/FEXBridge.mm`, and `FEX/Source/Windows/ARM64EC/Module.cpp` at base/FEX commits recorded in `docs/SOURCES.md`; Track B is still research in `PLAN.md`.
- **Status:** Track A workflow is drafted; no-JIT target remains a blocker.

## Binary release gate review (2026-10-14)

**Decision: not cleared.** The pinned Wine fork's `wine/LICENSE-MADEIRA.md` says LGPL-2.1-or-later, while the root `THIRD-PARTY-NOTICES.md` describes the fork as GPL-3.0-or-later. The base project's own `docs/LICENSING.md` calls lawyer review and a clean recipient rebuild/relink/re-sign/install test open items. GnuTLS, FFmpeg and the DXMT D3D9 frontend also bring LGPL static-link obligations. Removing Apple's converter and custom D3D12 files removes that separate proprietary component but does not settle these remaining questions. Therefore do not set the repository variable `WINEPHONE_BINARY_RELEASE_CLEARED`; CI may build and validate locally, but must not publish an IPA artifact. This is a source and evidence gate decision, not a conclusion that source publication is unlawful.
