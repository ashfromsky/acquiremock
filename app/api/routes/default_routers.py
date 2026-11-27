import html
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import BASE_URL
from app.core.limiter import limiter

templates = Jinja2Templates(directory="templates/pages")
router = APIRouter(tags=["pages"])

REPO_ROOT = Path(__file__).resolve().parents[3]
SPA_INDEX_PATH = REPO_ROOT / "frontend" / "dist" / "index.html"


def render_spa_or_fallback(
    request: Request,
    fallback_template: str,
    extra_ctx: Optional[dict] = None,
) -> HTMLResponse:
    if SPA_INDEX_PATH.is_file():
        content = SPA_INDEX_PATH.read_text(encoding="utf-8")
        meta_tag = f'<meta name="acquiremock-base-url" content="{html.escape(BASE_URL, quote=True)}">'
        if "<!-- BASE_URL_META -->" in content:
            content = content.replace("<!-- BASE_URL_META -->", meta_tag, 1)
        elif "</head>" in content:
            content = content.replace("</head>", f"  {meta_tag}\n</head>", 1)
        return HTMLResponse(content=content)

    context = {"request": request, "base_url": BASE_URL}
    if extra_ctx:
        context.update(extra_ctx)
    return templates.TemplateResponse(request, fallback_template, context)


@router.get("/", response_class=HTMLResponse)
@limiter.limit("60/minute")
async def read_root(request: Request):
    return render_spa_or_fallback(request, "index.html")


@router.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    return render_spa_or_fallback(request, "test.html")


@router.get("/app", response_class=HTMLResponse)
@router.get("/app/overview", response_class=HTMLResponse)
@router.get("/app/payments", response_class=HTMLResponse)
@router.get("/app/payments/{payment_id}", response_class=HTMLResponse)
@router.get("/app/testing", response_class=HTMLResponse)
@router.get("/app/webhooks", response_class=HTMLResponse)
@router.get("/app/settings", response_class=HTMLResponse)
@router.get("/app/login", response_class=HTMLResponse)
async def app_shell(request: Request):
    return render_spa_or_fallback(request, "index.html")
