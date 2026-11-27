import hashlib
import hmac
import json
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

import app.core.config as config
import app.database.core.session as db_session_module
from app.core.time import utcnow
from app.functional.main_functions import get_payment, log_webhook, update_payment
from app.models.main_models import Payment, WebhookLog
from app.security.ssrf import (
    build_pinned_async_client,
    resolve_and_validate_webhook_target,
)

logger = logging.getLogger(__name__)


def serialize_webhook_payload(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def generate_webhook_signature(payload: dict, secret: Optional[str] = None) -> str:
    signing_secret = config.WEBHOOK_SECRET if secret is None else secret
    message = serialize_webhook_payload(payload)
    return hmac.new(
        signing_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def send_webhook_with_retry(
    payment: Payment,
    db: AsyncSession,
    timeout: int = config.WEBHOOK_TIMEOUT_SECONDS,
    trigger: str = "auto",
) -> bool:
    webhook_url = payment.webhook_url

    if not webhook_url:
        logger.warning("No webhook URL for payment %s", payment.id)
        return False

    now = utcnow()
    attempt = payment.webhook_attempts + 1

    webhook_data = {
        "payment_id": payment.id,
        "reference": payment.reference,
        "amount": payment.amount,
        "status": payment.status,
        "timestamp": now.isoformat(),
        "card_mask": payment.card_mask,
    }

    payload_body = serialize_webhook_payload(webhook_data)
    signature = generate_webhook_signature(webhook_data)

    try:
        target = await resolve_and_validate_webhook_target(webhook_url)
    except ValueError as exc:
        logger.error("Blocked unsafe webhook URL for payment %s: %s", payment.id, exc)
        webhook_log = WebhookLog(
            payment_id=payment.id,
            webhook_url=webhook_url,
            payload=payload_body,
            signature=signature,
            attempt_number=attempt,
            trigger=trigger,
            success=False,
            error_message=str(exc)[:500],
        )
        await log_webhook(db, webhook_log)
        payment.webhook_attempts = attempt
        payment.webhook_last_attempt = now
        payment.webhook_status = "failed"
        await update_payment(db, payment)
        return False

    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "X-Payment-ID": payment.id,
    }

    logger.info(
        "Sending webhook to %s (pinned=%s) for payment %s, attempt %s",
        target.url,
        target.pinned_ip,
        payment.id,
        attempt,
    )

    try:
        async with build_pinned_async_client(target, timeout=timeout) as client:
            response = await client.post(
                target.url,
                content=payload_body.encode("utf-8"),
                headers=headers,
            )

        if 300 <= response.status_code < 400:
            success = False
            error_msg = f"Redirect responses are not allowed (HTTP {response.status_code})"
        else:
            success = response.status_code in (200, 201, 202, 204)
            error_msg = None if success else f"Unexpected HTTP status {response.status_code}"

        webhook_log = WebhookLog(
            payment_id=payment.id,
            webhook_url=target.url,
            payload=payload_body,
            response_status=response.status_code,
            response_body=response.text[:1000],
            signature=signature,
            attempt_number=attempt,
            trigger=trigger,
            success=success,
            error_message=error_msg,
        )
        await log_webhook(db, webhook_log)

        payment.webhook_attempts = attempt
        payment.webhook_last_attempt = utcnow()
        payment.webhook_status = "success" if success else "failed"
        await update_payment(db, payment)
        return success

    except Exception as exc:
        error_msg = "Request timeout" if "Timeout" in type(exc).__name__ else str(exc)[:500]
        logger.error("Webhook delivery error for payment %s: %s", payment.id, error_msg)

        webhook_log = WebhookLog(
            payment_id=payment.id,
            webhook_url=target.url,
            payload=payload_body,
            signature=signature,
            attempt_number=attempt,
            trigger=trigger,
            success=False,
            error_message=error_msg,
        )
        await log_webhook(db, webhook_log)

        payment.webhook_attempts = attempt
        payment.webhook_last_attempt = utcnow()
        payment.webhook_status = "failed"
        await update_payment(db, payment)
        return False


async def dispatch_webhook(
    payment_id: str,
    timeout: int = config.WEBHOOK_TIMEOUT_SECONDS,
) -> bool:
    async with db_session_module.AsyncSessionLocal() as db:
        payment = await get_payment(db, payment_id)
        if not payment:
            logger.warning("Cannot dispatch webhook: payment %s not found", payment_id)
            return False
        return await send_webhook_with_retry(payment, db, timeout=timeout)


def verify_webhook_signature(
    payload: dict,
    signature: str,
    secret: Optional[str] = None,
) -> bool:
    expected_signature = generate_webhook_signature(payload, secret=secret)
    return hmac.compare_digest(expected_signature, signature)
