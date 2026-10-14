# WinePhone

WinePhone is an experimental iOS runtime project based on the iOS adaptations
in [Madeira](https://github.com/willfaust/Madeira). It combines Wine for
Windows APIs, FEX for x86-64-to-ARM64 translation, and DXMT for Direct3D-to-
Metal translation. Those components are reused from pinned source revisions;
WinePhone does not implement them from scratch.

**Status:** source study and build automation are in progress. No WinePhone IPA
has been built by this repository, and no iPhone 17/iOS 27 run or performance
measurement has been recorded. An iOS 27 device, signing, JIT availability,
memory headroom, game compatibility, and sustained performance all need direct
verification. This project does not claim that AAA games currently work here.

## Architecture

```text
Windows x86-64 game + Direct3D
  -> Wine Win32/NT compatibility layer
  -> FEX CPU translation -> ARM64
  -> DXMT graphics translation -> Metal
  -> iOS app process, UIKit, GameController, CoreAudio
```

Track A is a sideloaded build using the debugger-assisted JIT path present in
the pinned Madeira source. The separate no-JIT target is not implemented, so
this workflow is not an App Store-style build. D3D12 is not supported by this
release configuration. DRM, anti-cheat, and protected games are out of scope;
users provide their own legal game files.

Architecture source references: Madeira `README.md` and `docs/BUILDING.md` at
`279fd0f83170425db002fe25d6bd62f6355f497d`; FEX `FEX/Source/Windows/ARM64EC/Module.cpp`
at `f59cab95659e8add0c88f0c76ec1cf483c536dbf`; DXMT
`dxmt/src/winemetal/unix/winemetal_unix.c` at
`128b297c6e9a00014408dc68b4c2b2373b5813de`.

## Build

The iOS app requires a macOS host with Xcode. The repository workflow targets
GitHub Actions `macos-26`, selects Xcode 26.6, builds from pinned sources, and
produces an **unsigned** IPA. The first cold build may take a long time because
it builds LLVM for iOS. See [IPA build notes](docs/IPA_BUILD.md) and
[build automation](scripts/build-ipa.sh).

Run `bash scripts/bootstrap.sh` and `bash scripts/build-ipa.sh` on macOS. Never
put games or Microsoft Visual C++ runtime DLLs in this repository. The build
validator rejects non-Wine runtime DLLs in the app farm. Apple SDKs/Xcode are
provided by the runner and are not redistributed.

## Licensing

WinePhone-authored changes use GPL-3.0-or-later. In plain terms, when you
distribute a modified combined program, recipients must be able to get the
corresponding source and keep the same freedoms. It does not change the licenses
of Wine, FEX, DXMT, LLVM, or other included components; each keeps its own
license and notices. GPL is not a blanket permission to include proprietary
files.

See [license provenance](LICENSES/PROVENANCE.md) and
[the license decision](docs/LICENSE_POLICY.md). A public binary release stays
blocked until the conflicting Wine license notices and LGPL relinking route
have been reconciled with evidence. The Apple Metal Shader Converter binary
and Madeira's D3D12 runtime are excluded. Apple D3DMetal/GPTK is never used.
GitHub Actions keeps IPA uploads disabled until the repository variable
`WINEPHONE_BINARY_RELEASE_CLEARED` is explicitly set after that review.

## Project records

- [Plan and progress](PLAN.md) · [decisions](DECISIONS.md) · [blockers](BLOCKERS.md)
- [Source pins](docs/SOURCES.md) · [study](docs/STUDY.md) · [modification catalog](docs/MODIFICATION_CATALOG.md)
- [Compatibility data](compat/catalog.json) · [installation notes](docs/INSTALL.md)
- [Third-party notices](THIRD-PARTY-NOTICES.md)
