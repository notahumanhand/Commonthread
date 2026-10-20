#!/usr/bin/env python3
"""Deterministically generate Commonthread's fictional advancement reporting dataset."""
from __future__ import annotations
import argparse
import json
import random
import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

SEED = 20261019
ALUMNI_COUNT = 1000
DB_NAME = "commonthread.sqlite"
UNITS = [
    ("U01", "School of Arts and Letters", "Humanities"),
    ("U02", "School of Commerce", "Professional"),
    ("U03", "School of Learning", "Professional"),
    ("U04", "School of Engineering", "STEM"),
    ("U05", "School of Health and Life Sciences", "STEM"),
    ("U06", "School of Creative Practice", "Arts"),
]
CAMPAIGNS = [
    # id, name, start, end, goal cents, category, unit, story
    ("C01", "First Steps Challenge", "2023-09-01", "2023-11-30", 2_000_000, "Participation", None, "first_time"),
    ("C02", "Founders Circle Initiative", "2024-02-01", "2024-12-31", 18_000_000, "Major Gifts", "U02", "major_gift"),
    ("C03", "Learning Futures Fund", "2022-10-01", "2023-06-30", 5_000_000, "Annual Giving", "U03", "weak"),
    ("C04", "Winter Giving Week", "2022-12-01", "2022-12-15", 1_500_000, "Participation", None, "seasonal"),
    ("C05", "Access for All", "2025-01-15", "2025-06-30", 7_000_000, "Scholarships", "U01", "moderate"),
    ("C06", "Tomorrow's Makers", "2025-09-01", "2026-04-30", 12_000_000, "Capital", "U04", "moderate"),
    ("C07", "Community Health Appeal", "2024-10-01", "2025-03-31", 4_000_000, "Annual Giving", "U05", "moderate"),
    ("C08", "Arts in Reach", "2023-04-01", "2024-03-31", 3_500_000, "Participation", "U06", "weak"),
    ("C09", "Future Scholars Match", "2025-11-15", "2026-01-31", 2_500_000, "Matching", "U03", "first_time"),
    ("C10", "Quiet Campus Renewal", "2022-07-01", "2026-06-30", 30_000_000, "Annual Giving", None, "weak"),
]

FIRST_NAMES = [
    "Avery", "Jordan", "Morgan", "Riley", "Casey", "Taylor", "Quinn", "Rowan",
    "Cameron", "Reese", "Parker", "Hayden", "Emerson", "Finley", "Skyler",
    "Alex", "Jamie", "Robin", "Dakota", "Sage", "Ellis", "Kendall", "Micah",
    "Arden", "Remy", "Shiloh", "Drew", "Blair", "Jules", "River", "Marlowe",
]
LAST_NAMES = [
    "Ashford", "Bellamy", "Calder", "Dunley", "Ellery", "Fenwick", "Grafton",
    "Hollis", "Iverson", "Juniper", "Kestrel", "Linden", "Merritt", "North",
    "Oakley", "Pritchard", "Quill", "Rowley", "Sutter", "Tolland", "Umber",
    "Vale", "Whitlock", "Yarrow", "Zephyr", "Alder", "Briar", "Corwin",
]
CITIES = ["Northbridge", "Lakehaven", "Westmere", "Pine Crossing", "Fairwater",
          "Stonefield", "Cedar Hollow", "Brightwell", "Redfern", "Mapleford"]
STATES = ["PA", "OH", "MI", "VA", "NC", "NY", "MA", "IL", "CO", "OR"]
DEGREES = ["BA", "BS", "BFA", "MA", "MS", "MBA", "PhD"]
GIFT_TYPES = ["one_time", "recurring", "matching", "major_gift"]
STATUSES = ["completed", "refunded", "voided"]

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE academic_units (
    academic_unit_id TEXT PRIMARY KEY,
    unit_name TEXT NOT NULL UNIQUE,
    unit_category TEXT NOT NULL
);
CREATE TABLE alumni (
    alumni_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    graduation_year INTEGER NOT NULL CHECK (graduation_year BETWEEN 1975 AND 2026),
    academic_unit_id TEXT NOT NULL REFERENCES academic_units(academic_unit_id),
    degree_type TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    engagement_score INTEGER NOT NULL CHECK (engagement_score BETWEEN 0 AND 100)
);
CREATE TABLE campaigns (
    campaign_id TEXT PRIMARY KEY,
    campaign_name TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    goal_cents INTEGER NOT NULL CHECK (goal_cents > 0),
    campaign_category TEXT NOT NULL,
    academic_unit_id TEXT REFERENCES academic_units(academic_unit_id),
    intended_story TEXT NOT NULL,
    CHECK (start_date <= end_date)
);
CREATE TABLE gifts (
    gift_id INTEGER PRIMARY KEY,
    alumni_id INTEGER NOT NULL REFERENCES alumni(alumni_id),
    campaign_id TEXT REFERENCES campaigns(campaign_id),
    academic_unit_id TEXT NOT NULL REFERENCES academic_units(academic_unit_id),
    gift_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    gift_type TEXT NOT NULL CHECK (gift_type IN ('one_time','recurring','matching','major_gift')),
    status TEXT NOT NULL CHECK (status IN ('completed','refunded','voided')),
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_gifts_date ON gifts(gift_date);
CREATE INDEX ix_gifts_alumni_date ON gifts(alumni_id, gift_date);
CREATE INDEX ix_gifts_campaign ON gifts(campaign_id);
CREATE INDEX ix_gifts_unit_date ON gifts(academic_unit_id, gift_date);
CREATE INDEX ix_alumni_unit_grad ON alumni(academic_unit_id, graduation_year);
"""

def fiscal_year(d: date) -> int:
    return d.year + 1 if d.month >= 7 else d.year

def parse_date(s: str) -> date:
    return date.fromisoformat(s)

def daterange(start: date, end: date) -> int:
    return (end - start).days

def weighted_choice(rng, values, weights):
    return rng.choices(values, weights=weights, k=1)[0]

def generate(db_path: Path, seed: int = SEED, alumni_count: int = ALUMNI_COUNT) -> dict:
    rng = random.Random(seed)
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO academic_units VALUES (?,?,?)", UNITS)
    conn.executemany("INSERT INTO campaigns VALUES (?,?,?,?,?,?,?,?)", CAMPAIGNS)

    # Cohort at FY2026 end (2026-06-30): recent 0-5, early 6-15,
    # established 16-30, senior 31+. These are descriptive bins, not fixed donor labels.
    cohort_targets = [(2021, 2026, 0.25), (2011, 2020, 0.30),
                      (1996, 2010, 0.25), (1975, 1995, 0.20)]
    cohort_labels = ["recent", "early_career", "established", "senior"]
    cohort_weights = [0.25, 0.30, 0.25, 0.20]
    unit_weights = [0.22, 0.16, 0.15, 0.17, 0.18, 0.12]
    alumni = {}
    for aid in range(1, alumni_count + 1):
        cohort_i = weighted_choice(rng, list(range(4)), cohort_weights)
        lo, hi, _ = cohort_targets[cohort_i]
        grad = rng.randint(lo, hi)
        unit = weighted_choice(rng, [u[0] for u in UNITS], unit_weights)
        # Stable latent propensity induces repeated-giving correlation across years.
        propensity = rng.betavariate(2.0 + cohort_i * 0.35, 6.5 - cohort_i * 0.65)
        engagement = max(0, min(100, int(propensity * 115 + rng.gauss(0, 10))))
        row = (
            aid,
            rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES), grad, unit,
            rng.choice(DEGREES), rng.choice(CITIES), rng.choice(STATES), engagement
        )
        conn.execute("INSERT INTO alumni VALUES (?,?,?,?,?,?,?,?,?)", row)
        alumni[aid] = {"grad": grad, "unit": unit, "prop": propensity,
                       "engagement": engagement, "cohort_i": cohort_i}

    # One or more gifts can occur per donor. Date range is exactly FY2022-FY2026.
    start, end = date(2021, 7, 1), date(2026, 6, 30)
    gifts = []
    next_id = 1
    donor_first_qualifying = {}
    donor_gift_count = Counter()
    campaign_totals = Counter()

    # Distinct latent groups: some persistent recurring donors, many sporadic donors,
    # and a sizeable non-donor population. Annual probability differs by cohort.
    annual_base = [0.105, 0.215, 0.345, 0.435]
    years = list(range(2021, 2026))  # calendar years touched; fiscal periods below
    # Generate a pool of gift events by fiscal year to support annual trend patterns.
    fiscal_years = range(2022, 2027)
    donor_recurring = {aid: (rng.random() < (0.04 + alumni[aid]["prop"] * 0.75))
                       for aid in alumni}
    donor_last_gift = {}
    donor_ever_gave = set()

    for fy in fiscal_years:
        fy_start, fy_end = date(fy - 1, 7, 1), date(fy, 6, 30)
        for aid, a in alumni.items():
            ci = a["cohort_i"]
            p = annual_base[ci] * (0.35 + a["prop"] * 2.2)
            if aid in donor_ever_gave:
                p *= 1.12  # retention tendency
            if aid in donor_last_gift and (fy - donor_last_gift[aid]) >= 2:
                p *= 0.42  # lapsed donors are less likely to return
            p = min(0.88, p)

            # Temporary first-time campaign lift is an association-generating overlay.
            campaign_window = fy_start <= date(2023, 9, 1) <= fy_end or fy == 2024
            if campaign_window and aid not in donor_ever_gave and a["engagement"] < 55:
                p *= 1.55
            if rng.random() < p:
                count = 1
                if donor_recurring[aid] and rng.random() < 0.68:
                    count = rng.choices([1, 2, 3, 4], [0.20, 0.40, 0.28, 0.12])[0]
                elif a["prop"] > 0.48 and rng.random() < 0.22:
                    count = 2
                for j in range(count):
                    # Seasonal weights, particularly year-end (Nov-Dec) and June.
                    month = weighted_choice(rng, list(range(1, 13)),
                        [0.055,0.055,0.060,0.060,0.060,0.085,0.055,0.055,0.070,0.075,0.125,0.145])
                    day = rng.randint(1, 28)
                    d = date(fy_start.year, month, day)
                    if not (fy_start <= d <= fy_end):
                        # Keep within this fiscal year while preserving seasonal tendency.
                        d = fy_start + timedelta(days=rng.randrange((fy_end-fy_start).days + 1))
                    # Force some exact fiscal boundaries as explicit test fixtures.
                    if aid == 1 and fy == 2022 and j == 0:
                        d = date(2021, 7, 1)
                    if aid == 2 and fy == 2026 and j == 0:
                        d = date(2026, 6, 30)

                    # Campaign association, not causality: campaign presence changes
                    # event propensity and/or amount only in this synthetic scenario.
                    active = [c for c in CAMPAIGNS if parse_date(c[2]) <= d <= parse_date(c[3])]
                    campaign = None
                    if active and rng.random() < 0.58:
                        weights = []
                        for c in active:
                            story = c[7]
                            weights.append({"first_time": 1.8, "major_gift": 1.2,
                                            "moderate": 1.0, "seasonal": 1.35,
                                            "weak": 0.45}.get(story, 1.0))
                        campaign = weighted_choice(rng, active, weights)[0]

                    # Gift size: right-skewed; established/senior cohorts have larger gifts.
                    size_scale = [0.72, 1.0, 1.45, 2.1][ci]
                    if campaign == "C02":
                        size_scale *= 1.2
                    amount = int(max(1000, rng.lognormvariate(8.15, 0.9) * size_scale))
                    # A small number of major gifts dominate dollars in the major-gift campaign.
                    if campaign == "C02" and rng.random() < 0.075:
                        amount = rng.choice([2_500_000, 4_000_000, 6_500_000, 9_000_000])
                    elif rng.random() < 0.008:
                        amount = rng.choice([1_000_000, 2_000_000, 3_500_000])

                    # Add a small count of nonqualifying transaction rows.
                    status = "completed"
                    if rng.random() < 0.018:
                        status = "refunded"
                    elif rng.random() < 0.012:
                        status = "voided"
                    gift_type = "recurring" if donor_recurring[aid] and count > 1 else (
                        "major_gift" if amount >= 1_000_000 else
                        weighted_choice(rng, ["one_time", "matching"], [0.94, 0.06]))
                    gift_unit = campaign and next(c[6] for c in CAMPAIGNS if c[0] == campaign)
                    if not gift_unit:
                        gift_unit = weighted_choice(rng, [u[0] for u in UNITS], unit_weights)
                    note = ""
                    if status == "refunded":
                        note = "Synthetic full refund; excluded from qualifying totals"
                    elif status == "voided":
                        note = "Synthetic void; excluded from qualifying totals"
                    gifts.append((next_id, aid, campaign, gift_unit, d.isoformat(),
                                  amount, gift_type, status, note))
                    if status == "completed" and amount > 0:
                        donor_ever_gave.add(aid)
                        donor_last_gift[aid] = fy
                        donor_first_qualifying.setdefault(aid, d)
                        if campaign:
                            campaign_totals[campaign] += amount
                    donor_gift_count[aid] += 1
                    next_id += 1

    # Guarantee one clearly visible underperformer by retaining a low-lift campaign goal.
    # Ensure the generated transaction count stays in target bounds via deterministic
    # adjustment: add small recurring-style transactions if necessary, remove only from
    # excess tail while retaining boundary fixtures.
    target_min, target_max = 4000, 6000
    while len(gifts) < target_min:
        aid = rng.randint(1, alumni_count)
        d = start + timedelta(days=rng.randrange((end-start).days + 1))
        active = [c for c in CAMPAIGNS if parse_date(c[2]) <= d <= parse_date(c[3])]
        c = weighted_choice(rng, active, [1 if x[7] == "weak" else 2 for x in active])[0] if active else None
        unit = next((x[6] for x in CAMPAIGNS if x[0] == c and x[6]), alumni[aid]["unit"])
        gifts.append((next_id, aid, c, unit, d.isoformat(), rng.choice([2500,5000,7500,10000]),
                      "one_time", "completed", "Synthetic balancing gift to meet row-count target"))
        next_id += 1
    if len(gifts) > target_max:
        # Preserve boundary fixtures and remove excess rows from the end only.
        protected = {g[0] for g in gifts if g[4] in ("2021-07-01", "2026-06-30")}
        keep = []
        for g in gifts:
            if len(gifts) - len(keep) > target_max and g[0] not in protected:
                continue
            keep.append(g)
        gifts = keep[:target_max]

    conn.executemany("INSERT INTO gifts VALUES (?,?,?,?,?,?,?,?,?)", gifts)
    conn.commit()

    # Campaign attribution is a transaction property; active-date overlap is not attribution.
    checks = run_checks(conn)
    metadata = {
        "seed": seed,
        "alumni_count": alumni_count,
        "academic_unit_count": len(UNITS),
        "campaign_count": len(CAMPAIGNS),
        "gift_transaction_count": len(gifts),
        "date_min": min(g[4] for g in gifts),
        "date_max": max(g[4] for g in gifts),
        "qualifying_rule": "status='completed' AND amount_cents > 0",
        "currency_storage": "integer cents",
        "fiscal_year": "July 1 through June 30; FY2026 is 2025-07-01 through 2026-06-30",
        "causal_caveat": "Campaign overlays indicate temporal association only; generated patterns do not establish causal impact.",
        "checks": checks,
    }
    ((db_path.parent.parent if db_path.parent.name == "data" else db_path.parent) / "expected_checks.json").write_text(json.dumps(metadata, indent=2) + "\n")
    conn.close()
    return metadata

def run_checks(conn: sqlite3.Connection) -> dict:
    conn.execute("PRAGMA foreign_keys = ON")
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    row_counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("academic_units", "alumni", "campaigns", "gifts")}
    invalid_dates = conn.execute("""
        SELECT COUNT(*) FROM gifts
        WHERE gift_date < '2021-07-01' OR gift_date > '2026-06-30'
    """).fetchone()[0]
    qualifying = conn.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount_cents),0), COUNT(DISTINCT alumni_id)
        FROM gifts WHERE status='completed' AND amount_cents > 0
    """).fetchone()
    fy2026 = conn.execute("""
        SELECT COUNT(*) FROM gifts
        WHERE gift_date >= '2025-07-01' AND gift_date <= '2026-06-30'
    """).fetchone()[0]
    first_gifts = conn.execute("""
        WITH first_gift AS (
          SELECT alumni_id, MIN(gift_date) AS first_date
          FROM gifts WHERE status='completed' AND amount_cents > 0 GROUP BY alumni_id
        )
        SELECT COUNT(*) FROM first_gift
    """).fetchone()[0]
    non_donors = conn.execute("""
        SELECT COUNT(*) FROM alumni a
        WHERE NOT EXISTS (
          SELECT 1 FROM gifts g WHERE g.alumni_id=a.alumni_id
            AND g.status='completed' AND g.amount_cents > 0
        )
    """).fetchone()[0]
    multiple = conn.execute("""
        SELECT COUNT(*) FROM (
          SELECT alumni_id, gift_date FROM gifts
          WHERE status='completed' AND amount_cents > 0
          GROUP BY alumni_id, gift_date HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    refunded = conn.execute("SELECT COUNT(*) FROM gifts WHERE status='refunded'").fetchone()[0]
    voided = conn.execute("SELECT COUNT(*) FROM gifts WHERE status='voided'").fetchone()[0]
    campaign = conn.execute("""
        SELECT c.campaign_id, c.campaign_name, c.goal_cents,
               COALESCE(SUM(CASE WHEN g.status='completed' AND g.amount_cents>0
                                 THEN g.amount_cents ELSE 0 END),0) AS actual_cents
        FROM campaigns c LEFT JOIN gifts g ON g.campaign_id=c.campaign_id
        GROUP BY c.campaign_id ORDER BY c.campaign_id
    """).fetchall()
    return {
        "row_counts": row_counts,
        "foreign_key_violations": len(fk),
        "invalid_gift_dates": invalid_dates,
        "qualifying_gift_count": qualifying[0],
        "qualifying_giving_cents": qualifying[1],
        "unique_qualifying_donors": qualifying[2],
        "fy2026_gift_rows": fy2026,
        "donors_with_first_qualifying_gift": first_gifts,
        "non_donors": non_donors,
        "donor_date_groups_with_multiple_qualifying_gifts": multiple,
        "refunded_rows": refunded,
        "voided_rows": voided,
        "campaign_goal_check": [
            {"campaign_id": r[0], "campaign_name": r[1], "goal_cents": r[2],
             "attributed_qualifying_cents": r[3],
             "attainment_pct": round(r[3] / r[2] * 100, 2)}
            for r in campaign
        ],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/commonthread.sqlite")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--alumni", type=int, default=ALUMNI_COUNT)
    args = parser.parse_args()
    result = generate(Path(args.output), args.seed, args.alumni)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
