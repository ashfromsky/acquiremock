import httpx
import json
import hmac
import hashlib
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.main_models import WebhookLog, Payment
from app.functional.main_functions import log_webhook, update_payment
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'default_secret_key_change_in_production')


def generate_webhook_signature(payload: dict, secret: str = WEBHOOK_SECRET) -> str:
    message = json.dumps(payload, sort_keys=True)
    return hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


async def send_webhook_with_retry(
        payment: Payment,
        db: AsyncSession,
        max_retries: int = 5,
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

    signature = generate_webhook_signature(webhook_data)

    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "X-Payment-ID": payment.id
    }

    attempt = payment.webhook_attempts + 1

    logger.info(f"Sending webhook to {webhook_url} for payment {payment.id}, attempt {attempt}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                webhook_url,
                json=webhook_data,
                headers=headers
            )

            success = response.status_code in [200, 201, 202, 204]

            webhook_log = WebhookLog(
                payment_id=payment.id,
                webhook_url=webhook_url,
                payload=json.dumps(webhook_data),
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
            payload=json.dumps(webhook_data),
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
            payload=json.dumps(webhook_data),
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


def verify_webhook_signature(payload: dict, signature: str, secret: str = WEBHOOK_SECRET) -> bool:
    expected_signature = generate_webhook_signature(payload, secret)
    return hmac.compare_digest(expected_signature, signature)