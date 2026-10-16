"""Find 8-byte little-endian values in the image's read-only data.

A function with zero direct callers is usually a vtable slot, so the pointer
value itself is the way to find the table -- and the table's neighbours name
the rest of the class. Returns every hit with its section and VA.
"""
import struct
import sys

PE_PATH = sys.argv[1]
VALUE = int(sys.argv[2], 16)
ONLY = sys.argv[3] if len(sys.argv) > 3 else None

data = open(PE_PATH, "rb").read()
pe = struct.unpack_from("<I", data, 0x3c)[0]
nsec = struct.unpack_from("<H", data, pe + 6)[0]
optsz = struct.unpack_from("<H", data, pe + 20)[0]
opt = pe + 24
image_base = struct.unpack_from("<Q", data, opt + 24)[0]
sec = opt + optsz

sections = []
for i in range(nsec):
    o = sec + i * 40
    name = data[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, o + 8)
    sections.append((name, vaddr, vsize, raddr, rsize))

pat = struct.pack("<Q", VALUE)
WORD = 8

for name, vaddr, vsize, raddr, rsize in sections:
    if ONLY and name != ONLY:
        continue
    blob = data[raddr:raddr + rsize]
    if name not in (".rdata", "_RDATA", ".data") and not ONLY:
        continue
    at = blob.find(pat)
    while at >= 0:
        base = image_base + vaddr + (at // WORD) * WORD
        print("%-8s slot VA 0x%012x  -> 0x%x" % (name, base, VALUE))
        at = blob.find(pat, at + 1)

print()
print("neighbours of every hit (up to 12 slots either side):")
for name, vaddr, vsize, raddr, rsize in sections:
    if name not in (".rdata", "_RDATA", ".data"):
        continue
    blob = data[raddr:raddr + rsize]
    at = blob.find(pat)
    while at >= 0:
        slot = (at // WORD) * WORD
        lo = max(0, slot - 12 * WORD)
        hi = min(len(blob), slot + 13 * WORD)
        print("  --- table around 0x%x ---" % (image_base + vaddr + slot))
        for k in range(lo, hi, WORD):
            v = struct.unpack_from("<Q", blob, k)[0]
            mark = "  <== the function" if k == slot else ""
            inside = image_base + vaddr <= v < image_base + vaddr + vsize
            print("   %s0x%012x  %s%s" % (">" if k == slot else " ",
                                          image_base + vaddr + k,
                                          "0x%x" % v, " (in this section)" if inside else ""))
        at = blob.find(pat, at + 1)