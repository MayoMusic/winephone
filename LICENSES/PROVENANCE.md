# License provenance

This table records the base project snapshot. It is an engineering inventory,
not a legal opinion. Keep each upstream notice and license file with the
corresponding source. Do not infer that one component's license applies to
another.

| Component | Source / pinned revision | License evidence in base | WinePhone handling |
|---|---|---|---|
| Madeira application, scripts, and build files | `https://github.com/willfaust/Madeira`, `279fd0f83170425db002fe25d6bd62f6355f497d` | `LICENSE`, `CONTRIBUTING.md`, `LICENSE-EXCEPTION.md` | Existing base work retains its authorship/license. New WinePhone-authored changes use GPL-3.0-or-later. Do not claim Madeira's converter exception for new code. |
| Wine fork | `https://github.com/willfaust/wine`, `9129e9684daaeae70da9435e7c6060e59392634e` | `wine/LICENSE-MADEIRA.md` says this rebuilt Wine 11.4 branch retains LGPL-2.1-or-later; parent `THIRD-PARTY-NOTICES.md` says GPL-3.0-or-later | Preserve Wine's per-file terms; record the conflicting parent notice and obtain a complete clean-build/relink review before distributing a linked IPA. |
| FEX fork | `https://github.com/willfaust/FEX`, `f59cab95659e8add0c88f0c76ec1cf483c536dbf` | `FEX/LICENSE` is MIT; fork changes are separately described in parent notices and Madeira licensing docs | Keep upstream MIT and downstream modifications attributable separately; no AI-authored upstream contribution. |
| DXMT fork | `https://github.com/willfaust/dxmt`, `128b297c6e9a00014408dc68b4c2c2373b5813de` | `dxmt/LICENSE` is MIT; fork changes are separately described in parent notices and Madeira licensing docs | Keep upstream MIT and downstream modifications attributable separately; no AI-authored upstream contribution. |
| DXMT Direct3D 9 / DXSO frontend | Same DXMT fork; source imported from `https://github.com/dacevedo12/dxmt` (import provenance recorded in `THIRD-PARTY-NOTICES.md`) | LGPL-2.1-or-later per `THIRD-PARTY-NOTICES.md` and `dxmt/COPYING.LIB` | Keep LGPL notice and corresponding source; do not describe all DXMT code as MIT. |
| DirectX-Headers | `https://github.com/misyltoad/mingw-directx-headers`, `9df86f2341616ef1888ae59919feaa6d4fad693d` | Parent `THIRD-PARTY-NOTICES.md`; nested license file inspection pending | Preserve upstream license and attribution. |
| NVAPI headers | `https://github.com/NVIDIA/nvapi`, `d08488fcc82eef313b0464db37d2955709691e94` | `THIRD-PARTY-NOTICES.md`, `LICENSES/MIT-NVAPI.txt` | Headers only; no NVIDIA runtime binary is included by this source. |
| Madeira Dock | `https://github.com/willfaust/madeira-dock`, `72558e416a390f3669457930f09a389e54f49556` | `docs/LICENSING.md`; exact submodule commit pinned | GPL-3.0-or-later per Madeira's record; this build does not bundle dockhost. |
| rpmalloc | FEX `External/rpmalloc`, `812c2b9cf4310ffacf14e6b64066e78ab0c394b5` | `LICENSES/rpmalloc-0BSD.txt`; `docs/LICENSING.md` | Preserve upstream 0BSD notices and distinguish downstream modifications. |
| GnuTLS, Nettle, Hogweed, GMP | Tracked source archives under `build/gnutls-ios/src` | `THIRD-PARTY-NOTICES.md`, archive checksums | LGPL selections documented by Madeira; validate static-link notices and relink route. |
| FFmpeg | Tracked source archive under `build/ffmpeg/src` | `THIRD-PARTY-NOTICES.md`, `docs/BUILDING.md` | LGPL-only configuration is documented; verify exact build flags and corresponding source. |
| Apple Metal Shader Converter / Madeira D3D12 research path | Base `build/madeira-d3d12/`; base commit `279fd0f83170425db002fe25d6bd62f6355f497d` | Apple agreement and Madeira exception materials | Converter dylib and Madeira D3D12 PE modules/test binaries are deleted from the WinePhone tree and excluded from the build. Wine's own D3D12 builtin stub may remain; no D3D12 game support is claimed. Never use or redistribute Apple D3DMetal/GPTK. |
| Wine builtin C/C++ runtime modules | Wine fork `9129e9684daaeae70da9435e7c6060e59392634e`; ARM64 and ARM64EC DLL farms | Each reviewed farm DLL contains Wine's `Wine builtin DLL` marker; Microsoft x86_64 runtime folder is absent | These are Wine implementations with familiar DLL names, not Microsoft's VC++ redistributables. Keep the binary marker verification in the IPA build gate. |
| Microsoft Visual C++ runtime DLLs | User-supplied only, per `tools/fetch-vcruntime.md` | Microsoft redistributable terms (not the project license) | Never commit, bundle, upload, or redistribute these DLLs. |

## Release gate

Before a public binary release, enumerate every bundled file, its origin,
license, notices, and source availability; validate LGPL static-link/relink
requirements against a clean rebuild. The base project's own `docs/LICENSING.md`
marks clean-machine relinking and legal review as open.
