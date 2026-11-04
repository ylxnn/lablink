from pathlib import Path
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / ".local"
DATA.mkdir(exist_ok=True)
secret_file = DATA / "jwt-secret"
if not secret_file.exists():
    secret_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env.lab", extra="ignore")
    PROJECT_NAME: str = "LabLink · 实验室资源协作平台"
    DATABASE_URL: str = "sqlite:///" + (DATA / "lablink.db").as_posix()
    SECRET_KEY: str = secret_file.read_text(encoding="utf-8").strip()
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    APP_ENV: str = "development"
    SEED_DEMO: bool = False
    WORKER_ENABLED: bool = True
    API_V1_STR: str = "/api/v1"


settings = Settings()
