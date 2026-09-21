#!/usr/bin/env python3
"""Append or update one LEA row in lea_specific_contribution_rates_PROGRESS.csv.

    ./add_row.py --lea "X County Council" --fund X --p22 21.6 --p25 19.0 \
                 [--t22 ...] [--t25 ...] [--notes "..."] [--update]

Primary_change_pp is always computed, never passed in, so it cannot disagree
with the two primary rates.
"""
import argparse, csv, os

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "lea_specific_contribution_rates_PROGRESS.csv")

p = argparse.ArgumentParser()
p.add_argument("--lea", required=True)
p.add_argument("--fund", required=True)
p.add_argument("--p22", default="")
p.add_argument("--p25", default="")
p.add_argument("--t22", default="")
p.add_argument("--t25", default="")
p.add_argument("--notes", default="")
p.add_argument("--update", action="store_true", help="edit existing row instead of appending")
a = p.parse_args()

change = ""
if a.p22 and a.p25:
    change = f"{round(float(a.p25) - float(a.p22), 1):+g}".lstrip("+")

rows = list(csv.reader(open(CSV)))
hdr, body = rows[0], rows[1:]
new = [a.lea, a.fund, a.p22, a.p25, change, a.t22, a.t25, a.notes]
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
