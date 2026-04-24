import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..models.circuit import CircuitInfo

router = APIRouter()
_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "circuits.json"


def _load_all() -> dict:
    return json.loads(_DATA_PATH.read_text())


@router.get("/circuits/{circuit_id}", response_model=CircuitInfo)
def get_circuit(circuit_id: str):
    data = _load_all()
    if circuit_id not in data:
        raise HTTPException(status_code=404, detail=f"Unknown circuit: {circuit_id}")
    return CircuitInfo(id=circuit_id, **data[circuit_id])
