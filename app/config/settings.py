from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr
    database_url: str
    redis_url: str
    admin_ids: set[int] = Field(default_factory=set)
    environment: str = "production"
    webhook_url: str | None = None
    webhook_path: str = "/telegram/webhook"
    webhook_secret: SecretStr | None = None
    host: str = "0.0.0.0"
    port: int = 8080
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    subscription_cache_ttl: int = 600
    rate_limit_per_second: int = 2
    broadcast_concurrency: int = 20
    broadcast_rate_per_second: int = 25
    run_broadcast_worker: bool = False

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> set[int]:
        if not value:
            return set()
        if isinstance(value, int):
            return {value}
        if isinstance(value, str):
            return {int(item.strip()) for item in value.split(",") if item.strip()}
        return {int(item) for item in value}  # type: ignore[arg-type]

    @field_validator("db_pool_max_size")
    @classmethod
    def validate_pool(cls, value: int, info) -> int:  # type: ignore[no-untyped-def]
        minimum = info.data.get("db_pool_min_size", 1)
        if value < minimum:
            raise ValueError("DB_POOL_MAX_SIZE must be >= DB_POOL_MIN_SIZE")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
