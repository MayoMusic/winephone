# Wine configure's "not found" messages and what actually provides that on iOS

`build/wine-macos/configure.sh` runs Wine's configure on the **macOS runner** to
produce `wine/build-macos`, and the log is full of probes that fail: EGL,
Wayland, inotify, PulseAudio, ALSA, GStreamer, Vulkan/MoltenVK, X11 and the
optional desktop libraries. They are evidence about the *host* Wine was
configured for, not about the iOS build:

- `wine/build-macos` is configured with `--enable-archs=aarch64 --without-x
  --disable-tests` and is used as a **header and import-library source**: every
  unix-side stage compiles against its `include/` (`-include
  .../include/config.h`, the widl-generated `dwrite_3.h`/`d2d1.h`/`mfobjects.h`),
  and DXMT's PE build reads its `tools/winebuild/winebuild` and
  `aarch64-windows` import libraries. No object from that tree is linked into
  the app and no Wine binary from it runs on the device.
- The iOS unix libraries are compiled from Wine's *source* tree by
  `build/ntdll-unix/build.sh` and `build/win32u-unix/build.sh`, with the
  desktop back-ends replaced or compiled out on purpose (below).
- A probe that fails therefore means "this feature is not provided by the host
  Wine build", which is the intended state: `build/win32u-unix/config_ios.h`
  and the per-translation-unit defines in the build scripts are where the iOS
  answer is made explicit.

## Where each capability actually is on iOS

| Configure probe | iOS implementation in this tree | Evidence |
|---|---|---|
| FreeType (`ft2build.h`, `SONAME_LIBFREETYPE`) | Static `libfreetype.a` for arm64-iOS, merged into `libwin32u_unix.a`; `dwrite`'s unix side compiles the same library in. `config_ios.h` `#undef`s `HAVE_FT2BUILD_H`/`SONAME_LIBFREETYPE` for every other TU and the two font TUs re-define them and rewrite `dlopen`/`dlsym` onto a direct symbol table. | `build/freetype-ios/build.sh`, `build/win32u-unix/freetype_ios.c`, `build/ntdll-unix/dwrite_freetype_ios.c` |
| fontconfig | Not used: disabled for the whole stage (`-USONAME_LIBFONTCONFIG`), `load_mac_fonts`'s CoreText sweep is stubbed out (`CTFontCollectionCreateFromAvailableFonts` renamed), and fonts come from the prefix's `windows/fonts`. | `build/win32u-unix/build.sh`, `build/win32u-unix/freetype_ios.c` |
| GnuTLS (`gnutls.h`, `pkcs12.h`) | Static GnuTLS/nettle/GMP prefix, with a generated symbol table so the static archive can be resolved through the `dlopen`/`dlsym` call sites Wine's `bcrypt`, `secur32`/`schannel` and `crypt32` unix sides use. | `build/gnutls-ios/build.sh`, `build/crypto-unix/gen_gnutls_symtab.sh`, `build/crypto-unix/ios_gnutls_shim.h` |
| GStreamer / FFmpeg | GStreamer does not exist on iOS: `build/ffmpeg/build.sh` builds an LGPL-only FFmpeg prefix (WMA-family decoders, mp3/wav/mov demuxers) that `winegstreamer_unixlib_ios.c` uses for the `wg_transform`/`wg_parser` subset `wma_decoder.c` needs. H.264/HEVC and AAC are decoded by Apple's VideoToolbox/AudioToolbox instead of FFmpeg. | `build/ffmpeg/build.sh`, `build/ntdll-unix/winegstreamer_unixlib_ios.c`, `build/ntdll-unix/wg_parser_apple_ios.c` |
| ALSA / PulseAudio | Neither exists on iOS. The driver unix table is `build/ntdll-unix/audio_null_ios.c`: one render endpoint with WASAPI render semantics over a lock-free ring, played by a **Core Audio RemoteIO AudioUnit** (real audio output), with `IAudioClock` advancing at real time from `mach_absolute_time`. If the AudioUnit cannot be set up it degrades to the wall-clock null behaviour so game timing never breaks. `build/wineios-drv/wineios.c` is only the PE-side `DllMain` shim mmdevapi loads. | header comment and `AudioUnitSetProperty` use in `build/ntdll-unix/audio_null_ios.c` |
| inotify | Not available. `build/madsync` is a userspace ntsync driver that `ntdll` and `wineserver` compile against (`-DHAVE_LINUX_NTSYNC_H=1`); `wineserver` additionally replaces `inproc_sync`, `sock`, `thread`, `mach` and friends with iOS implementations. | `build/ntdll-unix/build.sh`, `build/wineserver/build.sh`, `build/madsync/` |
| Vulkan / MoltenVK, EGL, X11, Wayland | Not used. Graphics go to Metal through DXMT (`winemetal`) and the app's own bridged runtime; EGL/Vulkan references are compiled out (`-USONAME_LIBEGL`, `-USONAME_LIBVULKAN`) and Wine is configured `--without-x`. | `build/win32u-unix/build.sh`, `build/dxmt-ios/build.sh`, `build/madeira-d3d12/` |

## What is *not* claimed

- No probe, build or run of any of the above has been executed on a device from
  this workspace: there is no macOS host and no iPhone here. The table records
  which implementation a capability is expected to come from, with its source
  file, so a device run can be attributed.
- A capability whose replacement is a null/stub implementation is named as such
  (`audio_null_ios.c`'s Tier-1 fallback, `cdrom_stub.c`, `build/wineios-drv`).
  Those are deliberate, documented fallbacks for behaviour iOS cannot provide
  (an optical drive, a desktop audio server), not silent successes.
