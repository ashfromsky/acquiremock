from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core.limiter import limiter

templates = Jinja2Templates(directory="templates/pages")
router = APIRouter(tags=["pages"])

@router.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})
