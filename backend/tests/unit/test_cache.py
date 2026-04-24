import time
import pytest
from pathlib import Path
from app.cache.file_cache import FileCache


@pytest.fixture
def cache(tmp_path):
    return FileCache(tmp_path / "cache")


def test_cache_miss_returns_none(cache):
    assert cache.get("missing_key") is None


def test_cache_set_and_get(cache):
    cache.set("timing", {"entries": []}, ttl_seconds=60)
    result = cache.get("timing")
    assert result == {"entries": []}


def test_cache_expired_returns_none(cache):
    cache.set("timing", {"entries": []}, ttl_seconds=0)
    time.sleep(0.05)
    assert cache.get("timing") is None


def test_cache_delete(cache):
    cache.set("timing", {"entries": []}, ttl_seconds=60)
    cache.delete("timing")
    assert cache.get("timing") is None


def test_cache_slash_in_key(cache):
    cache.set("historical/VER/spa", {"wins": 3}, ttl_seconds=60)
    assert cache.get("historical/VER/spa") == {"wins": 3}
