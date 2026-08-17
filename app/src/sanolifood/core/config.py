from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "SanoliFood Operations"
    app_env: str = "development"
    app_version: str = "0.2.2"
    app_debug: bool = False
    app_timezone: str = "UTC"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://sanolifood_app:change-me@postgres:5432/sanolifood"
    allowed_hosts: str = "localhost,127.0.0.1"
    session_secret: SecretStr = SecretStr("change-me-before-production")
    session_max_age_seconds: int = 28_800
    login_max_attempts: int = 5
    login_lockout_seconds: int = 900
    bootstrap_admin_username: str = "admin.sanolifood"
    bootstrap_admin_email: str = "admin@sanolifood.local"
    bootstrap_admin_full_name: str = "Administrador SanoliFood"
    bootstrap_admin_password: SecretStr = SecretStr("")

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
