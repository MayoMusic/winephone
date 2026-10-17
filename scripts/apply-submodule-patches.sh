#!/usr/bin/env bash
# Apply every patches/*.patch to the tree it targets, and prove the result took.
#
# Why this exists
# ---------------
# wine/, FEX/ and dxmt/ are pinned third-party submodules, so a change to their
# sources cannot be committed here. patches/ is how such a change is carried.
# Nothing applied it: build-ipa.sh configured and compiled dxmt straight out of
# the submodule, so what got compiled was whatever happened to be sitting in the
# working directory. patches/dxmt-winemetal-static-implibs.patch had never been
# applied at all -- meson.build still read `],` and a lib_dbghelp line with no
# `static: true`, which is the patch's "before" state verbatim.
#
# "Deterministic" means three things
# ---------------------------------
#   1. The set is derived from the files on disk, and a patch that no target
#      rule claims is a hard error. A new patch cannot be added and forgotten.
#   2. "applies", "already applied" and "fits neither" are three distinct
#      outcomes. The first two continue -- so a warm working tree is not a
#      failure and a build is repeatable -- and only the third stops the build.
#   3. Success is verified against the resulting SOURCE, not against git's exit
#      status. A patch can apply cleanly and still not be the change it claims
#      to be, and a patch that was already applied proves nothing on its own.
#
# Exits non-zero, with the reason, on anything else.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH_DIR="$ROOT/patches"

# patch glob -> the tree it applies to. "self" is the WinePhone repo; anything
# else is the path of a submodule, applied from that submodule's own root.
# Order matters: the first match wins.
#
# 0001-* is a git-format-patch series and targets files this repository tracks,
# so it applies to the parent tree -- it was already committed here and lands in
# the "already present" branch, which is the point: the rule has to exist for the
# script not to reject it.
PATCH_TARGETS=(
  'dxmt-*.patch:dxmt'
  'fex-*.patch:FEX'
  'wine-*.patch:wine'
  'madeira-dock-*.patch:madeira-dock'
  '0001-*.patch:self'
  '*-self.patch:self'
)

# Checked after applying, so a patch cannot apply and be believed. Each names a
# host check that inspects the patched source for what the patch was for.
PATCH_VERIFY=(
  'dxmt-wmt-null-dest.patch:tests/host/check-wmt-null-dest.py'
)

shopt -s nullglob
all_patches=("$PATCH_DIR"/*.patch)
if (( ${#all_patches[@]} == 0 )); then
  echo "error: no patches in $PATCH_DIR -- expected the submodule patches to travel with the repo" >&2
  exit 1
fi

target_for() {
  local patch="$1" rule glob target
  for rule in "${PATCH_TARGETS[@]}"; do
    glob="${rule%:*}"
    target="${rule##*:}"
    # shellcheck disable=SC2053  # the glob is meant to expand here
    if [[ $(basename "$patch") == $glob ]]; then
      printf '%s\n' "$target"
      return 0
    fi
  done
  return 1
}

# Bring a submodule up if it was never checked out, so this script does not
# depend on which stage ran bootstrap.
ensure_tree() {
  local target="$1"
  [[ "$target" == self ]] && { printf '%s\n' "$ROOT"; return 0; }
  if [[ -e "$ROOT/$target/.git" ]]; then
    printf '%s\n' "$ROOT/$target"
    return 0
  fi
  echo "-- $target is not checked out; initialising it"
  git submodule update --init --depth 1 "$target"
  if [[ ! -e "$ROOT/$target/.git" ]]; then
    echo "error: submodule '$target' is still absent after 'git submodule update --init $target'." >&2
    echo "       A patch cannot be applied to a tree that is not there; this is not" >&2
    echo "       something to skip past." >&2
    exit 1
  fi
  printf '%s\n' "$ROOT/$target"
}

applied=0
already=0

for patch in "${all_patches[@]}"; do
  name="$(basename "$patch")"
  if ! target="$(target_for "$patch")"; then
    echo "error: patches/$name matches no rule in PATCH_TARGETS." >&2
    echo "       Add one, or the patch will sit in the tree doing nothing -- which" >&2
    echo "       is how dxmt-winemetal-static-implibs.patch went unapplied." >&2
    exit 1
  fi
  tree="$(ensure_tree "$target")"

  printf '\n--- %s -> %s\n' "$name" "${target#./}"
  if git -C "$tree" apply --check "$patch" 2>/dev/null; then
    git -C "$tree" apply "$patch"
    echo "applied"
    applied=$((applied + 1))
  elif git -C "$tree" apply --check --reverse "$patch" 2>/dev/null; then
    echo "already present"
    already=$((already + 1))
  else
    echo "error: patches/$name does not apply to $tree" >&2
    echo "       at $(git -C "$tree" rev-parse --short HEAD)." >&2
    echo "       It fits neither the patch's context nor its reverse, so it is" >&2
    echo "       stale against this submodule pin. Regenerate it:" >&2
    echo "         git -C $target apply -R patches/$name   # then re-derive and" >&2
    echo "         git -C $target diff --output=../patches/$name" >&2
    git -C "$tree" apply --check "$patch" || true      # print git's own reason
    exit 1
  fi
done

# Prove the patches are in the tree: each one must now reverse cleanly.
for patch in "${all_patches[@]}"; do
  name="$(basename "$patch")"
  target="$(target_for "$patch")"
  tree="$(ensure_tree "$target")"
  if ! git -C "$tree" apply --check --reverse "$patch" 2>/dev/null; then
    echo "error: patches/$name reported success but is not in $target's source." >&2
    exit 1
  fi
done

# And prove the intended CHANGE is there, not merely that a diff matched. This
# runs in the build, on the patched tree, and fails it if the change is absent.
for entry in "${PATCH_VERIFY[@]}"; do
  patch="${entry%%:*}"
  check="${entry##*:}"
  [[ -f "$ROOT/$check" ]] || {
    echo "error: verification $check is registered for patches/$patch but is missing." >&2
    exit 1
  }
  [[ -f "$PATCH_DIR/$patch" ]] || {
    echo "error: PATCH_VERIFY names patches/$patch, which is not in patches/." >&2
    echo "       Restore the patch or drop the entry -- a verification that stops" >&2
    echo "       running because its patch was deleted is worse than none." >&2
    exit 1
  }
  printf '\n--- verifying %s (the intended change, on the patched source)\n' "$check"
  python3 "$ROOT/$check"
done

printf '\npatches: %d applied, %d already present\n' "$applied" "$already"