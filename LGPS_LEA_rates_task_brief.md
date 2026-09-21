# Task: LGPS employer contribution rate change, by LEA, 2022 vs 2025 valuations

## Objective

For each Local Education Authority (LEA) in England and Wales, find that
specific council's own employer pension contribution rate in the 2022 LGPS
valuation and the 2025 LGPS valuation, and calculate the change. Not the
whole-fund average - the council's own line in the Rates and Adjustments
Certificate. Output a single CSV covering all funds.

## Why this distinction matters

Early attempts used each fund's headline "primary rate" (a payroll-weighted
average across every employer in the fund - district councils, colleges,
academies, contractors, parish councils, etc). This is NOT the LEA's own
rate and can differ from it substantially. Example already found:

| | Whole-fund average | Hampshire County Council specifically |
|---|---|---|
| Primary rate 2022 | 18.3% | 17.8% |
| Primary rate 2025 | 18.8% | 18.9% |
| Change | +0.5pp | +1.1pp |

The council's own rate rose more than twice as much as the fund average
suggested. Always extract the named council's own line, not the headline
fund-wide figure.

## Data sources

`lgps_fund_report_urls.csv` (delivered alongside this brief) has one row per
fund with `URL_2025` and `URL_2022` - the direct PDF links for both
valuations, already resolved from the Scheme Advisory Board's index pages
(https://lgpsboard.org/reports/triennial-valuations/root/fund-valuations-2025/
and .../fund-valuations-2022/). 87 rows (86 funds; Environment Agency's
active and closed sections count separately and are not real LEAs - skip
them). No re-scraping of the index pages should be needed.

## What to extract from each report

Every report has, near the end, an **"Appendix: Rates and Adjustments
Certificate"** - a long table listing every participating employer with
their primary rate, secondary rate, and total contribution rate for the
three years of that valuation cycle. Find the LEA's own row (see matching
notes below) and record:

- **Primary rate** (% of pay) - always a single clean percentage, most
  reliable field to compare across funds and years
- **Total contribution rate** for the first year of the cycle, if easily
  available (2026/27 for the 2025 valuation, 2023/24 for the 2022
  valuation) - useful supplementary figure, but secondary rates are often
  cash amounts rather than percentages for large councils (see gotchas),
  so don't block on this if it's not a clean percentage

Do not use the fund-wide "Fund primary rate" quoted in the Executive
Summary / dashboard sections - that is the payroll-weighted average
described above, not the council's own rate.

## Matching the LEA's own row

Employer naming is inconsistent across funds and even across the two years
within the same fund. Known patterns seen so far:

- Usually a plain match: "Essex County Council", "Kent County Council"
- Sometimes suffixed: "Hampshire County Council Group", "Surrey County
  Council Pool" (2022) vs "Surrey County Council Pool" (2025, same)
- Sometimes split into two rows for the same council: Staffordshire has
  both "Staffordshire County Council (excl. schools)" and "Staffordshire
  County Council LEA Schools" as separate lines with different rates - use
  the "(excl. schools)" / non-schools line for consistency with other
  funds, and note the schools line separately if easy to capture
- Metropolitan and Welsh funds may cover several LEAs each (e.g. Greater
  Manchester covers 10 boroughs, West Yorkshire covers 5, Tyne and Wear
  covers 5, Merseyside covers 5, South Yorkshire covers 4, Rhondda Cynon
  Taf / Cardiff / Swansea / Clwyd / Dyfed / Gwynedd / Greater Gwent cover
  Welsh unitary authorities) - extract every LEA row in these funds, not
  just one
- **Employer codes are the most reliable cross-year matching key where
  present**: the same employer typically keeps the same code (e.g. Essex
  County Council is employer code "1" in both the 2022 and 2025 Essex
  reports). If a code appears in both years' tables, match on that rather
  than on name text, since names occasionally change slightly between
  cycles (e.g. "Essex County Council" (2025) vs "Essex County Council
  (incl. former GM schools)" (2022) - same code "1", same council)

## Known gotchas

- **Report size**: these are long documents (50-90 pages), and funds with
  many academies or admitted bodies (Essex, Staffordshire, Kent, Hampshire
  all seen so far) can run to several hundred employer rows. Extract only
  the target row(s) - don't process the whole employer table.
- **Report structure varies by actuary.** Four actuarial firms produce
  these: Hymans Robertson, Barnett Waddingham, Aon, Mercer. Appendix
  numbering and section titles differ between them (e.g. Hymans' Section
  13 dashboard is usually "Appendix 5"; Barnett Waddingham's dashboard is
  usually "Appendix 7"), but every report has a Rates and Adjustments
  Certificate near the end with the same substantive content.
- **Secondary rate format varies by employer size within the same
  report**: large councils often have a cash secondary contribution (e.g.
  "£14,198,000") rather than a percentage, while smaller employers and
  academies get a percentage secondary rate. This is normal - just take
  the primary rate as the reliable comparable figure.
- **2025 reports also include a Section 13 / GAD dashboard appendix**
  with a "3-year average total employer contribution rate" for the whole
  fund and both years - useful as a sense-check for the fund average, but
  again this is fund-wide, not the LEA's own figure.
- **Pre-paid contributions**: some councils pre-pay their whole three-year
  secondary contribution as a lump sum with a stated discount rate (see
  Staffordshire's "Notes to the Rates & Adjustments Certificate" for an
  example) - this doesn't change the primary rate, just how the secondary
  is presented.

## Output format

One CSV, one row per LEA (not per fund - metropolitan/Welsh funds produce
several rows each):

```
LEA, Fund, Primary_2022, Primary_2025, Primary_change_pp, Total_2022_year1, Total_2025_year1, Notes
```

`Notes` should flag anything uncertain: ambiguous name matches, LEAs with
schools split into a separate row, funds where the actuary's report format
made extraction unusually difficult, etc. Better to flag uncertainty than
to guess silently.

## Progress so far (manual work, this session)

4 LEAs fully complete, 1 in progress:

| LEA | Fund | Primary 2022 | Primary 2025 | Change |
|---|---|---|---|---|
| Hampshire County Council | Hampshire | 17.8% | 18.9% | +1.1pp |
| Surrey County Council | Surrey | 18.9% | 15.8% | -3.1pp |
| Kent County Council | Kent | 20.5% | 16.6% | -3.9pp |
| Essex County Council | Essex | 21.7% | 18.2% | -3.5pp |
| Staffordshire County Council | Staffordshire | *pending* | 19.0% | *pending* |

(Full detail, including the employer-code and row-text evidence for each,
is in the conversation this brief was drawn from if a re-check is ever
needed - not reproduced here for brevity.)

## Practical note on running this

Each report fetch has turned out to be very large - several of the four
completed funds involved reports with hundreds of employer rows (academy
trusts in particular). An agent with the ability to fetch a URL, extract
just the relevant few lines via text search/regex rather than loading the
whole document into a context window, and move on to the next fund
without carrying prior reports' full text forward, should handle this far
more efficiently than doing it conversationally. That's the reason for
handing this off.
