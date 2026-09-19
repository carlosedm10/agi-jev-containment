from httpx import AsyncClient


class TestHealth:
    async def test_health_ok(self, client: AsyncClient):
        """GET /health — returns ok when the API is up."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
