from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://schrt:schrt_pass@postgres/schrt"
    secret_key: str = "super-secret-key-change-in-production"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "submissions"
    minio_use_ssl: bool = False

    link_prefix: str = "http://localhost:5174/s/"

    first_teacher_username: str = "teacher"
    first_teacher_password: str = "teacher"

    opencode_go_api_key: str = ""
    opencode_go_base_url: str = "https://opencode.ai/zen/go/v1"
    opencode_go_model: str = "glm-5.3-flash"
    worker_poll_seconds: int = 5

    @property
    def ai_enabled(self) -> bool:
        return bool(self.opencode_go_api_key)


settings = Settings()
