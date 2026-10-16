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
- **Status: retired.** A full `git submodule update --init --recursive` completed in a scratch clone outside the tracked tree on 2026-10-16: all 25 submodules resolved to their exact pinned commits in 1012.4 s, including `FEX/External/vixl` at `5f418449c48f6ca3ad37c47ec632f17a561c0580` with no stale lock, and the previously unfetched binary test-corpus submodules did resolve. See `docs/SOURCES.md`, "Recursive-clone verification". The clean-run workflow therefore has no submodule blocker left; only the corpus binaries remain intentionally unbuilt, which they were always meant to be.

## B-004: Device-side behavior not verified

- **Evidence:** No IPA exists and no device logs were provided. JIT behavior on iOS 27, signing entitlements, jetsam limits, and runtime compatibility remain untested.
- **Impact:** No performance or compatibility claim can be made.
- **Next path:** Build IPA in CI, then user installs/enables JIT and shares logs. User will provide a game name before title-specific analysis.
- **Status:** Active.

## B-006: FEX iOS configure assumes Linux host probes

- **Evidence:** GitHub Actions run `38637082925` completed bootstrap/cache and failed FEX configure after `NeedDisabledSVE.py` attempted `/proc/cpuinfo`; its `aarch64_fit_native.py` import failure left the CPU string empty for CMake `string(STRIP ...)`. The five `HAS_SYSCALL_*` messages are optional compile probes, not by themselves fatal. Exact FEX source pin: `f59cab95659e8add0c88f0c76ec1cf483c536dbf`.
- **Impact:** No Darwin configure, FEXCore compile, IPA link/package, or device test is proven.
- **Next path:** Keep generic `TUNE_CPU=none`; `patches/fex-darwin.patch` is **deleted** and `build/fex-ios/build.sh` no longer defines `FEX_IOS_HOST`/`FEX_IOS_HOST_BUILD`, which are the Windows-PE-module (`fex-wow64`/`fex-arm64ec`) flags, not native `fex-ios` ones (`docs/MADEIRA_RECIPE.md` correction; `FEX/FEXCore/Source/Utils/ArchHelpers/Arm64.cpp:719`). Confirm configure+compile once in the macOS `only_stage=fex-ios` dispatch, then address the first remaining compile error.
- **Status:** The `fex-ios` stage now **passes** (run `38644632372` reached and completed it). `FEX_IOS_HOST`/`FEX_IOS_HOST_BUILD` are the Windows-PE-module flags, but the recipe-alignment change was reverted because the stage works as-is and FEX must not be touched; `TUNE_CPU=none` stays. The failure moved downstream to B-008.

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

## B-008: `wine/build-macos` is never configured, so every unix-side compile fails

- **Evidence:** run `38644632372`, stage `wine-ntdll-unix`: `wg_parser_apple_ios... OK` and ~37 other translation units `FAILED` in 0.2-0.4 s each with no compiler text in the log. `build/ntdll-unix/build.sh:27,65` pass `-include "$WINE_BUILD/include/config.h"` with `WINE_BUILD=wine/build-macos` (`:7`); `wg_parser_apple_ios` (`:153-163`) is the only compile that passes no Wine include, and it is the only one that succeeded. `build/ntdll-unix/build.sh` is byte-identical to Madeira's at `279fd0f`. No script in the repository configures `wine/build-macos`; its consumers are `build/ntdll-unix/build.sh`, `build/win32u-unix/build.sh:14`, `build/wineserver/build.sh:28`, `build/d3d11-triangle/build.sh:50`, `tests/dxmt/build.sh:21`, `scripts/build-ipa.sh:84`, and the out-of-band status is documented in `build/dxmt-ios/README.md:47-49` and `tests/host/check-wma-decoder.py:25-27`.
- **Impact:** The whole `wine-ntdll-unix`, `wineserver` and `win32u-unix` chain, DXMT's PE build, and therefore the app link and IPA cannot proceed.
- **Next path:** New `build/wine-macos/configure.sh` (stage `wine-macos` in `scripts/build-ipa.sh`, also reachable with `only_stage=wine-ntdll-unix`) configures the tree with `--enable-archs=aarch64 --without-x --disable-tests`. `build/ntdll-unix/build.sh` now prints each failing compile's exact command line and first 40 lines of stderr, so one run shows the real errors. Whether the tree must additionally be **built** (`make tools/winebuild` + `aarch64-windows` import libs) for DXMT is a further step.
- **Status:** **The configure half is verified.** Run `38651245572` (`only_stage=wine-ntdll-unix`, commit `62f3269`) reported `31 OK / 6 FAILED` and **none** of the six failures was `config.h`: every other translation unit found `-include wine/build-macos/include/config.h`. The six failures were four missing *other* prerequisites and one SDK field, now B-009 and B-010.

## B-009: the stage-only path built none of the header prefixes the stage consumes

- **Evidence:** run `38651245572` (`only_stage=wine-ntdll-unix`): `bcrypt_unixlib` and `secur32_unixlib` failed on `gnutls/gnutls.h` (`wine/dlls/bcrypt/gnutls.c:34`, `wine/dlls/secur32/schannel_gnutls.c:36`), `crypt32_unixlib` on `gnutls/pkcs12.h` (`build/crypto-unix/crypt32_unixlib_ios.c:40`), `winegstreamer_unixlib` on `libavcodec/avcodec.h` (`build/ntdll-unix/winegstreamer_unixlib_ios.c:251`), `dwrite_unixlib` on `ft2build.h` (`wine/dlls/dwrite/freetype.c:31`). `build/ntdll-unix/build.sh` reads those prefixes from `$REPO_ROOT`-relative paths (`:20-24`) that are **identical in both paths** â€” `toolchains/gnutls-ios`, `toolchains/ffmpeg-ios`, `research/freetype` â€” but the stage-only path ran none of their producers. `scripts/bootstrap.sh` builds only LLVM/toolchains (`:19-43`, `:66-83`): it never builds GnuTLS, FFmpeg or FreeType, and `research/freetype` is git-ignored (`.gitignore:113`). Madeira's `docs/BUILDING.md` at `279fd0f` has GnuTLS and FFmpeg as its first two steps (`:33-35`, `:38-42`) but its "Inputs that are not in the repository" table (`:17-25`) has no FreeType and no Wine build tree, and `build/freetype-ios/build.sh` at HEAD refused to run without a pre-cloned `research/freetype` (`:18`).
- **Impact:** Four of six failures in the stage; the whole crypto/network, media and text (dwrite) side of `libntdll_unix.a`.
- **Next path:** `scripts/build-ipa.sh:68-69` now runs the `gnutls` and `ffmpeg` stages before `wine-macos`/`wine-ntdll-unix` in the `only_stage=wine-ntdll-unix` path; FreeType is a separate pinned build with its own cache key (`.github/workflows/build-ipa.yml:88-113`, `winephone-freetype-2.13.3-42608f77â€¦`) whose script clones tag `VER-2-13-3` and verifies the annotated tag's **commit** (`42608f77f20749dd6ddc9e0536788eaad70ea4b5`). The toolchain cache key is untouched, so LLVM is not rebuilt.
- **Status:** Fixed, **UNVERIFIED** until the next stage-limited run.

## B-010: two unixlibs need widl-generated headers, which only a *built* Wine tree has

- **Evidence:** `wine/dlls/dwrite/dwrite_private.h:24-25` includes `dwrite_3.h` and `d2d1.h` (`wine/dlls/dwrite/freetype.c:44` includes `dwrite_private.h`), and `wine/dlls/winegstreamer/unixlib.h:32` includes `mfobjects.h`; none of those four headers exists anywhere in the checkout (`find wine -name dwrite_3.h -o -name d2d1.h -o -name mfobjects.h -o -name mftransform.h` is empty â€” only the `.idl` inputs are tracked). They are widl output and widl is itself a build product, so configure alone cannot create them: `wine/aclocal.m4:293` `wine_fn_config_makefile()` and `wine/configure:24365` `wine_fn_output_makedep()` only *write* the rules (makedep is compiled and run there), and `wine/tools/makedep.c:2004-2009` gives every `include/*.idl` a `.h` target in that directory's Makefile, invoking widl by its literal path (`:4914`). In both pipeline paths `wine-ntdll-unix` (`scripts/build-ipa.sh:71`, `:96`) runs before the first `make` in a Wine tree (`wine-pe-ntdll`, `build/wine-pe/build-ntdll.sh:20`). Run `38651245572` could not show this: `dwrite` stops at `ft2build.h` first and `winegstreamer` at `avcodec.h`.
- **Impact:** Without the headers, `dwrite_unixlib` and `winegstreamer_unixlib` fail as soon as B-009 is fixed, so `libntdll_unix.a` still cannot be linked.
- **Next path:** `build/wine-macos/configure.sh` now generates them in `wine/build-macos/include` â€” the tree every unix side already includes â€” with `make -C wine/build-macos/tools/widl` (only when the binary is absent) followed by `make -C wine/build-macos/include`, and prints `present`/`MISSING` for all four headers. It is deliberately best-effort: a failure is printed and the stage continues, so the diagnosis stays with `build/ntdll-unix/build.sh:26-73` and any compile still fails loudly with its command line.
- **Status:** Fix added, **UNVERIFIED**: the make invocations were read out of makedep/configure, not executed (this worktree has no macOS, no bison/flex and no root, so no Wine build tree can be generated); whether `make -C include` needs further generated sources first is unknown.

## B-011: the unix-side header diagnostic named two paths that are not dependencies

- **Evidence:** run `38651245572`'s diagnostic block reported
  `MISSING: wine/build-arm64ec/include/dwrite_3.h` and
  `MISSING: build/freetype-ios/build/include/ft2build.h`. Neither is a real
  dependency of the `wine-ntdll-unix` stage:
  - `wine/build-arm64ec` is the ARM64EC PE tree, created by
    `build/wine-pe/build-ntdll.sh` (`:20`) which `scripts/build-ipa.sh` runs
    *after* `wine-ntdll-unix`; the widl-generated `dwrite_3.h`/`d2d1.h` the
    compile needs come from `wine/build-macos/include`, which
    `build/wine-macos/configure.sh` generates and `compile_unixlib` already
    passes as `-I"$WINE_BUILD/include"`. The extra `-I` flag pointed at a tree
    that cannot exist yet.
  - FreeType's CMake build (freetype `42608f77f2`, `CMakeLists.txt`) writes
    `${PROJECT_BINARY_DIR}/include/freetype/config/{ftconfig.h,ftoption.h}` and
    globs `include/ft2build.h` from the *source* tree; it never writes
    `ft2build.h` into the build tree, so that path does not exist on any
    configuration. What the compile really needs from the build tree is the
    generated `ftconfig.h` (the UNIX one, from `builds/unix/ftconfig.h.in`),
    named *before* `research/freetype/include` so it wins over the ANSI copy
    there â€” the order `build/win32u-unix/build.sh` has always used. Comparing
    the two files: `builds/unix/ftconfig.h.in` differs from
    `include/freetype/config/ftconfig.h` only by `#undef HAVE_UNISTD_H` /
    `#undef HAVE_FCNTL_H`, which CMake turns into defines when the headers are
    present; the include list below them is identical.
- **Impact:** the diagnostic reported two false MISSING lines on a healthy tree
  and never checked the generated header the compile depends on.
- **Next path:** `build/ntdll-unix/build.sh` now splits its list into
  `REQUIRED_HEADERS` (checked, and a miss exits 1 by name before the compiles)
  and `INFORMATIONAL_PATHS` (the arm64ec tree and `libfreetype.a`, named so the
  pipeline order is visible), and the comment records which stage produces each
  one. `dwrite_unixlib` now gets `-I"$FREETYPE_INC_BUILD" -I"$FREETYPE_INC_SRC"`;
  `build/win32u-unix/build.sh` and `build/freetype-ios/build.sh` check the same
  pair (the producer verifies the archive, its arm64 slice, both generated
  headers and the source `ft2build.h`).
- **Status:** fixed in the tree, **UNVERIFIED** until a `wine-ntdll-unix` stage
  runs again (this worktree has no macOS and no Wine source to execute it).

## B-012: nothing in CI ran the `tests/host` suite

- **Evidence:** the repository's only workflow, `.github/workflows/build-ipa.yml`,
  had no step that invoked `tests/host/*`. Ten checks assert that it does, and
  failed on a clean checkout: `check-lean-diag.py:252`,
  `check-power-probe.py:262`, `check-eco-native.py:137`,
  `check-quiet-log.py:201`, `check-srv-direct.py:588`,
  `check-srv-fd-reply.py`, `check-srv-eco-follow.py`,
  `check-msc-unbounded-retry.py:286`, `check-x64-image-nocopy.py:160`
  (all "CI runs this check"), plus `check-shader-pack.py:970` and
  `check-vcruntime-mfc.py:38`, which index specific steps of a workflow that no
  longer has them.
- **Impact:** ~150 regression checks, several of which guard the exact defects
  B-009/B-010 describe, were never run by CI; a green `build-ipa` job said
  nothing about them.
- **Next path:** a new `host-checks` job (`ubuntu-latest`) runs the 106 checks
  that need no submodule and no Swift toolchain, one step per check, named
  `Check <name>` as the checks expect. The remaining checks need the wine, DXMT
  or FEX submodules or `swiftc`; they run locally (with the submodules
  initialised) and are named in the job's comment.
  `check-vcruntime-mfc.py` and `check-shader-pack.py` were **not** changed: the
  former asserts Madeira's step that fetches Microsoft's runtime DLLs, which
  WinePhone deliberately refuses (`DECISIONS.md`, IPA_BUILD.md item 4,
  `tools/validate_release_inputs.py`), and the latter indexes a step this
  workflow does not have. Both are recorded here rather than edited, because
  changing an inherited test to match a different release policy is a decision
  for the project, not a build repair.
- **Status:** job added; it ran here on the same checks
  (`python3 tests/host/check-<name>.py`), 106/106 passing on Linux. **UNVERIFIED**
  on a GitHub runner.

## B-013: the wineserver stage had no producer for its base `libwineserver.a`

- **Evidence:** the full-path run at `3daa133` (user-supplied log) reached
  `=== wineserver ===` immediately after `wine-ntdll-unix` succeeded 37/37 and
  died with `ERROR: No base libwineserver.a found`, exit 1. The stage
  (`build/wineserver/build.sh`, old `:16-22`) required the archive to already
  exist at `build/wineserver/obj/libwineserver.a` or `app/Madeira/libwineserver.a`.
  That file is git-ignored (`.gitignore:33`), `git log --all --
  app/Madeira/libwineserver.a` is empty, and no script in the repository
  produced it: it was an out-of-band artifact of the original development
  machine. The Xcode project links it (`project.pbxproj:74`), so it is a real
  input, not a diagnostic nicety.
- **Impact:** every clean checkout â€” i.e. every CI run â€” fails at this stage,
  so `win32u-unix`, `wine-pe-*`, DXMT, `xcodebuild` and the IPA can never run.
- **Next path:** `build/wineserver/build.sh` now produces the base itself:
  `build_base_from_source()` compiles every `.c` in the pinned submodule's
  `server/Makefile.in` `SOURCES` (44 files at wine `9129e968`, counted from
  the pinned file itself, which also lists `security.h` and three man pages) for iOS arm64
  with the stage's own `CC_FLAGS`, under their natural member names
  (`foo.c -> foo.o`) so the existing `PATCHED_FILES`/`REPLACEMENTS` swap and the
  `llvm-objcopy` symbol-rename sweep still apply object-by-object.
  Resolution order preserves local workflows: an existing `obj/` archive, then
  a developer's `app/Madeira/libwineserver.a`, else the source build. `$0 base`
  builds only the archive; a missing submodule names
  `git submodule update --init wine` as the prerequisite; an unparseable
  `SOURCES` list refuses to build an empty archive rather than satisfying the
  file check. `tests/host/check-wineserver-base.py` runs the real script end to
  end in a sandbox (stub `xcrun`/`ar`/`llvm-objcopy`) and pins the member set,
  the object swap, the rename sweep and the failure diagnostics.
- **Status:** repaired in the tree; the 44 real iOS compiles are **UNVERIFIED**
  until a full workflow run. By design that run reports every failing
  `server/*.c` at once (counted summary) instead of one per dispatch. The stage
  is also dispatchable on its own (`only_stage=wineserver`, which runs the
  `wine-macos` configure it needs first) so it can be checked without the
  fex-ios/fex-arm64ec legs.
- **ABI hazard this repair removes â€” found by reading the fork, not documented
  elsewhere.** `wine/server/thread.h:147-148` carries
  `C_ASSERT( offsetof(struct thread, completion_wait) == 640 )` and
  `C_ASSERT( offsetof(struct thread, token) == 600 )` under `WINE_IOS`. The
  comment at `:135-146` states the archive is expected to hold **27 objects that
  `build.sh` never recompiles** (`completion.o`, `event.o`, `mutex.o`, `timer.o`,
  `handle.o`, `token.o`, ...), that those objects read `struct thread` at the
  offsets they were compiled with, and that inserting a field anywhere above
  `ios_mach_suspended` moved `completion_wait` 640 -> 648 and made
  `cleanup_thread_completion()` dereference garbage on every thread teardown
  (fault `0x110e5e0007b5`) â€” undetected, because the `objcopy` repack refreshes
  every member's mtime so the archive still looked freshly built. It then gives
  the instruction that this repair follows: "either move your new field to the
  end of the struct, **or rebuild every object in the archive from these
  headers** and then update it."
  Rebuilding all 44 `SOURCES` from the pinned headers with one flag set is that
  second option, so every member agrees on the layout by construction and the
  `C_ASSERT`s hold by definition. Mixing a fresh `thread.o` with a 27-object
  archive built from older headers is exactly the failure above, and the old
  producer could not have been caught by the mtime. Consequences to record once
  the stage passes: the "27 prebuilt objects" wording at `thread.h:103` and
  `:137` becomes stale and should be corrected with the new count, and
  `SOURCES` was confirmed to hold exactly 44 `.c` entries with none on disk
  missing from the list. VERIFY the two `C_ASSERT` values on the arm64 iOS
  target: `offsetof` depends on the target ABI, so this host's x86-64 numbers
  prove nothing.

## B-014: FEX diagnostics recorded as warnings â€” adjudicated, not "fixed"

- **Evidence:** the `only_stage=all` log the user supplied (also summarised in
  `docs/HANDOFF.md`) records, from the pinned FEX fork
  (`f59cab95659e8add0c88f0c76ec1cf483c536dbf`): ARM64EC inline-assembly
  warnings naming X23/X24/X28 in `LongJump.cpp`, a possible out-of-bounds
  `Info->FileName[1]` in `Source/Windows/Common/ImageTracker.cpp:261`, unused
  functions in `AllocWatch.cpp`/`CPUFeatures.cpp`, an unused CMake option
  `ENABLE_OFFLINE_RUNTIME`, failed feature probes (`getcpu`, `gettid`, `tgkill`,
  `statx`, `renameat2`) and range-v3's "unknown system iOS". None of these stop
  the FEX stages: `libFEXCore.a`/`libFEXCore_Base.a` and `libarm64ecfex.dll`
  were produced in that run.
- **What was checked here (2026-10-15, sources read at the pin):**
  `ImageTracker.cpp` was fetched from the pin and its guard read directly: the
  access is `Info->FileNameLength == 4 && Info->FileName[0] == '.' &&
  Info->FileName[1] == '.'`, so `FileName[1]` is only evaluated when the
  reported length is two WCHARs of a name `NtQueryDirectoryFile` wrote into the
  buffer â€” the warning is the compiler's view of the `WCHAR FileName[1]`
  flexible-array declaration, not a reachable out-of-bounds read. The file's
  `LoadAOTImages` also differs substantially from current FEX upstream `main`
  (upstream carries `CacheFile`/`EnableLoadedSection` code this pin does not
  have), so the pin's shape is a fork/revision gap, not a WinePhone edit â€” this
  is the fork's own code, and no WinePhone change was made to it.
- **Impact:** none demonstrated: an unfalsifiable warning was resolved to false
  positive by reading the guard, and the platform-probe failures are expected
  for a Linux-hosted cross build (`FEX_IOS_HOST`/Darwin probes).
- **Next path:** the ARM64EC X23/X24/X28 assembly warnings are the one item that
  can name real ABI misuse (those registers are reserved in the ARM64EC ABI),
  so they need the fork's `LongJump.cpp` read against Microsoft's ARM64EC
  register rules and a compile under the ARM64EC target to be confirmed either
  way. Neither is possible in this Linux worktree (no ARM64EC toolchain, no
  Windows host), and an unverifiable assembly rewrite is exactly what the
  project's rules exclude, so it stays open **UNVERIFIED** with the file, the
  registers and the warning named above.
- **Status:** investigated; no change made; one item (ARM64EC asm registers)
  explicitly still open.

## B-015: the GnuTLS stage never placed the four archives the app links

- **Evidence:** the Xcode target links 20 static archives
  (`app/Madeira.xcodeproj/project.pbxproj`, `Frameworks` phase); 13 are bare
  file references (`path = libgnutls.a;` and so on), which
  `tools/validate_release_inputs.py` resolves as `app/Madeira/<name>` â€” the same
  base that makes the project's `../../FEX/build-ios/...` references resolve,
  and the base every other producer writes to
  (`app/Madeira/libwineserver.a`, `libntdll_unix.a`, `libwin32u_unix.a`,
  `libdxmt_combined.a`, `libmadeira_rppairing.a`, FFmpeg's four).
  `build/gnutls-ios/build.sh` installed only to
  `toolchains/gnutls-ios/lib/{libgnutls,libhogweed,libnettle,libgmp}.a` and had
  no copy step, `.gitignore` had no entries for them under `app/Madeira/`, and
  no other script names them: nothing put them where the link and the validator
  look.
- **Impact:** `scripts/build-ipa.sh` runs `tools/validate_release_inputs.py`
  after every producer and before `xcodebuild`; with the four absent it exits 2
  with `Missing linked archives: app/Madeira/libgnutls.a â€¦`, and had the
  validator been bypassed the link would fail on the same files. It is the same
  producer/consumer class as B-013, one stage later; it could not be seen before
  because no run ever reached past the wineserver stage.
- **Next path:** the GnuTLS stage now copies `libgmp`, `libnettle`,
  `libhogweed` and `libgnutls` from its prefix into `app/Madeira/` (dependency
  order, `APP_DIR="$REPO_ROOT/app/Madeira"`), verifies each placed archive
  exists and carries an arm64 slice with `lipo -archs`, and fails by name when
  one is missing or not the iOS slice (rather than shipping a macOS or
  simulator archive that links and then fails at load). `.gitignore` gained the
  four paths, like the other rebuilt archives.
  `tests/host/check-ipa-build-graph.py` now derives the bare-name set from the
  project file itself and requires a producer that places each one in
  `app/Madeira` â€” the check that fails on B-013's and B-015's shape.
- **Status:** fixed in the tree; **UNVERIFIED** until a macOS run executes the
  GnuTLS stage (no GnuTLS sources are built here) and the validator then sees
  the four files.
- **One ambiguity left to the next run:** the project's `Libraries` group has no
  `path`, so Xcode resolves a bare reference from the project directory. The
  relative `../../FEX/build-ios/...` references only resolve from
  `app/Madeira/`, which is the base this stage (and the validator) now uses; but
  `.gitignore` also carries `app/libwineserver.a` and `app/libwin32u_unix.a`,
  the two archives that predate this work, so an earlier project revision
  resolved them one level up. If the next run's `xcodebuild` reports a missing
  archive after the validator passes, the resolution base is `app/` and the
  correct repair is to make those file references explicit (or copy alongside,
  as the older entries imply) â€” the log will name the path.

## B-016: `airconv_context.cpp` could not find its generated AIR headers

- **Evidence:** run `38832880011` reached `dxmt-ios` and failed on one unit of
  83 — `Results: 82 succeeded, 1 failed / Failed: airconv_context` — with
  `dxmt/src/airconv/airconv_context.cpp:29:10: fatal error: 'air_msad.h' file
  not found`.
- **Root cause (corrected).** The three headers are **generated build
  artefacts, not Apple-licensed material**, and the earlier entry in this file
  said otherwise. `dxmt/meson.build:149-165` builds them from shaders that live
  in the submodule itself — `src/airconv/shaders/air_msad.metal` (1493 bytes),
  `air_samplepos.metal` (1305) and `air_tessellation.metal` (29134) — using
  `xcrun -sdk macosx metal` to produce `<n>.air` and `xxd -n <n> -i <n>.air
  <n>.h` to wrap it. Both are ordinary build tools: `xcrun`'s `metal` subtool is
  a compiler shipped with Xcode, like `clang`. `xxd` is likewise ordinary and
  was already proven present on the runner, because `meson.build:160` calls
  `find_program('xxd')` during `dxmt-pe-configure` and that configure has
  succeeded. Nothing here is Apple's licence-bound Metal Shader Converter, which
  this tree still omits by policy (D-002) and which `scripts/build-ipa.sh` still
  refuses to ship.
- **Why it failed.** `build/dxmt-ios/build.sh` compiles the airconv sources
  directly with clang instead of going through meson, so nothing generated those
  headers and the compile had no `air_msad.h` to include.
- **Fix.** The stage now generates all three headers with the exact commands
  `dxmt/meson.build` uses, into `$OBJ_DIR/air`, and passes that directory on the
  airconv compile line.
- **Correction of a wrong decision.** The previous revision of this entry
  recorded a licensing restriction, added
  `patches/dxmt-airconv-noapple-air.patch`, and compiled the three link
  functions out under `-DWINEPHONE_NO_APPLE_AIR`. That silently removed MSAD,
  sample positions and tessellation — a real functional loss — on the strength
  of a wrong cause. Both the patch and the define are deleted. The only remaining
  patch for dxmt is `dxmt-winemetal-static-implibs.patch`.
- **Method note.** This was found by reading `src/airconv/meson.build` for the
  generators, not by another build-and-inspect cycle. The same question had
  already been answered wrongly once from the symptom alone. Reading the build
  system is cheap; a CI cycle is thirteen minutes.
- **Status:** fix written. That the headers now generate and that MSAD,
  sample positions and tessellation work at run time are **UNVERIFIED**; this
  needs a macOS runner.
