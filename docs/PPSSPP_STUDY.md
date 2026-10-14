# PPSSPP reference study (partial, no code reused)

Status: source-level analogy only, not a WinePhone implementation or benchmark.
Repository revision `0b557116c29a07f608552c578a209db7bc57a27c` was fetched
sparsely into `J:\tmp\WinePhoneReferences\ppsspp`. `LICENSE.TXT` includes the
GPL-2.0 license; no code was copied.

## IR interpreter observation

`Core/MIPS/MIPS.cpp` selects `CPUCore::IR_INTERPRETER` and constructs
`MIPSComp::IRJit(this, false)`; `Core/CmdLine.cpp` exposes a command-line option
for the IR interpreter. This demonstrates a project-specific intermediate
representation execution mode without selecting the native JIT path. It does
not prove that the IR interpreter is fast enough for x86 Windows games or that
an equivalent FEX x86 interpreter exists.

## WinePhone use

The reusable idea is one guest execution interface with multiple backends and
a portable no-code-generation fallback. WinePhone still needs an x86-64
interpreter or a static-recompiler research path; PPSSPP's MIPS core cannot be
reused as an x86 implementation. No iOS JIT-detection path, Metal cache design,
or iOS frontend was audited in this partial pass. No interpreter/JIT timing
was measured.
