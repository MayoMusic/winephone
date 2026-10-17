#!/usr/bin/env bash
# Exercise scripts/apply-submodule-patches.sh's outcomes on a throwaway tree.
#
# The script decides between "applies", "already applied" and "fits neither",
# and refuses to continue on anything but the first two. That is the property
# that makes patch application deterministic, and it is only worth anything if
# the three branches are actually distinguished -- so drive all of them, plus
# the rule that a patch no target rule claims is an error rather than a file
# nobody looks at.
#
# Builds its own scratch git repos, so it needs no submodule and no network and
# cannot touch the real working tree. Run directly, or from CI:
#     bash tests/host/check-submodule-patches.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/apply-submodule-patches.sh"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT

[[ -f "$SCRIPT" ]] || { echo "FAIL $SCRIPT is missing"; exit 1; }

mkdir -p "$T/repo/scripts" "$T/repo/patches"
cp "$SCRIPT" "$T/repo/scripts/"
cd "$T/repo" || exit 1

# Blank the verification list so the scratch cases are not stopped by a check
# that only exists in the real repo. That guard gets its own cases (F, G), and
# the real list is restored before them.
perl -0pi -e 's/PATCH_VERIFY=\(\n[^)]*\)/PATCH_VERIFY=()/' scripts/apply-submodule-patches.sh
grep -q 'PATCH_VERIFY=()' scripts/apply-submodule-patches.sh || {
  echo "FAIL could not blank PATCH_VERIFY in the scratch copy"; exit 1; }

git init -q .; git config user.email t@t; git config user.name t
git init -q dxmt; git -C dxmt config user.email t@t; git -C dxmt config user.name t
mkdir -p dxmt/src
printf 'line one\nline two\nline three\n' > dxmt/src/a.txt
git -C dxmt add -A; git -C dxmt commit -qm base

# one patch that fits the pin
printf 'line one\nline TWO\nline three\n' > dxmt/src/a.txt
git -C dxmt diff --output="$T/repo/patches/dxmt-fresh.patch"
git -C dxmt checkout -q src/a.txt
# one generated against different content, so it fits neither way
printf 'line one\nline TWO\nline THREE\n' > dxmt/src/a.txt
git -C dxmt add -A; git -C dxmt commit -qm moved
git -C dxmt diff HEAD~1 --output="$T/repo/stale.patch"
git -C dxmt reset -q --hard HEAD~1

fails=0
expect() {   # expect <label> <wanted-exit> <needle|->
  local label="$1" want="$2" needle="$3" out rc
  out="$(bash scripts/apply-submodule-patches.sh 2>&1)"; rc=$?
  if [[ "$rc" != "$want" ]]; then
    echo "FAIL $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/     /'; fails=$((fails + 1)); return
  fi
  if [[ "$needle" != "-" && "$out" != *"$needle"* ]]; then
    echo "FAIL $label: exit $rc but output lacks '$needle'"; echo "$out" | sed 's/^/     /'; fails=$((fails + 1)); return
  fi
  echo "ok   $label (exit $rc)"
}

expect "a patch that applies is applied"                 0 "applied"
expect "re-running is idempotent"                        0 "already present"

cp stale.patch patches/dxmt-stale.patch
expect "a stale patch stops the build with a reason"     1 "does not apply to"
rm -f patches/dxmt-stale.patch

printf 'x\n' > patches/zzz-unclaimed.patch
expect "a patch no rule claims stops the build"          1 "matches no rule"
rm -f patches/zzz-unclaimed.patch

expect "clean and idempotent afterwards"                 0 "already present"

# The real verification list, with its patch absent: the guard that stops a
# check from quietly ceasing to run.
cp "$SCRIPT" scripts/apply-submodule-patches.sh
mkdir -p tests/host; printf 'ok\n' > tests/host/check-wmt-null-dest.py
expect "a verification whose patch is gone stops it"     1 "which is not in patches/"

# Patch present and valid, but the check it names is gone.
cp patches/dxmt-fresh.patch patches/dxmt-wmt-null-dest.patch
rm -f tests/host/check-wmt-null-dest.py
expect "a verification whose check is gone stops it"     1 "but is missing"

echo
if [[ $fails -eq 0 ]]; then echo PASS; else echo "FAILED: $fails"; fi
exit $fails