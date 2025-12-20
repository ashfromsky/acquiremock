# AcquireMock

**Mock payment gateway for testing payment integrations without real money.**

Stop using real payment providers in development. AcquireMock simulates complete payment flows including OTP verification, webhooks, and card storage.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-blue.svg)](https://fastapi.tiangolo.com)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

![Demo](assets/acquiremock.gif)

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and start
git clone https://github.com/illusiOxd/acquiremock.git
cd acquiremock
docker-compose up
```

Visit `http://localhost:8000`

### Option 2: Manual Setup

```bash
# Clone repository
git clone https://github.com/illusiOxd/acquiremock.git
cd acquiremock

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy configuration
cp .env.example .env

# Edit configuration
nano .env

# Start application
uvicorn main:app --port 8000 --reload
```

---

## How It Works

AcquireMock simulates a real payment gateway with complete payment lifecycle:

**Basic Flow:**
```bash
# 1. Create payment
curl -X POST http://localhost:8000/api/create-invoice \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 25000,
    "reference": "ORDER-123",
    "webhookUrl": "https://your-site.com/webhook"
  }'

# 2. User completes checkout (UI)
# 3. OTP verification via email
# 4. Webhook sent to your server
# 5. Payment confirmed
```

**Test Card:**
```
Card:   4444 4444 4444 4444
CVV:    any 3 digits
Expiry: any future date (MM/YY)
```

---

## Features

- **Complete Payment Flow** - From invoice creation to webhook delivery
- **OTP Verification** - Email-based payment confirmation
- **Webhook Delivery** - HMAC-SHA256 signed callbacks with retry logic
- **Card Storage** - Save cards for returning customers
- **Transaction History** - Track all operations per user
- **Auto-Expiry** - Payments automatically expire after 15 minutes
- **Idempotency** - Prevent duplicate payment processing
- **Multi-Language UI** - Support for UK/EN/DE/RU with dark mode
- **Interactive Test Page** - Built-in testing interface

---

## Configuration

### Environment Variables

Create `.env` file with these settings:

```env
# Database (Required)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/payment_db
# For development: sqlite+aiosqlite:///./payment.db

# Security (Required)
WEBHOOK_SECRET=your-secret-key-min-32-chars
BASE_URL=http://localhost:8000

# Email (Optional - logs to console if not configured)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

### Database Options

**Production (PostgreSQL):**
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/payment_db
```

**Development (SQLite):**
```env
DATABASE_URL=sqlite+aiosqlite:///./payment.db
```

### Email Configuration

Email is optional. If not configured, OTP codes will be logged to console for testing.

For Gmail, generate an app-specific password at: https://myaccount.google.com/apppasswords

---

## Usage Examples

### Create Payment Invoice

```bash
curl -X POST http://localhost:8000/api/create-invoice \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 25000,
    "reference": "ORDER-123",
    "webhookUrl": "https://your-site.com/webhook",
    "redirectUrl": "https://your-site.com/success"
  }'
```

**Response:**
```json
{
  "pageUrl": "http://localhost:8000/checkout/{payment_id}"
}
```

### Handle Webhook

```python
import hmac
import hashlib
import json
from fastapi import Request, HTTPException

def verify_webhook(payload: dict, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature"""
    message = json.dumps(payload, sort_keys=True)
    expected = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.post("/webhook")
async def payment_webhook(request: Request):
    signature = request.headers.get("X-Signature")
    payload = await request.json()
    
    if not verify_webhook(payload, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Process payment
    if payload["status"] == "paid":
        order = await Order.get(payment_id=payload["payment_id"])
        order.status = "paid"
        await order.save()
    
    return {"status": "ok"}
```

### Webhook Payload

```json
{
  "payment_id": "pay_abc123",
  "reference": "ORDER-123",
  "amount": 25000,
  "status": "paid",
  "timestamp": "2024-12-20T10:30:00Z"
}
```

---

## Advanced Features

### Card Storage

Users can save cards for future payments:

```bash
# Payment with card storage
POST /api/create-invoice
{
  "amount": 10000,
  "reference": "ORDER-456",
  "email": "user@example.com",
  "saveCard": true
}
```

Saved cards are hashed using bcrypt and never stored in plain text.

### Transaction History

View all transactions for a user:

```bash
GET /api/transactions?email=user@example.com
```

### Interactive Testing

Visit `http://localhost:8000/test` for built-in test interface with:
- Payment creation form
- Webhook URL testing
- Response inspection
- Status tracking

---

## Security Features

AcquireMock implements production-grade security practices:

- **HMAC-SHA256 Signatures** - All webhooks are cryptographically signed
- **CSRF Protection** - Token validation on all forms
- **Bcrypt Hashing** - Secure card data storage
- **Security Headers** - XSS protection, frame options, content-type sniffing prevention
- **Rate Limiting** - 5 requests per minute per IP
- **Input Sanitization** - All user input validated and sanitized
- **Secure Cookies** - HTTPOnly, Secure, SameSite attributes
- **No Plaintext Storage** - Card data always hashed

---

## Architecture

```
acquiremock/
├── main.py                          # FastAPI application entry point
├── database/
│   ├── models/                      # SQLModel schemas
│   │   ├── payment.py              # Payment entity
│   │   ├── saved_card.py           # Saved cards
│   │   └── webhook_log.py          # Webhook delivery logs
│   └── functional/                  # Database operations
│       ├── payment_crud.py         # Payment CRUD
│       ├── card_crud.py            # Card operations
│       └── webhook_crud.py         # Webhook logging
├── services/
│   ├── smtp_service.py             # Email delivery
│   ├── webhook_service.py          # Webhook HTTP calls
│   └── background_tasks.py         # Async job processing
├── security/
│   ├── crypto.py                   # Hashing & HMAC
│   └── middleware.py               # Security headers
├── templates/                       # Jinja2 HTML templates
│   ├── checkout.html               # Payment page
│   ├── otp.html                    # OTP verification
│   └── test.html                   # Test interface
└── static/                          # CSS, JS, images
```

---

## Database Schema

### Payments Table
- payment_id (PK)
- amount
- reference
- status (pending/paid/failed/expired)
- email
- webhook_url
- created_at
- expires_at

### Saved Cards Table
- card_id (PK)
- email
- card_last4
- card_hash (bcrypt)
- created_at

### Webhook Logs Table
- log_id (PK)
- payment_id (FK)
- url
- status_code
- response_body
- attempt_number
- created_at

---

## Roadmap

### Current Status (v1.0)
- Basic payment flow with OTP verification
- Webhook delivery with HMAC signatures
- Card storage and transaction history
- Multi-language UI with dark mode

### Next Steps (v1.1-1.2)
- **Multi-PSP Emulation** - Switch between Stripe, PayPal, Square response formats
- **Custom Response Builder** - Define success/failure scenarios
- **Advanced Webhook Testing** - Simulate delays, failures, retries with custom timing
- **3D Secure Flow** - Mock authentication pages
- **Refund & Chargeback Simulation** - Test full payment lifecycle

### Future Vision (v2.0+)
- **Visual Flow Builder** - Drag-and-drop payment scenario designer
- **Plugin System** - Add custom payment methods (crypto, BNPL, etc.)
- **API Playground** - Interactive testing without writing code
- **Multi-Currency Support** - Test currency conversion scenarios
- **Fraud Detection Simulator** - Test suspicious transaction handling
- **Dashboard UI** - Visual transaction monitoring

---

## Migration to Production

When ready to use a real payment provider (Stripe, PayPal, etc.):

1. **Replace Card Validation** - Switch from mock validation to PSP API calls
2. **Implement Tokenization** - Use PSP tokens instead of card storage
3. **Add 3D Secure** - Implement authentication flow
4. **Add Refund Endpoint** - Handle refund requests
5. **PCI DSS Compliance** - Remove any card data handling
6. **Update Webhooks** - Adapt to PSP webhook format

AcquireMock's structure makes this transition straightforward - most business logic remains the same.

---

## Development

### Install for Development

```bash
# Clone repository
git clone https://github.com/illusiOxd/acquiremock.git
cd acquiremock

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Format code
black .
isort .

# Type checking
mypy .
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_webhooks.py -v

# Coverage report
pytest --cov=. --cov-report=html
```

---

## Docker Deployment

### Development

```bash
docker-compose up
```

### Production

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:password@db:5432/payment_db
      - WEBHOOK_SECRET=${WEBHOOK_SECRET}
      - BASE_URL=https://your-domain.com
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=payment_db
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Requirements

- **Python**: 3.11+
- **Database**: PostgreSQL 12+ (recommended) or SQLite
- **Docker**: Optional but recommended

---

## Use Cases

- **Development Testing** - Test payment flows without real payment providers
- **Integration Testing** - Automated tests for payment workflows
- **Learning** - Understand payment gateway integration patterns
- **MVP Development** - Build prototypes without payment provider setup
- **Educational Projects** - Demonstrate payment processing concepts
- **QA Environment** - Isolated payment testing

---

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

## License

**Apache License 2.0**

This project is free and open-source software. See [LICENSE](LICENSE) for details.

Key points:
- Free to use, modify, and distribute
- Must preserve copyright notices
- Provides patent grant
- No trademark rights granted

---

## Important Disclaimer

**This is a MOCK payment gateway for testing purposes only.**

- Do NOT use in production with real payment data
- Do NOT store real credit card information
- Do NOT use for actual financial transactions
- Do NOT use for PCI DSS compliance testing

For production use, integrate with certified payment providers like Stripe, PayPal, Square, or your regional payment service provider.

---

## Links

- **GitHub**: [https://github.com/illusiOxd/acquiremock](https://github.com/illusiOxd/acquiremock)
- **Issues**: [https://github.com/illusiOxd/acquiremock/issues](https://github.com/illusiOxd/acquiremock/issues)
- **Discussions**: [https://github.com/illusiOxd/acquiremock/discussions](https://github.com/illusiOxd/acquiremock/discussions)
- **Documentation**: [Wiki](https://github.com/illusiOxd/acquiremock/wiki)

---

**Safe payment testing for serious development.**

Built with FastAPI, SQLModel, and Jinja2 for developers who need reliable payment mocking.
