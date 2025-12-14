"""
Test version of main application WITHOUT background tasks.
Used during pytest to prevent tests from hanging.
"""
import logging
import os

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.models.errors import PaymentError
from app.core.limiter import limiter
from app.security.middleware import SecurityHeadersMiddleware

from app.api.routes import (
    auth,
    payments,
    pages,
    webhooks,
    user,
    health,
    default_routers,
    merchant,
    checkout
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AcquireMock (Test)",
    version="2.0.0-test"
)

app.add_middleware(SecurityHeadersMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.exception_handler(PaymentError)
async def payment_error_handler(request: Request, exc: PaymentError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "payment_id": exc.payment_id
        }
    )


@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates/pages")
    return templates.TemplateResponse(
        "404.html",
        {"request": request},
        status_code=404
    )


app.include_router(health.router)
app.include_router(default_routers.router)
app.include_router(auth.router)
app.include_router(payments.router)
app.include_router(pages.router)
app.include_router(webhooks.router)
app.include_router(user.router)
app.include_router(merchant.router)
app.include_router(checkout.router)

logger.info("Test application initialized (no background tasks)")