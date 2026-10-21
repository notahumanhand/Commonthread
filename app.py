import os
import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)

DATABASE_PATH = (
    Path(__file__).resolve().parent
    / "tools"
    / "commonthread_synthetic_data"
    / "data"
    / "commonthread.sqlite"
)

QUALIFYING_GIFT = "status = 'completed' AND amount_cents > 0"
VALID_METRICS = {
    "unique_donors",
    "first_time_donors",
    "total_giving",
    "amount_per_donor",
    "gifts_per_donor",
}
VALID_GRANULARITIES = {"month", "quarter", "year"}
VALID_GIFT_TYPES = {"one_time", "recurring", "matching", "major_gift"}


def get_db_connection():
    """Open the bundled SQLite database read-only."""
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Commonthread database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(
        DATABASE_PATH.as_uri() + "?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def fiscal_year_start(year):
    return date(year - 1, 7, 1)


def parse_date(value, fallback):
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid date: {value}. Use YYYY-MM-DD.")


def fiscal_year_range(year):
    return date(year - 1, 7, 1), date(year, 7, 1)


def get_filters(args):
    today = date.today()
    default_start, default_end_exclusive = fiscal_year_range(min(max(today.year, 2022), 2026))
    start_date = parse_date(args.get("start_date"), default_start)
    end_date = parse_date(args.get("end_date"), default_end_exclusive.fromordinal(default_end_exclusive.toordinal() - 1))
    if start_date > end_date:
        raise ValueError("Start date must be on or before end date.")

    metric = args.get("metric", "unique_donors")
    granularity = args.get("granularity", "month")
    gift_type = args.get("gift_type", "all")
    if metric not in VALID_METRICS:
        raise ValueError("Unsupported metric selection.")
    if granularity not in VALID_GRANULARITIES:
        raise ValueError("Unsupported time granularity.")
    if gift_type != "all" and gift_type not in VALID_GIFT_TYPES:
        raise ValueError("Unsupported gift type.")

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "metric": metric,
        "granularity": granularity,
        "academic_unit_id": args.get("academic_unit", "all"),
        "cohort": args.get("cohort", "all"),
        "campaign_id": args.get("campaign", "all"),
        "gift_type": gift_type,
    }


def filter_sql(filters, alias="g", include_dates=True, include_cohort=True):
    clauses = [QUALIFYING_GIFT.replace("status", f"{alias}.status").replace("amount_cents", f"{alias}.amount_cents")]
    params = []
    if include_dates:
        clauses.append(f"{alias}.gift_date >= ? AND {alias}.gift_date <= ?")
        params.extend([filters["start_date"], filters["end_date"]])
    if filters["academic_unit_id"] != "all":
        clauses.append(f"{alias}.academic_unit_id = ?")
        params.append(filters["academic_unit_id"])
    if filters["campaign_id"] != "all":
        clauses.append(f"{alias}.campaign_id = ?")
        params.append(filters["campaign_id"])
    if filters["gift_type"] != "all":
        clauses.append(f"{alias}.gift_type = ?")
        params.append(filters["gift_type"])
    if include_cohort and filters["cohort"] != "all":
        # Cohort is defined relative to the selected reporting period's end year.
        end_year = int(filters["end_date"][:4])
        years_since_grad = f"({end_year} - a.graduation_year)"
        cohort_ranges = {
            "recent": (f"{years_since_grad} BETWEEN 0 AND 5"),
            "early": (f"{years_since_grad} BETWEEN 6 AND 15"),
            "established": (f"{years_since_grad} BETWEEN 16 AND 30"),
            "senior": (f"{years_since_grad} >= 31"),
        }
        clauses.append(f"EXISTS (SELECT 1 FROM alumni a WHERE a.alumni_id = {alias}.alumni_id AND {cohort_ranges[filters['cohort']]})")
    return " AND ".join(clauses), params


def bucket_expression(granularity, alias="g"):
    if granularity == "year":
        # Fiscal-year labels: FY2022 begins in July 2021.
        return f"'FY' || CAST(CAST(strftime('%Y', {alias}.gift_date) AS INTEGER) + (CAST(strftime('%m', {alias}.gift_date) AS INTEGER) >= 7) AS TEXT)"
    if granularity == "quarter":
        return (
            f"'FY' || CAST(CAST(strftime('%Y', {alias}.gift_date) AS INTEGER) + "
            f"(CAST(strftime('%m', {alias}.gift_date) AS INTEGER) >= 7) AS TEXT) || ' Q' || "
            f"CAST(((CAST(strftime('%m', {alias}.gift_date) AS INTEGER) + 5) % 12) / 3 + 1 AS INTEGER)"
        )
    return f"strftime('%Y-%m', {alias}.gift_date)"


def bucket_sort_expression(granularity, alias="g"):
    if granularity == "year":
        return f"(CAST(strftime('%Y', {alias}.gift_date) AS INTEGER) + (CAST(strftime('%m', {alias}.gift_date) AS INTEGER) >= 7))"
    if granularity == "quarter":
        return (
            f"(CAST(strftime('%Y', {alias}.gift_date) AS INTEGER) * 12 + "
            f"CAST(strftime('%m', {alias}.gift_date) AS INTEGER))"
        )
    return f"strftime('%Y-%m', {alias}.gift_date)"


def metric_value(metric, gift_count, donors, giving, first_time_donors):
    if metric == "unique_donors":
        return donors
    if metric == "first_time_donors":
        return first_time_donors
    if metric == "total_giving":
        return giving / 100
    if metric == "amount_per_donor":
        return (giving / donors / 100) if donors else None
    if metric == "gifts_per_donor":
        return (gift_count / donors) if donors else None
    return 0


def build_dashboard_data(connection, filters):
    where, params = filter_sql(filters)
    # The first qualifying gift is determined from full university-wide history,
    # before applying the selected dashboard filters.
    first_gift_cte = f"""
        WITH first_gift AS (
            SELECT alumni_id, MIN(gift_date) AS first_gift_date
            FROM gifts
            WHERE {QUALIFYING_GIFT}
            GROUP BY alumni_id
        )
    """
    bucket = bucket_expression(filters["granularity"])
    bucket_sort = bucket_sort_expression(filters["granularity"])
    rows = connection.execute(
        first_gift_cte + f"""
        SELECT {bucket} AS period, MIN({bucket_sort}) AS sort_value,
               COUNT(*) AS gift_count,
               COUNT(DISTINCT g.alumni_id) AS donors,
               COALESCE(SUM(g.amount_cents), 0) AS giving,
               COUNT(DISTINCT CASE WHEN fg.first_gift_date = g.gift_date THEN g.alumni_id END) AS first_time_donors
        FROM gifts g
        JOIN first_gift fg ON fg.alumni_id = g.alumni_id
        WHERE {where}
        GROUP BY period
        ORDER BY sort_value, period
        """,
        params,
    ).fetchall()

    series = []
    for row in rows:
        series.append({
            "period": row["period"],
            "gift_count": row["gift_count"],
            "donors": row["donors"],
            "giving_cents": row["giving"],
            "first_time_donors": row["first_time_donors"],
            "value": metric_value(filters["metric"], row["gift_count"], row["donors"], row["giving"], row["first_time_donors"]),
        })

    summary = connection.execute(
        f"""SELECT COUNT(*) AS gift_count,
                   COUNT(DISTINCT g.alumni_id) AS donors,
                   COALESCE(SUM(g.amount_cents), 0) AS giving
            FROM gifts g
            WHERE {where}""",
        params,
    ).fetchone()

    # Calculate first-time donors for the whole selected date range, using full history.
    first_where, first_params = filter_sql(filters, alias="g", include_dates=True)
    first_time_count = connection.execute(
        first_gift_cte + f"""
        SELECT COUNT(DISTINCT g.alumni_id)
        FROM gifts g
        JOIN first_gift fg ON fg.alumni_id = g.alumni_id AND fg.first_gift_date = g.gift_date
        WHERE {first_where}
        """,
        first_params,
    ).fetchone()[0]

    campaign_rows = connection.execute(
        """SELECT c.campaign_id, c.campaign_name, c.start_date, c.end_date,
                  c.goal_cents,
                  COALESCE(SUM(CASE WHEN g.status = 'completed' AND g.amount_cents > 0
                                    THEN g.amount_cents ELSE 0 END), 0) AS attributed_cents
           FROM campaigns c
           LEFT JOIN gifts g ON g.campaign_id = c.campaign_id
           GROUP BY c.campaign_id
           ORDER BY c.start_date, c.campaign_name"""
    ).fetchall()
    campaigns = [{
        "id": row["campaign_id"],
        "name": row["campaign_name"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "goal_cents": row["goal_cents"],
        "attributed_cents": row["attributed_cents"],
        "attainment": row["attributed_cents"] / row["goal_cents"] if row["goal_cents"] else 0,
    } for row in campaign_rows]

    # Transaction detail is paginated and uses exactly the selected filters.
    transaction_where, transaction_params = filter_sql(filters)
    detail_rows = connection.execute(
        f"""SELECT g.gift_id, g.gift_date, g.amount_cents, g.gift_type,
                   a.first_name || ' ' || a.last_name AS donor_name,
                   u.unit_name, c.campaign_name
            FROM gifts g
            JOIN alumni a ON a.alumni_id = g.alumni_id
            JOIN academic_units u ON u.academic_unit_id = g.academic_unit_id
            LEFT JOIN campaigns c ON c.campaign_id = g.campaign_id
            WHERE {transaction_where}
            ORDER BY g.gift_date DESC, g.gift_id DESC
            LIMIT 25""",
        transaction_params,
    ).fetchall()
    transactions = [{
        "gift_id": row["gift_id"],
        "gift_date": row["gift_date"],
        "amount_cents": row["amount_cents"],
        "gift_type": row["gift_type"],
        "donor_name": row["donor_name"],
        "unit_name": row["unit_name"],
        "campaign_name": row["campaign_name"],
    } for row in detail_rows]

    return {
        "filters": filters,
        "summary": {
            "gift_count": summary["gift_count"],
            "donors": summary["donors"],
            "giving_cents": summary["giving"],
            "first_time_donors": first_time_count,
            "amount_per_donor_cents": summary["giving"] / summary["donors"] if summary["donors"] else None,
            "gifts_per_donor": summary["gift_count"] / summary["donors"] if summary["donors"] else None,
        },
        "series": series,
        "campaigns": campaigns,
        "transactions": transactions,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/about")
def about():
    return render_template("about.html")


@app.get("/home")
def home():
    """Keep legacy dashboard URLs working by redirecting to the homepage."""
    return redirect(url_for("index"))


@app.get("/data")
def data():
    return render_template("data.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/dashboard/options")
def dashboard_options():
    connection = get_db_connection()
    try:
        units = connection.execute(
            "SELECT academic_unit_id AS id, unit_name AS name FROM academic_units ORDER BY unit_name"
        ).fetchall()
        campaigns = connection.execute(
            "SELECT campaign_id AS id, campaign_name AS name FROM campaigns ORDER BY campaign_name"
        ).fetchall()
        min_date, max_date = connection.execute(
            "SELECT MIN(gift_date), MAX(gift_date) FROM gifts"
        ).fetchone()
        return jsonify({
            "academic_units": [dict(row) for row in units],
            "campaigns": [dict(row) for row in campaigns],
            "min_date": min_date,
            "max_date": max_date,
        })
    finally:
        connection.close()


@app.get("/api/dashboard/transactions")
def dashboard_transactions_api():
    try:
        filters = get_filters(request.args)
        period_start = parse_date(request.args.get("period_start"), date.fromisoformat(filters["start_date"]))
        period_end = parse_date(request.args.get("period_end"), date.fromisoformat(filters["end_date"]))
        if period_start > period_end:
            raise ValueError("Transaction period start must be on or before its end.")
        filters["start_date"] = max(period_start, date.fromisoformat(filters["start_date"])).isoformat()
        filters["end_date"] = min(period_end, date.fromisoformat(filters["end_date"])).isoformat()
        if filters["start_date"] > filters["end_date"]:
            return jsonify({"transactions": []})
        connection = get_db_connection()
        try:
            where, params = filter_sql(filters)
            rows = connection.execute(
                f"""SELECT g.gift_id, g.gift_date, g.amount_cents, g.gift_type,
                           a.first_name || ' ' || a.last_name AS donor_name,
                           u.unit_name, c.campaign_name
                    FROM gifts g
                    JOIN alumni a ON a.alumni_id = g.alumni_id
                    JOIN academic_units u ON u.academic_unit_id = g.academic_unit_id
                    LEFT JOIN campaigns c ON c.campaign_id = g.campaign_id
                    WHERE {where}
                    ORDER BY g.gift_date DESC, g.gift_id DESC
                    LIMIT 25""",
                params,
            ).fetchall()
            return jsonify({"transactions": [{
                "gift_id": row["gift_id"], "gift_date": row["gift_date"],
                "amount_cents": row["amount_cents"], "gift_type": row["gift_type"],
                "donor_name": row["donor_name"], "unit_name": row["unit_name"],
                "campaign_name": row["campaign_name"],
            } for row in rows]})
        finally:
            connection.close()
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        app.logger.exception("Dashboard database is unavailable")
        return jsonify({"error": str(error)}), 500


@app.get("/api/dashboard")
def dashboard_api():
    try:
        filters = get_filters(request.args)
        connection = get_db_connection()
        try:
            return jsonify(build_dashboard_data(connection, filters))
        finally:
            connection.close()
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        app.logger.exception("Dashboard database is unavailable")
        return jsonify({"error": str(error)}), 500



# Raw data page: filtering, sorting, pagination, and CSV export.
DATA_SORT_COLUMNS = {
    "gift_id": "g.gift_id",
    "gift_date": "g.gift_date",
    "donor": "a.last_name",
    "graduation_year": "a.graduation_year",
    "unit": "u.unit_name",
    "campaign": "c.campaign_name",
    "amount": "g.amount_cents",
    "gift_type": "g.gift_type",
    "status": "g.status",
}


def data_query_filters(args):
    allowed_statuses = {"all", "completed", "refunded", "voided"}
    allowed_types = {"all", "one_time", "recurring", "matching", "major_gift"}
    status = args.get("status", "all")
    gift_type = args.get("gift_type", "all")
    unit = args.get("academic_unit", "all")
    campaign = args.get("campaign", "all")
    search = args.get("search", "").strip()[:120]
    start_date = args.get("start_date", "").strip()
    end_date = args.get("end_date", "").strip()

    if status not in allowed_statuses:
        raise ValueError("Unsupported transaction status.")
    if gift_type not in allowed_types:
        raise ValueError("Unsupported gift type.")
    for value in (start_date, end_date):
        if value:
            parse_date(value, date.today())
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date must be on or before end date.")

    clauses = []
    params = []
    if status != "all":
        clauses.append("g.status = ?")
        params.append(status)
    if gift_type != "all":
        clauses.append("g.gift_type = ?")
        params.append(gift_type)
    if unit != "all":
        clauses.append("g.academic_unit_id = ?")
        params.append(unit)
    if campaign != "all":
        if campaign == "none":
            clauses.append("g.campaign_id IS NULL")
        else:
            clauses.append("g.campaign_id = ?")
            params.append(campaign)
    if start_date:
        clauses.append("g.gift_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("g.gift_date <= ?")
        params.append(end_date)
    if search:
        clauses.append("""(
            CAST(g.gift_id AS TEXT) LIKE ? OR
            (a.first_name || ' ' || a.last_name) LIKE ? OR
            u.unit_name LIKE ? OR COALESCE(c.campaign_name, '') LIKE ? OR
            g.gift_type LIKE ? OR g.status LIKE ? OR g.note LIKE ?
        )""")
        pattern = f"%{search}%"
        params.extend([pattern] * 7)
    return (" AND ".join(clauses) if clauses else "1 = 1"), params


DATA_SELECT = """
    SELECT g.gift_id, g.alumni_id, a.first_name || ' ' || a.last_name AS donor_name,
           a.graduation_year, g.academic_unit_id, u.unit_name,
           g.campaign_id, c.campaign_name, g.gift_date, g.amount_cents,
           g.gift_type, g.status, g.note
    FROM gifts g
    JOIN alumni a ON a.alumni_id = g.alumni_id
    JOIN academic_units u ON u.academic_unit_id = g.academic_unit_id
    LEFT JOIN campaigns c ON c.campaign_id = g.campaign_id
"""


def get_data_page(connection, args, include_pagination=True):
    where, params = data_query_filters(args)
    sort = args.get("sort", "gift_date")
    direction = args.get("direction", "desc").lower()
    if sort not in DATA_SORT_COLUMNS:
        raise ValueError("Unsupported sort column.")
    if direction not in {"asc", "desc"}:
        raise ValueError("Sort direction must be asc or desc.")
    order = DATA_SORT_COLUMNS[sort]
    order_direction = direction.upper()
    count = connection.execute(
        f"""SELECT COUNT(*)
            FROM gifts g
            JOIN alumni a ON a.alumni_id = g.alumni_id
            JOIN academic_units u ON u.academic_unit_id = g.academic_unit_id
            LEFT JOIN campaigns c ON c.campaign_id = g.campaign_id
            WHERE {where}""",
        params,
    ).fetchone()[0]
    query = f"{DATA_SELECT} WHERE {where} ORDER BY {order} {order_direction}, g.gift_id DESC"
    page = 1
    page_size = 50
    if include_pagination:
        try:
            page = max(1, int(args.get("page", "1")))
            page_size = int(args.get("page_size", "50"))
        except ValueError:
            raise ValueError("Page and page size must be integers.")
        if page_size not in {10, 25, 50}:
            raise ValueError("Page size must be 10, 25, or 50.")
        page = min(page, max(1, (count + page_size - 1) // page_size))
        query += " LIMIT ? OFFSET ?"
        params = params + [page_size, (page - 1) * page_size]
    rows = connection.execute(query, params).fetchall()
    return {
        "rows": [dict(row) for row in rows],
        "total": count,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (count + page_size - 1) // page_size),
        "sort": sort,
        "direction": direction,
    }


@app.get("/api/data/options")
def raw_data_options():
    connection = get_db_connection()
    try:
        units = connection.execute(
            "SELECT academic_unit_id AS id, unit_name AS name FROM academic_units ORDER BY unit_name"
        ).fetchall()
        campaigns = connection.execute(
            "SELECT campaign_id AS id, campaign_name AS name FROM campaigns ORDER BY campaign_name"
        ).fetchall()
        min_date, max_date = connection.execute(
            "SELECT MIN(gift_date), MAX(gift_date) FROM gifts"
        ).fetchone()
        return jsonify({
            "academic_units": [dict(row) for row in units],
            "campaigns": [dict(row) for row in campaigns],
            "min_date": min_date,
            "max_date": max_date,
        })
    finally:
        connection.close()


@app.get("/api/data")
def raw_data_api():
    try:
        connection = get_db_connection()
        try:
            return jsonify(get_data_page(connection, request.args))
        finally:
            connection.close()
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        app.logger.exception("Commonthread database is unavailable")
        return jsonify({"error": str(error)}), 500


@app.get("/api/data/export.csv")
def raw_data_csv():
    import csv
    import io

    try:
        connection = get_db_connection()
        try:
            result = get_data_page(connection, request.args, include_pagination=False)
        finally:
            connection.close()
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        app.logger.exception("Commonthread database is unavailable")
        return jsonify({"error": str(error)}), 500

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "Gift ID", "Alumni ID", "Donor", "Graduation Year",
        "Academic Unit ID", "Academic Unit", "Campaign ID", "Campaign",
        "Gift Date", "Amount (USD)", "Gift Type", "Status", "Note",
    ])
    for row in result["rows"]:
        writer.writerow([
            row["gift_id"], row["alumni_id"], row["donor_name"], row["graduation_year"],
            row["academic_unit_id"], row["unit_name"], row["campaign_id"] or "",
            row["campaign_name"] or "", row["gift_date"],
            f'{row["amount_cents"] / 100:.2f}', row["gift_type"], row["status"], row["note"],
        ])
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="commonthread-gifts.csv"'},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
