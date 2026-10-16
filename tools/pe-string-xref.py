"""Read the full string at a VA, then find every RIP-relative LEA in .text that
targets it.

x64 code reaches a string with `lea reg,[rip+disp32]`: 48/4C 8D <modrm> rel32
with mod=00 and r/m=101. That is the whole reference set for a string in a
non-stripped x64 PE, so the xrefs are exact rather than heuristic.
"""
import re
import struct
import sys

PE_PATH = sys.argv[1]
TARGET_VA = int(sys.argv[2], 16)

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


def va_to_off(va):
    rva = va - image_base
    for name, vaddr, vsize, raddr, rsize in sections:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None


def off_to_va(off):
    for name, vaddr, vsize, raddr, rsize in sections:
        if raddr <= off < raddr + rsize:
            return image_base + vaddr + (off - raddr)
    return None


def cstring_at(va):
    off = va_to_off(va)
    if off is None:
        return "<unmapped>"
    end = data.index(b"\0", off)
    return data[off:end].decode("ascii", "replace")


print("target VA 0x%x -> file %s" % (TARGET_VA, hex(va_to_off(TARGET_VA)) if va_to_off(TARGET_VA) else "?"))
# Walk back to the start of the NUL-terminated run that contains the target.
off = va_to_off(TARGET_VA)
start = off
while start > 0 and data[start - 1] != 0:
    start -= 1
whole = data[start:data.index(b"\0", start)].decode("ascii", "replace")
print("whole string at 0x%x: %s" % (off_to_va(start), whole))
print()

# lea r64,[rip+disp32] = [REX.W] 8D modrm(rel32) with mod=00 r/m=101
text = next(s for s in sections if s[0] == ".text")
name, vaddr, vsize, raddr, rsize = text
blob = data[raddr:raddr + rsize]

hits = []
i = 0
while i < len(blob) - 7:
    rex = blob[i]
    if rex in (0x48, 0x4C) and blob[i + 1] == 0x8D:
        modrm = blob[i + 2]
        if (modrm & 0xC7) == 0x05:          # mod=00, r/m=101 -> RIP-relative
            disp = struct.unpack_from("<i", blob, i + 3)[0]
            insn_va = off_to_va(raddr + i)
            target = insn_va + 7 + disp
            if target == TARGET_VA:
                reg = (modrm >> 3) & 7
                reg = ("rax rdx rbx rsp rbp rsi rdi".split()[reg]
                       if rex == 0x48 else
                       "r8 r9 r10 r11 r12 r13 r14 r15".split()[reg])
                hits.append((insn_va, reg))
    i += 1

print("xrefs to 0x%x (%d):" % (TARGET_VA, len(hits)))
for va, reg in hits:
    print("   0x%012x  lea %s,[rip+...]" % (va, reg))