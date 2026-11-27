from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import CURRENCY_SYMBOL

templates = Jinja2Templates(directory="templates/pages")

router = APIRouter(
    prefix="/merchant",
    tags=["merchant"],
)


@router.get("/login", response_class=HTMLResponse)
async def merchant_login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse)
async def merchant_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {
        "request": request,
        "currency_symbol": CURRENCY_SYMBOL
    })