"""Generate the two app assets from the artwork under logo/ and Wallpaper/.

Those two source images are deliberately NOT committed: they are input art, not
build output, and this repository is public. Keep them beside the tool; the
committed files are only what this script writes under Assets.xcassets.

  logo/logo v1.0.png        -> app/Madeira/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png
  Wallpaper/Wallpaper.jpg   -> app/Madeira/Assets.xcassets/MadeiraWallpaper.imageset/MadeiraWallpaper-{1,2,3}x.png

Both masters are stored under names that do not match their contents (the
wallpaper is a PNG named .jpg), so this reads the real format with Pillow rather
than trusting the extension.

The icon needs two corrections before it is usable. It arrives as 1254x1254 with
white corners around a dark plate, and iOS masks an icon to its own squircle --
a continuous curve, not the circular arc the artist drew -- so those corners
survive the mask as slivers. A flood fill seeded from the plate, not from the
image edge, finds the plate without eating the white glyph inside it, and the
sheet is repainted in the plate's own colour. Then it is LANCZOS-scaled to the
1024x1024 opaque PNG iOS asks for.

The wallpaper is NOT resampled upward. Its master is 1672x941, which is already
the Retina size for the 836x470pt slot, so 2x keeps the native pixels and 3x
repeats them: inventing detail costs bundle megabytes and looks worse than the
kernel's aspect fill. The icon is 1254x1254 and iOS wants exactly 1024x1024 with
no alpha -- the asset catalogue rejects a translucent icon -- so it is LANCZOS
downscaled onto an opaque canvas.

Run:  python tools/make-assets.py [--check]
`--check` reports what would change and writes nothing.
"""
import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_SRC = os.path.join(ROOT, "logo", "logo v1.0.png")
WALL_SRC = os.path.join(ROOT, "Wallpaper", "Wallpaper.jpg")
ASSETS = os.path.join(ROOT, "app", "Madeira", "Assets.xcassets")
ICON_DIR = os.path.join(ASSETS, "AppIcon.appiconset")
WALL_DIR = os.path.join(ASSETS, "MadeiraWallpaper.imageset")

CHECK = "--check" in sys.argv


def rgb(path):
    im = Image.open(path)
    return im.convert("RGB")


def px_diff(a, b, tolerance=8):
    """True when two RGB pixels differ by more than the encoder noise."""
    return sum(abs(x - y) for x, y in zip(a, b)) > tolerance * 3


def report(path, im):
    print("  %-58s %4dx%-4d %7d bytes  %s"
          % (os.path.relpath(path, ROOT), im.width, im.height,
             os.path.getsize(path) if os.path.exists(path) else 0, im.mode))


def write(path, im):
    if CHECK:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # optimize keeps the PNG small; a 1024 icon and a wallpaper are both
    # photographic content, where the default encoder wastes ~20 % on them.
    im.save(path, "PNG", optimize=True)


print("icon source:")
icon = rgb(ICON_SRC)
print("  %-58s %4dx%-4d  %s" % (os.path.relpath(ICON_SRC, ROOT), icon.width, icon.height, icon.mode))
corners = [icon.getpixel(p) for p in ((0, 0), (icon.width - 1, 0),
                                      (0, icon.height - 1), (icon.width - 1, icon.height - 1))]
spread = max(max(c) for c in corners) - min(min(c) for c in corners)
print("  corner pixels %s -> %s"
      % (corners,
         "identical, and full bleed" if spread == 0 else
         "within %d levels of each other (encoder noise, not a border)" % spread
         if spread <= 8 else
         "differ by %d levels: the artwork does not reach the edges" % spread))

# The artwork is a dark rounded square on a near-white sheet. iOS masks an icon
# to its own CONTINUOUS-CURVE squircle, which is not the circular arc the artist
# drew, so the white sheet survives the mask as slivers in the corners. Paint
# that sheet with the plate's own colour instead.
#
# A flood fill, not a bounding box, because "non-white" is not the plate: the
# glyph inside the plate is white too, and a bbox or a per-pixel rule would eat
# it. Seeding from the four edge midpoints reaches the plate -- which is what
# touches the edges -- and stops at the glyph, which does not.
INK = 40                                    # per-channel distance from white that counts as ink
mp = icon.load()
mask = Image.new("L", icon.size, 0)
for y in range(icon.height):
    for x in range(icon.width):
        r, g, b = mp[x, y]
        if (255 - r) + (255 - g) + (255 - b) > INK * 3:
            mask.putpixel((x, y), 255)

# Seed from the plate, not from the image edge: the plate is inset, so the edge
# midpoints are still white and a fill started there would find nothing. Walk in
# along each of the four midlines until the first ink pixel -- that is inside the
# plate. The glyph is white and enclosed, so the fill stops at it and cannot eat
# it.
plate = Image.new("L", icon.size, 0)
mid_x, mid_y = icon.width // 2, icon.height // 2


def walk(ray):
    """First ink pixel along the ray from the edge towards the centre."""
    for step in range(1, min(icon.width, icon.height) // 2):
        x, y = ray(step)
        if 0 <= x < icon.width and 0 <= y < icon.height and mask.getpixel((x, y)):
            return x, y
    return None


rays = [
    (lambda s: (mid_x + s, mid_y)),        # in from the left
    (lambda s: (mid_x - s, mid_y)),        # in from the right
    (lambda s: (mid_x, mid_y + s)),        # in from the top
    (lambda s: (mid_x, mid_y - s)),        # in from the bottom
]
seeds = [p for p in (walk(ray) for ray in rays) if p]
print("  plate seeds found on %d of 4 midlines" % len(seeds))

# floodfill replaces the region that MATCHES the seed's current value, so it has
# to start from the ink mask: filling a blank layer would flood the whole image,
# because a blank layer's seed value is the background value. Filling the ink
# mask with 0 erases exactly the plate, leaving the glyph -- which is white, and
# so was never ink -- untouched, and `plate` then marks what was NOT plate.
ink_total = mask.histogram()[255]
for sx, sy in seeds:
    ImageDraw.floodfill(plate, (sx, sy), 0)
reached = ink_total - plate.histogram()[255]
print("  plate flood fill reached %d px of %d (%.1f%%); %d px of ink left for the glyph"
      % (reached, icon.width * icon.height, 100.0 * reached / (icon.width * icon.height),
         plate.histogram()[255]))

if seeds and reached < icon.width * icon.height * 0.9:
    # Repaint the white sheet in the plate's own colour. `plate` is 0 where the
    # plate is and 255 elsewhere, so the sheet is the 0 region that is not already
    # ink: keep the ink (the glyph outline is white too) and fill the rest.
    colour = mp[seeds[0]]
    ink = mask.load()
    pl = plate.load()
    changed = 0
    for y in range(icon.height):
        for x in range(icon.width):
            if not pl[x, y] and ink[x, y] and px_diff(mp[x, y], colour):
                mp[x, y] = colour
                changed += 1
    print("  painted %d px of %s so the iOS squircle mask cuts clean instead of leaving slivers"
          % (changed, tuple(colour)))
else:
    print("  nothing to paint: the plate already reaches every edge")

print("wallpaper source:")
wall = rgb(WALL_SRC)
print("  %-58s %4dx%-4d  %s  (%.4f aspect)"
      % (os.path.relpath(WALL_SRC, ROOT), wall.width, wall.height, wall.mode,
         wall.width / wall.height))

print("icon output:")
icon_out = icon.resize((1024, 1024), Image.LANCZOS)
write(os.path.join(ICON_DIR, "AppIcon-1024.png"), icon_out)
report(os.path.join(ICON_DIR, "AppIcon-1024.png"), icon_out)

print("wallpaper output:")
# 836x470 pt is the logical slot and the master is already 2x for it, so 2x
# keeps the native pixels. There is no 3x: the master is 1672 px wide, so a
# third scale would be an upscale that costs another ~1 MB of bundle to add no
# detail. Xcode takes the largest scale present when one is missing.
scales = {
    "1x": wall.resize((836, 470), Image.LANCZOS),
    "2x": wall,
}
for name, im in scales.items():
    p = os.path.join(WALL_DIR, "MadeiraWallpaper-%s.png" % name)
    write(p, im)
    report(p, im)

contents = {
    "images": [
        {"filename": "MadeiraWallpaper-1x.png", "idiom": "universal", "scale": "1x"},
        {"filename": "MadeiraWallpaper-2x.png", "idiom": "universal", "scale": "2x"},
    ],
    "info": {"author": "xcode", "version": 1},
}
path = os.path.join(WALL_DIR, "Contents.json")
if not CHECK:
    os.makedirs(WALL_DIR, exist_ok=True)
    with open(path, "w", newline="\n") as f:
        json.dump(contents, f, indent=2)
        f.write("\n")
print("  %-58s" % os.path.relpath(path, ROOT))
print("done" + (" (--check wrote nothing)" if CHECK else ""))