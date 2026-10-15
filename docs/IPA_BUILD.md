# IPA build plan and current evidence

## Host and target

The local host is Windows 10 x64 and has no Xcode or `xcodebuild` (see
`PROGRESS.md`). The IPA therefore must be built on a macOS GitHub Actions
runner. No IPA has been built or tested. The current workflow builds only the
debugger-enabled Track A sideload app. A separate working no-JIT target does
not exist yet; this output is not an App Store-style build.

## Build graph recorded by Madeira

`docs/BUILDING.md` at base commit `279fd0f83170425db002fe25d6bd62f6355f497d`
lists iOS native libraries (GnuTLS/FFmpeg, FEX, Wine unix-side, DXMT),
ARM64EC PE modules (Wine/FEX/DXMT), and an Xcode app build. The current IPA
script builds those chains and checks linked archives immediately before
Xcode. It excludes Madeira's proprietary converter dylib and custom D3D12
runtime; Wine's own D3D12 builtin may be present but is not a supported API
path. The script has not yet run on macOS, so clean-build success is unproven.

## Inputs/gaps

- Runner choice: use the stable `macos-26` arm64 image and select its Xcode
  26.6 installation explicitly. The workflow logs both numbers with the command
  that produced them, because they are different things: **Xcode 26.6**
  (`xcodebuild -version`) is the installation, and the **iPhoneOS SDK 26.5**
  (`xcrun --sdk iphoneos --show-sdk-version`) is the SDK inside it. The earlier
  "iOS SDK 26.4" figure in this document came from the image manifest, not from
  a run; PROGRESS.md's run `38628969464` reported Xcode 26.6 / iOS SDK 26.5,
  and `build/ntdll-unix/server_ios.c` records `ri_page_wait_time_mach` as
  absent from `rusage_info_v6` in the 26.5 SDK. The selection step now fails
  with the list of installed Xcodes if `Xcode_26.6.app` is not there, instead
  of letting `xcode-select` fail on a path. Xcode 27 is in public preview and
  is not the default. **VERIFY:** confirm the image still contains these
  versions when the workflow runs.
- llvm-mingw: Madeira documents release `20260421` and SHA-256
  `bd85a3975723815cef28dbbd2ca2cb0c926f6b348a12a0453f39f7af273cb3f7`.
- LLVM iOS and host builds: Madeira documents LLVM revision `8dfdcc7b7` and
  separate build directories; clean rebuild and duration are unverified.
- User-supplied VC++ runtime files are not a CI input and must not be stored
  in artifacts or source.
- The Xcode project originally referenced the absent `x86_64-vcruntime`
  folder. WinePhone removes that resource reference. The ARM64/ARM64EC runtime
  DLLs with similar names are Wine builtins; the gate verifies their embedded
  `Wine builtin DLL` marker before packaging.
- The DXMT script originally left `libdxmt_combined.a` absent on a clean build.
  WinePhone now creates it from the fresh DXMT objects plus the pinned LLVM iOS
  archives.
- Validate required `.a` archives and excluded proprietary/user DLLs before
  linking/packaging; fail with a named missing-input message.
- Sign disabled for build artifact; unsigned IPA is not installable until the
  user signs/sideloads it.

## What the workflow now verifies

- **Toolchain cache.** `scripts/bootstrap.sh` is the only validator of the
  restored `toolchains/` tree: it reuses `llvm-project` only when the checkout is
  at the LLVM pin, `llvm-host-build` only when `bin/llvm-tblgen` exists (and the
  source is at the pin), and `llvm-ios-build` only when
  `include/llvm/Config/llvm-config.h` and `lib/*.a` exist; anything else is
  rebuilt there, so a cache hit is cheap and a damaged cache still ends
  complete. The pinned sources are always fetched. The cache *save* is skipped
  on an exact-key hit, because `actions/cache/save` cannot reserve a key that
  already exists. `tests/host/check-toolchain-cache.py` runs both paths.
- **FreeType.** `build/freetype-ios/build.sh` verifies the pinned commit, then
  the archive, its arm64 slice and both generated headers
  (`build/include/freetype/config/{ftconfig.h,ftoption.h}`) plus the source
  `research/freetype/include/ft2build.h`, and fails if any is absent.
  `build/ntdll-unix/build.sh` and `build/win32u-unix/build.sh` refuse to build
  their font translation units without those headers.
- **GnuTLS archives.** `build/gnutls-ios/build.sh` installs `libgnutls.a`,
  `libhogweed.a`, `libnettle.a` and `libgmp.a` into `app/Madeira/` — the base
  the Xcode file references and `tools/validate_release_inputs.py` resolve
  against, and the same base the wineserver, ntdll, win32u, DXMT, rppairing and
  FFmpeg stages write to — and fails when one is missing or carries no arm64
  slice. No stage placed them before (B-015): the pre-xcodebuild validator
  would have reported `Missing linked archives` on the first run to get that
  far.
- **Wine server base archive.** `build/wineserver/build.sh` builds its own
  base `libwineserver.a` from the pinned submodule's `server/Makefile.in`
  (`build_base_from_source`), then swaps in the iOS-patched objects as before;
  a developer's pre-existing `app/Madeira/libwineserver.a` is still honoured.
  `tests/host/check-wineserver-base.py` runs the script end to end in a
  sandbox (stub `xcrun`/`ar`/`llvm-objcopy`) and pins the member set, the
  object swap, the rename sweep and both failure diagnostics.
- **Stage-only dispatch.** `only_stage` can name `fex-ios`, `wine-ntdll-unix`
  or `wineserver`. Each such run must have the pinned toolchain cache restored,
  fetches only its own submodules, and runs its own prerequisites: `wineserver`
  runs `build/wine-macos/configure.sh` first, because the stage's compiles
  include `wine/build-macos/include` (its `config.h` and the widl-generated
  public headers) — the iOS shims and the ntsync header it also includes are
  tracked in this repository, and it links no other stage's output. A
  stage-only run writes `IPA_PRESENT=0` and produces no IPA. The full path
  (`all`, including the `push` event, where the dispatch input is unset) runs
  bootstrap and everything after it; the workflow expresses that as one
  predicate, `(inputs.only_stage || 'all')`, and
  `tests/host/check-ipa-build-graph.py` pins it.
- **Verified picking of the Xcode.** The selection step fails by name when
  `Xcode_26.6.app` is absent (listing the installed Xcodes), and then checks
  that `xcodebuild -version` reports Xcode 26.6, that the iPhoneOS SDK path
  `xcrun` reports exists, and that the SDK's major version is at least the 17.0
  every stage compiles against. The two versions a log shows — Xcode 26.6
  (build 17F113) and SDK 26.5 — are one installation: the macOS 26 runner
  image maps `iphoneos26.5` to both Xcode 26.5 and 26.6.
- **Packaged artifact.** `tools/validate-ipa.sh` (called by
  `scripts/build-ipa.sh`, exercised by
  `tests/host/check-ipa-validation.py`) checks the archive's
  `Payload/<App>.app/Info.plist`, that `CFBundleExecutable` names a file that is
  in the bundle *and* in the archive, that `Payload` holds exactly one `.app`,
  that the executable has an arm64 slice, that no forbidden converter/Microsoft
  runtime file is inside, and that `SHA256SUMS` is the hash of that same IPA
  (`shasum -a 256 -c`).
- **What the run produced.** `scripts/build-ipa.sh` writes
  `artifacts/build-status.txt` (`IPA_PRESENT=1` with path, arch and hash, or
  `IPA_PRESENT=0` for a stage-only dispatch); the workflow prints it in a
  "Report build result" step and a "Report stage-only run" step says plainly
  that a stage-only dispatch produces no IPA.
- **Host regression checks.** A `host-checks` job runs the `tests/host` suite
  (a step per check). The checks that need the wine/DXMT/FEX submodules or a
  Swift toolchain are not in it; they are listed in the job's comment.

## Acceptance evidence still required

1. A clean workflow clone resolves selected build submodules without fetching
   FEX binary test corpora.
2. CI builds from pinned sources without user game/runtime files or proprietary
   Apple converter assets.
3. IPA archive contains `Payload/<App>.app/Info.plist` and executable; record
   SHA-256 and build duration. (The structural checks are in place; no run of
   the full path has produced an IPA yet.)
4. The workflow uploads artifacts only when the repository variable
   `WINEPHONE_BINARY_RELEASE_CLEARED` is exactly `true`, and only after
   `shasum -a 256 -c artifacts/SHA256SUMS` verifies the file being uploaded.
   Keep the variable unset until the Wine notice conflict and LGPL relink route
   have been reviewed and resolved. Only then upload the IPA or create a public
   release.
5. Device installation and JIT remain untested until user supplies device logs.

## Current runner source

- [GitHub Actions runner-images, macOS 26 image inventory](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md)
- [GitHub Actions runner-images, macOS 26 toolset manifest](https://github.com/actions/runner-images/blob/main/images/macos/toolsets/toolset-26.json)
- [GitHub Actions runner labels](https://github.com/actions/runner-images)
- GitHub documents a default 10 GB per-repository Actions cache limit; the
  workflow caches only pinned LLVM/llvm-mingw inputs and build trees. Check
  actual cache size and eviction after the first successful cold build.
  **VERIFY:** exact cache usage on the WinePhone repository after CI.

## Local source checks completed so far

- `tools/ios_audit.sh` scanned Wine, FEX, DXMT, and the app. Its raw local log
  SHA-256 is `7D0470D28A30A39E56A38C62EF4754EAE7C6BDC68D632B9BE023F309564C7932`.
- This is a grep-based source inventory, not proof that every hit is reachable
  or that the app builds. No Xcode, compiler build, IPA, or runtime test ran on
  the Windows host.
