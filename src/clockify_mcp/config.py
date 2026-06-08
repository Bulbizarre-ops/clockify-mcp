"""Configuration loading: environment variables override a persistent TOML file."""

from __future__ import annotations

import logging
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "clockify-mcp" / "config.toml"

_TRUTHY = {"1", "true", "yes", "on"}
_TELEMETRY_DETAILS = {"metadata", "ids", "full"}
_ACCESS_MODES = {"read", "time-tracking", "full"}
_REGIONS = {"euc1", "use2", "euw2", "apse2"}


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    api_key: str
    regular_base: str
    reports_base: str
    default_workspace_id: str | None = None
    access_mode: str = "read"
    telemetry_enabled: bool = False
    telemetry_detail: str = "metadata"

    def __repr__(self) -> str:
        return (
            f"Config(regular_base={self.regular_base!r}, reports_base={self.reports_base!r}, "
            f"api_key='***', default_workspace_id={self.default_workspace_id!r}, "
            f"access_mode={self.access_mode!r}, telemetry_enabled={self.telemetry_enabled}, "
            f"telemetry_detail={self.telemetry_detail!r})"
        )

    @property
    def enable_writes(self) -> bool:
        return self.access_mode == "full"

    @classmethod
    def load(cls, env: Mapping[str, str], config_path: Path = DEFAULT_CONFIG_PATH) -> Config:
        file_values = _read_toml(config_path)

        api_key = env.get("CLOCKIFY_API_KEY") or file_values.get("api_key")
        if not api_key:
            raise ConfigError(
                "Missing api_key. Set CLOCKIFY_API_KEY or 'api_key' in the config file."
            )

        base_url = env.get("CLOCKIFY_BASE_URL") or file_values.get("base_url")
        region = (env.get("CLOCKIFY_REGION") or file_values.get("region") or "global").lower()
        regular_base, reports_base = _resolve_hosts(base_url, region)

        default_workspace_id = (
            env.get("CLOCKIFY_DEFAULT_WORKSPACE_ID")
            or file_values.get("default_workspace_id")
            or None
        )
        enable_writes_raw = _resolve_truthy(
            env, file_values, "CLOCKIFY_ENABLE_WRITES", "enable_writes"
        )
        access_mode = (
            env.get("CLOCKIFY_ACCESS_MODE") or file_values.get("access_mode") or ""
        ).strip().lower()
        if not access_mode:
            access_mode = "full" if enable_writes_raw else "read"
        if access_mode not in _ACCESS_MODES:
            access_mode = "read"
        telemetry_enabled = _resolve_truthy(
            env, file_values, "CLOCKIFY_TELEMETRY", "telemetry_enabled"
        )
        telemetry_detail = (
            env.get("CLOCKIFY_TELEMETRY_DETAIL")
            or file_values.get("telemetry_detail")
            or "metadata"
        )
        if telemetry_detail not in _TELEMETRY_DETAILS:
            telemetry_detail = "metadata"

        return cls(
            api_key=api_key,
            regular_base=regular_base,
            reports_base=reports_base,
            default_workspace_id=default_workspace_id,
            access_mode=access_mode,
            telemetry_enabled=telemetry_enabled,
            telemetry_detail=telemetry_detail,
        )


def _resolve_hosts(base_url: str | None, region: str) -> tuple[str, str]:
    """Return (regular_base, reports_base) from an explicit base_url or a region."""
    if base_url:
        root = base_url.rstrip("/")
        return f"{root}/api/v1", f"{root}/report/v1"
    if region in _REGIONS:
        return (
            f"https://{region}.clockify.me/api/v1",
            f"https://{region}.clockify.me/report/v1",
        )
    return "https://api.clockify.me/api/v1", "https://reports.api.clockify.me/v1"


def _resolve_truthy(env: Mapping[str, str], file_values: dict, env_key: str, file_key: str) -> bool:
    raw = env.get(env_key)
    if raw is not None:
        return raw.strip().lower() in _TRUTHY
    return bool(file_values.get(file_key, False))


def _read_toml(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open("rb") as fh:
        return tomllib.load(fh)
