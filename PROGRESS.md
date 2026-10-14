# WinePhone progress

## 2026-10-14 (workspace local date)

### FP0 environment

- Workspace: `J:\GameMode`; initially empty and not a Git repository.
- Host: Windows 10 Pro, OS build `10.0.26200`, x64, about 17.0 GB RAM.
- J: drive: NTFS, about 91.9 GB free at inspection.
- Available: Git `2.55.0.windows.5`, GitHub CLI `2.102.0`, Python `3.10.11`, Clang `21.1.6`, 7-Zip, tar.
- Missing: Xcode, `xcodebuild`, CMake, Ninja, Meson.
- `gh auth status`: not logged into any GitHub host.
- Network: `git ls-remote https://github.com/willfaust/Madeira.git HEAD` succeeded and returned `279fd0f83170425db002fe25d6bd62f6355f497d`.
- Existing sibling checkout `J:\games\wine-ios` has user modifications; left untouched.
- Madeira base (`279fd0f83170425db002fe25d6bd62f6355f497d`), FEX (`f59cab95659e8add0c88f0c76ec1cf483c536dbf`), DXMT (`128b297c6e9a00014408dc68b4c2c2373b5813de`), madeira-dock (`72558e416a390f3669457930f09a389e54f49556`), and Wine (`9129e9684daaeae70da9435e7c6060e59392634e`) match their gitlinks. Wine is a depth-1 exact commit. Required source dependencies are mapped in `docs/SOURCES.md`; FEX test-corpus submodules remain deinitialized. One partial corpus fetch occurred during the interrupted recursive clone; no binary was executed or added to the WinePhone working tree.
- Measured FP0 wall time: approximately 2 minutes to initial source fetch and host inventory; exact stage timing was not instrumented. Source fetch and repair elapsed about 12 minutes, including the abandoned full Wine history fetch; no clean-room timer was running.

### Initial source findings (not build evidence)

- Madeira README identifies Wine 11.4, FEX, DXMT and a single-process wineserver arrangement, and states upstream FEX/Wine/DXMT checkouts do not build for iOS.
- `docs/BUILDING.md` says a clean checkout lacks llvm-mingw and built LLVM/iOS toolchains; the project also referenced an absent Microsoft VC++ runtime folder. WinePhone removes that resource from the Xcode bundle so those DLLs remain user-supplied and undistributed.
- That document identifies a Metal Shader Converter installer and tracked library for the D3D12 research path. WinePhone will omit that path pending licensing review.
- The app build requires Xcode/iOS SDK and cannot run on this Windows host.
- Added pinned macOS bootstrap and unsigned IPA workflow scripts. Static checks passed; no CI run, IPA build, simulator/device run, FPS measurement, or game compatibility test has occurred.
- Persisted the requested user environment settings with Windows `setx` and created the target directories: `CODEX_HOME=J:\codex-home`, `TEMP/TMP=J:\tmp`, `npm_config_cache=J:\npm-cache`, and `PIP_CACHE_DIR=J:\pip-cache`.

### FP1/FP2 source and build preparation

- Submodule pins match the Madeira gitlinks. Build-required FEX/DXMT dependencies are recorded in `docs/SOURCES.md`; binary test-corpus submodules remain uninitialized. The local VIXL submodule worktree is empty due a stale Git lock; clean workflow fetch is unverified.
- Ran `tools/ios_audit.sh`; raw log SHA-256: `7D0470D28A30A39E56A38C62EF4754EAE7C6BDC68D632B9BE023F309564C7932`. Findings and limits are in `docs/STUDY.md`.
- Updated the DXMT build script to create `libdxmt_combined.a` on a clean build. Removed Xcode resource references to the absent user-supplied VC++ runtime folder and to the proprietary converter/custom D3D12 payload. D3D12 support is not claimed.
- Added `scripts/bootstrap.sh`, `scripts/build-ipa.sh`, `.github/workflows/build-ipa.yml`, and a closed release-input validator. Static validation passed: Bash syntax parse, Python bytecode compile, Wine builtin marker scan (29 runtime-named DLLs), JSON parse, text patch reverse-apply check, and `git diff --cached --check` (only Windows LF/CRLF warnings).
- `python tools/validate_release_inputs.py .` correctly reports missing generated archives on this unbuilt Windows host; `--skip-archives` passes the release exclusion/provenance checks. This is expected and is not a build test.
- Winlator app source was inspected at public commit `3981d86efa4f333b2a34a7da8b6521476cd8c8b9` as fallback because parent-pinned app commit `a030f552f452158a2db64fdb32b490fa19c0b48d` could not be checked out. PPSSPP source at `0b557116c29a07f608552c578a209db7bc57a27c` confirms an IR interpreter path. GameHub website timed out; claims remain unverified. No code copied.
- No Mac build, workflow run, IPA SHA-256, device install, or game test. Build-stage durations cannot be measured until CI runs. Approximate prior fetch timings are recorded above and are not precision measurements.

### GitHub publication and license review

- User confirmed `gh auth login`; `gh auth status` reports active account `MayoMusic` with repo/workflow scopes. Created public repository `https://github.com/MayoMusic/winephone`.
- Reviewed root `THIRD-PARTY-NOTICES.md`, `docs/LICENSING.md`, `wine/LICENSE-MADEIRA.md` (as recorded by the provenance audit), and the LGPL dependency inventory. The project itself records unresolved conflict and clean recipient relink/re-sign/install test. Binary release is therefore **not cleared**; no `WINEPHONE_BINARY_RELEASE_CLEARED` variable will be set. Workflow artifact upload remains gated.
- No code or IPA has yet been pushed or built in CI at this point.
