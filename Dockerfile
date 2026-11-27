FROM node:22-alpine AS frontend-builder

WORKDIR /src/frontend

COPY app/static/css/tokens.css /src/app/static/css/tokens.css
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-builder /src/frontend/dist /app/frontend/dist

RUN groupadd --system appuser && useradd --system --gid appuser --no-create-home appuser && chown -R appuser:appuser /app

USER appuser

EXPOSE ${PORT:-8000}

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health')"

CMD ["sh", "-c", "exec gunicorn app.main:app --workers ${WORKERS:-2} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000}"]
