# Winlator reference study (partial, no code reused)

Status: source-level design reference only. This was not built or run here.
The reference tree is outside the WinePhone repository under
`J:\tmp\WinePhoneReferences`.

## Revisions and license

- Original app repository `brunodev85/winlator`: `b6b2259158cf38d06067c34430d840d56b46d220`.
- Its `.gitmodules` pins the Android app submodule at `a030f552f452158a2db64fdb32b490fa19c0b48d`.
- The pinned app commit was not available through the partial fetch. For code reading, the public app main revision `3981d86efa4f333b2a34a7da8b6521476cd8c8b9` was fetched sparsely instead. It is not the parent's pinned submodule revision; re-check at the pinned commit before drawing version-specific conclusions.
- The original project and app identify LGPL-2.1. No code was copied.

## Verified design observations

- The parent repo declares `app`, `vortek`, and `gladio` as separate submodules (`.gitmodules` at the parent revision). Its README describes Winlator as an Android app running x86/x86-64 Windows apps with Wine and Box86/Box64.
- In the app source, `Container` stores a Wine version, Box64 preset, and container configuration. `ContainerDetailFragment` edits and persists per-container settings. `ContainerManager` enumerates executables as shortcuts.
- `XServerDisplayActivity.java` sets `WINEPREFIX` to the container's `drive_c` prefix and builds a Wine desktop launch command. When a shortcut is selected, it resolves shortcut-specific Box64 preset values before launching the guest program. This is the source-level launch sequence verified in this partial study: app activity -> container/prefix -> environment and selected shortcut -> Wine launcher -> Box64 preset -> X server display.
- `Box64PresetManager.java` defines Stability, Conservative, Intermediate, and Performance presets. For example, Stability sets `SAFEFLAGS=2`, `FASTNAN=0`, `FASTROUND=0`, `BIGBLOCK=0`, `STRONGMEM=2`, `CALLRET=0`; Performance uses `SAFEFLAGS=1`, `FASTNAN=1`, `FASTROUND=1`, `BIGBLOCK=3`, `STRONGMEM=0`, `CALLRET=1`. These are Box64 values and have no direct FEX equivalence without measurement.
- Native `gpu_image.c` allocates Android `AHardwareBuffer` images; this is an Android-only presentation/resource path. WinePhone's equivalent stays UIKit/CAMetalLayer and Metal.
- The public README's tips recommend per-shortcut overrides and Box64 presets. The source confirms the profile concept; it does not make Android compatibility or performance transferable to iOS.

## WinePhone mappings

| Winlator idea | WinePhone mapping |
|---|---|
| Container plus executable shortcut | Declarative per-game Wine prefix/profile (NEW; schema is `compat/catalog.json` seed) |
| Per-container and per-shortcut Box64 preset | Per-game FEX profile, only for options the pinned FEX fork actually exposes; no direct Box64 variable mapping assumed |
| X server and Android buffer sharing | No port; UIKit/CAMetalLayer path already exists in Madeira |
| Downloadable GPU drivers/Vulkan stack | No port; iOS uses Apple's Metal driver and DXMT/MoltenVK choices |
| Audio latency controls | Design reference only; WinePhone uses CoreAudio and needs measured buffer controls |

## Not verified yet

The preset asset files and full UI launch path at the parent's pinned app
submodule commit are not read. No Winlator fork was selected after the named
`coffincolors/Winlator-Cmod` URL returned repository-not-found. Vortek runtime
forwarding, package contents, component download flow, and exact GPU driver
loading are not described here. The original Android architecture's Linux
userland, process model, and executable-memory assumptions do not port to iOS.
