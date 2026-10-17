"""Every RIP-relative reference to a VA in .text, with the opcode that made it.

A data slot's writer is not always a store: it can be `lea` (compute a pointer,
store elsewhere), `mov`/`cmov`, or an arithmetic form. `pe-data-var.py` only
looked at stores with a disp32 and reported "0 writers" for 0x141006d40, which
was wrong -- the answer simply uses a different opcode. This scans for the whole
family: any ModRM with mod!=00 and r/m!=100 whose disp32 lands on the target,
prefixed by whatever REX/opcode sits in front.
"""
import struct
import sys

PE_PATH = sys.argv[1]
TARGET = int(sys.argv[2], 16)

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

text = next(s[1:] for s in sections if s[0] == ".text")
tva, tvsize, traddr, trsize = text


def off_to_va(off):
    for name, vaddr, vsize, raddr, rsize in sections:
        if raddr <= off < raddr + rsize:
            return image_base + vaddr + (off - raddr)
    return None


blob = data[traddr:traddr + trsize]

# One-byte opcodes that take a ModRM; multi-byte ones are added when a hit needs
# them. Two-byte opcodes starting 0F are mapped to a readable tag.
ONE = set(list(range(0x00, 0x04)) + [0x8B, 0x89, 0x8D, 0xC6, 0xC7, 0x01, 0x03, 0x29, 0x31, 0x39]
         + list(range(0x80, 0x84)) + list(range(0x88, 0x8F)) + list(range(0xB8, 0xC0))
         + [0xD0, 0xD1, 0xD3] + list(range(0xF6, 0xFE)))
TWO = {0xB6: "movzx", 0xB7: "movzx", 0xBE: "movsx", 0xBF: "movsx", 0xAF: "imul",
       0x1F: "nop", 0x1E: "nop", 0x05: "syscall"}

hits = []
i = 0
while i < len(blob) - 7:
    start = i
    tag = None
    for _ in range(4):                      # REX prefixes (max 1 real, but be safe)
        if blob[i] in (0x40, 0x41, 0x44, 0x45):
            i += 1
    op = blob[i]
    size = 1
    if op == 0x0F:
        tag = TWO.get(blob[i + 1], "0f%02x" % blob[i + 1])
        op = blob[i + 1]
        size = 2
    elif op in ONE:
        tag = "op%02x" % op
    if tag:
        modrm_at = i + size
        modrm = blob[modrm_at]
        mod = (modrm & 0xC0) >> 6
        rm = modrm & 7
        here = off_to_va(traddr + start)
        # RIP-relative is mod=00 with r/m=101 and a DISP32 -- the form almost
        # every string and global reference uses. Reading it as "[reg+disp32]"
        # (mod=10) is why an earlier pass reported 0 references for an address
        # that is demonstrably referenced.
        if mod == 0 and rm == 5:
            disp = struct.unpack_from("<i", blob, modrm_at + 1)[0]
            if here is not None and here + (modrm_at + 5 - start) + disp == TARGET:
                hits.append((here, tag + "/rip32"))
        elif mod == 2 and rm != 4:         # [reg + disp32]
            disp = struct.unpack_from("<i", blob, modrm_at + 1)[0]
            if here is not None and here + (modrm_at + 5 - start) + disp == TARGET:
                hits.append((here, tag + "/disp32"))
        elif mod == 1 and rm != 4:         # [reg + disp8]
            disp = struct.unpack_from("<b", blob, modrm_at + 1)[0]
            if here is not None and here + (modrm_at + 3 - start) + disp == TARGET:
                hits.append((here, tag + "/disp8"))
    i = max(start + 1, i + 1)

print("references to 0x%x: %d" % (TARGET, len(hits)))
for va, tag in hits[:40]:
    print("   0x%012x  %s" % (va, tag))