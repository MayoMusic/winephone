"""Resolve a guest VA to its function using .pdata, then list its direct callers.

.pdata is the x64 exception directory: a flat array of RUNTIME_FUNCTION
{BeginAddress, EndAddress, UnwindInfo}, 12 bytes each, sorted by BeginAddress.
It is exact -- no prologue heuristics -- which matters when a heuristic would
mistake a function's own alignment padding for a new function.

Callers come from scanning .text for `E8 rel32`, the only direct-call encoding
in 64-bit mode. Indirect (register/memory) calls are not included, and the
caller list says so rather than pretending to be complete.
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

sections = {}
order = []
for i in range(nsec):
    o = sec + i * 40
    name = data[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, o + 8)
    sections[name] = (vaddr, vsize, raddr, rsize)
    order.append(name)

# The exception directory is data directory 3.
n_dd = struct.unpack_from("<I", data, opt + 108)[0]
dd = opt + 112
exc_rva, exc_size = struct.unpack_from("<II", data, dd + 3 * 8)


def rva_to_off(rva):
    for name, (vaddr, vsize, raddr, rsize) in sections.items():
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None


rva = VA - image_base
count = exc_size // 12
best = None
for i in range(count):
    off = rva_to_off(exc_rva + i * 12)
    if off is None:
        continue
    b, e, u = struct.unpack_from("<III", data, off)
    if b <= rva < e:
        best = (b, e, u)
        break

if best is None:
    print("no .pdata entry covers 0x%x" % VA)
    sys.exit(1)

fb, fe, unwind = best
fva = image_base + fb
print("function: 0x%x .. 0x%x  (0x%x bytes)  unwind=0x%x" % (fva, image_base + fe, fe - fb, unwind))
print("target VA 0x%x is +0x%x into it" % (VA, rva - fb))
print()

tva, tvsize, traddr, trsize = sections[".text"]
blob = data[traddr:traddr + trsize]
callers = []
for i in range(len(blob) - 5):
    if blob[i] == 0xE8:
        disp = struct.unpack_from("<i", blob, i + 1)[0]
        here = image_base + tva + i
        if here + 5 + disp == fva:
            callers.append(here)

print("direct call sites to 0x%x (%d):" % (fva, len(callers)))
for c in callers:
    print("   0x%012x" % c)