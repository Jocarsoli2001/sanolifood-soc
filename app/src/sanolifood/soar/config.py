from functools import lru_cache
import ipaddress
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SoarSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    soar_database_url: str = "postgresql+psycopg://soar_app:change-me@soar-db:5432/soar"
    soar_internal_token: SecretStr = SecretStr("")
    soar_response_mode: str = "dry-run"
    soar_app_url: str = "http://app:8000"
    soar_evidence_dir: str = "/var/lib/sanolifood-soar/evidence"
    soar_playbook_catalog: str = str(Path(__file__).with_name("playbooks.json"))
    soar_allowed_containment_cidrs: str = "10.20.0.0/24"
    soar_protected_ips: str = "10.20.0.10,10.20.0.20,127.0.0.1"
    soar_protected_users: str = "admin.sanolifood,socadmin"
    soar_max_ttl_seconds: int = 1800
    soar_http_timeout_seconds: int = 8

    @property
    def response_mode(self) -> str:
        if self.soar_response_mode not in {"dry-run", "live"}:
            raise ValueError("SOAR_RESPONSE_MODE must be dry-run or live")
        return self.soar_response_mode

    @property
    def allowed_containment_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [
            ipaddress.ip_network(value.strip(), strict=False)
            for value in self.soar_allowed_containment_cidrs.split(",")
            if value.strip()
        ]

    @property
    def protected_ips(self) -> set[str]:
        return {value.strip() for value in self.soar_protected_ips.split(",") if value.strip()}

    @property
    def protected_users(self) -> set[str]:
        return {
            value.strip().lower()
            for value in self.soar_protected_users.split(",")
            if value.strip()
        }


@lru_cache
def get_soar_settings() -> SoarSettings:
    return SoarSettings()
