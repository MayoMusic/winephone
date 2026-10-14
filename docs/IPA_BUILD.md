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
  26.6 installation explicitly. The official runner image manifest currently
  lists Xcode 26.6 and iOS SDK 26.4; log `xcodebuild -version` and
  `xcrun --sdk iphoneos --show-sdk-version` in every run. Xcode 27 is in
  public preview and is not the default. **VERIFY:** confirm the image still
  contains these versions when the workflow runs.
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

## Acceptance evidence still required

1. A clean workflow clone resolves selected build submodules without fetching
   FEX binary test corpora.
2. CI builds from pinned sources without user game/runtime files or proprietary
   Apple converter assets.
3. IPA archive contains `Payload/<App>.app/Info.plist` and executable; record
   SHA-256 and build duration.
4. The workflow uploads artifacts only when the repository variable
   `WINEPHONE_BINARY_RELEASE_CLEARED` is exactly `true`. Keep it unset until
   the Wine notice conflict and LGPL relink route have been reviewed and
   resolved. Only then upload the IPA or create a public release.
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
