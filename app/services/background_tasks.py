import asyncio
from typing import Optional

from app.worker import (
    cleanup_expired_auth_once,
    expire_overdue_payments_once,
    process_due_webhooks_once,
    run_worker_loops,
)


async def start_background_tasks(stop_event: Optional[asyncio.Event] = None) -> None:
    await run_worker_loops(stop_event)


__all__ = [
    "cleanup_expired_auth_once",
    "expire_overdue_payments_once",
    "process_due_webhooks_once",
    "start_background_tasks",
]
