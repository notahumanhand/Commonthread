import json
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "commonthread.sqlite"
EXPECTED = json.loads((ROOT / "expected_checks.json").read_text(encoding="utf-8"))

class SyntheticDataTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(DB)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def tearDown(self):
        self.conn.close()

    def scalar(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()[0]

    def test_expected_table_counts(self):
        for table, count in EXPECTED["checks"]["row_counts"].items():
            self.assertEqual(self.scalar(f"SELECT COUNT(*) FROM {table}"), count)

    def test_foreign_keys_and_date_bounds(self):
        self.assertEqual(len(self.conn.execute("PRAGMA foreign_key_check").fetchall()), 0)
        self.assertEqual(self.scalar("""
            SELECT COUNT(*) FROM gifts
            WHERE gift_date < '2021-07-01' OR gift_date > '2026-06-30'
        """), 0)

    def test_qualifying_totals_match_baseline(self):
        row = self.conn.execute("""
            SELECT COUNT(*), SUM(amount_cents), COUNT(DISTINCT alumni_id)
            FROM gifts WHERE status='completed' AND amount_cents > 0
        """).fetchone()
        checks = EXPECTED["checks"]
        self.assertEqual(row[0], checks["qualifying_gift_count"])
        self.assertEqual(row[1], checks["qualifying_giving_cents"])
        self.assertEqual(row[2], checks["unique_qualifying_donors"])

    def test_non_donors_and_nonqualifying_rows_exist(self):
        self.assertGreater(self.scalar("""
            SELECT COUNT(*) FROM alumni a WHERE NOT EXISTS (
              SELECT 1 FROM gifts g WHERE g.alumni_id=a.alumni_id
              AND g.status='completed' AND g.amount_cents > 0
            )
        """), 0)
        self.assertGreater(self.scalar("SELECT COUNT(*) FROM gifts WHERE status='refunded'"), 0)
        self.assertGreater(self.scalar("SELECT COUNT(*) FROM gifts WHERE status='voided'"), 0)

    def test_fiscal_year_2026_boundaries(self):
        self.assertGreater(self.scalar("""
            SELECT COUNT(*) FROM gifts
            WHERE gift_date >= '2025-07-01' AND gift_date <= '2026-06-30'
        """), 0)
        self.assertEqual(self.scalar("""
            SELECT COUNT(*) FROM gifts WHERE gift_date = '2026-07-01'
        """), 0)
        self.assertGreater(self.scalar("SELECT COUNT(*) FROM gifts WHERE gift_date='2026-06-30'"), 0)
        self.assertGreater(self.scalar("SELECT COUNT(*) FROM gifts WHERE gift_date='2021-07-01'"), 0)

    def test_first_time_uses_full_history(self):
        # A donor is first-time in a window only when their university-wide first
        # qualifying gift date is in that window; later gifts cannot make them new.
        self.assertEqual(self.scalar("""
            WITH first_gift AS (
              SELECT alumni_id, MIN(gift_date) AS first_date
              FROM gifts WHERE status='completed' AND amount_cents > 0
              GROUP BY alumni_id
            )
            SELECT COUNT(*) FROM first_gift
            WHERE first_date >= '2025-07-01' AND first_date <= '2026-06-30'
        """), self.scalar("""
            SELECT COUNT(*) FROM (
              SELECT alumni_id FROM gifts
              WHERE status='completed' AND amount_cents > 0
              GROUP BY alumni_id
              HAVING MIN(gift_date) >= '2025-07-01' AND MIN(gift_date) <= '2026-06-30'
            )
        """))

    def test_campaign_goals_include_under_and_over_performers(self):
        rows = self.conn.execute("""
            SELECT c.goal_cents,
              COALESCE(SUM(CASE WHEN g.status='completed' AND g.amount_cents>0
                                THEN g.amount_cents ELSE 0 END),0)
            FROM campaigns c LEFT JOIN gifts g ON g.campaign_id=c.campaign_id
            GROUP BY c.campaign_id
        """).fetchall()
        self.assertTrue(any(actual < goal for goal, actual in rows))
        self.assertTrue(any(actual > goal for goal, actual in rows))

    def test_campaign_windows_overlap(self):
        campaigns = self.conn.execute(
            "SELECT start_date, end_date FROM campaigns"
        ).fetchall()
        self.assertTrue(any(
            max(a[0], b[0]) <= min(a[1], b[1])
            for i, a in enumerate(campaigns)
            for b in campaigns[i+1:]
        ))

if __name__ == "__main__":
    unittest.main()
