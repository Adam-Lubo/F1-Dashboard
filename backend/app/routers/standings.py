import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..models.standings import DriverStanding, ConstructorStanding

router = APIRouter()
_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "standings.json"


def _load() -> dict:
    if not _DATA_PATH.exists():
        raise HTTPException(status_code=503, detail="Standings data unavailable")
    return json.loads(_DATA_PATH.read_text())


@router.get("/standings/drivers", response_model=list[DriverStanding])
def get_driver_standings():
    return [DriverStanding(**d) for d in _load()["drivers"]]


@router.get("/standings/constructors", response_model=list[ConstructorStanding])
def get_constructor_standings():
    return [ConstructorStanding(**c) for c in _load()["constructors"]]
