FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ ./templates/
COPY static/ ./static/

# Render may supply PORT; default to 8000 for local Docker runs.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --access-logfile - --error-logfile - app:app"]
