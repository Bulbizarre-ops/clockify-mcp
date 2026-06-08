import pytest

from clockify_mcp.config import Config


@pytest.fixture
def config() -> Config:
    return Config.load(
        env={
            "CLOCKIFY_API_KEY": "test-key",
            "CLOCKIFY_REGION": "global",
            "CLOCKIFY_DEFAULT_WORKSPACE_ID": "ws1",
        }
    )


@pytest.fixture
def config_writes() -> Config:
    return Config.load(
        env={
            "CLOCKIFY_API_KEY": "test-key",
            "CLOCKIFY_ENABLE_WRITES": "true",
            "CLOCKIFY_DEFAULT_WORKSPACE_ID": "ws1",
        }
    )


@pytest.fixture
def config_time_tracking() -> Config:
    return Config.load(
        env={
            "CLOCKIFY_API_KEY": "test-key",
            "CLOCKIFY_ACCESS_MODE": "time-tracking",
            "CLOCKIFY_DEFAULT_WORKSPACE_ID": "ws1",
        }
    )
