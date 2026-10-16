"""Read a 32-bit value out of .data at initial load, and list the code that
writes it. A runtime-configurable arena ceiling shows up as a .data slot that
something stores to; a compile-time constant shows up as initial data and no
writer at all. Which of the two it is decides whether the limit is patchable.
"""
import struct
import sys

PE_PATH = sys.argv[1]
VA = int(sys.argv[2], 16)

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


def rva_to_off(rva):
    for name, vaddr, vsize, raddr, rsize in sections:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None


def off_to_va(off):
    for name, vaddr, vsize, raddr, rsize in sections:
        if raddr <= off < raddr + rsize:
            return image_base + vaddr + (off - raddr)
    return None


off = rva_to_off(VA - image_base)
print("initial value at 0x%x: 0x%08x (%d)" % (VA, *((lambda v: (v, v))(struct.unpack_from("<I", data, off)[0]))))

# RIP-relative stores to the slot: [reg+disp32] with the target == VA.
text = next(s[1:] for s in sections if s[0] == ".text")
tva, tvsize, traddr, trsize = text
blob = data[traddr:traddr + trsize]

writers = []
i = 0
while i < len(blob) - 6:
    start = i
    rex = 0
    if blob[i] in (0x40, 0x41, 0x44, 0x45):
        rex = blob[i]
        i += 1
    if blob[i] in (0x89, 0x8B) and (blob[i + 1] & 0xC0) >> 6 == 2 and (blob[i + 1] & 7) != 4:
        disp = struct.unpack_from("<i", blob, i + 2)[0]
        here = off_to_va(traddr + start)
        if here + 6 + disp == VA:
            writers.append((here, "mov" if blob[i] == 0x89 else "mov(load)"))
    i = max(start + 1, i + 1)

print("writers: %d" % len(writers))
for va, what in writers[:24]:
    print("   0x%012x  %s" % (va, what))