# WinePhone blockers

## B-001: Local iOS build unavailable

- **Evidence:** FP0 found Windows 10 x64 and no `xcodebuild`/Xcode. Madeira's documented final build step is `xcodebuild -project app/Madeira.xcodeproj ...` (`docs/BUILDING.md` at base commit `279fd0f83170425db002fe25d6bd62f6355f497d`).
- **Impact:** IPA build must run on a macOS GitHub runner; this host cannot validate the IPA locally.
- **Next path:** Run the drafted macOS Actions workflow after GitHub authentication. The local platform limitation has a documented CI path.
- **Ladder tried:** (1) diagnosis; (3) use the documented macOS build route. (2) Not needed because source lists the correct platform-specific builder.
- **Status:** Active.

## B-002: GitHub publication requires user authentication

- **Evidence:** `gh auth status` reports no logged-in GitHub host.
- **Impact:** Cannot create the public repository, push changes, start a user-owned workflow, or publish a release.
- **Next path:** Prepare and review local work; then ask the user to run `gh auth login`.
- **Ladder tried:** (1) checked current CLI auth state; credential handling remains user-only by instruction.
- **Status:** Active.

## B-003: Full source history omitted; one local nested checkout has a stale lock

- **Evidence:** Full-history clone exceeded the time box; the Wine fork branch head is the exact gitlink SHA `9129e9684daaeae70da9435e7c6060e59392634e`. FEX `.gitmodules` includes binary test-corpus submodules (`fex-gcc-target-tests-bins`, `fex-gvisor-tests-bins`, `fex-posixtest-bins`).
- **Impact:** Full ancestry and unneeded test binaries are not fetched. `FEX/External/vixl` local worktree is empty although the exact gitlink is recorded; a stale `.git` lock prevented the current checkout from fetching it.
- **Next path:** The bootstrap fetches VIXL at its exact gitlink on the clean runner. Confirm this succeeds in CI.
- **Ladder tried:** (1) checked for an active Git process (none); (2) retained exact pinned gitlink and updated bootstrap to fetch selected nested sources; a stale lock removal was rejected by workspace safety policy. No corpus binary was run or added to the WinePhone tree.
- **Status:** Local worktree issue; clean-run verification pending.

## B-004: Device-side behavior not verified

- **Evidence:** No IPA exists and no device logs were provided. JIT behavior on iOS 27, signing entitlements, jetsam limits, and runtime compatibility remain untested.
- **Impact:** No performance or compatibility claim can be made.
- **Next path:** Build IPA in CI, then user installs/enables JIT and shares logs. User will provide a game name before title-specific analysis.
- **Status:** Active.

## B-006: macOS workflow and cold toolchain build unverified

- **Evidence:** `scripts/bootstrap.sh` and `.github/workflows/build-ipa.yml` have not run; the Windows host has no Xcode and GitHub is unauthenticated.
- **Impact:** No evidence yet that LLVM, component libraries, Xcode, or IPA packaging complete on the selected runner.
- **Next path:** After user authentication, start the workflow, inspect the first failure logs, and iterate.
- **Status:** Active.

## B-005: License/provenance review needed before public binary release

- **Evidence:** Madeira `docs/LICENSING.md` explicitly leaves LGPL static-link/relink capability and lawyer review open; `LICENSE-EXCEPTION.md` limits its exception to Madeira-authored code and does not cover Wine.
- **Impact:** Do not claim final distribution clearance for a combined IPA until the exact license bundle, notices, and relink route are verified.
- **Next path:** Audit `THIRD-PARTY-NOTICES.md`, submodule license files, converter exclusion, and clean rebuild/relink capability; retain per-component licenses. The workflow requires repository variable `WINEPHONE_BINARY_RELEASE_CLEARED=true` before publishing IPA artifacts.
- **Status:** Active.

## B-007: No-JIT target is not implemented

- **Evidence:** The app uses `JITAllocator.c` and FEX's iOS JIT pool environment variables; no AOT backend or interpreter fallback is wired into the app.
- **Impact:** The Track A sideload output does not meet the separate zero-JIT App-Store-style requirement.
- **Next path:** Track B feasibility study: measure code discoverability, prototype an existing lifter/interpreter integration, or document why it cannot meet the requirement.
- **Status:** Active; explicitly out of scope for the current Track A build.
