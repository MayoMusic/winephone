"""Find a UTF-16 or ASCII string inside a PE and print its file offset + RVA.

ROTTR.exe is a PE with ImageBase 0x140000000; the Wine host maps guest VAs, so
an RVA is what an xref inside the module is expressed against.
"""
import struct
import sys

path = sys.argv[1]
needle = sys.argv[2]
want_utf16 = len(sys.argv) > 3 and sys.argv[3] == "u16"

data = open(path, "rb").read()

if want_utf16:
    pat = needle.encode("utf-16-le")
else:
    pat = needle.encode("ascii")

hits = []
start = 0
while True:
    at = data.find(pat, start)
    if at < 0:
        break
    hits.append(at)
    start = at + 1

# PE headers -> section table
pe = struct.unpack_from("<I", data, 0x3c)[0]
assert data[pe:pe + 4] == b"PE\0\0", "not a PE"
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


def to_rva(off):
    for name, vaddr, vsize, raddr, rsize in sections:
        if raddr <= off < raddr + rsize:
            return name, vaddr + (off - raddr), image_base + vaddr + (off - raddr)
    return "?", None, None


print("%-28s %10s  %-10s %-18s" % ("encoding", "file off", "section", "VA"))
for h in hits[:40]:
    enc = "utf16" if want_utf16 else "ascii"
    name, rva, va = to_rva(h)
    print("%-28s 0x%08x  %-10s 0x%012x  (%s)" % (needle[:28], h, name, va, name))
print("total hits:", len(hits))
print("image base: 0x%x" % image_base)
for s in sections:
    print("  section %-8s vaddr=0x%-10x vsize=0x%-8x raddr=0x%-8x rsize=0x%x"
          % (s[0], s[1], s[2], s[3], s[4]))