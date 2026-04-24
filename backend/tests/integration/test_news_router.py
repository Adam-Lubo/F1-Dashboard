from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_news_returns_cached_list():
    cache.set("news", [{
        "title": "Verstappen confident ahead of Miami",
        "url": "https://the-race.com/test",
        "source": "The Race",
        "published_at": "2026-04-20T10:00:00",
        "summary": None,
    }], ttl_seconds=60)
    resp = client.get("/news")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "The Race"


def test_news_empty_on_cache_miss():
    cache.delete("news")
    # Mock fetch_all to return empty so test doesn't hit network
    from unittest.mock import patch
    with patch("app.services.news_client.fetch_all", return_value=[]):
        resp = client.get("/news")
    assert resp.status_code == 200
    assert resp.json() == []
