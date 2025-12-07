import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.core.session import get_db
from app.functional.main_functions import get_user_data

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["user"],
)


@router.get("/user-info")
async def get_user_info_api(email: str, db: AsyncSession = Depends(get_db)):
    operations, cards = await get_user_data(email, db)
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