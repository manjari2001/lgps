#!/usr/bin/env python3
"""Build support_staff_proxy_comparison.csv.

One row per LEA and valuation cycle where the council's total contribution is
(or was) a percentage-plus-cash figure. Compares the council-level payroll the
report implies, where it gives one, against DfE support staff costs for the
payroll base year, to test whether support staff costs could stand in for the
missing employer-level payroll.

Inputs: lea_specific_contribution_rates_PROGRESS.csv and the two DfE files
la_support_staff_payroll_2021_22.csv / la_support_staff_payroll_2024_25.csv.
"""
import csv, os, re

DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DIR, "support_staff_proxy_comparison.csv")
DFE = {"2022": os.path.join(DIR, "la_support_staff_payroll_2021_22.csv"),
       "2025": os.path.join(DIR, "la_support_staff_payroll_2024_25.csv")}

WALES_FUNDS = {"Cardiff", "Clwyd", "Dyfed", "Greater Gwent (Torfaen)", "Gwynedd", "Powys",
               "Rhondda Cynon Taf", "Swansea"}

# LEA name in the rates CSV -> LA_name in the DfE files, where plain normalisation fails
ALIAS = {
    "Bath and North East Somerset Council": "Bath and North East Somerset",
    "Bristol City Council": "Bristol, City of",
    "Bournemouth, Christchurch and Poole Council": "Bournemouth, Christchurch and Poole",
    "Royal Borough of Windsor and Maidenhead": "Windsor and Maidenhead",
    "Kingston upon Hull City Council": "Kingston upon Hull, City of",
    "Durham County Council": "County Durham",
    "St Helens MBC": "St. Helens",
    "Telford & Wrekin Council": "Telford and Wrekin",
    "Westminster City Council": "Westminster",
    "City of London Corporation": "City of London",
}

# Council-level payroll implied by the certificate's own 'equivalent total rate'
# footnote: cash / (equivalent rate - printed percentage). Pool-level, for the
# first certificate year (2023/24), so it is deflated to the 2021-22 base year
# using the fund's own ratio of 2023/24 assumed payroll to 2021-22 actual pay.
IMPLIED = {
    ("London Borough of Harrow", "2022"): dict(pct=16.0, cash=6_000_000, equiv=23.0,
        fund_assumed=122.4e6, fund_actual=112.691e6,
        src="Certificate footnote 2: equivalent total rate for the London Borough of Harrow Pool is 23.0% (pool = LB Harrow, Cannon Lane F&M School, Grange Primary School)"),
    ("London Borough of Lewisham", "2022"): dict(pct=17.6, cash=5_750_000, equiv=22.0,
        fund_assumed=174.5e6, fund_actual=161.996e6,
        src="Certificate footnote 1: equivalent rate for the London Borough of Lewisham Pool is 22.0% for 2023/24"),
    ("London Borough of Lambeth", "2022"): dict(pct=19.3, cash=8_500_000, equiv=24.8,
        fund_assumed=165.8e6, fund_actual=155.595e6,
        src="Certificate footnote 1: equivalent rate for the London Borough of Lambeth Pool is 24.8% (footnote also says it applies to LEA schools)"),
}

def norm(s):
    s = re.sub(r"^(London Borough of|Royal Borough of|The )\s*", "", s)
    s = re.sub(r"\s+(County Borough Council|Borough Council|County Council|City Council|Council|MBC|MDC)$", "", s)
    return s.strip().lower()

dfe = {}
for y, p in DFE.items():
    dfe[y] = {norm(r["LA_name"]): (r["LA_code"], r["LA_name"], float(r["Support_staff_costs_total_GBP"]))
              for r in csv.DictReader(open(p, encoding="utf-8-sig"))}

rows = list(csv.DictReader(open(os.path.join(DIR, "lea_specific_contribution_rates_PROGRESS.csv"), encoding="utf-8-sig")))
out = []
for r in rows:
    for y in ("2022", "2025"):
        total = r[f"Total_{y}_year1"]
        key = (r["LEA"], y)
        if "£" not in total and key not in IMPLIED:
            continue
        excl = bool(re.search(r"excl\.? schools|non-schools|non schools|non-school staff", r["Notes"], re.I))
        d = dfe[y].get(norm(ALIAS.get(r["LEA"], r["LEA"])))
        rec = {
            "LEA": r["LEA"], "Fund": r["Fund"], "Valuation": y,
            "Payroll_base_year": r[f"Payroll_base_year_{y}"],
            "Certificate_total_year1": total if "£" in total else "",
            "Council_line_excludes_schools": "Yes" if excl else "No",
            "Report_payroll_GBP": "", "Report_payroll_base_year_GBP": "", "Report_payroll_source": "",
            "DfE_LA_code": d[0] if d else "", "DfE_LA_name": d[1] if d else "",
            "DfE_support_staff_costs_GBP": f"{d[2]:.0f}" if d else "",
            "DfE_vs_report_pct": "", "Notes": "",
        }
        if key in IMPLIED:
            m = IMPLIED[key]
            pay = m["cash"] / ((m["equiv"] - m["pct"]) / 100)
            base = pay * m["fund_actual"] / m["fund_assumed"]
            rec["Certificate_total_year1"] = f"{m['pct']}% plus £{m['cash']:,}"
            rec["Report_payroll_GBP"] = f"{pay:.0f}"
            rec["Report_payroll_base_year_GBP"] = f"{base:.0f}"
            rec["Report_payroll_source"] = m["src"]
            if d:
                rec["DfE_vs_report_pct"] = f"{(d[2] / base - 1) * 100:.1f}"
            rec["Notes"] = ("Implied pool payroll for 2023/24, deflated to 2021-22 using the fund's own ratio of "
                            "2023/24 assumed payroll to 2021-22 actual pay. Pool-level, not council-only.")
        else:
            rec["Report_payroll_source"] = "None published - report gives whole-fund payroll only"
        if r["Fund"] in WALES_FUNDS:
            rec["Notes"] = (rec["Notes"] + " " if rec["Notes"] else "") + "Welsh LEA: not covered by the DfE (England-only) data."
        elif not d:
            rec["Notes"] = (rec["Notes"] + " " if rec["Notes"] else "") + "No matching LA in the DfE file."
        out.append(rec)

with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
print(f"{len(out)} rows -> {OUT}")
