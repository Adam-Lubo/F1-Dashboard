import json
import time
from fastapi import APIRouter
from pydantic import BaseModel
from ..config import settings

router = APIRouter()


class PredictionEntry(BaseModel):
    position: int
    driver_code: str
    team_id: str
    win_probability: float


class Predictions(BaseModel):
    entries: list[PredictionEntry]
    model: str
    updated_at: float


_STUB_PREDICTIONS = Predictions(
    entries=[
        PredictionEntry(position=1, driver_code="VER", team_id="redbull", win_probability=0.38),
        PredictionEntry(position=2, driver_code="NOR", team_id="mclaren", win_probability=0.24),
        PredictionEntry(position=3, driver_code="LEC", team_id="ferrari", win_probability=0.15),
        PredictionEntry(position=4, driver_code="PIA", team_id="mclaren", win_probability=0.11),
        PredictionEntry(position=5, driver_code="HAM", team_id="ferrari", win_probability=0.06),
        PredictionEntry(position=6, driver_code="RUS", team_id="mercedes", win_probability=0.06),
    ],
    model="stub — mar-antaya fork not yet wired",
    updated_at=time.time(),
)


@router.get("/predictions", response_model=Predictions)
def get_predictions():
    path = settings.predictions_path
    if path.exists():
        try:
            raw = json.loads(path.read_text())
            return Predictions(**raw)
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    return _STUB_PREDICTIONS
