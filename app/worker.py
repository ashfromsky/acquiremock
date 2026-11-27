import asyncio
import logging
import signal
from typing import Optional

from sqlalchemy import or_
from sqlmodel import delete

import app.database.core.session as db_session_module
from app.core.time import utcnow
from app.models.main_models import AdminSession, AuthChallenge
from app.services.payments.lifecycle import expire_overdue_payments
from app.services.webhooks.delivery import dispatch_webhook
from app.services.webhooks.retry import claim_due_webhooks

logger = logging.getLogger(__name__)


async def process_due_webhooks_once(batch_size: int = 20) -> int:
    async with db_session_module.AsyncSessionLocal() as session:
        payment_ids = await claim_due_webhooks(session, batch_size=batch_size)

    if not payment_ids:
        return 0

    results = await asyncio.gather(
        *(dispatch_webhook(pid, trigger="auto") for pid in payment_ids),
        return_exceptions=True,
    )
    for pid, res in zip(payment_ids, results):
        if isinstance(res, Exception):
            logger.error("Webhook worker error for %s: %s", pid, res)
    return len(payment_ids)


async def expire_overdue_payments_once() -> int:
    async with db_session_module.AsyncSessionLocal() as session:
        expired = await expire_overdue_payments(session)
    if expired:
        logger.info("Expired %s overdue payments", expired)
    return expired


async def cleanup_expired_auth_once() -> int:
    now = utcnow()
    async with db_session_module.AsyncSessionLocal() as session:
        auth_res = await session.execute(
            delete(AuthChallenge).where(AuthChallenge.expires_at <= now)
        )
        admin_res = await session.execute(
            delete(AdminSession).where(
                or_(
                    AdminSession.expires_at <= now,
                    AdminSession.revoked_at.is_not(None),
                )
            )
        )
        await session.commit()
    return int(auth_res.rowcount or 0) + int(admin_res.rowcount or 0)


async def _run_periodic(
    name: str,
    interval_seconds: float,
    coro_fn,
    stop_event: asyncio.Event,
) -> None:
    logger.info("Starting worker loop: %s (interval=%ss)", name, interval_seconds)
    while not stop_event.is_set():
        try:
            await coro_fn()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Error in worker loop %s: %s", name, exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            raise


async def run_worker_loops(stop_event: Optional[asyncio.Event] = None) -> None:
    event = stop_event or asyncio.Event()
    tasks = [
        asyncio.create_task(_run_periodic("webhook-retries", 5.0, process_due_webhooks_once, event)),
        asyncio.create_task(_run_periodic("payment-expiration", 30.0, expire_overdue_payments_once, event)),
        asyncio.create_task(_run_periodic("auth-cleanup", 300.0, cleanup_expired_auth_once, event)),
    ]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    logger.info("AcquireMock background worker starting")
    try:
        await run_worker_loops(stop_event)
    finally:
        await db_session_module.engine.dispose()
        logger.info("AcquireMock background worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
