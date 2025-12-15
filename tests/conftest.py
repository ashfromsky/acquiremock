import os
import pytest
import asyncio
from typing import AsyncGenerator

os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from httpx import AsyncClient, ASGITransport
from sqlalchemy. ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.main import app
from app.database. core.session import get_db


TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

TestAsyncSessionLocal = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata. drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides. clear()


@pytest.fixture
def sample_invoice_data():
    return {
        "amount": 10000,
        "reference": "ORDER-12345",
        "webhookUrl": "https://example.com/webhook",
        "redirectUrl": "https://example.com/success"
    }


@pytest.fixture
def sample_card_data():
    return {
        "card_number": "4111111111111111",
        "expiry":  "12/25",
        "cvv": "123",
        "email": "test@example.com"
    }