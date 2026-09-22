#!/usr/bin/env python3
"""Resolve a git merge conflict in lea_specific_contribution_rates_PROGRESS.csv
(or failures.json) caused by two concurrent runs appending distinct rows.

For the CSV: each conflict hunk contains two sets of distinct new data rows
(no shared LEA/Fund pairs expected, since each run works on a different
fund). Resolution is simply the union of both sides, theirs first.

Usage: ./resolve_conflict.py <path>
"""
import re, sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()

pattern = re.compile(
    r"<<<<<<< [^\n]*\n(.*?)\n?=======\n(.*?)\n?>>>>>>> [^\n]*\n",
    re.DOTALL,
)

def merge(m):
    ours, theirs = m.group(1), m.group(2)
    ours_lines = [l for l in ours.split("\n") if l.strip()]
    theirs_lines = [l for l in theirs.split("\n") if l.strip()]
    # union, preserving order, theirs first, dropping exact duplicate lines
    seen = set()
    out = []
    for l in theirs_lines + ours_lines:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return "\n".join(out) + "\n"

new_text, n = pattern.subn(merge, text)
if n == 0:
    print("no conflict markers found", file=sys.stderr)
    sys.exit(1)

open(path, "w", encoding="utf-8").write(new_text)
print(f"resolved {n} hunk(s) in {path}")
