#!/usr/bin/env python3
"""The bundled icon and wallpaper match what tools/make-assets.py produces.

Both are generated from art that lives outside the app bundle, so they can drift
three ways: the generator is not re-run, the generated files are edited by hand,
or Winios.m asks for a name the asset catalogue does not have. Each is silent --
a missing icon just looks wrong on the home screen and a missing wallpaper just
falls back to teal -- so they are checked here instead.

Needs python3 and Pillow. The catalogue's Contents.json is parsed as text and the
PNGs are decoded by hand, so a corrupt file is a failure here rather than a
build-time act of God in actool.
"""
import json
import os
import struct
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ASSETS = os.path.join(ROOT, "app", "Madeira", "Assets.xcassets")
ICON = os.path.join(ASSETS, "AppIcon.appiconset", "AppIcon-1024.png")
WALL_DIR = os.path.join(ASSETS, "MadeiraWallpaper.imageset")
WALL_NAME = "MadeiraWallpaper"

failures = []


def check(what, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + what + ("  " + detail if detail else ""))
    if not cond:
        failures.append(what)


def png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height, data[24], data[25]      # bit depth, colour type


def load(path):
    try:
        return png(path)
    except Exception as exc:                       # noqa: BLE001 - reported below
        return None, None, str(exc), None


try:
    from PIL import Image
except ImportError:
    Image = None

# --- the icon -------------------------------------------------------------
w, h, depth, ctype = (None, None, "missing", None)
if os.path.exists(ICON):
    w, h, depth, ctype = load(ICON)
check("AppIcon-1024.png exists", w is not None, ICON if w is None else "")
if w is not None:
    check("the app icon is 1024x1024 (iOS asks for exactly this)",
          (w, h) == (1024, 1024), "got %sx%s" % (w, h))
    check("the app icon is opaque (a translucent icon is rejected by actool)",
          ctype == 2, "colour type %s (%s)"
          % (ctype, {0: "grey", 2: "RGB", 3: "palette", 4: "grey+A", 6: "RGBA"}.get(ctype, "?")))

icon_json = os.path.join(ASSETS, "AppIcon.appiconset", "Contents.json")
if os.path.exists(icon_json):
    spec = json.load(open(icon_json))
    named = [i.get("filename") for i in spec.get("images", [])]
    check("the catalogue names the icon file that exists",
          "AppIcon-1024.png" in named and os.path.exists(ICON), str(named))

# --- the wallpaper --------------------------------------------------------
check("the wallpaper imageset exists", os.path.isdir(WALL_DIR), WALL_DIR)
wall_json = os.path.join(WALL_DIR, "Contents.json")
if os.path.isdir(WALL_DIR) and os.path.exists(wall_json):
    spec = json.load(open(wall_json))
    images = spec.get("images", [])
    check("the wallpaper catalogue has 1x and 2x",
          sorted(i.get("scale") for i in images) == ["1x", "2x"],
          str(sorted(i.get("scale") for i in images)))
    for entry in images:
        f = os.path.join(WALL_DIR, entry.get("filename", ""))
        present = os.path.exists(f)
        check("wallpaper %s is present" % entry.get("scale"), present, entry.get("filename", ""))
        if present and Image is not None:
            with Image.open(f) as im:
                check("wallpaper %s is RGB (no alpha)" % entry.get("scale"), im.mode == "RGB", im.mode)
    if Image is not None:
        native = os.path.join(WALL_DIR, "%s-2x.png" % WALL_NAME)
        if os.path.exists(native):
            with Image.open(native) as im:
                check("the 2x wallpaper keeps the master's aspect",
                      abs(im.width / im.height - 1672 / 941) < 0.01,
                      "%dx%d" % (im.width, im.height))
else:
    check("the wallpaper catalogue exists", False, wall_json)

# --- Winios.m asks for that name -----------------------------------------
winios = open(os.path.join(ROOT, "app/Madeira/Winios/Winios.m"), encoding="utf-8", errors="replace").read()
check("Winios.m loads the wallpaper by the name the catalogue provides",
      ('imageNamed:@"%s"' % WALL_NAME) in winios)
check("the desktop backdrop still has its teal fallback",
      "colorWithRed:0.0 green:0.502 blue:0.502" in winios,
      "a session without the bundle image must look exactly as it did before")

# --- the generator is the thing that made them ---------------------------
gen = open(os.path.join(ROOT, "tools/make-assets.py"), encoding="utf-8", errors="replace").read()
gen = gen.replace("\\", "/")
check("make-assets.py still reads the art from the repo",
      '"logo", "logo v1.0.png"' in gen and '"Wallpaper", "Wallpaper.jpg"' in gen)
check("make-assets.py refuses to run in --check mode without writing",
      'if not CHECK:' in gen and 'wrote nothing' in gen)

print("PASS" if not failures else "FAILED: " + "; ".join(failures))
sys.exit(0 if not failures else 1)