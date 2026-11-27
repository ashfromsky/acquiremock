import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

import app.core.config as config
from app.core.time import utcnow
from app.functional.main_functions import create_payment
from app.models.invoice import CreateInvoiceRequest
from app.models.main_models import Payment, PaymentStatus
from app.security.sanitizer import validate_reference


async def create_invoice_payment(
    db: AsyncSession,
    invoice: CreateInvoiceRequest,
) -> Payment:
    clean_reference = validate_reference(invoice.reference)
    now = utcnow()
    payment = Payment(
        id=str(uuid.uuid4()),
        amount=invoice.amount,
        reference=clean_reference,
        webhook_url=invoice.webhook_url,
        redirect_url=invoice.redirect_url,
        status=PaymentStatus.PENDING.value,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=config.PAYMENT_TTL_MINUTES),
    )
    return await create_payment(db, payment)
