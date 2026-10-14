#!/usr/bin/env bash
# Static portability search. Hits require manual reachability/source review.
set -u
cd "$(dirname "$0")/.."

targets=(wine FEX dxmt app)
for target in "${targets[@]}"; do
  if [[ ! -d "$target" ]]; then
    printf 'SKIP %s (directory absent or submodule not checked out)\n' "$target"
    continue
  fi
  printf '\n===== %s: process creation / IPC =====\n' "$target"
  rg -n --hidden --glob '!**/.git/**' 'fork\(|execve|execv\(|posix_spawn|vfork\(|socketpair|AF_UNIX' "$target" || true
  printf '\n===== %s: executable memory / JIT =====\n' "$target"
  rg -n --hidden --glob '!**/.git/**' 'PROT_EXEC|MAP_JIT|mprotect|pthread_jit_write_protect|sys_icache_invalidate' "$target" || true
  printf '\n===== %s: exceptions =====\n' "$target"
  rg -n --hidden --glob '!**/.git/**' 'sigaction|SIGSEGV|SIGBUS|SIGILL|mach_exception|task_set_exception_ports' "$target" || true
  printf '\n===== %s: address-space assumptions =====\n' "$target"
  rg -n --hidden --glob '!**/.git/**' 'MAP_FIXED|vm_allocate|0x7fff|reserve.{0,24}(low|4GB)|mmap\(.{0,80}0x' "$target" || true
  printf '\n===== %s: dynamic loading =====\n' "$target"
  rg -n --hidden --glob '!**/.git/**' 'dlopen|dlsym|NSBundle load' "$target" || true
  printf '\n===== %s: macOS-only APIs =====\n' "$target"
  rg -n --hidden --glob '!**/.git/**' 'AppKit|NSScreen|NSWindow|CGDisplay|IOKit|MTLGPUFamilyMac|TARGET_OS_OSX' "$target" || true
done
