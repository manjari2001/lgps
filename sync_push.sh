#!/usr/bin/env bash
export GIT_EDITOR=true
# Push local commits to origin/main, retrying with a rebase + auto-merge of
# lea_specific_contribution_rates_PROGRESS.csv / failures.json on conflict.
# Concurrent runs append distinct rows, so conflicts are always safe unions.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

for i in 1 2 3 4 5; do
  if git push origin main 2>/tmp/sync_push_err.log; then
    echo "PUSHED"
    exit 0
  fi
  echo "push failed (attempt $i), fetching + rebasing..." >&2
  git fetch origin main
  if git pull --rebase origin main >/tmp/sync_rebase.log 2>&1; then
    continue
  fi
  # conflict: resolve known files, then continue rebase
  resolved=0
  for f in lea_specific_contribution_rates_PROGRESS.csv failures.json; do
    if git status --porcelain | grep -q "^UU $f"; then
      python3 resolve_conflict.py "$f" && git add "$f" && resolved=1
    fi
  done
  if [ "$resolved" = 1 ]; then
    git rebase --continue
  else
    echo "UNRESOLVED CONFLICT - manual intervention needed" >&2
    git status >&2
    exit 1
  fi
done
echo "FAILED after retries" >&2
exit 1
