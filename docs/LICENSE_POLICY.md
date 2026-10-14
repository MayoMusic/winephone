# WinePhone license choice

WinePhone-authored changes use **GPL-3.0-or-later**, matching the main
Madeira tree's `COPYING` file. In everyday terms: if the project is shared as
a modified program, recipients must be able to obtain its corresponding
source and have the same rights to modify and share it. The license does not
erase another component's license or grant rights to proprietary assets.

The GPL choice is not a claim that every file in the tree is GPL. Wine's pinned
branch has `wine/LICENSE-MADEIRA.md`, which says the branch retains
LGPL-2.1-or-later, while the parent `THIRD-PARTY-NOTICES.md` labels Wine
GPL-3.0-or-later. We preserve the per-component notice and treat the mismatch
as an unresolved release gate. LGPL libraries are statically linked in the
planned app; the required clean rebuild/relink route is also not yet proven.

The Madeira exception is limited to qualifying Madeira-authored works and is
specific to the Apple Metal Shader Converter. WinePhone does not rely on that
exception: the converter dylib and Madeira D3D12 runtime are removed from the
release tree. We do not use or redistribute Apple D3DMetal/GPTK. Third-party
licenses and exact revisions are listed in `LICENSES/PROVENANCE.md`.

**VERIFY before a binary distribution:** run a clean, recipient-accessible
rebuild/relink; inspect all packaged files and notices; obtain a qualified
license review for the conflicting Wine notices and static LGPL combination.
