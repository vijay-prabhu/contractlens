"""Test fixtures and configuration."""
import asyncio
import uuid
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.database import get_db
from app.core.auth import get_current_user, CurrentUser
from app.models.base import Base


# Test database URL (in-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    # Create in-memory SQLite engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def mock_user() -> CurrentUser:
    """Create a mock authenticated user."""
    return CurrentUser(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
    )


@pytest.fixture
def auth_headers(mock_user: CurrentUser) -> dict:
    """Create mock auth headers."""
    return {"Authorization": "Bearer mock-jwt-token"}


@pytest.fixture
def client(mock_user: CurrentUser) -> Generator[TestClient, None, None]:
    """Create test client with mocked auth."""

    async def mock_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = mock_get_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(
    mock_user: CurrentUser,
    test_db: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with mocked dependencies."""

    async def mock_get_current_user():
        return mock_user

    async def mock_get_db():
        yield test_db

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db] = mock_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    with patch("app.services.document_service.get_supabase_client") as mock:
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_bucket = MagicMock()

        mock_bucket.upload = MagicMock(return_value=None)
        mock_bucket.download = MagicMock(return_value=b"mock file content")
        mock_bucket.remove = MagicMock(return_value=None)

        mock_storage.from_ = MagicMock(return_value=mock_bucket)
        mock_client.storage = mock_storage

        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_pdf_content() -> bytes:
    """Create minimal PDF content for testing."""
    # Minimal valid PDF
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""
