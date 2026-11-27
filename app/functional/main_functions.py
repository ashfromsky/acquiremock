from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from app.core.time import utcnow
from app.models.main_models import Payment, PaymentStatus, SavedCard, SuccessfulOperation, WebhookLog


async def send_successful_operation(session: AsyncSession, operation: SuccessfulOperation):
    session.add(operation)
    await session.commit()
    await session.refresh(operation)
    return operation


async def init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def create_payment(session: AsyncSession, payment: Payment) -> Payment:
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def get_payment(session: AsyncSession, payment_id: str) -> Optional[Payment]:
    result = await session.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    return result.scalars().first()


async def update_payment(session: AsyncSession, payment: Payment) -> Payment:
    payment.updated_at = utcnow()
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def get_payment_by_idempotency(session: AsyncSession, idempotency_key: str) -> Optional[Payment]:
    result = await session.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    return result.scalars().first()


async def get_expired_payments(session: AsyncSession):
    now = utcnow()
    result = await session.execute(
        select(Payment).where(
            Payment.status.in_([
                PaymentStatus.PENDING.value,
                PaymentStatus.WAITING_FOR_OTP.value,
            ]),
            Payment.expires_at <= now,
        )
    )
    return result.scalars().all()


async def log_webhook(session: AsyncSession, log: WebhookLog):
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def get_failed_webhooks(session: AsyncSession, max_attempts: int = 5):
    result = await session.execute(
        select(Payment).where(
            Payment.webhook_attempts < max_attempts,
            Payment.webhook_status == "failed",
            Payment.status == PaymentStatus.PAID.value,
        )
    )
    return result.scalars().all()


async def get_user_data(email: str, db: AsyncSession):
    if not email:
        return [], []

    op_query = (
        select(SuccessfulOperation)
        .where(SuccessfulOperation.email == email)
        .order_by(SuccessfulOperation.id.desc())
        .limit(5)
    )
    op_result = await db.execute(op_query)

    card_query = (
        select(SavedCard)
        .where(SavedCard.email == email)
        .order_by(SavedCard.id.desc())
    )
    card_result = await db.execute(card_query)

    return op_result.scalars().all(), card_result.scalars().all()
