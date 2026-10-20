-- Commonthread dashboard validation queries
-- Always apply the qualification predicate consistently.
-- Total giving and gift count by fiscal year:
SELECT
  CASE WHEN CAST(strftime('%m', gift_date) AS INTEGER) >= 7
       THEN CAST(strftime('%Y', gift_date) AS INTEGER) + 1
       ELSE CAST(strftime('%Y', gift_date) AS INTEGER)
  END AS fiscal_year,
  COUNT(*) AS qualifying_gifts,
  COUNT(DISTINCT alumni_id) AS unique_donors,
  SUM(amount_cents) AS total_giving_cents
FROM gifts
WHERE status = 'completed' AND amount_cents > 0
GROUP BY fiscal_year
ORDER BY fiscal_year;

-- First-time donors by fiscal year: calculate first-ever university-wide gift first.
WITH first_gift AS (
  SELECT alumni_id, MIN(gift_date) AS first_gift_date
  FROM gifts
  WHERE status = 'completed' AND amount_cents > 0
  GROUP BY alumni_id
)
SELECT
  CASE WHEN CAST(strftime('%m', first_gift_date) AS INTEGER) >= 7
       THEN CAST(strftime('%Y', first_gift_date) AS INTEGER) + 1
       ELSE CAST(strftime('%Y', first_gift_date) AS INTEGER)
  END AS fiscal_year,
  COUNT(*) AS first_time_donors
FROM first_gift
GROUP BY fiscal_year
ORDER BY fiscal_year;

-- Campaign attainment: campaign-attributed gifts only, not every gift during active dates.
SELECT c.campaign_id, c.campaign_name, c.goal_cents,
       COALESCE(SUM(CASE WHEN g.status='completed' AND g.amount_cents > 0
                         THEN g.amount_cents ELSE 0 END), 0) AS actual_cents,
       100.0 * COALESCE(SUM(CASE WHEN g.status='completed' AND g.amount_cents > 0
                                 THEN g.amount_cents ELSE 0 END), 0)
             / c.goal_cents AS attainment_pct
FROM campaigns c
LEFT JOIN gifts g ON g.campaign_id = c.campaign_id
GROUP BY c.campaign_id, c.campaign_name, c.goal_cents
ORDER BY c.campaign_id;
