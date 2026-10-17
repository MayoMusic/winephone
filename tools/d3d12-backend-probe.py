"""Re-derive the D3D12 verdict from the tree, and from a game's own imports.

The question this answers is narrow and was previously answered wrongly:
COMPAT.md claimed D3D12 was excluded "for licensing", which is not what the tree
does -- `app/Madeira/*-windows/d3d12.dll` is a full Wine implementation and it
is built and shipped. What is missing is everything UNDER it.

Wine's d3d12 is a vkd3d front end: it speaks D3D12 to the guest and Vulkan to
whatever driver is underneath. So the backend is complete or not depending
entirely on whether a Vulkan device exists at run time. This script looks for
one, and reports what it found rather than assuming.

A loader is not a driver. `vulkan-1.dll` is the Khronos loader: it imports the
C runtime and kernel32 and nothing else, and it discovers the real driver
through an ICD manifest or the Khronos registry key. A payload carrying the
loader and no driver has no Vulkan device, which is the case that has to be
distinguished from "no vulkan at all" -- the first looks like support.

Usage:
    d3d12-backend-probe.py                       # just the tree
    d3d12-backend-probe.py "C:/Games/Some Game"  # and what a game imports

Exit status is 0 when the tree has a Vulkan driver and 1 when it does not, so
this can gate a claim. It never reports a game as playable; it reports which
backend that game's imports require and whether this build completes it.
"""
import os
import struct
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PAYLOADS = [os.path.join(ROOT, "app", "Madeira", "aarch64-windows"),
            os.path.join(ROOT, "app", "Madeira", "arm64ec-windows")]
# scripts/build-ipa.sh copies dxmt's PE output into arm64ec-windows, so that is
# the payload the IPA ships. A module present only in aarch64-windows is not on
# the device, and d3d12.dll is exactly that case.
SHIPPED = os.path.join(ROOT, "app", "Madeira", "arm64ec-windows")

VULKAN_DRIVERS = ("moltenvk", "swiftshader", "vk_swiftshader", "lavapipe", "lvp_")
ICD_MARKERS = ("vk_icd", "vulkan_driver", "khronos")
# The registry path a Vulkan ICD is discovered through. Searching for the bare
# word "Khronos" instead finds copyright headers and unrelated notes -- that is
# how the first version of this probe reported a registry setup that is not there.
ICD_REGISTRY = ("Vulkan\\Drivers", "Vulkan/Drivers", "SOFTWARE\\Khronos")


def pe_imports(path):
    """Imported DLL!symbol pairs, or [] if the file is not a readable PE."""
    try:
        data = open(path, "rb").read()
        if data[:2] != b"MZ":
            return []
        pe = struct.unpack_from("<I", data, 0x3c)[0]
        if data[pe:pe + 4] != b"PE\0\0":
            return []
        nsec = struct.unpack_from("<H", data, pe + 6)[0]
        optsz = struct.unpack_from("<H", data, pe + 20)[0]
        opt = pe + 24
        magic = struct.unpack_from("<H", data, opt)[0]
        dd = opt + (112 if magic == 0x20b else 96)
        imp_rva, imp_sz = struct.unpack_from("<II", data, dd + 8)
        secs = []
        for i in range(nsec):
            o = opt + optsz + i * 40
            _n, vs, va, rs, ra = struct.unpack_from("<IIIII", data, o + 4)[:5]
            secs.append((va, vs, ra, rs))

        def rva2off(rva):
            for va, vs, ra, rs in secs:
                if va <= rva < va + max(vs, rs):
                    return ra + (rva - va)
            return None

        off = rva2off(imp_rva)
        if off is None:
            return []
        out = []
        while True:
            fields = struct.unpack_from("<IIIII", data, off)
            name_rva, thunk = fields[3], fields[4]
            if not name_rva and not thunk:
                break
            no = rva2off(name_rva)
            if no is not None:
                end = data.index(b"\0", no)
                dll = data[no:end].decode("ascii", "replace")
                t = rva2off(thunk or fields[0])
                step = 8 if magic == 0x20b else 4
                fmt = "<Q" if magic == 0x20b else "<I"
                while t is not None:
                    val = struct.unpack_from(fmt, data, t)[0]
                    if not val:
                        break
                    if not (val & (1 << 63)):
                        so = rva2off(val & 0x7fffffff)
                        if so is not None:
                            he = data.index(b"\0", so + 2)
                            out.append("%s!%s" % (dll, data[so + 2:he].decode("ascii", "replace")))
                    t += step
            off += 20
        return out
    except Exception:                              # noqa: BLE001 - a probe, not a gate
        return []


def describe_pe(path, label):
    if not os.path.exists(path):
        print("  %-14s MISSING" % label)
        return None
    size = os.path.getsize(path)
    imports = pe_imports(path)
    hostish = [i for i in imports if i.split("!")[1].startswith(("Nt", "Zw", "Rtl"))]
    print("  %-14s %9d bytes, %d imports%s"
          % (label, size, len(imports),
             ", %d ntdll" % len(hostish) if hostish else ""))
    return size, imports


def main():
    print("== what the tree ships for D3D12 ==")
    have_d3d12 = {}
    for payload in PAYLOADS:
        tag = os.path.basename(payload)
        print(" %s" % tag)
        for name, label in (("d3d12.dll", "d3d12"), ("wined3d.dll", "wined3d")):
            r = describe_pe(os.path.join(payload, name), label)
            if r:
                have_d3d12.setdefault(label, []).append((tag, r[1]))

    for tag, imports in have_d3d12.get("d3d12", []):
        front = sorted({i.split("!")[0] for i in imports
                        if "vkd3d" in i or "vulkan" in i.lower()})
        print("  d3d12 -> %s" % (", ".join(front) if front else "(no vkd3d/vulkan import)"))

    print("\n== is there a Vulkan device underneath it? ==")
    drivers = []
    for root, _dirs, files in os.walk(os.path.join(ROOT, "app")):
        for f in files:
            low = f.lower()
            if any(m in low for m in VULKAN_DRIVERS):
                drivers.append(os.path.join(root, f))
            elif low.endswith(".json") and any(m in low for m in ICD_MARKERS):
                drivers.append(os.path.join(root, f))
    print("  translation or software driver found: %s"
          % (", ".join(os.path.relpath(d, ROOT) for d in drivers) if drivers else "NONE"))

    loaders = []
    for payload in PAYLOADS:
        for name in ("vulkan-1.dll", "winevulkan.dll"):
            path = os.path.join(payload, name)
            if not os.path.exists(path):
                continue
            imports = pe_imports(path)
            # A loader imports the CRT and kernel32 and stops. A driver imports
            # the loader. Nothing here tells us which, so measure it: if the
            # file resolved any Vulkan entry point itself, it is a driver.
            selfcontained = [i for i in imports if i.lower().startswith("vulkan-1!")]
            loaders.append((os.path.relpath(path, ROOT), os.path.getsize(path),
                            len(imports), len(selfcontained)))
    if not loaders:
        print("  vulkan loader: NONE")
    for path, size, nimp, nvk in loaders:
        print("  %-46s %9d bytes, %d imports, %d resolved vulkan symbols"
              % (path, size, nimp, nvk))
        print("     -> %s" % ("a loader: it needs an ICD and there is none"
                              if nvk == 0 else "resolves Vulkan symbols itself"))

    # The registry half of ICD discovery. The path, not the word "Khronos":
    # matching that alone finds FEX's glcorearb copyright and a comment in
    # build-stub-dlls.py, and reports a driver setup that does not exist.
    icd_setup = []
    for root, _dirs, files in os.walk(ROOT):
        if any(s in root for s in ("\\.git", "\\upstream", "\\FEX\\External")):
            continue
        for f in files:
            if not f.endswith((".c", ".h", ".m", ".sh", ".ps1", ".py", ".reg", ".yml")):
                continue
            # This file names the key it is searching for; matching itself would
            # report a driver setup out of its own constant.
            if os.path.normpath(os.path.join(root, f)) == os.path.normpath(__file__):
                continue
            try:
                text = open(os.path.join(root, f), encoding="utf-8",
                            errors="replace").read()
            except OSError:
                continue
            for key in ICD_REGISTRY:
                if key in text:
                    icd_setup.append("%s: %s" % (os.path.relpath(os.path.join(root, f), ROOT), key))

    # A stub answers the loader's shape and nothing else, which is the whole
    # point of shipping one: it lets an import resolve so a title can fall back.
    stub = os.path.join(ROOT, "tools", "build-stub-dlls.py")
    stubbed = os.path.exists(stub) and "vulkan-1" in open(stub, encoding="utf-8",
                                                        errors="replace").read()

    shipped_d3d12 = os.path.exists(os.path.join(SHIPPED, "d3d12.dll"))
    complete = bool(drivers)
    print("\n== verdict ==")
    print("  shipped payload:    %s" % os.path.relpath(SHIPPED, ROOT))
    print("  d3d12.dll there:    %s" % ("present" if shipped_d3d12 else "ABSENT"))
    print("  Vulkan device:      %s" % ("present" if complete else "ABSENT"))
    print("  ICD registry key:   %s"
          % ("set in " + ", ".join(icd_setup) if icd_setup else "never set"))
    if stubbed and not complete:
        print("  vulkan-1.dll:       a DELIBERATE stub (tools/build-stub-dlls.py)")
    if shipped_d3d12 and complete:
        print("  The D3D12 path is complete in this build.")
        return 0
    if not shipped_d3d12:
        print("  Gap 1 of 2: the shipped arm64ec payload has no d3d12.dll, so a")
        print("  D3D12 import does not resolve at all. The aarch64-windows copy is")
        print("  a prebuilt binary in the repo, not something this build produces.")
    if not complete:
        print("  Gap 2 of 2: no Vulkan driver. Wine's d3d12 is a vkd3d front end")
        print("  over Vulkan, and the stub answers VK_ERROR_INCOMPATIBLE_DRIVER, so")
        print("  vkd3d has no device to talk to.")
    print("  Scope: this says the D3D12 BACKEND IS INCOMPLETE HERE. It is not a")
    print("  claim about D3D12 in general -- docs/D3D12_BACKEND.md lists what has")
    print("  not been ruled out and what would close each gap.")
    return 1


if __name__ == "__main__":
    sys.exit(main())