"""Name every imported call made inside a VA range.

`callq *disp(%rip) # 0x140d0xxxx` is an indirect call through the IAT. Inside a
function's byte range, collecting those targets and resolving them through the
import directory says what that code calls from outside the module -- which is
the only place the name of an API actually appears.
"""
import struct
import sys

PE_PATH = sys.argv[1]
LO = int(sys.argv[2], 16)
HI = int(sys.argv[3], 16)

data = open(PE_PATH, "rb").read()
pe = struct.unpack_from("<I", data, 0x3c)[0]
nsec = struct.unpack_from("<H", data, pe + 6)[0]
optsz = struct.unpack_from("<H", data, pe + 20)[0]
opt = pe + 24
image_base = struct.unpack_from("<Q", data, opt + 24)[0]
sec = opt + optsz
dd = opt + 112

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


def cstr(off):
    return data[off:data.index(b"\0", off)].decode("ascii", "replace")


iat = {}
imp_rva, _ = struct.unpack_from("<II", data, dd + 8)
off = rva_to_off(imp_rva)
i = 0
while True:
    o = off + i * 20
    ilt, ts, fchain, name_rva, iat_rva = struct.unpack_from("<IIIII", data, o)
    if not name_rva:
        break
    dll = cstr(rva_to_off(name_rva))
    toff = rva_to_off(ilt or iat_rva)
    k = 0
    while True:
        entry = struct.unpack_from("<Q", data, toff + k * 8)[0]
        if not entry:
            break
        slot = image_base + iat_rva + k * 8
        nm = ("ordinal %d" % (entry & 0xffff)) if entry & (1 << 63) \
            else cstr(rva_to_off(entry & 0x7fffffff) + 2)
        iat[slot] = "%s!%s" % (dll, nm)
        k += 1
    i += 1

text = next(s for s in sections if s[0] == ".text")
tva, tvsize, traddr, trsize = text[1], text[2], text[3], text[4]
blob = data[traddr:traddr + trsize]

lo_rva, hi_rva = LO - image_base, HI - image_base
found = {}
for i in range(len(blob) - 7):
    here = image_base + tva + i
    if not (LO <= here < HI):
        continue
    if blob[i] == 0xFF and blob[i + 1] == 0x15:            # call *[rip+disp32]
        disp = struct.unpack_from("<i", blob, i + 2)[0]
        slot = here + 6 + disp
        if slot in iat:
            found.setdefault(iat[slot], []).append(here)

for name in sorted(found):
    sites = found[name]
    print("%-46s x%-3d  first 0x%x" % (name, len(sites), sites[0]))