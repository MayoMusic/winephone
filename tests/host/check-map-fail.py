#!/usr/bin/env python3
"""[map-fail] / [map-rate] / [alloc-fail-ex] name the memory requests that used to vanish.

ROTTR.exe on iPhone18,3 / iOS 27.0.1 (cores=2, pool=512) reaches the main menu
and then aborts in its own allocator -- "Out of memory, UNKNOWN requested
112460 bytes (1010343740 total free = 963.5 MB)". Three logs had zero
[alloc-fail], so the reading was "the kernel was never asked". That reading was
wrong twice over, and this check exists so it cannot be repeated:

  1. [alloc-fail] ml814 lives only in NtAllocateVirtualMemory. FEX's ARM64EC
     AllocatorHooks call ::VirtualAlloc2, i.e. NtAllocateVirtualMemoryEx, which
     had no failure line at all -- so "zero [alloc-fail]" was never a
     measurement of both guest allocation entry points.
  2. NtMapViewOfSection and NtMapViewOfSectionEx both ended in a bare
     `return virtual_map_section( ... );` with no log on any failing return,
     so a refused section mapping -- what a streaming allocator asks for --
     left no trace.

Textual: there is no Wine to run, and the format strings are what a reader
greps for. The macOS build job compiles this code with -Werror, which is what
catches a type or scope mistake; this check catches a hook being dropped again.
Needs python3 only.
"""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
src = (root / 'build/ntdll-unix/virtual_ios.c').read_text()
catalog = (root / 'app/Madeira/ConfigCatalog.generated.swift').read_text()

failures = []


def body(name):
    """The braces of the DEFINITION of name, matched from its opening brace.

    Definitions in this file sit at column 0 behind a return type and are
    followed by `{` on the next line; forward declarations end in `;` and every
    other mention of the name is an indented call site or a comment. Requiring
    all three is what tells them apart.
    """
    head = re.compile(r'^[A-Za-z_][A-Za-z0-9_ \*]*\b' + re.escape(name) + r'\s*\(')
    for m in re.finditer(re.escape(name) + r'\s*\(', src):
        start = src.rindex('\n', 0, m.start()) + 1
        if not head.match(src[start:src.index('\n', m.start())]):
            continue
        close = src.index(')', m.end())
        if src[close + 1:].lstrip()[:1] != '{':
            continue
        open_brace = src.index('{', close)
        depth, i = 0, open_brace
        while True:
            if src[i] == '{':
                depth += 1
            elif src[i] == '}':
                depth -= 1
                if depth == 0:
                    return src[start:i + 1]
            i += 1
    raise AssertionError('no definition of %s found' % name)


def check(what, cond):
    print(('ok   ' if cond else 'FAIL ') + what)
    if not cond:
        failures.append(what)


for entry in ('NtMapViewOfSection', 'NtMapViewOfSectionEx'):
    text = body(entry)
    check('%s no longer returns virtual_map_section bare' % entry,
          not re.search(r'return\s+virtual_map_section\(', text))
    check('%s routes every exit through ios_map_fail' % entry,
          text.count('ios_map_fail(') >= 2)
    check('%s counts both outcomes with ios_map_note_map' % entry,
          text.count('ios_map_note_map(') >= 2)
    check('%s takes the exit status from a local, not the call itself' % entry,
          'unsigned int st = virtual_map_section(' in text)
    # The APC path returns through result.map_view*.status, which must be
    # reported too -- a cross-process map fails there, not at the local call.
    check('%s reports the cross-process APC status' % entry,
          'result.map_view' in text and text.count('ios_map_fail(') >= 4)

alloc = body('NtAllocateVirtualMemory')
check('NtAllocateVirtualMemory still has ml814 and now counts too',
      '[alloc-fail] ml814' in alloc and 'ios_map_note_alloc(' in alloc)

alloc_ex = body('NtAllocateVirtualMemoryEx')
check('NtAllocateVirtualMemoryEx has the failure line it never had',
      '[alloc-fail-ex] ml1217' in alloc_ex)
check('NtAllocateVirtualMemoryEx counts too', 'ios_map_note_alloc(' in alloc_ex)
# The two tags must stay distinguishable: ml814's name is what three earlier
# logs were grepped by, so reusing it for the Ex path would silently change
# what an old result means. Compare the format strings, not the prose, which
# names both tags on purpose.
tags = set(re.findall(r'"\[alloc-fail(?:-ex)?\][^"]*"', alloc + alloc_ex))
check('the two allocation failure tags are distinct and both present',
      len(tags) == 2 and any('[alloc-fail]' in t for t in tags)
      and any('[alloc-fail-ex]' in t for t in tags))

# [map-fail] must be ungated: a refusal is rare and a missing line is exactly
# the ambiguity this change exists to remove.
fail_fn = src[src.index('static void ios_map_fail('):]
fail_fn = fail_fn[:fail_fn.index('\n}\n')]
check('[map-fail] is not gated on map-trace', 'ios_map_trace_on' not in fail_fn)
check('[map-fail] prints the first 32 in full, then every 32nd',
      'i <= 32' in fail_fn and '(i % 32) == 0' in fail_fn)
check('[map-fail] names the request, the footprint and the swap tier',
      all(token in fail_fn for token in
          ('size=0x%llx', 'off=0x%llx', 'alloc_type=0x%x', 'protect=0x%x',
           'footprint=%llu MB', 'not-applicable', 'refused=%llu')))
check('[map-fail] says the swap tier cannot decide a section map',
      'virtual_map_section never calls ios_swap_commit' in fail_fn)

rate = src[src.index('static void ios_map_rate( void )\n{'):]
rate = rate[:rate.index('\n}\n')]
check('[map-rate] resets its window, so the counts are per second',
      '__atomic_exchange_n' in rate and '1000000000ull' in rate)
check('[map-rate] counts both allocation and both section-map outcomes',
      all(k in rate for k in ('ios_alloc_ok', 'ios_alloc_bad', 'ios_map_ok', 'ios_map_bad')))
gate = 'if (ios_map_trace_on()) ios_map_rate();'
check('[map-rate] is reached only through the gate, from both note helpers',
      src.count('ios_map_rate();') == 2 and all(
          gate in body(fn) for fn in ('ios_map_note_alloc', 'ios_map_note_map')))

check('map-trace is read from madeira.cfg', 'madeira_cfg_int( "map-trace", 0 )' in src)
check('map-trace appears in Settings', 'key: "map-trace"' in catalog)

# Build fcb453c failed on exactly this: the forward declaration sat AFTER the
# first call, so clang took an implicit non-static declaration from the call
# and rejected the later "static" one. Cheap to assert, expensive to rediscover.
decl = src.index('static void ios_map_note_alloc( int ok );')
check('ios_map_note_alloc is declared before its first call',
      decl < src.index('ios_map_note_alloc( st == STATUS_SUCCESS )'))
check('the declaration is above NtAllocateVirtualMemory, which calls it',
      decl < src.index('NTSTATUS WINAPI NtAllocateVirtualMemory('))
check('ios_map_fail prints its hint as a pointer, not a ULONG_PTR',
      'const void *hint' in fail_fn and 'ULONG_PTR hint' not in fail_fn)

print('PASS' if not failures else 'FAILED: ' + '; '.join(failures))
raise SystemExit(0 if not failures else 1)