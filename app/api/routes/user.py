import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.currency import format_minor_amount
from app.database.core.session import get_db
from app.functional.main_functions import get_user_data
from app.models.main_models import SavedCard
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
                "formatted_amount": format_minor_amount(op.amount),
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


@router.delete("/user/cards/{card_id}")
async def delete_user_card(
    card_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    verified_email = verify_signed_email_token(request.cookies.get("user_session"))
    if not verified_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await db.execute(
        select(SavedCard).where(
            SavedCard.id == card_id,
            SavedCard.email == verified_email
        )
    )
    card = result.scalars().first()
    if not card:
        raise HTTPException(status_code=404, detail="Saved card not found")

    await db.delete(card)
    await db.commit()
    return {"status": "deleted", "id": card_id}
