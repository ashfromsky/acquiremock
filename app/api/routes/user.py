import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.core.session import get_db
from app.functional.main_functions import get_user_data
from app.security.crypto import verify_signed_email_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["user"],
)


@router.get("/user-info")
async def get_user_info_api(
    request: Request,
    email: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    verified_email = verify_signed_email_token(request.cookies.get("user_session"))
    if not verified_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    if email and email != verified_email:
        raise HTTPException(status_code=403, detail="Forbidden")

    operations, cards = await get_user_data(verified_email, db)
    return {
        "operations": [
            {
                "reference": op.reference,
                "amount": op.amount,
                "card_mask": op.card_mask,
                "date": op.created_at.strftime("%Y-%m-%d %H:%M")
            }
            for op in operations
        ],
        "cards": [
            {
                "id": c.id,
                "mask": c.card_mask,
                "expiry": c.expiry
            }
            for c in cards
        ]
    }
