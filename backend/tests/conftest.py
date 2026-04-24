import pytest
from pathlib import Path
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "spa_2024"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
