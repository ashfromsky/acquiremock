import os
from typing import AsyncGenerator

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "AdminTestPassword!2026"
TEST_ADMIN_PASSWORD_HASH = bcrypt.hashpw(
    TEST_ADMIN_PASSWORD.encode("utf-8"),
    bcrypt.gensalt(rounds=4),
).decode("utf-8")

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["TESTING"] = "true"
os.environ.setdefault("WEBHOOK_SECRET", "dev-pytest-webhook-secret-8f4c1a9e3b7d2056")
os.environ.setdefault("SESSION_SECRET", "dev-pytest-session-secret-5a2d9c8e1f4b7039")
os.environ.setdefault("ADMIN_USERNAME", TEST_ADMIN_USERNAME)
os.environ.setdefault("ADMIN_PASSWORD_HASH", TEST_ADMIN_PASSWORD_HASH)

import app.database.core.session as db_session_module
from app.core.limiter import limiter
from app.database.core.session import get_db
from app.main_test import app

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
    original_session_local = db_session_module.AsyncSessionLocal
    db_session_module.AsyncSessionLocal = TestSessionLocal

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with TestSessionLocal() as session:
            yield session
    finally:
        db_session_module.AsyncSessionLocal = original_session_local
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
        await test_engine.dispose()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    if hasattr(limiter, "_storage"):
        limiter._storage.reset()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=5.0,
    ) as c:
        yield c

    app.dependency_overrides.clear()


async def login_as_admin(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/admin/login",
        json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["csrf_token"]


@pytest.fixture(scope="function")
async def admin_csrf(client: AsyncClient) -> str:
    return await login_as_admin(client)
