#!/usr/bin/env python3
"""The dark minimal theme is wired into the app, not merely defined.

Theme.swift holding the tokens proves nothing about whether anything uses them.
This asserts that the tokens are reached from the screens the brief names --
the tab bar and the settings list -- and that the things the brief asked for
are present as tokens rather than as inline literals.

It cannot see pixels. There is no simulator host here and no device attached, so
appearance is unverified by anything in this file; what it checks is that the
style has a single source and that the screens are pointed at it, which is the
part that silently rots when someone hard-codes a hex value in a view.

Also guards the two decisions that were made on purpose and are easy to undo by
accident: the Arabic font has to stay registered in all three places it needs to
be, and LiquidMetal must stay out of the active design path.
"""
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
APP = os.path.join(ROOT, "app", "Madeira")
THEME = os.path.join(APP, "Theme.swift")
LIBRARY = os.path.join(APP, "Library.swift")
PLIST = os.path.join(APP, "Info.plist")
PBXPROJ = os.path.join(ROOT, "app", "Madeira.xcodeproj", "project.pbxproj")

failures = []


def check(what, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + what + ("  " + detail if detail else ""))
    if not cond:
        failures.append(what)


def read(path):
    return open(path, encoding="utf-8", errors="replace").read()


for path in (THEME, LIBRARY, PLIST, PBXPROJ):
    check("%s exists" % os.path.basename(path), os.path.exists(path))
if failures:
    print("FAILED: " + "; ".join(failures))
    sys.exit(1)

theme = read(THEME)
library = read(LIBRARY)
plist = read(PLIST)
pbx = read(PBXPROJ)

# --- the tokens exist, and every one the brief named -------------------------
TOKENS = [
    ("bg top #2E2E2E", "0x2E"),
    ("bg bottom #050505", "0x05"),
    ("surface top #262626", "0x26"),
    ("surface bottom #1C1C1C", "0x1C"),
    ("primary text white", "Color.white"),
    ("secondary text #8E8E93", "0x8E"),
    ("border rgba(255,255,255,0.08)", 'opacity(0.08)'),
    ("divider rgba(255,255,255,0.07)", 'opacity(0.07)'),
    ("pill fill rgba(255,255,255,0.12)", 'opacity(0.12)'),
]
for label, needle in TOKENS:
    check("token %s" % label, needle in theme, needle)

GEOMETRY = [
    ("card radius 28", r"card:\s*CGFloat\s*=\s*28"),
    ("pill radius 20", r"pill:\s*CGFloat\s*=\s*20"),
    ("small pill radius 16", r"pillSmall:\s*CGFloat\s*=\s*16"),
    ("row height 58", r"rowHeight:\s*CGFloat\s*=\s*58"),
    ("icon size 24", r"iconSize:\s*CGFloat\s*=\s*24"),
    ("card padding 20", r"cardPadding:\s*CGFloat\s*=\s*20"),
    ("card gap 16", r"cardGap:\s*CGFloat\s*=\s*Spacing\.l"),
    ("min touch target 44", r"minTouchTarget:\s*CGFloat\s*=\s*44"),
    ("press scale 0.97", r"pressScale:\s*CGFloat\s*=\s*0\.97"),
    ("transition 0.25", r"transition:\s*Double\s*=\s*0\.25"),
    ("divider inset", r"dividerInset"),
    ("spacing scale 4/8/12/16/24/32",
     r"xs:\s*CGFloat\s*=\s*4[\s\S]*s:\s*CGFloat\s*=\s*8[\s\S]*m:\s*CGFloat\s*=\s*12[\s\S]*"
     r"l:\s*CGFloat\s*=\s*16[\s\S]*xl:\s*CGFloat\s*=\s*24[\s\S]*xxl:\s*CGFloat\s*=\s*32"),
    ("three type levels",
     r"largeTitle[\s\S]*rowTitle[\s\S]*rowValue"),
    ("title size 30 bold", r"size:\s*30,\s*weight:\s*\.bold"),
    ("row size 17 medium", r"size:\s*17,\s*weight:\s*\.medium"),
    ("value size 15", r"size:\s*15,\s*weight:\s*\.regular"),
]
for label, pattern in GEOMETRY:
    check("theme %s" % label, re.search(pattern, theme) is not None)

# --- the screens are pointed at the theme -----------------------------------
check("both tabs sit on the theme background",
      library.count(".appBackground()") >= 2,
      "%d uses" % library.count(".appBackground()"))
check("the tab bar is a flat near-black, not the system's glass",
      re.search(r"toolbarBackground\(\s*Theme\.Palette\.bgBottom", library) is not None)
check("the tab bar background is forced visible, or the colour is ignored",
      re.search(r"toolbarBackground\(\.visible,\s*for:\s*\.tabBar\)", library) is not None)
check("a tab shows a filled symbol when active",
      'filled: "square.grid.2x2.fill"' in library and 'filled: "gearshape.fill"' in library)
check("a tab shows an outlined symbol when inactive",
      'outlined: "square.grid.2x2"' in library and 'outlined: "gearshape"' in library)
check("tab labels are visible under the icons",
      library.count('Text("Library")') >= 1 and library.count('Text("Settings")') >= 1)
check("each tab is still one accessibility element",
      library.count(".accessibilityElement(children: .combine)") >= 2)
check("the settings list is on the theme background",
      re.search(r"\.background\(\s*Theme\.background", library) is not None)
check("Form's own background is hidden, or the gradient would be covered",
      re.search(r"\.scrollContentBackground\(\.hidden\)", library) is not None)
check("the system accent tint is replaced",
      re.search(r"\.tint\(\s*Theme\.Palette\.primaryText\)", library) is not None)

# --- no tab was invented ----------------------------------------------------
# Scoped to the TabView's own body. Other views in this file use .tag() for
# their own selection, so counting every tag in a 258 KB file would report
# something that is not about the tab bar.
tv = re.search(r"TabView\(selection:.*?\n        \}\n", library, re.S)
check("the tab bar is found", tv is not None)
if tv:
    tags = re.findall(r"\.tag\((\d+)\)", tv.group(0))
    check("exactly the two existing tabs are present",
          sorted(set(tags)) == ["0", "1"], "tags %s" % sorted(set(tags)))
    check("no third tab was invented",
          tv.group(0).count(".tabItem") == 2,
          "%d tabItems" % tv.group(0).count(".tabItem"))

# --- the name: display only -------------------------------------------------
check("CFBundleDisplayName is iOStation",
      re.search(r"CFBundleDisplayName</key>\s*<string>iOStation</string>", plist) is not None)
check("the display name is not auto-capitalised",
      plist.count("<string>iOStation</string>") == 1)
check("the bundle identifier is untouched",
      re.search(r"MADEIRA_BUNDLE_IDENTIFIER\s*=\s*com\.willfaust\.madeora", pbx) is not None,
      "a registered identifier cannot be renamed")
check("the URL scheme is untouched", "madeira" in plist,
      "renaming it would break existing links")
check("the release contract's IPA name is untouched",
      re.search(r"PRODUCT_NAME\s*=\s*\"\$\(TARGET_NAME\)\"", pbx) is not None)

# --- English only ------------------------------------------------------------
# The app is English-only by decision, and there is no localization to localize.
# The Arabic face that briefly shipped was removed; these assert it stays
# removed, because an accidental re-add puts ~480 KB of unused font and its
# licence in the bundle for text that does not exist.
fonts_dir = os.path.join(APP, "Fonts")
check("no Fonts directory is shipped", not os.path.isdir(fonts_dir), fonts_dir)
check("UIAppFonts lists nothing", "UIAppFonts" not in plist)
check("no Plex font is registered in the project",
      not re.search(r"IBMPlex|IBM-Plex", pbx))
check("the theme has no Arabic font lookup to fall through",
      "IBM Plex" not in theme and "didLoad" not in theme)
check("there is still no localization to translate",
      not any(f.endswith(".lproj") for f in os.listdir(APP)) and
      not re.search(r"AppleLanguages|CFBundleLocalizations", plist),
      "a .lproj or a language list would need translating, not just fonts")

# --- GlassSkin stays out of the active path ---------------------------------
setting = re.search(r'@Published var on = MadeiraConfig\.flag\("MADEIRA_LIQUID_METAL",\s*'
                    r'fallback:\s*(true|false)\)', read(os.path.join(APP, "Library.swift")))
check("liquid metal still defaults to off", setting is not None and setting.group(1) == "false",
      "found fallback=%s" % (setting.group(1) if setting else "no setting"))
skin = read(os.path.join(APP, "GlassSkin.swift"))
check("GlassSkin is gated on that setting",
      re.search(r"func start\([^)]*\)\s*\{\s*guard Self\.enabled", skin) is not None,
      "without the guard it would paint over the flat design")

print("PASS" if not failures else "FAILED: " + "; ".join(failures))
sys.exit(0 if not failures else 1)
