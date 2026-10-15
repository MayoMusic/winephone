# Source pins and acquisition record

Date checked: 2026-10-14 (workspace local date). Primary source is the
repository itself; URLs below were checked with `git ls-remote`.

| Item | URL | Revision | Acquisition/status |
|---|---|---|---|
| Madeira base | `https://github.com/willfaust/Madeira.git` | `279fd0f83170425db002fe25d6bd62f6355f497d` | Main checkout complete. |
| FEX iOS fork | `https://github.com/willfaust/FEX.git` | `f59cab95659e8add0c88f0c76ec1cf483c536dbf` | Pinned top-level submodule; branch `ios-port-2607` head matched via `git ls-remote`. Binary test-corpus submodules intentionally not fetched. |
| DXMT iOS fork | `https://github.com/willfaust/dxmt.git` | `128b297c6e9a00014408dc68b4c2c2373b5813de` | Pinned top-level submodule; branch `ios-port` head matched via `git ls-remote`. |
| Wine LGPL fork | `https://github.com/willfaust/wine.git` | `9129e9684daaeae70da9435e7c6060e59392634e` | Pinned submodule; branch `madeira-lgpl` head matched via `git ls-remote`; fetched shallow, then detached checkout verified exact SHA. |
| Madeira Dock | `https://github.com/willfaust/madeira-dock.git` | `72558e416a390f3669457930f09a389e54f49556` | Pinned top-level submodule; branch `main` head matched via `git ls-remote`. |

Build-required nested source pins checked against the parent gitlinks:

| Parent/path | Repository | Pinned revision |
|---|---|---|
| FEX `External/fmt` | `https://github.com/fmtlib/fmt.git` | `407c905e45ad75fc29bf0f9bb7c5c2fd3475976f` |
| FEX `External/range-v3` | `https://github.com/ericniebler/range-v3.git` | `ca1388fb9da8e69314dda222dc7b139ca84e092f` |
| FEX `External/rpmalloc` | `https://github.com/willfaust/rpmalloc.git` | `812c2b9cf4310ffacf14e6b64066e78ab0c394b5` |
| FEX `External/unordered_dense` | `https://github.com/martinus/unordered_dense.git` | `3234af2c03549bc85656bfd3a86993bf1cd8aef1` |
| FEX `External/xxhash` | `https://github.com/Cyan4973/xxHash.git` | `e626a72bc2321cd320e953a0ccf1584cad60f363` |
| FEX `Source/Common/cpp-optparse` | `https://github.com/Sonicadvance1/cpp-optparse` | `9f94388a339fcbb0bc95c17768eb786c85988f6e` |
| DXMT `external/nvapi` | `https://github.com/NVIDIA/nvapi.git` | `d08488fcc82eef313b0464db37d2955709691e94` |
| DXMT `include/native/directx` | `https://github.com/misyltoad/mingw-directx-headers` | `9df86f2341616ef1888ae59919feaa6d4fad693d` |
| FEX `External/vixl` | `https://github.com/FEX-Emu/vixl.git` | `5f418449c48f6ca3ad37c47ec632f17a561c0580` |
| FEX `External/jemalloc_glibc` | `https://github.com/FEX-Emu/jemalloc.git` | `8436195ad5e1bc347d9b39743af3d29abee59f06` |

Build toolchain pins:

| Item | Source | Pin/checksum |
|---|---|---|
| llvm-mingw macOS universal | `https://github.com/mstorsjo/llvm-mingw/releases/tag/20260421` | SHA-256 `bd85a3975723815cef28dbbd2ca2cb0c926f6b348a12a0453f39f7af273cb3f7` |
| LLVM source | `https://github.com/llvm/llvm-project` | `8dfdcc7b7bf66834a761bd8de445840ef68e4d1a` |

Design-only references (never used as WinePhone build dependencies):

| Item | URL | Revision/evidence | Use and limits |
|---|---|---|---|
| Winlator parent | `https://github.com/brunodev85/winlator` | `b6b2259158cf38d06067c34430d840d56b46d220` | LGPL-2.1; app is a submodule; see `docs/WINLATOR_STUDY.md`. |
| Winlator app reference | `https://github.com/brunodev85/winlator-app` | Parent gitlink `a030f552f452158a2db64fdb32b490fa19c0b48d`; fallback current-main study `3981d86efa4f333b2a34a7da8b6521476cd8c8b9` | Fallback is not the parent's pinned revision; design study only. |
| PPSSPP | `https://github.com/hrydgard/ppsspp` | `0b557116c29a07f608552c578a209db7bc57a27c` | GPL-2.0 in `LICENSE.TXT`; source study only, no code copied. |
| GameHub public site | `https://gamehub.xiaoji.com/en` | No revision; fetch timed out during this study | Closed-source public behavior only; facts remain unverified in `docs/GAMEHUB_STUDY.md`. |
| FEX upstream contribution policy | `https://github.com/FEX-Emu/FEX` | `5285020de0b30dbdae7b44d0d83541af2d13d002`, `CONTRIBUTING.md` | Prohibits AI/ML/LLM-generated code contributions. |
| DXMT upstream contribution policy | `https://github.com/3Shain/dxmt` | `186a2327f1ec76376f6bc1ef64636f08b0728567`, `CONTRIBUTING.md` | Prohibits AI/LLM changes. |

The initial `git clone --recurse-submodules` was interrupted after the full
Wine history transfer exceeded the time box. A depth-1 fetch of its pinned
branch resolved to the exact gitlink SHA. The first submodule pass left three
empty worktrees; a forced checkout repaired them. Current worktree status must
be rechecked before committing. Nested FEX source submodules required for the
build are being selected separately; its binary test-corpus submodules remain
unfetched.

The selected build submodules are pinned gitlinks, not floating branch refs.
The binary test-corpus FEX submodules are intentionally not part of the build.
One recursive fetch in the first interrupted clone briefly downloaded part of
those test-corpus objects; no corpus binary was executed or added to the
WinePhone working tree, and those submodule worktrees remain deinitialized.
The FEX `External/vixl` worktree is currently empty locally because a stale
Git lock blocked its fetch; the clean-run workflow fetches the exact gitlink.
The bootstrap uses the llvm-mingw checksum and LLVM full commit listed above.

No game files, Microsoft runtime DLLs, or Apple SDKs are part of the source
checkout. The tracked Apple Metal Shader Converter dylib and D3D12 PE/test
binaries were removed from the WinePhone release tree; the macOS Metal shader
compiler remains an Xcode tool used by DXMT. No D3DMetal/GPTK assets are used.
Winlator and PPSSPP sparse study checkouts live under the temporary directory,
not in this repository; no binaries or source from them are redistributed.

## Recursive-clone verification (2026-10-16)

A full `git submodule update --init --recursive` was run to completion in a
scratch clone outside the tracked tree, and **every gitlink resolved to its
exact pinned commit** — 25 submodules, 1012.4 s wall clock. This retires the
open parts of B-003: `FEX/External/vixl` checked out cleanly at
`5f418449c48f6ca3ad37c47ec632f17a561c0580` with no stale lock, and the
previously unfetched binary test-corpus submodules do resolve.

| Submodule | Pinned commit | Ref it resolved to |
|---|---|---|
| Madeira (root) | `279fd0f83170425db002fe25d6bd62f6355f497d` | `main` |
| `wine` | `9129e9684daaeae70da9435e7c6060e59392634e` | `remotes/origin/madeira-lgpl` |
| `FEX` | `f59cab95659e8add0c88f0c76ec1cf483c536dbf` | `heads/ios-port-2607` |
| `dxmt` | `128b297c6e9a00014408dc68b4c2c2373b5813de` | `v0.73-185-g128b297` |
| `madeira-dock` | `72558e416a390f3669457930f09a389e54f49556` | `heads/main` |

All four are Madeira's own forks under `github.com/willfaust`, matching
`.gitmodules` at `279fd0f`. The pins were confirmed reachable in those public
forks through the GitHub API before cloning, which contradicts the note in
Madeira's `docs/BUILDING.md:10-14` (written at commit `8a8cabe`, 2026-09-16)
saying the submodule commits "exist only locally" and that a recursive clone
fails at the first submodule. That statement was true when written and is now
out of date; the forks were pushed on 2026-10-14.

`FEX/External/rpmalloc` resolves to `willfaust/rpmalloc` at
`812c2b9cf4310ffacf14e6b64066e78ab0c394b5`, confirming the fork relationship
recorded in Madeira's licensing table (upstream 0BSD, Madeira's changes
GPL-3.0-or-later with the converter exception).

The scratch clone is `upstream/`, which is git-ignored and exists only for
cross-checking; nothing in it is committed or redistributed.
