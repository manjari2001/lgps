#!/usr/bin/env python3
"""Phase 5: rebuild LEA total contribution rates from published spending data.

Estimates each council's LGPS pensionable payroll from public data, then turns
a mixed certificate total ("X% plus £Y") into a single percentage:

    payroll_base  = (RO employee costs - fire employees - CFR teacher costs)
                    x participation / on-cost factor
    payroll_year1 = payroll_base x pay growth (base year -> certificate year 1)
    total_pct     = X + Y / payroll_year1

Sources (downloaded on first run into CACHE_DIR, never committed):
  * MHCLG Revenue Outturn RSX: 'Total Service Expenditure - Employees' and
    'Fire and rescue services - Employees' per LA, 2021-22 / 2023-24 / 2024-25
  * DfE CFR (LA and school expenditure release): maintained schools' Teaching
    staff (E01) + Supply teaching staff (E02) per LA. Teachers are in the TPS,
    not the LGPS, so they are taken out of the RO employee total.
AAR (academies) is not used: academies are separate LGPS employers, so their
staff never sit in a council's own certificate line or in RO employee costs.

Step 1 validates on councils where an independent payroll is already known
(certificate footnote equivalents, and fund annual report contributions from
phase 1) and writes phase5_ro_cfr_validation.csv.
Step 2 applies the validated variant (base year x uplift) to every English LEA
whose certificate total is mixed, and writes the Est_* columns of the main CSV.
The printed Total_* columns are never changed.

    python3 method_testing/phase5_ro_cfr_model.py
"""
import csv
import io
import json
import os
import re
import statistics as st
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.environ.get("LGPS_CACHE", os.path.join(HERE, ".cache"))

# ---- Assumptions (change here) ------------------------------------------
PARTICIPATION = 0.95        # share of non-teaching pay that is in the LGPS
EMPLOYER_NI = 0.086         # 13.8% above ~£9.1k threshold on ~£24k average pay
EMPLOYER_PENSION = 0.20     # employer LGPS rate actually paid in the base year
APPRENTICESHIP_LEVY = 0.005
ONCOST = 1 + EMPLOYER_NI + EMPLOYER_PENSION + APPRENTICESHIP_LEVY
# Pay growth from valuation base year to certificate year 1.
# 2021-22 -> 2023/24: median RO growth across 144 English LAs was 1.152
# (NJC awards of £1,925 in 2022 and 2023). 2024-25 -> 2026/27: 3.2% (2025
# award) and an assumed 3.0% (2026).
UPLIFT = {"2022": 1.152, "2025": 1.032 * 1.030}

RO_URLS = {
    "2021-22": "https://assets.publishing.service.gov.uk/media/6825a5a1ab96d4ed0b262f78/RSX_2021-22_data_by_LA_Live.ods",
    "2023-24": "https://assets.publishing.service.gov.uk/media/6a291c0b3b15d05a7ce31ffe/RSX_2023-24_data_by_LA.ods",
    "2024-25": "https://assets.publishing.service.gov.uk/media/6a291b0fade52dc088221881/RSX_LA_Data_2024-25_data_by_LA.ods",
}
CFR_URL = ("https://content.explore-education-statistics.service.gov.uk/api/releases/"
           "d826124d-95f3-4b2f-a8ab-3425f84145fe/files?fromPage=ReleaseDownloads")
CFR_YEARS = {"202122": "2021-22", "202324": "2023-24", "202425": "2024-25"}

# Benchmark councils: phase 1 name -> (ONS code, main CSV LEA name)
BENCH = {
    "West Sussex CC": ("E10000032", "West Sussex County Council"),
    "Cambridgeshire CC": ("E10000003", "Cambridgeshire County Council"),
    "Derbyshire CC": ("E10000007", "Derbyshire County Council"),
    "Luton BC": ("E06000032", "Luton Borough Council"),
    "Central Bedfordshire": ("E06000056", "Central Bedfordshire Council"),
    "Bedford BC": ("E06000055", "Bedford Borough Council"),
    "RB Greenwich": ("E09000011", "Royal Borough of Greenwich"),
    "Dorset Council": ("E06000059", "Dorset Council"),
    "BCP Council": ("E06000058", "Bournemouth, Christchurch and Poole Council"),
    "Wokingham BC": ("E06000041", "Wokingham Borough Council"),
    "RB Windsor & Maidenhead": ("E06000040", "Royal Borough of Windsor and Maidenhead"),
    "Bristol CC": ("E06000023", "Bristol City Council"),
    "Bath & NE Somerset": ("E06000022", "Bath and North East Somerset Council"),
    "LB Bromley": ("E09000006", "London Borough of Bromley"),
    "Liverpool CC": ("E08000012", "Liverpool City Council"),
    "Gateshead": ("E08000037", "Gateshead Council"),
    "Newcastle CC": ("E08000021", "Newcastle City Council"),
    "North Tyneside": ("E08000022", "North Tyneside Council"),
    "Sunderland CC": ("E08000024", "City of Sunderland Council"),
}
# 2022 certificate footnotes giving both the mixed line and an equivalent %:
# (LEA, ONS, printed pct, cash £, equivalent total pct)
FOOTNOTES = [
    ("London Borough of Harrow", "E09000015", 16.0, 6_000_000, 23.0),
    ("London Borough of Lambeth", "E09000022", 19.3, 8_500_000, 24.8),
    ("London Borough of Lewisham", "E09000023", 17.6, 5_750_000, 22.0),
]
ROUTE_RANK = {"R1": 1, "R2": 2, "R3": 3}   # phase 1 routes, best first
# Error band quoted with each estimate, as a share of the rebuilt secondary.
# In validation |error| / |secondary| was <= 0.25 for 12 of 15 councils, and
# every council over it (Lambeth, Lewisham, RBWM) was a flagged or outlier case.
ERROR_SHARE = 0.25
FUND_SHARE_LIMIT = 0.9      # no estimate if payroll > 90% of whole-fund pay

# Main CSV names that do not normalise to an RO name, or whose ONS code
# changed at a reorganisation: {LEA: {base year: ONS}}
ONS_OVERRIDES = {
    "Newcastle City Council": {"2021-22": "E08000021", "2024-25": "E08000021"},
    "City of London Corporation": {"2021-22": "E09000001", "2024-25": "E09000001"},
    "Dorset Council": {"2021-22": "E06000059", "2024-25": "E06000059"},
    "Somerset Council": {"2021-22": "E10000027", "2024-25": "E06000066"},
    "North Yorkshire Council": {"2021-22": "E10000023", "2024-25": "E06000065"},
    "Cumberland Council": {"2024-25": "E06000063"},
    "Westmorland and Furness Council": {"2024-25": "E06000064"},
}
WELSH_FUNDS = {"Cardiff", "Clwyd", "Dyfed", "Greater Gwent (Torfaen)", "Gwynedd", "Powys",
               "Rhondda Cynon Taf", "Swansea"}
CYCLES = {"2022": ("Total_2022_year1", "2021-22"), "2025": ("Total_2025_year1", "2024-25")}
MAIN_CSV = os.path.join(HERE, "..", "lea_specific_contribution_rates_PROGRESS.csv")
EST_COLS = ["Est_payroll_2022_year1_GBPm", "Est_total_2022_year1", "Est_total_2022_error_pp",
            "Est_payroll_2025_year1_GBPm", "Est_total_2025_year1", "Est_total_2025_error_pp", "Est_notes"]


def fetch(url, name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, name)
    if not os.path.exists(path):
        with urllib.request.urlopen(url, timeout=600) as r, open(path, "wb") as f:
            f.write(r.read())
    return path


def read_ods_sheet(path, sheet_hint):
    """Minimal ODS reader (stdlib only): returns rows of the first sheet whose
    name contains sheet_hint."""
    t = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    o = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
    x = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    root = ET.fromstring(zipfile.ZipFile(path).read("content.xml"))
    for table in root.iter(t + "table"):
        if sheet_hint not in table.get(t + "name"):
            continue
        rows = []
        for r in table.iter(t + "table-row"):
            cells = []
            for c in r:
                if c.tag not in (t + "table-cell", t + "covered-table-cell"):
                    continue
                n = min(int(c.get(t + "number-columns-repeated", "1")), 500)
                v = c.get(o + "value")
                if v is None:
                    v = "\n".join("".join(p.itertext()) for p in c.findall(x + "p")) or None
                cells.extend([v] * n)
            rows.append(cells)
        return rows
    raise KeyError(sheet_hint)


def load_ro():
    """{(ons, year): {'G': £, 'Fire': £, 'Police': £}} from RSX."""
    out = {}
    for year, url in RO_URLS.items():
        rows = read_ods_sheet(fetch(url, os.path.basename(url)), "RSX_LA_Data")
        hi = next(i for i, r in enumerate(rows[:20]) if r and r[0] == "E-code")
        head = [(h or "").split("\n")[0].strip() for h in rows[hi]]

        def col(prefix):
            return next(i for i, h in enumerate(head) if h.replace(" ", "").startswith(prefix.replace(" ", "")))
        ci = {"G": col("Total Service Expenditure - Employees"),
              "Fire": col("Fire and rescue services - Employees"),
              "Police": col("Police services - Employees")}
        for r in rows[hi + 1:]:
            if len(r) < 2 or not re.match(r"E\d{8}$", str(r[1])):
                continue
            rec = {"name": r[2]}
            for k, i in ci.items():
                try:
                    rec[k] = float(r[i]) * 1000      # RO is in £000
                except (TypeError, ValueError, IndexError):
                    rec[k] = 0.0
            out[(r[1], year)] = rec
    return out


def load_cfr():
    """{(ons, year): teacher costs £ (E01 + E02), all maintained schools}."""
    z = zipfile.ZipFile(fetch(CFR_URL, "la_and_school_expenditure.zip"))
    out = defaultdict(float)
    with z.open("data/cfr_expenditure_la_regional_national.csv") as f:
        lines = (l.decode("cp1252") for l in f)
        for r in csv.DictReader(lines):
            if (r["geographic_level"] != "Local authority" or r["time_period"] not in CFR_YEARS
                    or r["school_phase"] != "All LA maintained schools"):
                continue
            if re.search(r"\((E01|E02)\)$", r["expenditure_description"]):
                try:
                    out[(r["new_la_code"], CFR_YEARS[r["time_period"]])] += float(r["expenditure"])
                except ValueError:
                    pass
    return out


def payroll(ro, cfr, ons, year):
    x = ro[(ons, year)]
    net = x["G"] - x["Fire"] - x["Police"] - cfr.get((ons, year), 0.0)
    return net, net * PARTICIPATION / ONCOST


def printed_pct(total_cell):
    m = re.match(r"\s*([\d.]+)%", total_cell or "")
    return float(m.group(1)) if m else None


def parse_mixed(cell):
    """'19.3% plus £8,500,000' -> (19.3, 8500000). Handles 'less', '£4.26m',
    '£8,940k' and several cash items (summed). None if not a mixed total."""
    m = re.match(r"\s*(-?[\d.]+)%", cell or "")
    items = re.findall(r"(plus|less)\s+£([\d,.]+)\s*(m|k)?", cell or "")
    if not m or not items:
        return None
    cash = 0.0
    for sign, num, unit in items:
        v = float(num.replace(",", "")) * {"m": 1e6, "k": 1e3}.get(unit, 1)
        cash += -v if sign == "less" else v
    return float(m.group(1)), cash, len(items)


def norm_name(s):
    s = s.lower().replace("&", "and").replace("-", " ").replace(",", "")
    for w in ["london borough of", "royal borough of", "city of", "county borough council", "borough council",
              "county council", "city council", "metropolitan borough council", "council", "mbc", "mdc",
              "cbc", "city and county of", "the ", "county of"]:
        s = s.replace(w, " ")
    s = re.sub(r"\s(cc|ua|bc|md|lb)$", "", s.strip())    # 2024-25 RO uses 'Devon CC' etc.
    return re.sub(r"\s+", " ", s).strip()


def load_fund_pay():
    """{(fund, valuation): whole-fund actual pay £} from phase 0."""
    return {(r["Fund"], r["Valuation"]): float(r["Whole_fund_actual_pay_GBP"]) for r in csv.DictReader(
        open(os.path.join(HERE, "phase0_whole_fund_actual_pay.csv"), encoding="utf-8-sig"))}


def estimate_main_csv(ro, cfr):
    raw = open(MAIN_CSV, "rb").read()
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    fields = [c for c in rows[0].keys() if c not in EST_COLS] + EST_COLS
    fund_pay = load_fund_pay()
    by_name = defaultdict(dict)
    for (ons, year), rec in ro.items():
        by_name[year].setdefault(norm_name(rec["name"]), ons)
    counts = defaultdict(int)
    for r in rows:
        for c in EST_COLS:
            r[c] = ""
        notes = []
        for val, (col, base_year) in CYCLES.items():
            parsed = parse_mixed(r[col])
            if not parsed:
                continue
            pct, cash, n_items = parsed
            ons = ONS_OVERRIDES.get(r["LEA"], {}).get(base_year) or by_name[base_year].get(norm_name(r["LEA"]))
            if not ons or (ons, base_year) not in ro:
                if r["Fund"] not in WELSH_FUNDS:
                    raise SystemExit(f"no RO match for English LEA {r['LEA']!r} ({base_year}): add to ONS_OVERRIDES")
                notes.append(f"{val}: no estimate - Welsh council, not in English RO/CFR data")
                counts["wales"] += 1
                continue
            _, base = payroll(ro, cfr, ons, base_year)
            fp = fund_pay.get((r["Fund"], val))
            if fp and base / fp > FUND_SHARE_LIMIT:
                notes.append(f"{val}: no estimate - RO-based payroll is {base / fp:.0%} of whole-fund pay, "
                             "so RO costs include staff outside this line")
                counts["flagged"] += 1
                continue
            year1 = base * UPLIFT[val]
            secondary = cash / year1 * 100
            r[f"Est_payroll_{val}_year1_GBPm"] = f"{year1 / 1e6:.1f}"
            r[f"Est_total_{val}_year1"] = f"{pct + secondary:.1f}"
            r[f"Est_total_{val}_error_pp"] = f"{max(0.1, abs(secondary) * ERROR_SHARE):.1f}"
            counts["estimated"] += 1
            if n_items > 1:
                notes.append(f"{val}: {n_items} cash items in the certificate line summed")
        if r["Est_total_2022_year1"] or r["Est_total_2025_year1"]:
            if re.search(r"non-school|excl\.? schools|separate '[^']*schools?[^']*' line|schools-staff pool|"
                         r"'pool \(schools\)'", r["Notes"], re.I):
                notes.append("certificate line excludes schools but estimated payroll includes school support "
                             "staff, so payroll may be overstated and the total understated")
        r["Est_notes"] = "; ".join(notes)
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    open(MAIN_CSV, "wb").write(("\ufeff" + buf.getvalue()).encode("utf-8"))
    print(f"main CSV: {counts['estimated']} estimates, {counts['flagged']} flagged, "
          f"{counts['wales']} Welsh cells skipped")


def main():
    ro, cfr = load_ro(), load_cfr()
    main_csv = {r["LEA"]: r for r in csv.DictReader(open(MAIN_CSV, encoding="utf-8-sig"))}

    fund_pay = {f: v for (f, val), v in load_fund_pay().items() if val == "2022"}

    # one benchmark per council: best phase 1 route
    bench = {}
    for r in csv.DictReader(open(os.path.join(HERE, "phase1_sample_results.csv"), encoding="utf-8-sig")):
        if r["LEA"] not in BENCH:
            continue
        rank = ROUTE_RANK[r["Route"][:2]]
        if r["LEA"] not in bench or rank < bench[r["LEA"]][0]:
            bench[r["LEA"]] = (rank, r)

    out = []
    for name, (rank, r) in bench.items():
        ons, lea = BENCH[name]
        cash = float(r["Certificate_cash_GBP"]) if r["Certificate_cash_GBP"] else None
        pct = printed_pct(main_csv[lea]["Total_2022_year1"]) if cash is not None else None
        out.append(dict(LEA=lea, Benchmark_source="Fund annual report, " + r["Route"],
                        Benchmark_payroll_2023_24=float(r["Payroll_2023_24_GBPm"]) * 1e6,
                        ons=ons, pct=pct, cash=cash))
    for lea, ons, pct, cash, eq in FOOTNOTES:
        out.append(dict(LEA=lea, Benchmark_source="2022 certificate footnote equivalent rate",
                        Benchmark_payroll_2023_24=cash / ((eq - pct) / 100), ons=ons, pct=pct, cash=cash))

    rows = []
    for b in out:
        net21, base21 = payroll(ro, cfr, b["ons"], "2021-22")
        net23, base23 = payroll(ro, cfr, b["ons"], "2023-24")
        est = {"A_base_year": base21, "B_base_uplifted": base21 * UPLIFT["2022"], "C_year1_actual_RO": base23}
        bp = b["Benchmark_payroll_2023_24"]
        row = {"LEA": b["LEA"], "Benchmark_source": b["Benchmark_source"],
               "RO_net_employees_2021_22_GBPm": round(net21 / 1e6, 1),
               "Benchmark_payroll_2023_24_GBPm": round(bp / 1e6, 1)}
        fp = fund_pay.get(main_csv[b["LEA"]]["Fund"])
        # A council cannot have more payroll than its whole fund: flag > 90%
        row["Est_base_share_of_whole_fund_pay_2021_22"] = round(base21 / fp, 2) if fp else ""
        row["Flag"] = "EXCEEDS_90PCT_OF_FUND" if fp and base21 / fp > 0.9 else ""
        for k, v in est.items():
            row[f"Est_payroll_{k}_GBPm"] = round(v / 1e6, 1)
            row[f"Payroll_err_{k}_pct"] = round((v / bp - 1) * 100, 1)
        if b["cash"] is not None and b["pct"] is not None:
            truth = b["pct"] + b["cash"] / bp * 100
            row["Cert_line_2022"] = f"{b['pct']}% plus £{b['cash']:,.0f}"
            row["Benchmark_total_pct"] = round(truth, 2)
            for k, v in est.items():
                row[f"Est_total_{k}_pct"] = round(b["pct"] + b["cash"] / v * 100, 2)
                row[f"Total_err_{k}_pp"] = round(b["pct"] + b["cash"] / v * 100 - truth, 2)
        rows.append(row)

    cols = []
    for r in rows:
        cols += [c for c in r if c not in cols]
    path = os.path.join(HERE, "phase5_ro_cfr_validation.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"Assumptions: participation {PARTICIPATION}, on-cost {ONCOST:.3f}, uplift 2022 {UPLIFT['2022']}")
    for k in ["A_base_year", "B_base_uplifted", "C_year1_actual_RO"]:
        pe = [r[f"Payroll_err_{k}_pct"] for r in rows]
        te = [abs(r[f"Total_err_{k}_pp"]) for r in rows if f"Total_err_{k}_pp" in r]
        print(f"{k:20} payroll err: median {st.median(pe):+.1f}%  mean abs {st.mean(map(abs, pe)):.1f}%  "
              f"| total rate abs err (n={len(te)}): median {st.median(te):.2f}pp, max {max(te):.2f}pp")
    print("wrote", path)
    estimate_main_csv(ro, cfr)


if __name__ == "__main__":
    main()
