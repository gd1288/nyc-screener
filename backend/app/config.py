from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_DIR / ".env", extra="ignore")

    socrata_app_token: str = ""
    census_api_key: str = ""
    rentcast_api_key: str = ""
    database_url: str = f"sqlite:///{DATA_DIR / 'screener.db'}"
    sources_file: Path = BACKEND_DIR / "sources.yaml"
    scheduler_enabled: bool = True
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # A relative sqlite path in .env is resolved against the backend dir, not the cwd.
    if s.database_url.startswith("sqlite:///./"):
        s.database_url = f"sqlite:///{BACKEND_DIR / s.database_url.removeprefix('sqlite:///./')}"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return s
