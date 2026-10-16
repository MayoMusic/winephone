"""Resolve IAT slots and call targets to imported function names.

`callq *0x93d840(%rip) # 0x140d02590` in a disassembly is an indirect call
through the import address table; nothing in the instruction says which
function. Parsing the import directory and mapping the slot VA back to the
name is what turns it into an answer.
"""
import struct
import sys

PE_PATH = sys.argv[1]
WANTED = [int(a, 16) for a in sys.argv[2:]]

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


imp_rva, imp_size = struct.unpack_from("<II", data, dd + 1 * 8)
iat = {}
off = rva_to_off(imp_rva)
i = 0
while True:
    o = off + i * 20
    ilt, ts, fchain, name_rva, iat_rva = struct.unpack_from("<IIIII", data, o)
    if not name_rva:
        break
    dll = cstr(rva_to_off(name_rva))
    thunk = ilt or iat_rva
    toff = rva_to_off(thunk)
    ioff = rva_to_off(iat_rva)
    k = 0
    while True:
        entry = struct.unpack_from("<Q", data, toff + k * 8)[0]
        if not entry:
            break
        slot = image_base + iat_rva + k * 8
        if entry & (1 << 63):
            nm = "ordinal %d" % (entry & 0xffff)
        else:
            nm = cstr(rva_to_off(entry & 0x7fffffff) + 2)
        iat[slot] = "%s!%s" % (dll, nm)
        k += 1
    i += 1

print("imports parsed:", len(iat))
if WANTED:
    for w in WANTED:
        print("  0x%x -> %s" % (w, iat.get(w, "<not an IAT slot>")))
else:
    for k in sorted(iat):
        print("  0x%x  %s" % (k, iat[k]))