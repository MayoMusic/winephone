#!/usr/bin/env bash
# Every submodule patch applies to the commit it is pinned against.
#
# tests/host/check-patch-bytes.py answers "is this readable and does it carry
# what it says", which is not the same question. A patch can be clean ASCII,
# contain every expected marker, and still not apply -- because the submodule
# moved, or because its context lines drifted. The last time a patch here was
# broken, it was broken this way and only the build found out, after the
# bootstrap and the Wine PE modules had already run.
#
# This runs `git apply --check` against the real pinned submodule and names the
# patch that does not fit. It is a host check because the submodules are present
# in the tree; in CI it runs after bootstrap.
#
# Both directions are checked, and so is the reverse, because "already applied"
# is a legitimate state for a warm working tree and must not read as failure.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PATCH_DIR="$ROOT/patches"
fails=0

for patch in "$PATCH_DIR"/dxmt-*.patch; do
  name="$(basename "$patch")"
  tree="$ROOT/dxmt"
  if [[ ! -e "$tree/.git" ]]; then
    echo "FAIL $name: dxmt is not checked out, so it cannot be verified here"
    echo "     (this check needs the submodule; CI runs it after bootstrap)"
    fails=$((fails + 1))
    continue
  fi
  pin="$(git -C "$tree" rev-parse --short HEAD)"
  if err="$(git -C "$tree" apply --check "$patch" 2>&1)"; then
    echo "ok   $name applies cleanly to dxmt@$pin"
  elif git -C "$tree" apply --check --reverse "$patch" 2>/dev/null; then
    echo "ok   $name is already applied to dxmt@$pin (idempotent, warm tree)"
  else
    echo "FAIL $name does not apply to dxmt@$pin"
    echo "     $err" | head -3 | sed 's/^/     /'
    echo "     Regenerate against the pin:"
    echo "       git -C dxmt checkout -- .    # start from the pinned tree"
    echo "       git -C dxmt apply -R \"$PATCH_DIR/$name\""
    echo "       # re-derive, then write with git's own output so the bytes stay ASCII:"
    echo "       git -C dxmt diff --output=\"$PATCH_DIR/$name\" -- <paths>"
    fails=$((fails + 1))
  fi
done

# FEX and wine patches are checked the same way where those submodules exist.
for entry in "fex-darwin.patch:FEX" "0001-winephone-build-exclusions.patch:."; do
  name="${entry%%:*}"
  target="${entry##*:}"
  patch="$PATCH_DIR/$name"
  [[ -f "$patch" ]] || continue
  tree="$ROOT/$target"
  if [[ "$target" == "." ]]; then tree="$ROOT"; fi
  if [[ ! -e "$tree/.git" ]]; then
    echo "ok   $name: $target not checked out, skipping (nothing to check against)"
    continue
  fi
  if git -C "$tree" apply --check "$patch" 2>/dev/null; then
    echo "ok   $name applies cleanly"
  elif git -C "$tree" apply --check --reverse "$patch" 2>/dev/null; then
    echo "ok   $name is already applied (idempotent, warm tree)"
  else
    echo "FAIL $name does not apply to $target"
    fails=$((fails + 1))
  fi
done

echo
if [[ $fails -eq 0 ]]; then echo PASS; else echo "FAILED: $fails"; fi
exit $fails