from fastapi import APIRouter
from ..main import cache
from ..models.grid import StartingGrid

router = APIRouter()


@router.get("/grid", response_model=StartingGrid)
def get_grid():
    data = cache.get("grid")
    if data is None:
        return StartingGrid(circuit="", entries=[], updated_at=0.0)
    return StartingGrid(**data)
