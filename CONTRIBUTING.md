# Contributing to AcquireMock

Thank you for contributing to AcquireMock.

## Development Setup

1. Clone the repository:

```bash
git clone https://github.com/ashfromsky/acquiremock.git
cd acquiremock
```

2. Create a Python virtual environment, install dependencies, and copy `.env.example`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx aiosqlite ruff
cp .env.example .env
```

3. Apply database migrations with Alembic:

```bash
.venv/bin/alembic upgrade head
```

4. Install and build the frontend:

```bash
cd frontend
npm ci
npm run build
cd ..
```

5. Start the API server and dedicated background worker:

```bash
.venv/bin/uvicorn app.main:app --reload
```

In a second terminal (or set `ENABLE_EMBEDDED_WORKER=true` for single-process local dev):

```bash
.venv/bin/python -m app.worker
```

## Running Tests

### Backend

```bash
TESTING=true \
DATABASE_URL=sqlite+aiosqlite:///:memory: \
WEBHOOK_SECRET=test-webhook-secret-key-at-least-32-characters \
SESSION_SECRET=test-session-secret-key-at-least-32-characters \
ADMIN_USERNAME=admin \
ADMIN_PASSWORD_HASH='$2b$12$i/bda5DB0i74vSubiIswMe6rBh9Ft4wVxieTuJbTo.PgMYHvzovC.' \
.venv/bin/pytest -v
```

### Frontend

```bash
cd frontend
npm run typecheck
npm test
npm run build
```

## Coding Standards

- Preserve existing module boundaries (`app/api/routes/`, `app/services/`, `app/security/`, `app/models/`).
- Keep all monetary amounts in integer minor units (never use floats for currency values).
- Never store secrets in code or commit `.env` files.
- Add or update regression tests for every bug fix and security change.
- Update relevant files in `docs/` when API contracts or configuration change.

## Pull Request Process

1. Create a feature or fix branch (`feat/...` or `fix/...`).
2. Verify Alembic migrations (`alembic upgrade head`), backend `pytest`, and frontend `typecheck`, `test`, and `build` all pass.
3. Open a pull request against the target branch with a clear description of the changes and verification results.
