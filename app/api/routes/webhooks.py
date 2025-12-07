import logging
from fastapi import APIRouter, Request, HTTPException
from app.services.webhook_service import verify_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)


@router.post("/verify")
async def verify_webhook(request: Request):
    data = await request.json()
    signature = request.headers.get("X-Signature")

    if not signature:
        raise HTTPException(400, "Missing signature")

    is_valid = verify_webhook_signature(data, signature)

    return {"valid": is_valid}