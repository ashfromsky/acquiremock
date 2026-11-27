# AcquireMock API Reference

Base URL: `http://localhost:8000` (configurable via `APP_HOST`)

All monetary `amount` fields are integers in the smallest currency unit (minor units), such as cents for USD (`25000` = `$250.00`), whole units for 0-decimal currencies like JPY (`1000` = `¥1,000`), and thousandths for 3-decimal currencies like KWD (`1500` = `1.500 KWD`).

---

## Public & Payment Endpoints

### Health Check

`GET /health`

Returns database connectivity health (`200 OK`):

```json
{"status": "ok"}
```

Returns `503 Service Unavailable` if the database check fails.

### Create Invoice

`POST /api/create-invoice` — Rate limit: `30/minute`

Request body:

```json
{
  "amount": 25000,
  "reference": "ORDER-1001",
  "webhook_url": "https://merchant.example.com/webhooks/acquiremock",
  "redirect_url": "https://merchant.example.com/return"
}
```

Validation notes:
- `amount`: positive integer in minor units (`> 0`).
- `reference`: optional string (`<= 120` chars, control characters rejected).
- `webhook_url`: required HTTP/HTTPS URL passing SSRF validation.
- `redirect_url`: optional HTTP/HTTPS URL passing safe URL validation.

Response (`200 OK`):

```json
{
  "pageUrl": "http://localhost:8000/checkout/pay_..."
}
```

### Hosted Checkout Page

`GET /checkout/{payment_id}` — Serves the HTML checkout page, sets the CSRF token cookie, and expires overdue payments automatically.

### Submit Card Payment

`POST /api/pay/{payment_id}` — Rate limit: `5/minute`

Content-Type: `application/x-www-form-urlencoded`

Required fields:
- `email`: payer email address (required)
- `csrf_token`: must match `csrf_token` cookie (constant-time verified)
- Card fields: either `(card_number, expiry, cvv)` or `saved_card_id` (requires valid `user_session` cookie)
- Optional: `save_card` (`"on"` / `"true"` to save a card for customer email sessions)

Optional header:
- `Idempotency-Key`: scoped per `(payment_id, idempotency_key)`. Replaying the exact same request returns the recorded response; reusing the same key with a different payload returns `409 Conflict`; concurrent in-flight requests with the same key return `409 Conflict`.

### OTP Verification & Resend

- `POST /otp/verify/{payment_id}` — Rate limit: `10/minute` (keyed by IP and `payment_id`). Verifies OTP code against bcrypt hash, enforces OTP expiration and a 5-attempt lockout (`429 OTP_MAX_ATTEMPTS`). On success, transitions atomically from `waiting_for_otp` to `paid`, records `SuccessfulOperation`, dispatches email receipt (if SMTP is configured), and triggers webhook delivery.
- `POST /otp/resend/{payment_id}` — Rate limit: `5/minute` (keyed by IP and `payment_id`). Rotates OTP and extends expiration, capped at `3` resends (`429`).

---

## Customer Saved-Card Authentication (`/api/auth/*` & `/api/user/*`)

Used solely for customer saved cards at checkout (never grants administrative console access):

- `POST /api/auth/send-code` (`5/minute`) — Sends a one-time email verification code backed by `auth_challenges`.
- `POST /api/auth/verify-code` (`10/minute`) — Verifies the code and sets signed HttpOnly `user_session` cookie.
- `POST /api/auth/logout` — Clears `user_session` cookie.
- `GET /api/user/cards` — Lists masked saved cards for the authenticated customer email.
- `DELETE /api/user/cards/{card_id}` — Deletes a saved card owned by the authenticated customer.

---

## Administrator Authentication (`/api/admin/*`)

Required before accessing any `/api/console/*` route. Fails closed (`503`) if `ADMIN_USERNAME` or `ADMIN_PASSWORD_HASH` is unset.

### Admin Login

`POST /api/admin/login` — Rate limit: `5/minute`

Request JSON:

```json
{
  "username": "admin",
  "password": "your-admin-password"
}
```

Sets:
- `admin_session`: HttpOnly signed session cookie backed by `admin_sessions` in the database.
- `admin_csrf`: readable CSRF cookie paired with `X-CSRF-Token` header on mutating admin/console requests.

### Admin Session Status

`GET /api/admin/session` — Returns `{authenticated, username, configured, expires_at}`.

### Admin Logout

`POST /api/admin/logout` — Requires valid `admin_session` and `X-CSRF-Token`, revokes the server-side `AdminSession` record, and clears cookies.

---

## Developer Console Endpoints (`/api/console/*`)

All endpoints below require an authenticated administrator session (`401` if unauthenticated, `503` if admin auth is not configured):

- `GET /api/console/config` — Non-secret gateway configuration (`currency_code`, `currency_symbol`, `currency_decimals`, `payment_ttl_minutes`, `webhook_max_attempts`, `webhook_timeout_seconds`, `allow_local_webhooks`).
- `GET /api/console/overview` — Aggregate counts, `paid_volume` (integer minor units), webhook delivery stats (`scheduled_retries`, `exhausted`, etc.), recent payments, and recent webhook logs.
- `GET /api/console/payments` — Filterable/paginated payments list (`status`, `q`, `limit`, `offset`) including `webhook_delivery_state`, `webhook_can_retry`, and `webhook_next_attempt_at`.
- `GET /api/console/payments/{payment_id}` — Payment details and full `webhook_logs` delivery history (`trigger`: `"auto"` or `"manual"`).
- `GET /api/console/webhooks` — Webhook delivery logs and aggregate delivery counters.
- `POST /api/console/webhooks/{payment_id}/retry` — Rate limit: `10/minute`. Requires `admin_session` AND `X-CSRF-Token`. Enforces:
  1. Payment must exist and have `status == "paid"`.
  2. Webhook must not already be `webhook_status == "succeeded"`.
  3. Attempts must be below `WEBHOOK_MAX_ATTEMPTS`.
  4. Target URL must pass live SSRF validation.

---

## Support

- **Issues:** [GitHub Issues](https://github.com/ashfromsky/acquiremock/issues)
- **Discussions:** [GitHub Discussions](https://github.com/ashfromsky/acquiremock/discussions)
