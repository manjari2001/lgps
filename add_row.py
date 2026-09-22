#!/usr/bin/env python3
"""Append or update one LEA row in lea_specific_contribution_rates_PROGRESS.csv.

    ./add_row.py --lea "X County Council" --fund X --p22 21.6 --p25 19.0 \
                 [--t22 ...] [--t25 ...] [--notes "..."] [--update]

Primary_change_pp is always computed, never passed in, so it cannot disagree
with the two primary rates. Actuary_2022/Actuary_2025 are auto-filled from
actuary_lookup.csv by fund name unless overridden with --a22/--a25; if the
two differ, "actuary changed between cycles" is appended to Notes.
"""
import argparse, csv, os

DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(DIR, "lea_specific_contribution_rates_PROGRESS.csv")
LOOKUP = os.path.join(DIR, "actuary_lookup.csv")

p = argparse.ArgumentParser()
p.add_argument("--lea", required=True)
p.add_argument("--fund", required=True)
p.add_argument("--p22", default="")
p.add_argument("--p25", default="")
p.add_argument("--t22", default="")
p.add_argument("--t25", default="")
p.add_argument("--a22", default=None)
p.add_argument("--a25", default=None)
p.add_argument("--notes", default="")
p.add_argument("--update", action="store_true", help="edit existing row instead of appending")
a = p.parse_args()

change = ""
if a.p22 and a.p25:
    change = f"{float(a.p25) - float(a.p22):.1f}"

a22, a25 = a.a22, a.a25
if a22 is None or a25 is None:
    lookup = {}
    if os.path.exists(LOOKUP):
        lookup = {r["Fund"]: (r["Actuary_2022"], r["Actuary_2025"])
                  for r in csv.DictReader(open(LOOKUP))}
    la22, la25 = lookup.get(a.fund, ("", ""))
    if a22 is None:
        a22 = la22
    if a25 is None:
        a25 = la25

notes = a.notes
if a22 and a25 and a22 != a25 and "actuary changed" not in notes.lower():
    tag = f"actuary changed between cycles ({a22} 2022, {a25} 2025)"
    notes = f"{notes}; {tag}" if notes else tag

rows = list(csv.reader(open(CSV)))
hdr, body = rows[0], rows[1:]
new = [a.lea, a.fund, a.p22, a.p25, change, a.t22, a.t25, a22, a25, notes]
assert len(new) == len(hdr), (new, hdr)

if a.update:
    hits = [i for i, r in enumerate(body) if r[0] == a.lea and r[1] == a.fund]
    assert len(hits) == 1, f"expected 1 existing row for {a.lea}/{a.fund}, got {len(hits)}"
    body[hits[0]] = new
else:
    assert not any(r[0] == a.lea and r[1] == a.fund for r in body), f"duplicate row {a.lea}/{a.fund}"
    body.append(new)

with open(CSV, "w", newline="") as f:
    csv.writer(f).writerows([hdr] + body)
print(",".join(new))
