// wine_stubs.c - Provide missing symbols for Wine on iOS

#include <CoreFoundation/CoreFoundation.h>

// Wine build version string (normally generated at compile time)
const char wine_build[] = "wine-10.0-ios";

// IOPowerSources stubs - not available on iOS
CFTypeRef IOPSCopyPowerSourcesInfo(void) { return NULL; }
CFArrayRef IOPSCopyPowerSourcesList(CFTypeRef blob) { (void)blob; return NULL; }
CFDictionaryRef IOPSGetPowerSourceDescription(CFTypeRef blob, CFTypeRef ps) {
    (void)blob; (void)ps; return NULL;
}

/* ---------------------------------------------------------------------------
 * Symbols the native link needs but that only exist in the Windows PE-module
 * builds of FEX, or in ncurses. Every one below is accounted for; none is a
 * guess. See BLOCKERS.md B-019.
 *
 * FEX's own source states the contract for IosSubfloorToReal, at
 * FEXCore/Source/Interface/Core/Frontend.cpp:1344-1348: "Addr unchanged when it
 * is not inside a registered sub-floor window, so the fast path is one compare."
 * Sub-floor aliasing is created by Source/Windows/ARM64EC/IosJitAlias.cpp:279
 * and Source/WOW64/Module.cpp:2089, which belong to the PE-module builds the
 * native app does not link. On the native path no window is ever registered, so
 * the documented behaviour is the identity function.
 * ------------------------------------------------------------------------- */

#include <stdint.h>

uint64_t IosSubfloorToReal(uint64_t Addr) { return Addr; }

/* The Mono (Android .ART) backpatcher and its bridge counters. The iOS runtime
 * never instantiates Mono, so these are instrumentation with no consumer. */
unsigned long long IosMonoResolveRW(void) { return 0; }
void      ios_fex_mono_bridge_armed(void) {}
void      ios_fex_mono_captured_count(void) {}
void      ios_fex_mono_count_activated(void) {}
void      ios_fex_mono_count_helper(void) {}
void      ios_fex_mono_take_pending(void) {}

/* Only read on FEX's allocation-failure path (fextl::ReportAllocationFailure),
 * to bracket the band in the log line. 0 means "not set". */
unsigned long long ios_fex_band_base(void) { return 0; }
unsigned long long ios_fex_band_end(void) { return 0; }

/* rpmalloc's compare-and-swap snapshot: the FEX fork adds it for the ARM64EC
 * module, and the native allocator has no snapshot to take. */
int rpm_cas_snapshot_take(void) { return 0; }

/* LLVM's llvm::sys::Process::FileDescriptorHasColors calls the terminfo API.
 * ncurses does not exist on iOS, and the only consumer is colour detection for
 * a diagnostic, so "no colour" is the faithful answer rather than a fake term. */
int setupterm(const char *t, int fd, int *err) { if (err) *err = -1; return -1; }
int set_curterm(int fd) { return -1; }
int del_curterm(int fd) { (void)fd; return 0; }
int tigetnum(const char *cap) { (void)cap; return -1; }

/* The D3D12 conversion path is excluded from this tree on licensing grounds
 * (DECISIONS.md D-002) and scripts/build-ipa.sh refuses to ship the converter,
 * but the app still calls into it. These report "not available" rather than
 * pretending a conversion happened, so the Swift call site keeps working and the
 * absence stays visible instead of becoming a silent success. */
int madeira_d3d12_canary_run_log(const char *fixture_dir, const char *dylib_path,
                                void (*sink)(const char *), const char *log_path,
                                const char *build_id)
{
    (void)fixture_dir; (void)dylib_path; (void)log_path; (void)build_id;
    if (sink) sink("d3d12: not built in WinePhone (excluded on licensing grounds)");
    return -1;
}

int madeira_ir_convert(const void *in, unsigned len, void *out, unsigned *out_len)
{
    (void)in; (void)len; (void)out;
    if (out_len) *out_len = 0;
    return -1;
}
