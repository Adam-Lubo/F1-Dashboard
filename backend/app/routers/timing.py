from fastapi import APIRouter
from ..main import cache
from ..models.timing import TimingTower

router = APIRouter()


@router.get("/timing", response_model=TimingTower)
def get_timing():
    data = cache.get("timing")
    if data is None:
        return TimingTower(entries=[], updated_at=0.0)
    return TimingTower(**data)
