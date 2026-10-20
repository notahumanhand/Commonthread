# Commonthread synthetic advancement dataset

This folder contains a deterministic, fictional dataset for the Commonthread university advancement analytics demo. It is not affiliated with any real institution and contains no real personal data.

## Contents

- `generate_data.py` — standard-library-only deterministic generator and integrity-check report.
- `data/commonthread.sqlite` — generated SQLite database.
- `expected_checks.json` — actual aggregate checks from the committed seed/run.
- `tests/test_data.py` — automated database and metric-semantic checks.
- `SCHEMA_AND_ASSUMPTIONS.md` — table definitions, metric rules, and known limitations.

## Reproduce

Requires Python 3.10+ and SQLite (the Python standard library `sqlite3` module).

```bash
python generate_data.py --output data/commonthread.sqlite
python -m unittest discover -s tests -v
```

The default seed is `20261019`. To use another seed, pass `--seed INTEGER`. To change the alumni count, pass `--alumni INTEGER`; the standard expected checks in `expected_checks.json` apply to the default seed and 1,000 alumni only.

The generator deletes and recreates the target database path. Do not point it at a database containing data you want to preserve.

## Baseline counts and aggregate checks

Generated with seed `20261019`:

- Academic units: 6
- Alumni: 1,000
- Campaigns: 10
- Gift transaction rows: 4,000
- Date range: 2021-07-01 through 2026-06-30
- Qualifying gifts: 3,964
- Qualifying giving: $995,325.43
- Unique qualifying donors across the full dataset: 963
- Alumni with no qualifying gifts: 37
- Refunded rows: 23
- Voided rows: 13
- Foreign-key violations: 0
- FY2026 gift rows (inclusive dates 2025-07-01 through 2026-06-30): 712

See `expected_checks.json` for per-campaign attributed totals and attainment. These are regression baselines for this seed, not claims about real fundraising.

## Qualification rule

A gift qualifies when `status = 'completed' AND amount_cents > 0`. Amounts are stored as integer cents. Refunded and voided rows remain in the transaction table for data-quality and exclusion testing but do not contribute to the qualifying gift count or giving total. This simple model represents full-refund transactions as nonqualifying rows rather than posting a separate negative reversal. Do not sum all statuses indiscriminately.

## Reproducibility and attribution

The random seed and generation algorithm are fixed. The data includes recurring and sporadic behavior, donor-level giving propensity, cohort-dependent participation and gift size, seasonal weighting, campaign-date overlaps, campaign attribution, and deliberately distinct campaign scenarios. Campaign associations are synthetic design features. They do **not** establish that a campaign caused any change. A gift is campaign-attributed only when `campaign_id` is populated; active campaign dates alone do not attribute a gift.

The names are selected from a small invented name pool and can repeat; no attempt is made to resemble or identify real alumni. Cities and states are generic synthetic values and should not be interpreted as actual residence records.

## Dashboard implementation note

Use the same qualification predicate in all aggregate and drill-through SQL. Determine first-time donor status using each alumnus's first qualifying gift across the entire university-wide history before applying the selected period, unit, campaign, or gift-type filters. Monthly unique-donor counts are distinct within each month and should not be summed to obtain annual unique donors. Fiscal year `FY2026` is `2025-07-01` through `2026-06-30`, inclusive.
