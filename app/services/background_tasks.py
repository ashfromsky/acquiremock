import asyncio
import logging
from app.functional.main_functions import get_expired_payments, update_payment, get_failed_webhooks
from app.database.core.session import AsyncSessionLocal
from app.services.webhook_service import send_webhook_with_retry

logger = logging.getLogger(__name__)


async def expire_pending_payments_task():
    logger.info("Starting payment expiration background task")

    while True:
        try:
            async with AsyncSessionLocal() as session:
                expired_payments = await get_expired_payments(session)

                for payment in expired_payments:
                    logger.info(f"Expiring payment {payment.id}")
                    payment.status = "expired"
                    await update_payment(session, payment)

                if expired_payments:
                    logger.info(f"Expired {len(expired_payments)} payments")

        except Exception as e:
            logger.error(f"Error in payment expiration task: {e}")

        await asyncio.sleep(60)


async def retry_failed_webhooks_task():
    logger.info("Starting webhook retry background task")

    while True:
        try:
            async with AsyncSessionLocal() as session:
                failed_payments = await get_failed_webhooks(session, max_attempts=5)

                for payment in failed_payments:
                    logger.info(f"Retrying webhook for payment {payment.id}, attempt {payment.webhook_attempts + 1}")

                    await asyncio.sleep(2 ** payment.webhook_attempts)

                    success = await send_webhook_with_retry(payment, session)

                    if success:
                        logger.info(f"Webhook retry successful for payment {payment.id}")
                    else:
                        logger.warning(f"Webhook retry failed for payment {payment.id}")

        except Exception as e:
            logger.error(f"Error in webhook retry task: {e}")

        await asyncio.sleep(300)


async def start_background_tasks():
    tasks = [
        asyncio.create_task(expire_pending_payments_task()),
        asyncio.create_task(retry_failed_webhooks_task())
    ]
    await asyncio.gather(*tasks)