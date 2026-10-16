"""Dump a vtable: consecutive 8-byte code pointers, with slot indexes."""
import struct
import sys

PE_PATH = sys.argv[1]
BASE = int(sys.argv[2], 16)
COUNT = int(sys.argv[3]) if len(sys.argv) > 3 else 64

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

tva, tvsize, traddr, trsize = next(s[1:] for s in sections if s[0] == ".text")


def rva_to_off(rva):
    for name, vaddr, vsize, raddr, rsize in sections:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None


def is_text(va):
    rva = va - image_base
    return tva <= rva < tva + tvsize


base_off = rva_to_off(BASE - image_base)
print("vtable at 0x%x  (file 0x%x)" % (BASE, base_off))
for i in range(COUNT):
    off = base_off + i * 8
    v = struct.unpack_from("<Q", data, off)[0]
    disp = i * 8
    slot = ("%+#x" % disp) if disp else "base"
    if i == 0:
        slot = "COL?"     # a complete-object-locator pointer may precede the table
    print("  [%3d] %-8s slot@0x%012x -> 0x%012x%s"
          % (i, slot, BASE + i * 8, v, "   (code)" if is_text(v) else ""))