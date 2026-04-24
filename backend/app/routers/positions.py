from fastapi import APIRouter
from ..main import cache
from ..models.position import TrackPositions

router = APIRouter()


@router.get("/positions", response_model=TrackPositions)
def get_positions():
    data = cache.get("positions")
    if data is None:
        return TrackPositions(drivers=[], updated_at=0.0)
    return TrackPositions(**data)
