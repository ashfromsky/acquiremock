import asyncio
import os
from typing import AsyncGenerator
from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["TESTING"] = "true"


async def mock_start_background_tasks():
    """Mock background tasks - do nothing"""
    pass


with patch('app.services.background_tasks.start_background_tasks', mock_start_background_tasks):
    from app.main import app
    from app.database.core.session import get_db

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with patch('app.main.asyncio.create_task') as mock_task:
        mock_task.return_value = MagicMock()

        async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                timeout=10.0
        ) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    """Configure pytest with timeout."""
    config.addinivalue_line(
        "markers", "timeout: mark test to run with timeout"
    )


@pytest.fixture(autouse=True)
def timeout_fixture():
    """Auto timeout for all tests."""
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("Test exceeded 30 second timeout")

    if hasattr(signal, 'SIGALRM'):
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)
        yield
        signal.alarm(0)
    else:
        yield