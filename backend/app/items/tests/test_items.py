import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app


class _EmptySession:
    def close(self) -> None:
        return None


def _override_get_db():
    db = _EmptySession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
async def client():
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestItems:
    async def test_list_items_empty(self, client: AsyncClient):
        """GET /api/items/ — returns empty list when no items exist."""
        response = await client.get("/api/items/")
        assert response.status_code == 200
        assert response.json() == []
