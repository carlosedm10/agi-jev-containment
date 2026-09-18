import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealth:
    async def test_health_ok(self, client: AsyncClient):
        """GET /health — returns ok when the API is up."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
