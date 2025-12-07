from datetime import datetime
from fastapi import APIRouter

from app.core.config import CURRENCY_CODE

router = APIRouter(
    tags=["system"],
)


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "currency": CURRENCY_CODE
    }