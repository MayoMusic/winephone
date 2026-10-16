"""Find indirect calls through a vtable slot: `call/jmp qword ptr [reg+disp8]`.

A virtual method with no direct callers is reached through the vtable, so the
call site encodes the slot index, not a target address. Encoding for
`call/jmp [reg+disp8]` is FF /2 (call) or FF /4 (jmp) with mod=01: modrm =
0x50|rm or 0x70|rm, so the slot byte is (modrm-0x50) for call and (modrm-0x70)
for jmp, with the displacement following. REX.B widens rm to r8..r15.

Both opcodes matter: a tail call is `jmp *slot(%rax)` and has no `call` at all,
which is why a scan for `call` alone reports a method that is demonstrably
reached 270 times.
"""
import struct
import sys

PE_PATH = sys.argv[1]
SLOT = int(sys.argv[2], 0)

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


def off_to_va(off):
    for name, vaddr, vsize, raddr, rsize in sections:
        if raddr <= off < raddr + rsize:
            return image_base + vaddr + (off - raddr)
    return None


def is_code_va(va):
    rva = va - image_base
    for name, vaddr, vsize, raddr, rsize in sections:
        if name == ".text" and vaddr <= rva < vaddr + vsize:
            return True
    return False


tva, tvsize, traddr, trsize = next(s[1:] for s in sections if s[0] == ".text")
blob = data[traddr:traddr + trsize]

REGS = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"]

hits = []
i = 0
while i < len(blob) - 3:
    start = i
    rex = 0
    if blob[i] in (0x40, 0x41, 0x44, 0x45):
        rex = blob[i]
        i += 1
    if i + 6 < len(blob) and blob[i] == 0xFF and (blob[i + 1] & 0xC0) >> 6 in (1, 2):
        op = (blob[i + 1] >> 3) & 7
        kind = {2: "call", 4: "jmp"}.get(op)
        modrm = blob[i + 1]
        mod = (modrm & 0xC0) >> 6
        rm = modrm & 7
        if kind and rm != 4:                      # rm=100 is disp32, not [reg]
            reg = REGS[rm]
            if rex & 0x01:
                reg = "r%d" % (8 + rm)
            if mod == 1:                          # [reg + disp8]
                disp = struct.unpack_from("<b", blob, i + 2)[0]
                size = 3
            else:                                  # [reg + disp32]
                disp = struct.unpack_from("<i", blob, i + 2)[0]
                size = 6
            if disp == SLOT:
                hits.append((off_to_va(traddr + start), reg, kind))
    i = max(start + 1, i + 1)

print("call/jmp [reg+0x%x] sites: %d  (%d call, %d jmp)"
      % (SLOT, len(hits), sum(1 for h in hits if h[2] == "call"),
         sum(1 for h in hits if h[2] == "jmp")))
for va, reg, kind in hits:
    print("   0x%012x  %s [%s+0x%x]" % (va, kind, reg, SLOT))