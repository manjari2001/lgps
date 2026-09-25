# Phase 5: rebuilding mixed total rates from RO + CFR payroll

Many certificate totals are printed as "X% plus £Y" (a percentage plus a cash
sum). To express them as one percentage we need the council's LGPS payroll,
which certificates almost never disclose. This phase estimates that payroll
from published spending data, tests it against councils where payroll is
already known, and writes estimates with an error band into the main CSV.

Run: `python3 method_testing/phase5_ro_cfr_model.py` (downloads source data to
`method_testing/.cache/`). This rewrites `phase5_ro_cfr_validation.csv` and the
`Est_*` columns of the main CSV. The printed `Total_*` columns are never changed.

## The calculation

    payroll_base  = (RO employee costs - fire employees - CFR teacher costs)
                    x 0.95 participation / 1.291 on-costs
    payroll_year1 = payroll_base x pay growth to certificate year 1
    total %       = X + Y / payroll_year1
    error band    = +/- 25% of (Y / payroll_year1)

| Input | Source | Why |
|---|---|---|
| Employee costs | MHCLG Revenue Outturn RSX, "Total Service Expenditure - Employees" (£000) | All staff the council pays, including maintained schools |
| Fire employees | RSX, "Fire and rescue services - Employees" | Firefighters are in the Firefighters' Pension Scheme |
| Teacher costs | DfE CFR, maintained schools E01 teaching + E02 supply teaching (£) | Teachers are in the Teachers' Pension Scheme |
| 0.95 participation | Assumption | Share of staff in the LGPS (the rest have opted out) |
| 1.291 on-costs | 8.6% employer NI + 20% employer pension + 0.5% apprenticeship levy | RO costs include on-costs; payroll excludes them |
| Pay growth | 2022 cycle: 1.152 (actual median RO growth, 144 LAs). 2025 cycle: 1.063 (3.2% 2025 award x an assumed 3.0% for 2026) | See "Which year" below |

AAR (academies) is not used. Academies are separate LGPS employers, so their
staff are in neither the council's certificate line nor its RO employee costs.
Welsh councils cannot be estimated, because RO and CFR cover England only.

## Which year, and why

The base year is the financial year ending on the valuation date: that is the
pay the actuary saw. The cash in the certificate is for **year 1**, which
starts a year after the valuation date. Dividing by year-1 payroll is what
turns the cash into the right percentage.

| | 2022 valuation | 2025 valuation |
|---|---|---|
| Valuation date | 31 Mar 2022 | 31 Mar 2025 |
| Base year (pay the actuary saw) | 2021-22 | 2024-25 |
| Certificate year 1 (year the cash is due) | 2023/24 | 2026/27 |

Pay grew 15.2% from 2021-22 to 2023/24 (two £1,925 NJC awards). Using
base-year pay without the uplift makes payroll 15% too low and the rebuilt
total too high.

## Ground truth and benchmarks (22 English councils)

Certificates almost never give a council's own payroll, so testing needs an
independent payroll from elsewhere. Three tiers:

| Tier | Councils | Payroll source | Quality |
|---|---|---|---|
| 1 | Harrow, Lambeth, Lewisham | 2022 certificate footnote giving an equivalent %: payroll = cash / (equivalent % - printed %) | Exact: the actuary's own figure. But these lines are pools, not only the council |
| 2 | Dorset, BCP (member £ / stated member rate); Derbyshire, Luton, Central Beds, Bedford, Liverpool (employer normal £ / primary rate) | 2023-24 fund annual reports, per-employer contributions | Good: the divisor is a known rate |
| 3 | West Sussex, Cambridgeshire, Greenwich, Wokingham, Windsor & Maidenhead, Bristol, Bath & NE Somerset, Bromley, Gateshead, Newcastle, North Tyneside, Sunderland | 2023-24 fund annual reports: member £ / an assumed 6.5% average member rate | Weaker: real average member rates run 5.5-7.5%, so about +/-10% error of their own |

Tiers 2 and 3 come from a previous session (`phase1_sample_results.csv`),
which extracted per-employer contributions from 2023-24 fund annual reports.
2023-24 is year 1 of the 2022 certificates, so these are exactly the right year.

15 of the 22 have a cash secondary, so the rebuilt total % can be checked.
For those, the "truth" total is X + Y / benchmark payroll. For the other 7,
only the payroll can be checked.

## Results (2022 cycle, base year x 1.152)

| Benchmark tier | Councils | Median payroll error | Councils with a rate check | Median rate error | Worst rate error |
|---|---|---|---|---|---|
| All | 22 | 13% | 15 | 0.62pp | 3.93pp |
| Tier 2 | 7 | 7.5% | 7 | 0.19pp | 1.10pp |
| Tier 3 | 12 | 17% | 5 | 0.78pp | 3.93pp |
| Tier 1 | 3 | 24% | 3 | 1.06pp | 1.47pp |

Without the uplift, payroll is 15% too low (median). The median rate error
looks slightly smaller (0.51pp), but the worst case is 6.43pp.

The rate error scales with the size of the secondary. Error ÷ secondary was
within ±25% for 12 of the 15 councils, and at most 33% for any.
The three above 25% were Lambeth and Lewisham (the fund check below now
excludes them) and Windsor & Maidenhead (31%). Hence the quoted band:
**± 25% of the rebuilt secondary**.
Example: 19.3% + a rebuilt secondary of 5.0pp = 24.3% ± 1.25pp.

## The 2025 cycle

There is no ground truth for 2025. No 2025 certificate prints an equivalent %
for a council's own line: Lambeth's footnote covers LEA schools only. And
2026/27 fund annual reports and RO data don't exist yet. The inputs (RO and
CFR 2024-25) are published, but the uplift to 2026/27 has to be forecast.
The main error source (council-level scatter) doesn't depend on the cycle, so
the same ±25% band is used. A 2% miss in the forecast uplift moves a rate by
only 2% of its secondary. Check the 2026 NJC award and update `UPLIFT["2025"]`
once it is known.

## Main CSV columns

| Column | Meaning |
|---|---|
| `Est_payroll_2022_year1_GBPm` / `_2025_` | Estimated 2023/24 / 2026/27 payroll, £m |
| `Est_total_2022_year1` / `_2025_` | Rebuilt single total % |
| `Est_total_2022_error_pp` / `_2025_` | ± band in percentage points (25% of the secondary, minimum 0.1) |
| `Est_notes` | Why a mixed cell has no estimate, or a caveat on one |

Filled only where the printed total is mixed. 72 mixed cells: 61 estimated,
8 withheld by the whole-fund check, 3 Welsh.

## Things that trip people up

1. **The % in "X% plus £Y" is not always the primary rate.** Harrow's primary is 17.8% but its line prints 16.0% + £6m. The formula uses the printed X.
2. **Tier 2/3 "truth" is itself an estimate.** Part of the measured error is benchmark error, so the method's real accuracy is probably between the Tier 2 figure and the all-council figure.
3. **The whole-fund check.** If estimated payroll is more than 90% of the whole fund's actual pay, there is no estimate. It happens in single-borough London funds (Lambeth, Lewisham, Camden, Tower Hamlets, Ealing, Islington, Havering, Barnet), where RO costs include staff outside the council's line, probably voluntary-aided and foundation school staff.
4. **Non-schools lines.** Several certificates put the council's own staff and its school staff on separate lines (Staffordshire, Cambridgeshire, Cornwall, Wiltshire and others). The estimate includes school support staff, so it may overstate payroll and understate the total. Removing school support staff was tested: it fixed Cambridgeshire (+34% → -1%) but broke Windsor & Maidenhead (-24% → -71%, most non-school services outsourced). So it is flagged in `Est_notes`, not applied.
5. **Only the uplift is measured.** 0.95 and 1.291 are assumptions, not fitted. They matched on average: 0.95 / 1.291 = 0.736 against an observed mean of 0.73.
6. **Actual year-1 RO data** (2023-24 for the 2022 cycle) has the best worst case (1.7pp) but can't be used for 2025, so it is only a check.
7. **Year 1 only.** Years 2 and 3 of each certificate have different cash sums.
8. **Signs and multiple cash items.** "less £Y" is a negative secondary (the Merseyside councils). Durham 2022 has two cash items ("plus £1,415,000 plus £5,481,000 in April"), which are summed.
9. **Units and codes.** RO is in £000s, CFR in £. Councils are matched by ONS code, because of the reorganisations (Somerset, North Yorkshire, Cumbria splitting into Cumberland and Westmorland & Furness).
