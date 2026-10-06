from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-only application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mcp_server_name: str = "kube-triage"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8080, ge=1, le=65535)
    database_url: str = "sqlite:///file:data/inventory.db?mode=ro&uri=true"
    prometheus_mode: Literal["fixture", "http"] = "fixture"
    prometheus_url: str | None = None
    prometheus_cluster_label: str = "cluster"
    prometheus_username: str | None = None
    prometheus_password: SecretStr | None = None
    prometheus_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    prometheus_max_range_hours: int = Field(default=24, ge=1, le=168)
    prometheus_min_step_seconds: int = Field(default=30, ge=1)
    prometheus_max_response_bytes: int = Field(default=2_000_000, ge=1024)
    prometheus_fixture_file: Path = Path("fixtures/prometheus.json")
    metric_stale_after_seconds: int = Field(default=300, ge=1)
    inventory_stale_after_hours: int = Field(default=168, ge=1)
    health_restart_warning: float = Field(default=5.0, ge=0)
    health_cpu_warning_ratio: float = Field(default=0.9, gt=0)
    health_memory_warning_ratio: float = Field(default=0.9, gt=0)
    inventory_max_rows: int = Field(default=200, ge=1, le=1000)
    skill_registry_dir: Path = Path("skill-registry")
    known_issues_file: Path = Path("known-issues/catalog.yaml")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @model_validator(mode="after")
    def require_http_endpoint(self) -> "Settings":
        if self.prometheus_mode == "http" and not self.prometheus_url:
            raise ValueError("PROMETHEUS_URL is required when PROMETHEUS_MODE=http")
        return self
