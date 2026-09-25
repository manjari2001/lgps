# Phase 5: RO + CFR payroll route (validation only)

Estimates a council's LGPS pensionable payroll from published spending data,
to turn "X% plus £Y" certificate totals into a single percentage.
Run: `python3 method_testing/phase5_ro_cfr_model.py` (downloads data to `method_testing/.cache/`).

    payroll = (RSX total employees - fire employees - CFR E01+E02 teachers)
              x 0.95 participation / 1.291 on-costs x pay growth to certificate year 1

Tested on 22 English councils with an independent payroll (19 from fund annual
reports, phase 1; 3 from 2022 certificate footnotes giving an equivalent %).
15 have a cash secondary, so the rebuilt total % can be compared directly.

| Variant | Payroll error, median | Payroll error, mean abs | Total rate error, median abs | Total rate error, max abs |
|---|---|---|---|---|
| A: base year only (2021-22), no uplift | -15.3% | 18.6% | 0.51pp | 6.43pp |
| B: base year x 1.152 growth to 2023/24 | -2.4% | 15.3% | 0.62pp | 3.93pp |
| C: actual RO 2023-24 (year 1) | -1.2% | 15.9% | 0.69pp | 1.72pp |

Findings:
- Assumptions hold on average: 0.95 / 1.291 = 0.736, and the mean ratio of benchmark payroll to RO-net-of-teachers was about 0.73.
- The base year (2021-22) must be uplifted to the certificate's year 1 (2023/24). Pay grew 15.2% (median of 144 LAs). Without this, payroll is 15% too low and secondary % too high.
- Individual councils scatter by roughly ±15% (worst +50%, Lewisham). Rate error is about secondary% x payroll error, so it matters most where the cash secondary is large relative to payroll (worst: Windsor & Maidenhead, +3.9pp).
- Lambeth and Lewisham estimates exceed their whole fund's actual pay, which is impossible. RO employee costs there include staff outside the council's line (likely VA/foundation school staff and other separately-employed groups). The `Flag` column catches this.
- Not tested: the 2025 cycle (no independent 2024-25 or 2026/27 council payroll yet), and Wales (not in RO/CFR).
- AAR is not used: academies are separate LGPS employers, so they are in neither the council's line nor RO employee costs.
