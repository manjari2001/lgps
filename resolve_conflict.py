#!/usr/bin/env python3
"""Resolve a git merge conflict in lea_specific_contribution_rates_PROGRESS.csv
(or failures.json) caused by two concurrent runs appending distinct rows.

For the CSV: each conflict hunk contains two sets of distinct new data rows
(no shared LEA/Fund pairs expected, since each run works on a different
fund). Resolution is simply the union of both sides, theirs first.

A row can also survive from an earlier rebase pass and reappear in a later
hunk (each rebase re-diffs against a fresh base), so per-hunk exact-line
dedup alone is not enough. For the CSV, a final whole-file pass drops any
row whose (LEA, Fund) key repeats, keeping the first occurrence.

Usage: ./resolve_conflict.py <path>
"""
import csv, json, re, subprocess, sys

path = sys.argv[1]

if path.endswith(".json"):
    # Naive text-line merging corrupts JSON structure (e.g. a hunk boundary
    # falling inside one object). Instead read both full versions from the
    # conflicted git stages and merge as data: union of records by "fund",
    # first occurrence (theirs, i.e. the remote/upstream side) wins.
    ours_raw = subprocess.run(["git", "show", f":2:{path}"], capture_output=True, text=True, check=True).stdout
    theirs_raw = subprocess.run(["git", "show", f":3:{path}"], capture_output=True, text=True, check=True).stdout
    ours = json.loads(ours_raw)
    theirs = json.loads(theirs_raw)
    seen = set()
    merged = []
    for entry in theirs + ours:
        key = entry.get("fund")
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")
    print(f"resolved JSON conflict in {path} ({len(merged)} entries)")
    sys.exit(0)

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

if path.endswith(".csv"):
    rows = list(csv.reader(open(path, newline="", encoding="utf-8")))
    hdr, body = rows[0], rows[1:]
    seen_keys = set()
    deduped = []
    removed = 0
    for r in body:
        key = (r[0], r[1])
        if key in seen_keys:
            removed += 1
            continue
        seen_keys.add(key)
        deduped.append(r)
    if removed:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(hdr)
            w.writerows(deduped)
        print(f"dropped {removed} duplicate (LEA, Fund) row(s) in {path}")
