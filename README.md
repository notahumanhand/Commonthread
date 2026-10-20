# Commonthread functional Home dashboard update

This update replaces `app.py`, `templates/home.html`, and `static/css/styles.css`, adds `static/js/home.js`, and updates `Dockerfile` so the SQLite database is included in the container.

## Apply the update

Copy the supplied files into the matching paths in your repository. Keep the database at:

`tools/commonthread_synthetic_data/data/commonthread.sqlite`

The dashboard uses Flask API routes backed by the bundled SQLite database. It opens SQLite in read-only mode. No additional Python dependencies are required beyond the existing Flask and Gunicorn requirements.

## Local test

From the repository root, install the requirements if needed and run:

```bash
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:8000/home`. API endpoints are:

- `/api/dashboard/options`
- `/api/dashboard`
- `/api/dashboard/transactions`

The dashboard supports date range, academic unit, graduation cohort, campaign, and gift-type filters; metric and granularity selectors; campaign timeline overlays; campaign goal progress; and click-through from a chart point to the supporting transaction list.

## Docker

The updated Dockerfile copies `tools/commonthread_synthetic_data/data/` into the image. Build from the repository root so this path is inside the Docker build context:

```bash
docker build -t commonthread .
docker run --rm -p 8000:8000 commonthread
```

## Notes

- Qualifying gifts are `status = 'completed' AND amount_cents > 0`.
- Fiscal years run July 1 through June 30.
- First-time donor status is based on the earliest qualifying gift in full university-wide history.
- Campaign overlay timing is contextual and does not establish causation.
- The transaction table displays up to 25 matching rows. This is a first functional dashboard iteration, not yet full server-side pagination or CSV export.
