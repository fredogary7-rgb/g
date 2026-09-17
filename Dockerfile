FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# $PORT est fourni par Railway / Render / Fly.io ; 8000 en fallback.
CMD gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8000}
