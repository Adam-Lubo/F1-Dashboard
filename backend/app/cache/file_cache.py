import json
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    def delete(self, key: str) -> None: ...


class FileCache:
    def __init__(self, cache_dir: Path):
        self._dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "__").replace(":", "_").replace(" ", "_")
        return self._dir / f"{safe}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if time.time() > data["expires_at"]:
            path.unlink(missing_ok=True)
            return None
        return data["value"]

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        path = self._path(key)
        path.write_text(json.dumps({
            "value": value,
            "expires_at": time.time() + ttl_seconds,
        }))

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
