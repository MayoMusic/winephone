#!/usr/bin/env python3
"""The iOS IPA build graph: which headers each stage consumes, and what the package is checked against.

Source-level check (no macOS, no Xcode, no Wine tree): it pins the *contract*
between the stages the runner executes.

  - build/freetype-ios/build.sh is the only FreeType producer. FreeType's CMake
    build writes its generated configuration headers into
    <build>/include/freetype/config/{ftconfig.h,ftoption.h} (its CMakeLists.txt
    points FTCONFIG_H_NAME/FTOPTION_H_NAME at ${PROJECT_BINARY_DIR}/include) and
    never writes ft2build.h: that is a tracked *source* header under
    research/freetype/include. A consumer needs both dirs, the generated one
    first, so the translation unit sees the same ftconfig.h the library was
    compiled with. build/win32u-unix/build.sh always did; build/ntdll-unix's
    dwrite_unixlib did not, and the stage's own header diagnostic listed two
    paths that no stage produces (build/freetype-ios/build/include/ft2build.h)
    or that cannot exist yet (wine/build-arm64ec/include).

  - wine/build-arm64ec is the ARM64EC PE tree built by build/wine-pe/build-ntdll.sh,
    which scripts/build-ipa.sh runs *after* wine-ntdll-unix: it cannot be a
    dependency of the unix side. The widl-generated dwrite_3.h/d2d1.h/mfobjects.h
    that dwrite_private.h and winegstreamer's unixlib.h include come from
    wine/build-macos/include, which build/wine-macos/configure.sh generates and
    compile_unixlib already passes.

  - build/wineserver/build.sh must produce its own base libwineserver.a from the
    pinned submodule's server/Makefile.in: the archive it patches was a
    git-ignored local artifact with no producer, so every clean checkout died at
    that stage. The functional half (member set, object swap, rename sweep) is
    tests/host/check-wineserver-base.py.

  - scripts/build-ipa.sh must validate the artifact it packages (bundle
    executable named by CFBundleExecutable, arm64 slice, exactly one app in
    Payload) and SHA256SUMS must be the hash of that same file, in a form
    `shasum -a 256 -c` can verify.

  - the workflow must not re-save an existing toolchain cache key, must keep the
    release gate on both uploads, must verify the published hash against the
    published IPA, must not present a stage-only dispatch as an IPA build, and
    must run the host checks (several of them assert their own presence here).
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
NTDLL = (ROOT / "build/ntdll-unix/build.sh").read_text(encoding="utf-8")
WIN32U = (ROOT / "build/win32u-unix/build.sh").read_text(encoding="utf-8")
FREETYPE = (ROOT / "build/freetype-ios/build.sh").read_text(encoding="utf-8")
WS = (ROOT / "build/wineserver/build.sh").read_text(encoding="utf-8")
IPA = (ROOT / "scripts/build-ipa.sh").read_text(encoding="utf-8")
VALIDATOR = (ROOT / "tools/validate-ipa.sh")
VAL = VALIDATOR.read_text(encoding="utf-8")
WF = (ROOT / ".github/workflows/build-ipa.yml").read_text(encoding="utf-8")

failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


def step(name):
    """The workflow text of the step whose name is exactly `name`."""
    i = WF.index("\n      - name: " + name + "\n")
    j = WF.find("\n      - name: ", i + 1)
    return WF[i:j if j >= 0 else len(WF)]


def step_if_present(name):
    try:
        return step(name)
    except ValueError:
        return None


def flat(text):
    """Collapse line continuations so a multi-line flag list can be matched as one string."""
    return re.sub(r"[ \t]*\\\n[ \t]*", " ", text)


f_ntdll, f_win32u, f_ipa = flat(NTDLL), flat(WIN32U), flat(IPA)


def call_block(text, needle, marker):
    """The whole `marker` invocation that names `needle` ('' when either is absent)."""
    if needle not in text or marker not in text[:text.index(needle)]:
        return ""
    i = text.index(needle)
    begin = text.rindex(marker, 0, i)
    end = text.find("\n\n", i)
    return text[begin:end if end >= 0 else len(text)]


def ordered(text, first, second):
    """True when both substrings occur and `first` comes before `second`."""
    return first in text and second in text and text.index(first) < text.index(second)


# ------------------------------------------------------------- FreeType include paths
dwrite = call_block(f_ntdll, "dwrite_freetype_ios.c", "compile_unixlib")
check('FREETYPE_INC_BUILD' in dwrite and 'FREETYPE_INC_SRC' in dwrite,
      "dwrite_unixlib names both FreeType include dirs explicitly")
check(ordered(dwrite, '"$FREETYPE_INC_BUILD"', '"$FREETYPE_INC_SRC"'),
      "the generated ftconfig.h dir precedes the source dir (the build's config wins)")
check(re.search(r'-I"[^"]*build-arm64ec', NTDLL) is None and "build-arm64ec" in NTDLL,
      "no wine-ntdll-unix compile includes wine/build-arm64ec, which wine-pe-ntdll builds later")
wineg = call_block(f_ntdll, "winegstreamer_unixlib_ios.c", "compile_unixlib")
check("FFMPEG_PREFIX" in wineg,
      "winegstreamer_unixlib still gets the FFmpeg prefix")
check('$WINE_BUILD/include' in NTDLL or 'WINE_BUILD' in NTDLL,
      "the widl headers come from the configured tree (wine/build-macos/include)")

# ------------------------------------------------------------- the stage diagnostic
check('$FREETYPE_BUILD/include/ft2build.h' not in NTDLL,
      "the diagnostic no longer requires build/freetype-ios/build/include/ft2build.h")
check("ft2build.h" in NTDLL and "freetype/config/ftconfig.h" in NTDLL
      and "freetype/config/ftoption.h" in NTDLL,
      "it requires the FreeType headers that do exist (source ft2build.h, generated config)")
check("REQUIRED_HEADERS" in NTDLL and "INFORMATIONAL_PATHS" in NTDLL,
      "required and informational paths are distinguished")
check(re.search(r"if \[ -n \"\$MISSING_REQUIRED\" \][\s\S]{0,1600}?exit 1", NTDLL) is not None,
      "a missing required header fails the stage with a named message before the compiles")
check("wine-pe-ntdll" in NTDLL or "wine-pe/build-ntdll.sh" in NTDLL,
      "the diagnostic records which stage produces the ARM64EC tree")

# ------------------------------------------------------------- win32u FreeType consumer
check('$FREETYPE_INC_BUILD' in f_win32u and '$FREETYPE_INC_SRC' in f_win32u,
      "win32u freetype_ios names both FreeType include dirs")
check(ordered(f_win32u, '"$FREETYPE_INC_BUILD"', '"$FREETYPE_INC_SRC"'),
      "and keeps the generated config first")
check("MISSING_REQUIRED" in WIN32U and "exit 1" in WIN32U,
      "win32u refuses to build the font unit without its FreeType headers")
check('$FREETYPE_LIB' in f_win32u and "build/freetype-ios/libfreetype.a" not in WIN32U,
      "the merged archive is named once, at the path the FreeType build writes")

# ------------------------------------------------------------- FreeType producer
check("FREETYPE_LIB" in FREETYPE and "ftconfig.h" in FREETYPE and "ftoption.h" in FREETYPE
      and "ft2build.h" in FREETYPE,
      "build/freetype-ios/build.sh verifies every artifact the consumers name")
check("lipo -archs" in FREETYPE and "arm64" in FREETYPE,
      "and that the archive carries an arm64 slice")
check(re.search(r"MISSING_REQUIRED[\s\S]{0,500}?exit 1", FREETYPE) is not None,
      "the FreeType build fails when an expected artifact is absent")
check("FREETYPE_COMMIT" in FREETYPE and "rev-parse HEAD" in FREETYPE,
      "the pinned source commit is still verified before the build")

# ------------------------------------------------------------- wineserver base producer
# app/Madeira/libwineserver.a was a git-ignored, never-committed local artifact
# with no producer in the repository: every clean checkout died in the wineserver
# stage with "No base libwineserver.a found". The stage now builds its own base
# from the submodule's server/Makefile.in (the functional half is exercised by
# tests/host/check-wineserver-base.py, which runs the real script in a sandbox).
check("build_base_from_source" in WS and "ensure_base_archive" in WS,
      "build/wineserver produces its base libwineserver.a from server/Makefile.in")
check(re.search(r'^\s*echo "ERROR: No base', WS, re.M) is None,
      "the wineserver stage no longer hard-fails on a clean checkout")
check("git submodule update --init wine" in WS,
      "its missing-tree diagnostic names the submodule fetch as the producer")
check(re.search(r"refusing to build[\s\S]{0,120}?empty libwineserver", WS) is not None,
      "an unparseable source list fails rather than shipping an empty archive")

# ------------------------------------------------------------- packaged artifact
# The packaging step validates through tools/validate-ipa.sh, which is itself
# exercised end to end by tests/host/check-ipa-validation.py.
check("CFBundleExecutable" in VAL and "plistlib" in VAL,
      "the IPA check reads CFBundleExecutable from the packaged Info.plist")
check("lipo -archs" in VAL and "arm64" in VAL,
      "the packaged executable is checked for the arm64 slice the device needs")
check(re.search(r"find \"\$PAYLOAD\"[^\n]*-name '\*\.app'", VAL) is not None
      and "expected exactly 1" in VAL,
      "Payload is checked to hold exactly one .app")
check("shasum -a 256 -c" in VAL and 'shasum -a 256 "$IPA"' in VAL,
      "SHA256SUMS is the hash of the packaged IPA and is verified with -c")
check("libmetalirconverter|d3d12core" in VAL,
      "the release exclusions are re-checked on the packaged bytes")
check("validate-ipa.sh" in IPA and 'sed -n \'s/^IPA_ARCHS=//p\'' in IPA,
      "build-ipa.sh runs the validator and believes its result, not its own copy")
check("build-status.txt" in IPA and "IPA_PRESENT=1" in IPA,
      "the script records whether it produced an IPA")
check("stage-only" in IPA.lower() and "IPA_PRESENT=0" in IPA,
      "a stage-only run records that it produced no IPA")
check('IPA: $IPA' in IPA, "the artifact path is printed for the workflow")

# ------------------------------------------------------------- workflow logic
check("cache-hit != 'true'" in step("Save toolchain cache after bootstrap"),
      "the toolchain cache is saved only on a miss (cache/save fails on an existing key)")
check("if-no-files-found" not in step("Bootstrap pinned sources and toolchains") and
      "cache-hit" not in step("Bootstrap pinned sources and toolchains"),
      "bootstrap still runs on a hit so the pinned sources are always fetched")
check("MISSING" in step("Report toolchain cache restore"),
      "the restore report shows which cache roots the runner actually has")
for upload in ("Upload unsigned IPA and hash", "Upload build evidence"):
    check("vars.WINEPHONE_BINARY_RELEASE_CLEARED == 'true'" in step(upload),
          "%s keeps the release gate" % upload)
check(WF.count("WINEPHONE_BINARY_RELEASE_CLEARED == 'true'") >= 3,
      "the hash verification is behind the same gate as the uploads")
check("shasum -a 256 -c artifacts/SHA256SUMS" in WF,
      "the workflow verifies the published hash against the published IPA")
check("- name: Report stage-only run" in WF,
      "a stage-only dispatch is reported as producing no IPA")
check(re.search(r"name: Build and package unsigned IPA\n\s+id: ipa", WF) is not None,
      "the packaging step is addressable so a later step can gate on it")
check("runs-on: ubuntu-latest" in WF and "tests/host/check-" in WF,
      "a job runs the host checks (the checks assert their own presence in this file)")
check("check-wineserver-base" in WF,
      "the workflow runs the functional wineserver base-archive check")

if failures:
    print("FAILED: %d" % len(failures))
    sys.exit(1)
print("OK")
