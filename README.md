# Commonthread

A minimal, Docker-ready starting point for Commonthread, an interactive university advancement analytics portfolio project.

## Current status

The site currently contains:
- A landing/navigation page titled **Commonthread**
- Shared, reusable CSS using green, gold, and tan/brown
- Navigation links to **About**, **Home**, and **Data**
- Medium-size About and Data panels with back-to-navigation controls
- A large Home panel with a **Return to Navigation** button
- Placeholder subtitles on each destination page

The application is still a scaffold. Analytics, database, and reporting functionality have not yet been implemented.

## Technology

- Python 3.12
- Flask
- HTML and shared CSS
- Docker

Flask currently serves the pages. The intended long-term architecture may introduce React + TypeScript, ASP.NET Core, and SQLite as development progresses.

## Run locally with Python

Python 3.12 or later is recommended.

Create and activate a virtual environment:

```bash
python -m venv .venv
```

**Windows PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux**
```bash
source .venv/bin/activate
```

Install dependencies and start the site:

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000.

## Run with Docker

Build the image from the project root:

```bash
docker build -t commonthread .
```

Run the container:

```bash
docker run --rm -p 8000:8000 commonthread
```

Open http://localhost:8000.

## Deploy to Render

1. Push this repository to GitHub.
2. In Render, create a new **Web Service** and connect the GitHub repository.
3. Select **Docker** as the runtime.
4. Deploy. The container listens on `0.0.0.0` using the `PORT` environment variable (default `8000`).

The `/health` endpoint returns a simple health status.

## Project structure

```text
commonthread/
├── app.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
├── README.md
├── static/
│   └── css/
│       └── styles.css
└── templates/
    ├── index.html
    ├── about.html
    ├── home.html
    └── data.html
```

## Licence

No licence has been selected yet. Add one before accepting external contributions or distributing the project under explicit open-source terms.
