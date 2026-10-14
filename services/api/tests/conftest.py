import asyncio
from collections.abc import AsyncGenerator
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Base


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Initializes the database engine for tests.

    Connects to the configured DATABASE_URL (e.g., PostgreSQL in Docker).
    If unreachable (e.g. running outside Docker without local Postgres),
    falls back cleanly to an in-memory SQLite engine with StaticPool.
    """
    engine = None
    try:
        candidate_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args={"timeout": 3} if "postgresql" in settings.DATABASE_URL else {},
        )
        async with candidate_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        engine = candidate_engine
    except Exception:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
def test_session_maker(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database(test_session_maker):
    """Ensures test isolation by emptying tables before each test."""
    async with test_session_maker() as session:
        await session.execute(text("DELETE FROM runs"))
        await session.execute(text("DELETE FROM problems"))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def client(test_session_maker) -> AsyncGenerator[AsyncClient, None]:
    """Provides an AsyncClient bound to the test database session."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
