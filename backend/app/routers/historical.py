from fastapi import APIRouter
from ..main import cache
from ..models.historical import HistoricalStats
from ..services import livef1_client

router = APIRouter()

_HISTORICAL_SEASONS = [2021, 2022, 2023, 2024]


def _compute_stats(driver_code: str, circuit: str) -> HistoricalStats:
    race_results: list[int] = []
    quali_results: list[int] = []

    for season in _HISTORICAL_SEASONS:
        for kind, bucket in (("Race", race_results), ("Qualifying", quali_results)):
            try:
                session = livef1_client.get_historical_session(season, circuit, kind)
                resolver = livef1_client.DriverResolver.from_session(session)
                rows = livef1_client.load_data(session, "TimingData")
                tower = livef1_client.parse_timing_snapshot(rows, resolver=resolver)
                entry = next(
                    (e for e in tower.entries if e.driver_code == driver_code),
                    None,
                )
                if entry:
                    bucket.append(entry.position)
            except Exception:
                continue

    return HistoricalStats(
        driver_code=driver_code,
        circuit=circuit,
        best_finish=min(race_results) if race_results else None,
        best_quali=min(quali_results) if quali_results else None,
        avg_race_pos=sum(race_results) / len(race_results) if race_results else None,
        avg_quali_pos=sum(quali_results) / len(quali_results) if quali_results else None,
        wins=race_results.count(1),
        poles=quali_results.count(1),
        races=len(race_results),
    )


@router.get("/historical/{driver_code}/{circuit}", response_model=HistoricalStats)
def get_historical(driver_code: str, circuit: str):
    cache_key = f"historical/{driver_code.upper()}/{circuit.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return HistoricalStats(**cached)
    stats = _compute_stats(driver_code.upper(), circuit.lower())
    cache.set(cache_key, stats.model_dump(), ttl_seconds=3600)
    return stats
