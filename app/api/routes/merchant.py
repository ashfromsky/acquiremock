from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.api.routes.default_routers import render_spa_or_fallback
from app.core.config import CURRENCY_SYMBOL

router = APIRouter(
    prefix="/merchant",
    tags=["merchant"],
)


@router.get("/login", response_class=HTMLResponse)
async def merchant_login(request: Request):
    return render_spa_or_fallback(request, "login.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def merchant_dashboard(request: Request):
    return render_spa_or_fallback(
        request,
        "dashboard.html",
        {"currency_symbol": CURRENCY_SYMBOL},
    )
