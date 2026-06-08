import pytest

from clockify_mcp.config import Config, ConfigError


def test_env_overrides_and_global_hosts():
    cfg = Config.load(
        env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_REGION": "global"},
        config_path=_missing_path(),
    )
    assert cfg.api_key == "k"
    assert cfg.regular_base == "https://api.clockify.me/api/v1"
    assert cfg.reports_base == "https://reports.api.clockify.me/v1"
    assert cfg.enable_writes is False
    assert cfg.default_workspace_id is None


def test_regional_hosts():
    cfg = Config.load(
        env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_REGION": "euc1"},
        config_path=_missing_path(),
    )
    assert cfg.regular_base == "https://euc1.clockify.me/api/v1"
    assert cfg.reports_base == "https://euc1.clockify.me/report/v1"


def test_base_url_override_for_subdomain():
    cfg = Config.load(
        env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_BASE_URL": "https://acme.clockify.me"},
        config_path=_missing_path(),
    )
    assert cfg.regular_base == "https://acme.clockify.me/api/v1"
    assert cfg.reports_base == "https://acme.clockify.me/report/v1"


def test_enable_writes_and_default_workspace():
    cfg = Config.load(
        env={
            "CLOCKIFY_API_KEY": "k",
            "CLOCKIFY_ENABLE_WRITES": "true",
            "CLOCKIFY_DEFAULT_WORKSPACE_ID": "ws1",
        },
        config_path=_missing_path(),
    )
    assert cfg.enable_writes is True
    assert cfg.default_workspace_id == "ws1"


def test_missing_api_key_raises():
    with pytest.raises(ConfigError):
        Config.load(env={}, config_path=_missing_path())


def test_repr_hides_api_key():
    cfg = Config.load(env={"CLOCKIFY_API_KEY": "supersecret"}, config_path=_missing_path())
    assert "supersecret" not in repr(cfg)


def test_default_access_mode_is_read():
    cfg = Config.load(env={"CLOCKIFY_API_KEY": "k"}, config_path=_missing_path())
    assert cfg.access_mode == "read"
    assert cfg.enable_writes is False


def test_access_mode_time_tracking():
    cfg = Config.load(
        env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ACCESS_MODE": "time-tracking"},
        config_path=_missing_path(),
    )
    assert cfg.access_mode == "time-tracking"
    assert cfg.enable_writes is False


def test_access_mode_full_enables_writes():
    cfg = Config.load(
        env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ACCESS_MODE": "full"},
        config_path=_missing_path(),
    )
    assert cfg.access_mode == "full"
    assert cfg.enable_writes is True


def test_enable_writes_backcompat_maps_to_full():
    cfg = Config.load(
        env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ENABLE_WRITES": "true"},
        config_path=_missing_path(),
    )
    assert cfg.access_mode == "full"
    assert cfg.enable_writes is True


def test_access_mode_overrides_enable_writes():
    cfg = Config.load(
        env={
            "CLOCKIFY_API_KEY": "k",
            "CLOCKIFY_ENABLE_WRITES": "true",
            "CLOCKIFY_ACCESS_MODE": "time-tracking",
        },
        config_path=_missing_path(),
    )
    assert cfg.access_mode == "time-tracking"
    assert cfg.enable_writes is False


def test_access_mode_is_case_insensitive():
    cfg = Config.load(
        env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ACCESS_MODE": "  Full  "},
        config_path=_missing_path(),
    )
    assert cfg.access_mode == "full"
    assert cfg.enable_writes is True


def test_invalid_access_mode_defaults_to_read():
    cfg = Config.load(
        env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ACCESS_MODE": "bogus"},
        config_path=_missing_path(),
    )
    assert cfg.access_mode == "read"
    assert cfg.enable_writes is False


def _missing_path():
    from pathlib import Path
    return Path("/nonexistent/clockify/config.toml")
