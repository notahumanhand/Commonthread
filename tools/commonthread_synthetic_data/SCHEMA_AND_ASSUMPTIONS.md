# Schema and synthetic-data assumptions

## Tables

### `academic_units`
- `academic_unit_id` — stable text primary key.
- `unit_name` — unique fictional academic unit.
- `unit_category` — broad synthetic grouping.

### `alumni`
- `alumni_id` — integer primary key.
- Fictional name, graduation year, graduating academic unit, degree, synthetic city/state, and engagement score.
- `graduation_year` is the year awarded, not a dynamic cohort label. Derive cohort from the selected reporting date (or use the documented FY2026-end cohort bands only for reproducing the generator's intended population mix).

### `campaigns`
- `campaign_id` — primary key.
- `start_date`, `end_date` — inclusive ISO dates.
- `goal_cents` — target amount in integer cents.
- `academic_unit_id` — nullable unit focus.
- `intended_story` — synthetic scenario label used to document generator intent; do not expose it as a business metric unless explicitly presented as simulation metadata.

### `gifts`
- `gift_id` — transaction primary key.
- `alumni_id` — foreign key to alumni.
- `campaign_id` — nullable foreign key; only populated when the transaction is attributed to a campaign.
- `academic_unit_id` — gift-designated unit, distinct from the alumnus's graduating unit.
- `gift_date` — ISO date in the five-FY reporting window.
- `amount_cents` — nonnegative integer cents.
- `gift_type` — `one_time`, `recurring`, `matching`, or `major_gift`.
- `status` — `completed`, `refunded`, or `voided`.
- `note` — explains synthetic nonqualifying rows or balancing rows.

## Metric semantics

Use the qualifying predicate `status = 'completed' AND amount_cents > 0`.

- **Total giving:** `SUM(amount_cents)` over qualifying gift rows.
- **Gift count:** `COUNT(*)` over qualifying gift rows.
- **Unique donors:** `COUNT(DISTINCT alumni_id)` over qualifying gift rows.
- **First-time donors:** alumni whose earliest qualifying university-wide gift date is within the selected interval. Establish first-ever status against the full gift history first, then apply filters to the first gift record. If multiple qualifying gifts occur on that first date, count the person once.
- **Amount per donor:** qualifying total divided by unique donors; return N/A when the denominator is zero.
- **Gifts per donor:** qualifying gift count divided by unique donors; return N/A when the denominator is zero.
- **Returning donor:** a qualifying donor with at least one qualifying gift dated before the selected period's start.
- **Campaign attainment:** campaign-attributed qualifying dollars divided by `goal_cents`. Do not treat every gift made during campaign dates as attributed to that campaign.
- **Fiscal year:** FY2022 = 2021-07-01 through 2022-06-30; FY2026 = 2025-07-01 through 2026-06-30.

## Synthetic behavior

- Cohort bins are designed around graduation year as of 2026-06-30: recent (2021–2026), early career (2011–2020), established (1996–2010), senior (1975–1995).
- Giving is not uniform. Each alumnus has a latent propensity which influences annual participation and recurring status. Prior giving raises future participation probability; a gap of at least two fiscal years lowers it.
- Gift size is right-skewed and varies by cohort; a few major gifts create concentration.
- Gift dates are seasonally weighted toward November, December, and June.
- Campaign windows overlap. Campaign-associated gift attribution and behavior are programmed into the generator, but no causal interpretation is valid.
- The generator targets 4,000–6,000 transaction rows. The default seed generates exactly 4,000. If the naturally generated row count is below the lower bound, small balancing transactions are added. With the default seed, this adjustment is not required.

## Limitations worth disclosing

- This is an illustrative dataset, not a statistically calibrated model of a real university.
- Campaigns are synthetic scenarios. Their presence coincides with programmed patterns by design, so the data must not be used to claim causal lift or estimate a real-world treatment effect.
- The first-time campaign propensity adjustment is a generator mechanism, not proof of campaign attribution. Use the campaign ID for attributed revenue and a separate campaign date overlay for timing.
- The data models a full refund by setting the transaction status to `refunded`; it does not model partial refunds or a separate negative reversal ledger.
- Campaign goals are intentionally heterogeneous and several are intentionally over- or under-attained.
