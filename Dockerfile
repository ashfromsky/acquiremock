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

EXPOSE ${PORT}

CMD gunicorn app.main:app --workers ${WORKERS:-1} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT}
