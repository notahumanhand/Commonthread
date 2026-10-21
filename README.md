# Commonthread

Commonthread is a synthetic university advancement analytics website. It demonstrates how an advancement team could explore fundraising activity, donor behavior, campaign timing, and gift-level records through an interactive dashboard.

All people, academic units, campaigns, locations, and transactions in the included database are fictional. The data is intended for demonstration and development—not as a representation of a real institution or as evidence of real fundraising outcomes.

## Website

### Advancement dashboard

The dashboard summarizes qualifying giving activity for a selected reporting period. It includes:

- **Total giving** — the sum of qualifying gift amounts.
- **Unique donors** — distinct alumni with qualifying gifts in the selected period.
- **First-time donors** — alumni whose first qualifying gift to the university falls within the selected period.
- **Gifts per donor** — qualifying gift count divided by unique donors.

Users can filter the dashboard by date range, academic unit, graduation cohort, campaign, and gift type. The trend chart can display unique donors, first-time donors, total giving, amount per donor, or gifts per donor, grouped monthly, quarterly, or by fiscal year. Selecting a chart point displays a supporting list of qualifying gift transactions.

The campaign section lists campaigns, attributed qualifying giving, and progress toward each campaign's goal. Campaign dates are shown on the trend chart as timeline bars to provide temporal context. Campaign timing and gift attribution are not proof that a campaign caused a change in giving.

### Raw gift data explorer

The Data page exposes the underlying synthetic gift transactions. Users can search records and filter by date, academic unit, campaign attribution, gift type, and status. The table supports sorting and pagination, and the currently filtered records can be exported as CSV.

The data explorer includes completed, refunded, and voided transaction rows. This makes it possible to inspect nonqualifying records and see how transaction status affects dashboard metrics.

### About page

The About page provides an overview of Commonthread, including its purpose as a synthetic university advancement analytics dashboard, its interactive reporting features, the structure and generation of its dataset, and the definitions used for fundraising metrics. It explains how users can explore giving trends, filter results by academic unit, graduation cohort, and campaign, and trace aggregate metrics to individual gift transactions. The page also documents the project's technical implementation and clarifies that all alumni, gift, and campaign records are synthetic and intended solely for demonstration and analytical exploration.

## Synthetic dataset

The website uses a bundled SQLite database generated specifically for Commonthread. The generator is deterministic for a given random seed, so the baseline dataset can be recreated.

The default generation uses seed `20261019` and creates:

- 1,000 fictional alumni
- 6 fictional academic units
- 10 fictional fundraising campaigns
- 4,000 gift transaction rows
- Gift dates from July 1, 2021 through June 30, 2026

The committed baseline dataset contains 3,964 qualifying gifts, representing $995,325.43 in qualifying giving and 963 distinct qualifying donors across the full dataset. It also contains 23 refunded rows and 13 voided rows. These values describe the generated baseline only; dashboard totals change with the selected filters.

### How the data was generated

The Python generator builds the schema and populates the database using a fixed-seed pseudo-random process. It creates fictional alumni attributes, including graduation year, degree type, academic unit, location, and an engagement score. It then generates gift activity across five fiscal years.

The generated giving patterns are intentionally varied rather than uniform:

- Alumni have different underlying giving propensities.
- Graduation cohorts have different participation patterns.
- Some donors give repeatedly or on a recurring pattern; others give sporadically, and some have no qualifying gifts.
- Prior giving can increase the likelihood of future giving, while a multi-year gap can reduce it.
- Gift amounts are right-skewed, with a small number of large gifts.
- Gift dates are seasonally weighted toward November, December, and June.
- Campaigns have distinct date ranges, goals, categories, and academic-unit associations. Campaign date ranges can overlap.

The campaign-related patterns are deliberately programmed simulation features. They are not a statistically calibrated model of a real university, and they must not be interpreted as evidence of causal campaign impact. A gift is attributed to a campaign only when its transaction record has a campaign ID; merely occurring during a campaign's active dates does not make a gift campaign-attributed.

Names are drawn from a small invented name pool and may repeat. Synthetic locations are generic values and should not be treated as real alumni residence data.

## Data definitions and reporting rules

### Qualifying gifts

A transaction contributes to the dashboard's qualifying-gift metrics only when:

`status = 'completed' AND amount_cents > 0`

Amounts are stored as integer cents to avoid floating-point storage for currency. Refunded and voided records remain available in the data explorer but are excluded from qualifying gift counts and giving totals.

### Fiscal years

The reporting calendar follows a July–June fiscal year. For example, FY2026 runs from July 1, 2025 through June 30, 2026, inclusive.

### Metric interpretation

- **Total giving:** sum of qualifying gift amounts.
- **Gift count:** number of qualifying gift transactions.
- **Unique donors:** distinct alumni with qualifying gifts in the selected interval.
- **First-time donors:** alumni whose earliest qualifying university-wide gift date falls in the selected interval. First-ever status is determined from the full dataset before applying the dashboard's other filters.
- **Amount per donor:** total qualifying giving divided by unique donors; shown as unavailable when there are no qualifying donors.
- **Gifts per donor:** qualifying gift count divided by unique donors; shown as unavailable when there are no qualifying donors.
- **Campaign attainment:** campaign-attributed qualifying giving divided by the campaign goal.

Monthly unique-donor values are distinct counts within each month. They should not be added together to calculate unique donors across a longer reporting period.

## Technology and data access

The site is implemented with Python and Flask, HTML templates, CSS, browser-side JavaScript, and SQLite. The Flask application serves the dashboard and data explorer and provides JSON endpoints for filter options, dashboard aggregates, supporting transactions, and raw-data browsing. The database is opened in read-only mode by the application.

The repository includes the generator, schema and assumptions documentation, validation SQL, expected baseline checks, and automated data tests so the synthetic dataset and its reporting assumptions can be inspected and reproduced.
