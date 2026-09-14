from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import v2
from tests.conftest import seed_store


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(v2.router)
    return TestClient(app)


def test_brief_endpoint_market_and_asset():
    seed_store()
    client = _client()
    market = client.get("/api/v2/insights/brief?force=true")
    assert market.status_code == 200
    body = market.json()
    assert body["tldr"]["now"]
    assert "prefer" not in body["headline"].lower()
    assert body["tab_assets"][0] == "HYPE"

    coin = client.get("/api/v2/insights/brief?asset=ETH&force=true")
    assert coin.status_code == 200
    eth = coin.json()
    assert eth["asset"] == "ETH"
    assert "BTC" not in eth["tldr"]["now"]
    assert eth["tab_assets"] == body["tab_assets"]
