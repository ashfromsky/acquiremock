import hashlib
import hmac
import json
import logging
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

import app.database.core.session as db_session_module
from app.core.config import WEBHOOK_SECRET
from app.functional.main_functions import get_payment, log_webhook, update_payment
from app.models.main_models import Payment, WebhookLog

logger = logging.getLogger(__name__)


def serialize_webhook_payload(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def generate_webhook_signature(payload: dict, secret: str = WEBHOOK_SECRET) -> str:
    message = serialize_webhook_payload(payload)
    return hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


async def send_webhook_with_retry(
        payment: Payment,
        db: AsyncSession,
        timeout: int = 10
) -> bool:
    webhook_url = payment.webhook_url

    if not webhook_url:
        logger.warning(f"No webhook URL for payment {payment.id}")
        return False

    webhook_data = {
        "payment_id": payment.id,
        "reference": payment.reference,
        "amount": payment.amount,
        "status": payment.status,
        "timestamp": datetime.utcnow().isoformat(),
        "card_mask": payment.card_mask
    }

    payload_body = serialize_webhook_payload(webhook_data)
    signature = generate_webhook_signature(webhook_data)

    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "X-Payment-ID": payment.id
    }

    attempt = payment.webhook_attempts + 1

    logger.info(f"Sending webhook to {webhook_url} for payment {payment.id}, attempt {attempt}")

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(
                webhook_url,
                content=payload_body.encode("utf-8"),
                headers=headers
            )

            success = response.status_code in [200, 201, 202, 204]

            webhook_log = WebhookLog(
                payment_id=payment.id,
                webhook_url=webhook_url,
                payload=payload_body,
                response_status=response.status_code,
                response_body=response.text[:1000],
                signature=signature,
                attempt_number=attempt,
                success=success
            )

            await log_webhook(db, webhook_log)

            payment.webhook_attempts = attempt
            payment.webhook_last_attempt = datetime.utcnow()

            if success:
                payment.webhook_status = "success"
                logger.info(f"Webhook sent successfully. Status: {response.status_code}")
            else:
                payment.webhook_status = "failed"
                logger.error(f"Webhook failed with status {response.status_code}")

            await update_payment(db, payment)

            return success

    except httpx.TimeoutException:
        logger.error(f"Webhook timeout for payment {payment.id}")

        webhook_log = WebhookLog(
            payment_id=payment.id,
            webhook_url=webhook_url,
            payload=payload_body,
            signature=signature,
            attempt_number=attempt,
            success=False,
            error_message="Request timeout"
        )

        await log_webhook(db, webhook_log)

        payment.webhook_attempts = attempt
        payment.webhook_last_attempt = datetime.utcnow()
        payment.webhook_status = "failed"
        await update_payment(db, payment)

        return False

    except Exception as e:
        logger.error(f"Webhook error for payment {payment.id}: {str(e)}")

        webhook_log = WebhookLog(
            payment_id=payment.id,
            webhook_url=webhook_url,
            payload=payload_body,
            signature=signature,
            attempt_number=attempt,
            success=False,
            error_message=str(e)
        )

        await log_webhook(db, webhook_log)

        payment.webhook_attempts = attempt
        payment.webhook_last_attempt = datetime.utcnow()
        payment.webhook_status = "failed"
        await update_payment(db, payment)

        return False


async def dispatch_webhook(payment_id: str, timeout: int = 10) -> bool:
    async with db_session_module.AsyncSessionLocal() as db:
        payment = await get_payment(db, payment_id)
        if not payment:
            logger.warning(f"Cannot dispatch webhook: payment {payment_id} not found")
            return False
        return await send_webhook_with_retry(payment, db, timeout=timeout)


def verify_webhook_signature(payload: dict, signature: str, secret: str = WEBHOOK_SECRET) -> bool:
    expected_signature = generate_webhook_signature(payload, secret)
    return hmac.compare_digest(expected_signature, signature)
