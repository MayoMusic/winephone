"""Find the site that says 'I am out of memory', by its argument signature.

The reporter takes (this, tag, totalFree, index) in rcx/rdx/r8/r9d, and
totalFree is the allocator's own counter at this+0x38. So the caller of the
report path is the one function that loads 0x38(%reg) into r8 and then makes an
indirect call or tail jump within a few instructions. That signature is narrow
enough to be an answer on its own, and it is what distinguishes the giving-up
site from every other allocator entry point.
"""
import struct
import sys

PE_PATH = sys.argv[1]
DISP = int(sys.argv[2], 0)      # the counter's offset within the object
DEST_REG = sys.argv[3] if len(sys.argv) > 3 else "r8"
WINDOW = int(sys.argv[4]) if len(sys.argv) > 4 else 32

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


# mov r/m64 -> r64 is 8B /r. mod=01 disp8 or mod=10 disp32; we want disp == DISP.
REGS = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"]
hits = []
for m in range(len(blob) - 4):
    i = m
    rex = 0
    for _ in range(4):
        if blob[i] in (0x40, 0x41, 0x44, 0x45):
            rex = blob[i]
            i += 1
    if blob[i] != 0x8B:
        continue
    # REX.W only. The counter is 64-bit (it is adjusted with `addq`), and a
    # 32-bit `movl 0x38(%r),%r8d` with the same displacement is a different
    # field entirely -- matching both returned a 32-bit predicate that has
    # nothing to do with the free counter.
    if not (rex & 0x08):
        continue
    modrm = blob[i + 1]
    mod = (modrm & 0xC0) >> 6
    reg = (modrm >> 3) & 7
    rm = modrm & 7
    if mod == 1 and rm != 4:
        disp = struct.unpack_from("<b", blob, i + 2)[0]
        after = i + 3
    elif mod == 2 and rm != 4:
        disp = struct.unpack_from("<i", blob, i + 2)[0]
        after = i + 6
    else:
        continue
    if disp != DISP:
        continue
    dst = "r%d" % (8 + reg) if rex & 0x04 else REGS[reg]
    src = "r%d" % (8 + rm) if rex & 0x01 else REGS[rm]
    hits.append((m, after, dst, src))

print("mov <obj+%#x>, %s: %d" % (DISP, DEST_REG, len(hits)))
matched = 0
for start, after, dst, src in hits:
    if dst != DEST_REG:
        continue
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
            if mod in (1, 2) and rm != 4:
                slot = (struct.unpack_from("<b", blob, k + 2)[0] if mod == 1
                        else struct.unpack_from("<i", blob, k + 2)[0])
                kind = "call" if (blob[k + 1] & 0x38) == 0x10 else "jmp"
                print("   0x%012x  mov 0x%x(%s), %s  ->  %s [%s+0x%x]  (+%d bytes)"
                      % (off_to_va(traddr + start), DISP, src, dst, kind, "reg", slot, k - start))
                matched += 1
                break
        j = k + 1
print("matches: %d" % matched)