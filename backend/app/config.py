from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env")

    # Exact-match origins (comma-separated in env: CORS_ORIGINS)
    cors_origins: list[str] = ["http://localhost:5173"]
    # Regex for Vercel preview deploys (matches *.vercel.app by default)
    cors_origin_regex: str | None = r"^https://.*\.vercel\.app$"

    cache_dir: Path = Path("/tmp/f1-cache")
    poll_interval_seconds: int = 3
    replay_session: str | None = None  # set to "spa_2024" to enable replay mode

    # Where the mar-antaya ML runner writes predictions (Fly volume in prod).
    # If the file exists, /predictions reads it; otherwise returns the stub.
    predictions_path: Path = Path("/data/predictions/latest.json")


settings = Settings()
