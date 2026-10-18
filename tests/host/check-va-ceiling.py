#!/usr/bin/env python3
"""Answer "who owns the untracked PROT_NONE regions", and keep the three fixes
that came out of the 2026-10-18 12:39 run from silently regressing.

That run (build a4c5dbca1f3d, ROTTR on iPhone18,3 / iOS 27.0.1) produced:

  [va-limit] ml749 walk=0x8000000000 kernel_max=0x7180000000 -> keeping walk
  [va-profile] post-limit host_addr_space_limit=0x8000000000 user_space_limit=0x8000000000
  [va-scan] FAILED window=0x7020000000..0x73ffff0000 size=0x800000 ... tries=163724
             skips=12 ... firstfail=0x70dc010000 errno=17(File exists) stage=fixed-map
             err=3 OCCUPIED 0x70dc010000+0x4000000 prot=0/7 shared=0
  [fex-arena] ml799 RESERVED 4GB @32-48G base=0x7038010000 size=0x100000000 -- held
              natively as PROT_NONE for the process lifetime and registered FEX_ONLY

Three separate facts, one window:

  1. The "untracked" 64MB/16MB/8MB regions are the ARENA'S UNCUT RESERVATION, not a
     foreign owner: every distinct OCCUPIED range sits inside
     [0x7038010000, 0x7138010000), and prot=0/7 (current VM_PROT_NONE, max
     VM_PROT_ALL) is exactly the signature of the mach_vm_map(PROT_NONE,
     VM_PROT_ALL) in ios_reserve_fex_arena. The arena is a RESERVED AREA, so the
     views tree the scanner walks cannot see it, and the uncarved remainder
     between two carved slices is reported by mach_vm_region in whatever size is
     left (64MB, 16MB, 8MB, 176KB in that run). map_reserved_area has already
     declined the request by the time the generic scan runs, so the scan must
     JUMP the arena instead of probing it a granule at a time.
  2. tries=163724 with skips=12 is not occupancy: it is the scan crawling the part
     of its window that lies ABOVE TASK_VM_INFO.max_address, where mach_vm_region
     finds nothing to skip and mach_vm_map refuses every fixed placement
     (kr=3). ml787 already clamps its CENSUS to max_address; the scanner was never
     told, and the same run's 53.9s stall watch is what that costs.
  3. committed=774MB of a 768MB range is a call sum, not a union: Windows lets a
     program re-commit pages it already holds, so 100% proved nothing about
     whether the range was full.

Textual: no Wine to run, and the strings below are what a reader greps for in the
log. Compiler-backed checks live elsewhere.
"""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
src = (root / 'build/ntdll-unix/virtual_ios.c').read_text()
proc = (root / 'build/ntdll-unix/process_ios.c').read_text()

failures = []


def body(text, name):
    """The definition of `name`, balanced. Same helper shape as check-map-fail.py."""
    head = re.compile(r'^[A-Za-z_][A-Za-z0-9_ \*]*\b' + re.escape(name) + r'\s*\(')
    for m in re.finditer(re.escape(name) + r'\s*\(', text):
        start = text.rindex('\n', 0, m.start()) + 1
        if not head.match(text[start:text.index('\n', m.start())]):
            continue
        close = text.index(')', m.end())
        if text[close + 1:].lstrip()[:1] != '{':
            continue
        open_brace = text.index('{', close)
        depth, i = 0, open_brace
        while True:
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
            i += 1
    raise AssertionError('no definition of %s found' % name)


def check(what, cond):
    print(('ok   ' if cond else 'FAIL ') + what)
    if not cond:
        failures.append(what)


# --- 1. the arena is jumped, not probed -------------------------------------
try_area = body(src, 'try_map_free_area')
check('try_map_free_area knows the FEX arena by its base and end',
      'ios_fex_arena_base_unix' in try_area and 'ios_fex_arena_end_unix' in try_area)
check('the arena skip is a jump, both directions',
      try_area.count('continue;') >= 3
      and 'ab - size' in try_area and 'ae + (size_t)step - 1' in try_area)
probe = try_area.index('anon_mmap_tryfixed( start, size, unix_prot, 0 )')
skip = try_area.index('ios_fex_arena_base_unix')
check('the arena skip happens before the probe, not after a refused mmap',
      skip < probe)
check('the skip says why, in the log, once per site',
      'SKIP scan over the FEX_ONLY arena' in try_area
      and 'uncarved PROT_NONE reservation, not a view' in try_area)
check('the arena globals are file-scope, not a local copy',
      '\nULONG_PTR ios_fex_arena_base_unix = 0;' in src
      and '\nULONG_PTR ios_fex_arena_end_unix = 0;' in src)

# --- 2. nothing scans above the task's own map ------------------------------
task_end = body(src, 'ios_scan_task_end')
check('ios_scan_task_end asks the kernel, not a constant',
      'TASK_VM_INFO' in task_end and 'vmi.max_address' in task_end)
check('an unknown max_address makes the clamp a no-op',
      '~(ULONG_PTR)0' in task_end and 'vmi.max_address < 0x100000000ULL' in task_end)
check('ios_scan_task_end is declared before map_free_area_inner uses it',
      src.index('static ULONG_PTR ios_scan_task_end( void )')
      < src.index('ULONG_PTR task_end = ios_scan_task_end();'))
inner = body(src, 'map_free_area_inner')
check('the scanner clamps its window to the task map',
      'ULONG_PTR task_end = ios_scan_task_end();' in inner
      and 'end = (void *)task_end;' in inner)
check('an emptied window is named, not silently empty',
      'ios_scan_stop = 10' in inner and 'case 10: return "window-above-task-map";' in src)
check('the clamp is reported, so the log keeps both geometries',
      '[va-ceiling]' in inner)
view = body(src, 'map_view')
check('map_view clamps the search bound it prints, so the FAILED window is honest',
      '[va-ceiling] ml1219 search window end' in view
      and 'ULONG_PTR task_end = ios_scan_task_end();' in view)
check('the clamp only lowers the search bound, never the advertised limit',
      'host_addr_space_limit =' not in view and 'user_space_limit =' not in view)

# --- 3. committed-in-a-range is a union, not a call sum ---------------------
commit = body(src, 'ios_bigres_commit')
check('ios_bigres_commit records both the call sum and the page union',
      '.committed += size' in commit and '.union_bytes += IOS_BIGRES_GRANULE' in commit)
check('only newly set granules add to the union',
      'if (!(*w & m))' in commit)
check('the granule is the allocator\'s own page size',
      '#define IOS_BIGRES_GRANULE (4u << 20)' in src)
check('a range too large for the bitmap is capped, not overrun',
      'IOS_BIGRES_WORDS * 64' in commit and 'bits[IOS_BIGRES_WORDS]' in src)
note = body(src, 'ios_bigres_note')
check('a reused table slot cannot inherit a stale bitmap',
      'memset( &ios_bigres_tab[ios_bigres_cnt], 0' in note)
report = body(src, 'ios_bigres_report')
check('the report distinguishes the call sum from the union',
      'call sum' in report and 'union=%llu MB' in report and 'pages' in report
      and 'reserved=%llu MB' in report)
check('a pool line carries the union too, since a pool is where 100% was misread',
      report.count('union=%lluMB') >= 1)

# --- 4. every termination is logged, with the last refusal ------------------
term = body(proc, 'NtTerminateProcess')
always = term.index('[term] #%lu handle=%p exit=%08x self=%d')
budget = term.index('if (term_log_count < 16')
check('NtTerminateProcess has an unbudgeted line per call', always >= 0)
check('the per-call line comes before the budgeted dump', always < budget)
check('the per-call line names the caller as module+RVA, which is what was asked',
      'caller=%s' in term and 'ios_guest_caller_string( term_rip, caller, sizeof(caller) );' in term)
check('the last refusal is in the per-call line',
      'last-refused: %s' in term and 'ios_lastfail_summary( lastfail, sizeof(lastfail) );' in term)
check('the full dump prints the refusal ring',
      'ios_lastfail_dump( "NtTerminateProcess" );' in term)
check('the budget no longer leaves a death unlogged',
      'term_log_count < 16' in term and 'term_log_count < 64' in term)

check('the ring is defined once, non-static, so the terminate path can link it',
      '\nvoid ios_lastfail_note( const char *tag, unsigned long long size, unsigned status, unsigned type )' in src
      and '\nvoid ios_lastfail_summary( char *buf, size_t len )' in src
      and '\nvoid ios_lastfail_dump( const char *why )' in src)
check('the ring is a ring: the newest refusal survives a retry chain',
      '#define IOS_LASTFAIL_MAX 4' in src and 'ios_lastfail_seq % IOS_LASTFAIL_MAX' in src)
check('one caller formatter, non-static, shared by [term] and [alloc-last]',
      '\nvoid ios_guest_caller_string( unsigned long long rip, char *buf, size_t len )' in src
      and 'ios_guest_caller_string( out[i].rip, caller, sizeof(caller) );' in body(src, 'ios_lastfail_dump'))
check('an unattributed caller prints its raw address, not a name+0',
      'not in any registered image' in body(src, 'ios_guest_caller_string'))
check('the summary reports size and status, which is what was asked for',
      'size=0x%llx status=%08x type=0x%x tid=%04x seq=%llu' in src)
check('nothing is refused without being recorded -- even outside the print budget',
      body(src, 'NtAllocateVirtualMemory').index('ios_lastfail_note( "alloc-fail"')
      < body(src, 'NtAllocateVirtualMemory').index('if (n <= 64')
      and body(src, 'NtAllocateVirtualMemoryEx').index('ios_lastfail_note( "alloc-fail-ex"')
      < body(src, 'NtAllocateVirtualMemoryEx').index('if (i2 <= 64')
      and body(src, 'ios_map_fail').index('ios_lastfail_note( "map-fail"')
      < body(src, 'ios_map_fail').index('if (i <= 32'))
check('[footprint] carries the number jetsam actually decides on',
      'avail=%llu MB' in src and 'os_proc_available_memory' in src)

print('PASS' if not failures else 'FAILED: ' + '; '.join(failures))
raise SystemExit(0 if not failures else 1)
