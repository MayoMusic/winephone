#!/usr/bin/env python3
"""Fail-closed checks for files linked or bundled by the WinePhone iOS app."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--skip-archives", action="store_true",
        help="check release exclusions and DLL provenance without built archives",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    app = root / "app/Madeira"
    project_path = root / "app/Madeira.xcodeproj/project.pbxproj"
    project = project_path.read_text(encoding="utf-8")

    for forbidden in ("x86_64-vcruntime", "libmetalirconverter", "d3d12"):
        if forbidden.casefold() in project.casefold():
            raise SystemExit(f"forbidden app resource reference remains: {forbidden}")

    for name in ("libmetalirconverter.dylib", "d3d12core.dll", "madeira_d3d12.dll"):
        matches = [p for p in app.rglob(name) if p.is_file()]
        if matches:
            raise SystemExit(
                "prohibited D3D12 release inputs remain: "
                + ", ".join(str(p.relative_to(root)) for p in matches)
            )

    runtime_prefixes = (
        "msvcp", "vcruntime", "concrt", "vcomp", "vcamp", "vccorlib", "mfc"
    )
    checked = 0
    for path in app.rglob("*.dll"):
        if path.name.casefold().startswith(runtime_prefixes):
            checked += 1
            if b"Wine builtin DLL" not in path.read_bytes():
                raise SystemExit(
                    "unverified Microsoft runtime candidate: " + str(path.relative_to(root))
                )
    if not (app / "x86_64-vcruntime").exists():
        print(f"Verified: {checked} bundled VC-runtime-named DLLs identify as Wine builtins.")
    else:
        raise SystemExit("user-supplied Microsoft runtime directory must not be bundled")

    if not args.skip_archives:
        refs = re.findall(r'path = "?([^";]+\.a)"?;', project)
        missing = sorted({str((app / rel).relative_to(root)) for rel in refs if not (app / rel).is_file()})
        if missing:
            print("Missing linked archives:", file=sys.stderr)
            print("\n".join(f"  {name}" for name in missing), file=sys.stderr)
            return 2
        print(f"Verified: all {len(refs)} Xcode static archive references exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
