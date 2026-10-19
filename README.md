# Commonthread

A minimal, Docker-ready starting point for Commonthread, an interactive university advancement analytics portfolio project.

## Current status

The site intentionally contains only:
- The title **Commonthread**
- A green, gold, and tan/brown colour scheme
- The message **This website is currently in progress**

No analytics, database, API, or frontend framework has been implemented yet.

## Technology

- Python 3.12
- Flask
- HTML and CSS
- Docker

Flask is used only to serve the placeholder page. This is a deliberately small initial scaffold and can be replaced with the planned React + TypeScript and ASP.NET Core architecture as development progresses.

## Run locally with Python

Python 3.12 or later is recommended.

```bash
python -m venv .venv
```

Activate the virtual environment:

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

Build the image from the repository root:

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
4. Deploy. The container listens on `0.0.0.0:8000`.

The application also reads the `PORT` environment variable, allowing the listening port to be configured by the hosting platform.

## Project structure

```text
commonthread/
├── app.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
├── README.md
└── templates/
    └── index.html
```

## Licence

No licence has been selected yet. Add one before accepting external contributions or distributing the project under explicit open-source terms.
