# Getting Started with AcquireMock

This guide walks through setting up AcquireMock v2.0 locally or with Docker Compose, applying Alembic database migrations, and creating your first payment.

## Option 1: Docker Compose (Recommended)

Docker Compose starts four coordinated services: `db` (PostgreSQL 15), `migrate` (`alembic upgrade head`), `app` (Gunicorn/Uvicorn API + console UI), and `worker` (`python -m app.worker`).

### 1. Clone and configure secrets

```bash
git clone https://github.com/ashfromsky/acquiremock.git
cd acquiremock
cp .env.example .env
```

Generate two distinct strong secrets (>= 32 characters) and an administrator bcrypt password hash:

```bash
python3 -c "import secrets; print('WEBHOOK_SECRET=' + secrets.token_urlsafe(32)); print('SESSION_SECRET=' + secrets.token_urlsafe(32))"
python3 -c "import bcrypt; print('ADMIN_PASSWORD_HASH=\'' + bcrypt.hashpw(b'your-strong-password', bcrypt.gensalt(12)).decode() + '\'')"
```

Set `WEBHOOK_SECRET`, `SESSION_SECRET`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD_HASH` in `.env`. Docker Compose fails closed if any of these four variables is missing.

### 2. Start the stack

```bash
docker compose up --build -d
```

Verify service health:

```bash
curl -s http://localhost:8000/health
```

Expected response:

```json
{"status": "ok"}
```

To sign in to the Developer Console, visit `http://localhost:8000/app/login` and enter `ADMIN_USERNAME` and your plain password.

---

## Option 2: Local Python + Node.js Setup

### Prerequisites

- Python 3.12+
- Node.js 22+
- SQLite (default) or PostgreSQL 15+

### 1. Install backend dependencies

```bash
git clone https://github.com/ashfromsky/acquiremock.git
cd acquiremock
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and ensure `WEBHOOK_SECRET`, `SESSION_SECRET`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD_HASH` are configured. Note that `ALLOW_LOCAL_WEBHOOKS` defaults to `false`; set `ALLOW_LOCAL_WEBHOOKS=true` only if you want local webhook tests to target `localhost` or private IP addresses.

### 3. Build frontend assets

```bash
cd frontend
npm ci
npm run build
cd ..
```

### 4. Apply database migrations

AcquireMock v2.0 uses Alembic for schema management and does **not** create tables automatically on startup:

```bash
.venv/bin/alembic upgrade head
```

### 5. Run the API server and worker

Start the FastAPI application:

```bash
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Start the dedicated background worker in a second terminal for automatic payment expiration and webhook retries:

```bash
.venv/bin/python -m app.worker
```

For single-process local development only, you may instead set `ENABLE_EMBEDDED_WORKER=true` in `.env`.

---

## Creating Your First Payment

AcquireMock uses integer minor currency units for `amount` (for example, `25000` equals `$250.00` USD):

```bash
curl -X POST http://localhost:8000/api/create-invoice \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 25000,
    "reference": "ORDER-1001",
    "webhook_url": "https://example.com/webhooks/acquiremock",
    "redirect_url": "https://example.com/checkout/complete"
  }'
```

Response:

```json
{
  "pageUrl": "http://localhost:8000/checkout/<payment_id>"
}
```

Open `pageUrl` in your browser to test the checkout UI, card entry, OTP verification (`waiting_for_otp` -> `paid`), and webhook delivery.

### Test Cards

| Card Number | Outcome |
| --- | --- |
| `4444 4444 4444 4444` (any future expiry, any 3-digit CVV) | Enters `waiting_for_otp`, settles as `paid` after valid OTP |
| `5555 5555 5555 5555` | Declined with `402 INSUFFICIENT_FUNDS` |
| Any other valid Luhn number | Enters `waiting_for_otp`, settles as `paid` after valid OTP |

---

## Next Steps

- [API Reference](./api-reference.md)
- [Webhook Integration Guide](./webhook-guide.md)
- [Issues](https://github.com/ashfromsky/acquiremock/issues)
- [Discussions](https://github.com/ashfromsky/acquiremock/discussions)
