#!/usr/bin/env python3
"""Append or update one LEA row in lea_specific_contribution_rates_PROGRESS.csv.

    ./add_row.py --lea "X County Council" --fund X --p22 21.6 --p25 19.0 \
                 [--t22 ...] [--t25 ...] [--b22 2021-22] [--b25 2024-25] \
                 [--notes "..."] [--update]

Primary_change_pp is always computed, never passed in, so it cannot disagree
with the two primary rates. Actuary_2022/Actuary_2025 are auto-filled from
actuary_lookup.csv by fund name unless overridden with --a22/--a25; if the
two differ, "actuary changed between cycles" is appended to Notes.

With --update, any field not passed keeps its existing value. The file is
read and written as UTF-8 with a BOM so Excel renders £ correctly.
"""
import argparse, csv, os

DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(DIR, "lea_specific_contribution_rates_PROGRESS.csv")
LOOKUP = os.path.join(DIR, "actuary_lookup.csv")

p = argparse.ArgumentParser()
p.add_argument("--lea", required=True)
p.add_argument("--fund", required=True)
for flag in ("p22", "p25", "t22", "t25", "a22", "a25", "b22", "b25", "notes"):
    p.add_argument(f"--{flag}", default=None)
p.add_argument("--update", action="store_true", help="edit existing row instead of appending")
a = p.parse_args()

rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig", newline="")))
hdr = next(csv.reader(open(CSV, encoding="utf-8-sig", newline="")))

hits = [i for i, r in enumerate(rows) if r["LEA"] == a.lea and r["Fund"] == a.fund]
if a.update:
    assert len(hits) == 1, f"expected 1 existing row for {a.lea}/{a.fund}, got {len(hits)}"
    row = dict(rows[hits[0]])
else:
    assert not hits, f"duplicate row {a.lea}/{a.fund}"
    row = {h: "" for h in hdr}
    row.update(LEA=a.lea, Fund=a.fund)

fields = {"p22": "Primary_2022", "p25": "Primary_2025", "t22": "Total_2022_year1",
          "t25": "Total_2025_year1", "a22": "Actuary_2022", "a25": "Actuary_2025",
          "b22": "Payroll_base_year_2022", "b25": "Payroll_base_year_2025", "notes": "Notes"}
for arg, col in fields.items():
    v = getattr(a, arg)
    if v is not None:
        assert col in hdr, f"column {col} not in CSV header"
        row[col] = v

if not a.update:
    lookup = {}
    if os.path.exists(LOOKUP):
        lookup = {r["Fund"]: (r["Actuary_2022"], r["Actuary_2025"])
                  for r in csv.DictReader(open(LOOKUP, encoding="utf-8-sig"))}
    la22, la25 = lookup.get(a.fund, ("", ""))
    if a.a22 is None:
        row["Actuary_2022"] = la22
    if a.a25 is None:
        row["Actuary_2025"] = la25

p22, p25 = row["Primary_2022"], row["Primary_2025"]
row["Primary_change_pp"] = f"{float(p25) - float(p22):.1f}" if p22 and p25 else ""

a22, a25, notes = row["Actuary_2022"], row["Actuary_2025"], row["Notes"]
if a22 and a25 and a22 != a25 and "actuary changed" not in notes.lower():
    tag = f"actuary changed between cycles ({a22} 2022, {a25} 2025)"
    row["Notes"] = f"{notes}; {tag}" if notes else tag

if a.update:
    rows[hits[0]] = row
else:
    rows.append(row)

with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=hdr)
    w.writeheader()
    w.writerows(rows)
print(",".join(row[h] for h in hdr))
