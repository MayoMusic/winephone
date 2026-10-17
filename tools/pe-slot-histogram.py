"""Which vtable slot does code dispatch after loading a global object?

`movq <singleton>(%rip), %rax` then `callq *0x48(%rax)` is how a game reaches its
allocator. The singleton is referenced thousands of times, so reading the calls
one at a time is hopeless; tallying the slot displacement shows which entry
points matter and, because a FAILURE path is only taken when an allocation
fails, which slot is the rare one.

The walk is bounded to the bytes before the next return-ish boundary, because a
longer window picks up unrelated calls made after the object is dead.
"""
import struct
import sys
from collections import Counter

PE_PATH = sys.argv[1]
SINGLETON = int(sys.argv[2], 16)
WINDOW = int(sys.argv[3]) if len(sys.argv) > 3 else 48

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
blob = data[traddr:traddr + trsize]


def off_to_va(off):
    for name, vaddr, vsize, raddr, rsize in sections:
        if raddr <= off < raddr + rsize:
            return image_base + vaddr + (off - raddr)
    return None


# Every RIP-relative load of the singleton.
loads = []
for m in range(0, len(blob) - 7):
    start = m
    i = m
    for _ in range(4):
        if blob[i] in (0x40, 0x41, 0x44, 0x45):
            i += 1
    if blob[i] != 0x8B:
        continue
    modrm = blob[i + 1]
    if (modrm & 0xC0) >> 6 != 0 or (modrm & 7) != 5:
        continue
    disp = struct.unpack_from("<i", blob, i + 2)[0]
    here = off_to_va(traddr + start)
    if here is not None and here + (i + 6 - start) + disp == SINGLETON:
        loads.append((start + 6, modrm >> 3 & 7, modrm >> 6 & 7))   # (after load, dst, rex.R)

print("singleton loads: %d" % len(loads))

hist = Counter()
rare = {}
for after, dst, _ in loads:
    j = after
    end = min(after + WINDOW, len(blob) - 7)
    while j < end:
        k = j
        for _ in range(4):
            if blob[k] in (0x40, 0x41, 0x44, 0x45):
                k += 1
        if blob[k] == 0xFF and (blob[k + 1] & 0x38) in (0x10, 0x20):
            modrm = blob[k + 1]
            mod = (modrm & 0xC0) >> 6
            rm = modrm & 7
            if mod == 1 and rm != 4:
                slot = struct.unpack_from("<b", blob, k + 2)[0]
            elif mod == 2 and rm != 4:
                slot = struct.unpack_from("<i", blob, k + 2)[0]
            else:
                j = k + 1
                continue
            hist[slot] += 1
            rare.setdefault(slot, []).append(off_to_va(traddr + j))
            break
        j = k + 1

print("%-10s %8s" % ("slot", "count"))
for slot, n in hist.most_common(24):
    print("  +0x%-6x %6d   first %s" % (slot, n, "0x%x" % rare[slot][0]))
print()
print("rarest slots (failure paths live here):")
for slot, n in hist.most_common()[-8:]:
    print("  +0x%-6x %6d   first 0x%x" % (slot, n, rare[slot][0]))