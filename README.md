# 💳 AcquireMock

> Mock payment gateway for testing payment integrations without real money

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com)
[![Tests](https://github.com/illusiOxd/acquiremock/workflows/Tests/badge.svg)](https://github.com/illusiOxd/acquiremock/actions)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A full-featured mock payment gateway that simulates real payment flows including OTP verification, webhooks with HMAC signatures, and card storage - perfect for testing e-commerce integrations.

![Demo](assets/acquiremock.gif)

## ✨ Features

- 🎨 **Beautiful UI** - Modern checkout with dark mode & 4 languages (UK/EN/DE/RU)
- 🔐 **OTP Verification** - Email-based payment confirmation
- 🔔 **Webhooks** - HMAC-SHA256 signed callbacks with auto-retry
- 💾 **Card Storage** - Save cards for returning customers
- ⏰ **Auto-Expiry** - Payments expire after 15 minutes
- 🔄 **Idempotency** - Prevent duplicate payments
- 📊 **Transaction History** - Track all operations per user
- 🐳 **Docker Ready** - One command deployment

## 🎯 Use Cases

- Testing payment flows in development
- Learning payment gateway integration
- Building MVPs without payment provider setup
- Educational projects and demos

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
git clone https://github.com/illusiOxd/acquiremock.git
cd acquiremock
docker-compose up
```

Visit `http://localhost:8000`

### Manual Installation

```bash
# Clone repository
git clone https://github.com/illusiOxd/acquiremock.git
cd acquiremock

# Install dependencies
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Setup environment
cp .env.example .env

# Edit .env and configure your database
nano .env

# Run application
uvicorn main:app --port 8000 --reload
```

## ⚙️ Configuration

### Required

```env
# Production (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/payment_db

# Development (SQLite)
# DATABASE_URL=sqlite+aiosqlite:///./payment.db

WEBHOOK_SECRET=your-secret-key-min-32-chars
BASE_URL=http://localhost:8000
```

### Optional (Email)

⚠️ **Email is optional.** If not configured, OTP codes will be logged to console.

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

## 📡 API Usage

### Create Payment

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

def verify_webhook(payload: dict, signature: str, secret: str) -> bool:
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
        return {"error": "Invalid signature"}, 403
    
    # Process payment
    if payload["status"] == "paid":
        order = await Order.get(payment_id=payload["payment_id"])
        order.status = "paid"
        await order.save()
    
    return {"status": "ok"}
```

## 🧪 Testing

### Test Payment Card

```
Card:   4444 4444 4444 4444
CVV:    any 3 digits
Expiry: any future date (MM/YY)
```

### Run Tests

```bash
pytest tests/ -v
```

### Interactive Test Page

Visit `http://localhost:8000/test` for a built-in test interface.

## 🏗️ Architecture

```
├── main.py                 # FastAPI application
├── database/
│   ├── models/            # SQLModel schemas
│   └── functional/        # Database operations
├── services/
│   ├── smtp_service.py    # Email sending
│   ├── webhook_service.py # Webhook delivery
│   └── background_tasks.py # Async jobs
├── security/
│   ├── crypto.py          # Hashing & tokens
│   └── middleware.py      # Security headers
├── templates/             # Jinja2 HTML templates
└── static/                # CSS, JS, images
```

## 🔒 Security Features

- CSRF token validation
- HMAC-SHA256 webhook signatures
- Bcrypt password hashing for stored cards
- Security headers (XSS, Frame Options, Content-Type)
- Rate limiting (5 req/min per IP)
- Input sanitization
- Secure cookies (HTTPOnly, Secure, SameSite)

## 📊 Database Schema

### Payments
- Stores all payment attempts
- Tracks status transitions
- Records webhook delivery attempts

### Saved Cards
- Hashed card data (never plaintext)
- Linked to user email
- Used for one-click payments

### Webhook Logs
- Full audit trail
- Response status & body
- Retry attempts

## 🐳 Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:password@db:5432/payment_db
      - WEBHOOK_SECRET=${WEBHOOK_SECRET}
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

## 🔄 Migration to Real PSP

When ready for production with Stripe/Fondy:

1. Replace card validation with PSP API calls
2. Implement tokenization instead of card storage
3. Add 3D Secure flow
4. Implement refund endpoint
5. Add PCI DSS compliance measures

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

## 📝 License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## ⚠️ Disclaimer

**This is a MOCK payment gateway for testing purposes only.**

- Do NOT use in production with real payment data
- Do NOT store real credit card information
- Do NOT use for actual financial transactions

For production use, integrate with certified payment providers like Stripe, PayPal, or your regional PSP.

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [SQLModel](https://sqlmodel.tiangolo.com/) - SQL databases in Python
- [Jinja2](https://jinja.palletsprojects.com/) - Template engine

## 📬 Contact

- **Issues**: [GitHub Issues](https://github.com/illusiOxd/acquiremock/issues)
- **Discussions**: [GitHub Discussions](https://github.com/illusiOxd/acquiremock/discussions)

---

<div align="center">

**[Documentation](https://github.com/illusiOxd/acquiremock/wiki)** • 
**[Report Bug](https://github.com/illusiOxd/acquiremock/issues)** • 
**[Request Feature](https://github.com/illusiOxd/acquiremock/issues)**

Made with ❤️ for developers who need to test payments

⭐ **Star us on GitHub — it helps!**

</div>