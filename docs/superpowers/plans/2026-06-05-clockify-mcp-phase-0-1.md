# Clockify MCP — Phase 0 + 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working, read-only Clockify MCP server — scaffolding (config, dual-host HTTP client, pagination, telemetry seam, server) plus the discovery and base-read domains (workspaces, users, groups).

**Architecture:** Python + FastMCP, modular per-domain (`register(mcp, client)`). Async `httpx` client with two hosts (regular API + Reports API), `X-Api-Key` auth, secret sanitization, and `429` backoff. Read-only here; writes land in later phases behind opt-in. Mirrors `invgate-service-desk-mcp`.

**Tech Stack:** Python 3.12+, `mcp` (FastMCP), `httpx`, `pytest` + `pytest-asyncio` + `respx`, `ruff`, `hatchling`, `uv`.

**Reference repo (read-only, for patterns):** `/home/alan/proyectos/mcp_invgate`

---

## File Structure

```
src/clockify_mcp/
  __init__.py        # version
  config.py          # env > TOML; host resolution; flags
  client.py          # dual-host httpx client; X-Api-Key; sanitize; 429 backoff
  pagination.py      # page/pageSize + Last-Page helpers
  telemetry.py       # Telemetry facade + InstrumentedFastMCP + build_telemetry (no-op seam)
  server.py          # build_server(); main(); INSTRUCTIONS
  domains/
    __init__.py
    workspaces.py     # get_current_user, list_workspaces, get_workspace
    users.py          # list_users, get_user_member_profile, find_user_team_manager
    groups.py         # list_user_groups
tests/
  __init__.py
  conftest.py        # shared fixtures (config, client, respx)
  test_config.py
  test_client.py
  test_pagination.py
  test_server.py
  test_workspaces.py
  test_users.py
  test_groups.py
pyproject.toml
config.toml.example
.github/workflows/ci.yml
README.md  LICENSE  CLAUDE.md  .gitignore
```

> **Note on telemetry:** Phase 0 ships a *no-op facade* (`telemetry.py`) that gives the client/server their `Telemetry` / `InstrumentedFastMCP` seam without pulling in the OpenTelemetry SDK. Full OTLP export (`_otel.py`, ported from invgate) is a later phase. The seam means no rewrite is needed when it lands.

---

## Task 1: Project skeleton, pyproject, CI

**Files:**
- Create: `pyproject.toml`, `src/clockify_mcp/__init__.py`, `src/clockify_mcp/domains/__init__.py`, `tests/__init__.py`, `.github/workflows/ci.yml`, `LICENSE`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "clockify-mcp"
version = "0.1.0"
description = "MCP server for the Clockify time-tracking API — exposes Clockify operations as Model Context Protocol tools."
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Alan (tracegazer)" }]
keywords = ["mcp", "clockify", "time-tracking", "model-context-protocol"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries",
]
dependencies = [
    "mcp>=1.2.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
telemetry = [
    "opentelemetry-sdk>=1.27",
    "opentelemetry-exporter-otlp-proto-http>=1.27",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
    "ruff>=0.6",
]

[project.scripts]
clockify-mcp = "clockify_mcp.server:main"

[project.urls]
Homepage = "https://github.com/tracegazer/clockify-mcp"
Repository = "https://github.com/tracegazer/clockify-mcp"
Issues = "https://github.com/tracegazer/clockify-mcp/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/clockify_mcp"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 2: Create package init files**

`src/clockify_mcp/__init__.py`:
```python
"""Clockify MCP server."""

__version__ = "0.1.0"
```

`src/clockify_mcp/domains/__init__.py`:
```python
"""Domain modules: each owns its tools and registers via register(mcp, client)."""
```

`tests/__init__.py`: (empty file)

- [ ] **Step 3: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v6
      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}
      - name: Install dependencies
        run: uv sync --extra dev
      - name: Lint
        run: uv run ruff check src/ tests/
      - name: Test
        run: uv run pytest tests/ -q
```

- [ ] **Step 4: Create `LICENSE`**

Copy the MIT license text from `/home/alan/proyectos/mcp_invgate/LICENSE`, keeping the same copyright holder line.

Run: `cp /home/alan/proyectos/mcp_invgate/LICENSE ./LICENSE`

- [ ] **Step 5: Sync the environment**

Run: `uv sync --extra dev`
Expected: resolves and installs `mcp`, `httpx`, `pytest`, `respx`, `ruff`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/clockify_mcp/__init__.py src/clockify_mcp/domains/__init__.py tests/__init__.py .github/workflows/ci.yml LICENSE uv.lock
git commit -m "chore: scaffold clockify-mcp package, deps, CI"
```

---

## Task 2: Configuration

**Files:**
- Create: `src/clockify_mcp/config.py`, `tests/test_config.py`

Config resolves from env vars (highest priority) then a TOML file. It also resolves the regular and reports host base URLs from `region`/`base_url`.

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:
```python
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


def _missing_path():
    from pathlib import Path
    return Path("/nonexistent/clockify/config.toml")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: clockify_mcp.config`.

- [ ] **Step 3: Write `src/clockify_mcp/config.py`**

```python
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
_REGIONS = {"euc1", "use2", "euw2", "apse2"}


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    api_key: str
    regular_base: str
    reports_base: str
    default_workspace_id: str | None = None
    enable_writes: bool = False
    telemetry_enabled: bool = False
    telemetry_detail: str = "metadata"

    def __repr__(self) -> str:
        return (
            f"Config(regular_base={self.regular_base!r}, reports_base={self.reports_base!r}, "
            f"api_key='***', default_workspace_id={self.default_workspace_id!r}, "
            f"enable_writes={self.enable_writes}, telemetry_enabled={self.telemetry_enabled}, "
            f"telemetry_detail={self.telemetry_detail!r})"
        )

    @classmethod
    def load(cls, env: Mapping[str, str], config_path: Path = DEFAULT_CONFIG_PATH) -> "Config":
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
        enable_writes = _resolve_truthy(env, file_values, "CLOCKIFY_ENABLE_WRITES", "enable_writes")
        telemetry_enabled = _resolve_truthy(
            env, file_values, "CLOCKIFY_TELEMETRY", "telemetry_enabled"
        )
        telemetry_detail = (
            env.get("CLOCKIFY_TELEMETRY_DETAIL") or file_values.get("telemetry_detail") or "metadata"
        )
        if telemetry_detail not in _TELEMETRY_DETAILS:
            telemetry_detail = "metadata"

        return cls(
            api_key=api_key,
            regular_base=regular_base,
            reports_base=reports_base,
            default_workspace_id=default_workspace_id,
            enable_writes=enable_writes,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/config.py tests/test_config.py
git commit -m "feat: config with env>TOML and host resolution"
```

---

## Task 3: Telemetry no-op facade

**Files:**
- Create: `src/clockify_mcp/telemetry.py`, `tests/test_server.py` (telemetry portion — extended in Task 6)

The facade gives the client and server their dependency seam without the OTel SDK.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server.py` (create the file):
```python
from clockify_mcp.telemetry import Telemetry, build_telemetry, InstrumentedFastMCP


def test_telemetry_client_span_is_context_manager():
    tel = Telemetry()
    with tel.client_span("GET", "workspaces", None) as span:
        span.set_status_code(200)
        span.set_result({"ok": True})
    # no exception => pass


def test_build_telemetry_returns_telemetry():
    from clockify_mcp.config import Config
    cfg = Config.load(env={"CLOCKIFY_API_KEY": "k"})
    assert isinstance(build_telemetry(cfg), Telemetry)


def test_instrumented_fastmcp_is_fastmcp():
    from mcp.server.fastmcp import FastMCP
    mcp = InstrumentedFastMCP(name="t", instructions="i", telemetry=Telemetry())
    assert isinstance(mcp, FastMCP)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -q`
Expected: FAIL — `ModuleNotFoundError: clockify_mcp.telemetry`.

- [ ] **Step 3: Write `src/clockify_mcp/telemetry.py`**

```python
"""Telemetry seam.

Phase 0 ships a no-op facade so the client and server can depend on a stable
Telemetry / InstrumentedFastMCP interface. Full OpenTelemetry export is ported
from invgate (_otel.py) in a later phase without changing these signatures.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    from .config import Config


class _NoopSpan:
    def set_status_code(self, status_code: int) -> None:  # noqa: D401
        pass

    def set_result(self, result: Any) -> None:
        pass


class Telemetry:
    """No-op telemetry facade. Replaced by an OTel-backed impl in a later phase."""

    def resource_service_name(self) -> str:
        return "clockify-mcp"

    @contextmanager
    def client_span(self, method: str, endpoint: str, params: Any):
        yield _NoopSpan()

    def shutdown(self) -> None:
        pass


class InstrumentedFastMCP(FastMCP):
    """FastMCP subclass carrying a Telemetry handle. No-op until OTel lands."""

    def __init__(self, *args: Any, telemetry: Telemetry | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._telemetry = telemetry or Telemetry()


def build_telemetry(config: "Config") -> Telemetry:
    """Return a Telemetry instance. No-op facade for now."""
    return Telemetry()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/telemetry.py tests/test_server.py
git commit -m "feat: telemetry no-op facade seam"
```

---

## Task 4: Pagination helpers

**Files:**
- Create: `src/clockify_mcp/pagination.py`, `tests/test_pagination.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_pagination.py`:
```python
from clockify_mcp.pagination import page_params, is_last_page


def test_page_params_drops_none():
    assert page_params(None, None) == {}
    assert page_params(2, 50) == {"page": 2, "page-size": 50}
    assert page_params(2, None) == {"page": 2}


def test_is_last_page_reads_header():
    assert is_last_page({"Last-Page": "true"}) is True
    assert is_last_page({"Last-Page": "false"}) is False
    assert is_last_page({}) is True  # no header => assume done
```

> Clockify's query param is `page-size` (hyphenated) on most list endpoints; the helper centralizes that spelling.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pagination.py -q`
Expected: FAIL — `ModuleNotFoundError: clockify_mcp.pagination`.

- [ ] **Step 3: Write `src/clockify_mcp/pagination.py`**

```python
"""Pagination helpers for Clockify list endpoints (page / page-size + Last-Page)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def page_params(page: int | None, page_size: int | None) -> dict[str, Any]:
    """Build query params for a paginated GET, dropping unset values.

    Clockify uses 1-indexed ``page`` and a hyphenated ``page-size``.
    """
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page
    if page_size is not None:
        params["page-size"] = page_size
    return params


def is_last_page(headers: Mapping[str, str]) -> bool:
    """Interpret the custom ``Last-Page`` response header.

    Missing header is treated as the last page (single-shot responses).
    """
    value = headers.get("Last-Page")
    if value is None:
        return True
    return value.strip().lower() == "true"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pagination.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/pagination.py tests/test_pagination.py
git commit -m "feat: pagination helpers (page-size, Last-Page)"
```

---

## Task 5: Dual-host HTTP client with 429 backoff

**Files:**
- Create: `src/clockify_mcp/client.py`, `tests/conftest.py`, `tests/test_client.py`

- [ ] **Step 1: Write shared fixtures `tests/conftest.py`**

```python
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
```

- [ ] **Step 2: Write the failing tests `tests/test_client.py`**

```python
import httpx
import pytest
import respx

from clockify_mcp.client import ClockifyClient, ClockifyAPIError


@respx.mock
async def test_get_hits_regular_host_with_api_key(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces").mock(
        return_value=httpx.Response(200, json=[{"id": "ws1"}])
    )
    client = ClockifyClient(config)
    result = await client.get("workspaces")
    assert result == [{"id": "ws1"}]
    assert route.calls.last.request.headers["X-Api-Key"] == "test-key"
    await client.aclose()


@respx.mock
async def test_report_hits_reports_host(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/summary"
    ).mock(return_value=httpx.Response(200, json={"totals": []}))
    client = ClockifyClient(config)
    result = await client.report("workspaces/ws1/reports/summary", {"x": 1})
    assert result == {"totals": []}
    assert route.called
    await client.aclose()


@respx.mock
async def test_error_is_sanitized(config):
    respx.get("https://api.clockify.me/api/v1/workspaces").mock(
        return_value=httpx.Response(401, json={"message": "bad key test-key", "code": 401})
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as exc:
        await client.get("workspaces")
    assert "test-key" not in str(exc.value)
    assert exc.value.status_code == 401
    await client.aclose()


@respx.mock
async def test_429_is_retried_then_succeeds(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, text="Too many requests"),
            httpx.Response(200, json=[{"id": "ws1"}]),
        ]
    )
    client = ClockifyClient(config)
    result = await client.get("workspaces")
    assert result == [{"id": "ws1"}]
    assert route.call_count == 2
    await client.aclose()


def test_writes_enabled_property(config, config_writes):
    assert ClockifyClient(config).writes_enabled is False
    assert ClockifyClient(config_writes).writes_enabled is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_client.py -q`
Expected: FAIL — `ModuleNotFoundError: clockify_mcp.client`.

- [ ] **Step 4: Write `src/clockify_mcp/client.py`**

```python
"""Async HTTP client for the Clockify API (regular + reports hosts)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .config import Config
from .telemetry import Telemetry

MAX_ERROR_LEN = 1000
_REDACTED = "***REDACTED***"
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds


class ClockifyAPIError(Exception):
    """Raised when the Clockify API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str, body: Any = None):
        super().__init__(f"Clockify API error {status_code}: {message}")
        self.status_code = status_code
        self.body = body


class ClockifyClient:
    """Thin async wrapper over the Clockify REST API.

    Two hosts: the regular API (config.regular_base) and the Reports API
    (config.reports_base). Read methods are exposed now; write verbs exist for
    later phases but are only surfaced as tools when writes are enabled.
    """

    def __init__(
        self,
        config: Config,
        http_client: httpx.AsyncClient | None = None,
        telemetry: Telemetry | None = None,
    ):
        self._config = config
        self._telemetry = telemetry or Telemetry()
        self._client = http_client or httpx.AsyncClient(
            headers={"X-Api-Key": config.api_key},
            timeout=30.0,
        )
        self._secrets = [s for s in (config.api_key,) if s]

    @property
    def writes_enabled(self) -> bool:
        return self._config.enable_writes

    @property
    def default_workspace_id(self) -> str | None:
        return self._config.default_workspace_id

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", self._config.regular_base, path, params=params)

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", self._config.regular_base, path, json=json)

    async def put(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._request("PUT", self._config.regular_base, path, json=json)

    async def patch(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._request("PATCH", self._config.regular_base, path, json=json)

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("DELETE", self._config.regular_base, path, params=params)

    async def report(self, path: str, json: dict[str, Any] | None = None) -> Any:
        """POST to the Reports API host (reports return data via POST filters)."""
        return await self._request("POST", self._config.reports_base, path, json=json)

    async def _request(
        self,
        method: str,
        base: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{base}/{path.lstrip('/')}"
        with self._telemetry.client_span(method, path, params or json) as span:
            response = await self._send_with_retry(
                method, url, params=self._clean(params), json=json
            )
            span.set_status_code(response.status_code)
            result = self._handle(response)
            span.set_result(result)
            return result

    async def _send_with_retry(
        self, method: str, url: str, *, params: dict[str, Any], json: dict[str, Any] | None
    ) -> httpx.Response:
        """Send, retrying 429 with light exponential backoff (honors Retry-After)."""
        attempt = 0
        while True:
            response = await self._client.request(method, url, params=params or None, json=json)
            if response.status_code != 429 or attempt >= _MAX_RETRIES:
                return response
            delay = self._retry_delay(response, attempt)
            await asyncio.sleep(delay)
            attempt += 1

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return _BACKOFF_BASE * (2**attempt)

    @staticmethod
    def _clean(values: dict[str, Any] | None) -> dict[str, Any]:
        """Drop None values from query params."""
        return {k: v for k, v in (values or {}).items() if v is not None}

    def _handle(self, response: httpx.Response) -> Any:
        if response.is_success:
            if not response.content:
                return None
            return response.json()
        try:
            body = response.json()
            message = body.get("message") or body.get("error") or response.text
        except Exception:
            body = response.text
            message = response.text
        raise ClockifyAPIError(
            response.status_code, self._sanitize(message), self._sanitize(body)
        )

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, str):
            for secret in self._secrets:
                value = value.replace(secret, _REDACTED)
            if len(value) > MAX_ERROR_LEN:
                value = value[:MAX_ERROR_LEN] + "...[truncated]"
            return value
        if isinstance(value, dict):
            return {k: self._sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize(v) for v in value]
        return value

    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -q`
Expected: PASS (5 tests). The 429 test sleeps ~0s (Retry-After: 0).

- [ ] **Step 6: Commit**

```bash
git add src/clockify_mcp/client.py tests/conftest.py tests/test_client.py
git commit -m "feat: dual-host async client with X-Api-Key, sanitize, 429 backoff"
```

---

## Task 6: Server assembly

**Files:**
- Create: `src/clockify_mcp/server.py`
- Modify: `tests/test_server.py` (append build_server tests)

- [ ] **Step 1: Append failing tests to `tests/test_server.py`**

```python
def test_build_server_registers_discovery_tools(config):
    from clockify_mcp.client import ClockifyClient
    from clockify_mcp.server import build_server
    import asyncio

    client = ClockifyClient(config)
    mcp = build_server(client)
    tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
    names = {t.name for t in tools}
    assert {"get_current_user", "list_workspaces", "get_workspace"} <= names
```

> If the test runner's event loop is already running, replace the body with an
> `async def test_...` and `tools = await mcp.list_tools()` (pytest-asyncio auto mode supports this).
> Prefer the async form:

```python
async def test_build_server_registers_discovery_tools(config):
    from clockify_mcp.client import ClockifyClient
    from clockify_mcp.server import build_server

    client = ClockifyClient(config)
    mcp = build_server(client)
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert {"get_current_user", "list_workspaces", "get_workspace"} <= names
```

Use the async form; delete the sync variant.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -q`
Expected: FAIL — `ModuleNotFoundError: clockify_mcp.server` (or no `build_server`).

- [ ] **Step 3: Write `src/clockify_mcp/server.py`**

```python
"""MCP server entrypoint for the Clockify API.

Each domain module owns its tools and registers them via register(mcp, client),
keeping this layer thin. Read-only by default; write tools register only when the
operator sets CLOCKIFY_ENABLE_WRITES.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Literal

from .client import ClockifyClient
from .config import Config
from .telemetry import InstrumentedFastMCP, Telemetry, build_telemetry
from .domains import groups, users, workspaces

INSTRUCTIONS = """\
Tools for the Clockify time-tracking API. Read-only by default; write tools are \
registered only when the operator sets CLOCKIFY_ENABLE_WRITES.

Almost every Clockify operation is scoped to a workspace. Tools accept an \
optional workspace_id; when omitted they use the configured default workspace. \
If there is no default and none is given, the tool returns an error asking you \
to resolve one first.

DISCOVERY: Call get_current_user and list_workspaces to resolve the workspace, \
list_users to resolve people, and the list_* tools to resolve projects, tasks, \
clients, and tags before filtering or (in later phases) creating anything.

DISAMBIGUATION: When a name search returns multiple matches, NEVER choose on \
your own. Present ALL matching options with their IDs and names and ask the user \
to choose.\
"""


def build_server(client: ClockifyClient, telemetry: Telemetry | None = None) -> InstrumentedFastMCP:
    """Build the MCP server and register all enabled domain tools."""
    mcp = InstrumentedFastMCP(
        name="clockify",
        instructions=INSTRUCTIONS,
        telemetry=telemetry or Telemetry(),
    )
    workspaces.register(mcp, client)
    users.register(mcp, client)
    groups.register(mcp, client)
    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="clockify-mcp")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio).",
    )
    args = parser.parse_args()

    warning = insecure_transport_warning(args.transport)
    if warning:
        print(warning, file=sys.stderr)

    config = Config.load(env=os.environ)
    telemetry = build_telemetry(config)
    client = ClockifyClient(config, telemetry=telemetry)
    mcp = build_server(client, telemetry=telemetry)
    try:
        mcp.run(transport=_transport(args.transport))
    finally:
        telemetry.shutdown()


def insecure_transport_warning(transport: str) -> str | None:
    if transport == "stdio":
        return None
    return (
        f"WARNING: transport '{transport}' has no built-in auth. It exposes every "
        "Clockify operation through the server's stored API key. Bind it to loopback "
        "or run it behind an authenticated reverse proxy; never expose it directly "
        "to an untrusted network."
    )


def _transport(value: str) -> Literal["stdio", "sse", "streamable-http"]:
    return value  # type: ignore[return-value]


if __name__ == "__main__":
    main()
```

> This imports `domains.workspaces`, `users`, `groups` — created in Tasks 7–9. To keep
> the suite green task-by-task, implement Tasks 7–9 before re-running this test, OR
> temporarily comment the three `register(...)` lines and the import until those tasks
> land. Recommended order: do Task 7, 8, 9 first, then this Step 4.

- [ ] **Step 4: Run test to verify it passes** (after Tasks 7–9 exist)

Run: `uv run pytest tests/test_server.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/server.py tests/test_server.py
git commit -m "feat: server assembly with discovery instructions"
```

---

## Task 7: Domain — workspaces

**Files:**
- Create: `src/clockify_mcp/domains/workspaces.py`, `tests/test_workspaces.py`

Tools: `get_current_user`, `list_workspaces`, `get_workspace`.

- [ ] **Step 1: Write the failing tests `tests/test_workspaces.py`**

```python
import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import workspaces


@respx.mock
async def test_get_current_user(config):
    respx.get("https://api.clockify.me/api/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "u1", "name": "Alan"})
    )
    client = ClockifyClient(config)
    assert await workspaces.get_current_user(client) == {"id": "u1", "name": "Alan"}
    await client.aclose()


@respx.mock
async def test_list_workspaces(config):
    respx.get("https://api.clockify.me/api/v1/workspaces").mock(
        return_value=httpx.Response(200, json=[{"id": "ws1"}, {"id": "ws2"}])
    )
    client = ClockifyClient(config)
    assert await workspaces.list_workspaces(client) == [{"id": "ws1"}, {"id": "ws2"}]
    await client.aclose()


@respx.mock
async def test_get_workspace_uses_default(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1").mock(
        return_value=httpx.Response(200, json={"id": "ws1", "name": "Main"})
    )
    client = ClockifyClient(config)
    assert await workspaces.get_workspace(client) == {"id": "ws1", "name": "Main"}
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_workspaces.py -q`
Expected: FAIL — no module `domains.workspaces`.

- [ ] **Step 3: Write `src/clockify_mcp/domains/workspaces.py`**

```python
"""Workspace & current-user discovery domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def resolve_workspace_id(client: ClockifyClient, workspace_id: str | None) -> str:
    """Return the explicit workspace_id, else the configured default, else error."""
    resolved = workspace_id or client.default_workspace_id
    if not resolved:
        raise ValueError(
            "No workspace_id given and no default configured. Call list_workspaces "
            "to find one, or set CLOCKIFY_DEFAULT_WORKSPACE_ID."
        )
    return resolved


async def get_current_user(client: ClockifyClient) -> Any:
    """Get the currently logged-in user's info (resolves your user id)."""
    return await client.get("user")


async def list_workspaces(client: ClockifyClient) -> Any:
    """List all workspaces the authenticated user belongs to."""
    return await client.get("workspaces")


async def get_workspace(client: ClockifyClient, workspace_id: str | None = None) -> Any:
    """Get info for one workspace (defaults to the configured workspace)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}")


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def get_current_user() -> Any:
        """Get the currently logged-in user's info (id, email, default workspace)."""
        return await get_current_user_fn(client)

    @mcp.tool()
    async def list_workspaces() -> Any:
        """List all workspaces the authenticated user belongs to."""
        return await list_workspaces_fn(client)

    @mcp.tool()
    async def get_workspace(workspace_id: str | None = None) -> Any:
        """Get info for one workspace (defaults to the configured workspace)."""
        return await get_workspace_fn(client, workspace_id)


get_current_user_fn = get_current_user
list_workspaces_fn = list_workspaces
get_workspace_fn = get_workspace
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workspaces.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/workspaces.py tests/test_workspaces.py
git commit -m "feat: workspaces domain (current user, list, get)"
```

---

## Task 8: Domain — users

**Files:**
- Create: `src/clockify_mcp/domains/users.py`, `tests/test_users.py`

Tools: `list_users` (paginated + name/email filter), `get_user_member_profile`, `find_user_team_manager`.

- [ ] **Step 1: Write the failing tests `tests/test_users.py`**

```python
import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import users


@respx.mock
async def test_list_users_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/users").mock(
        return_value=httpx.Response(200, json=[{"id": "u1"}])
    )
    client = ClockifyClient(config)
    result = await users.list_users(client, name="alan", page=2, page_size=10)
    assert result == [{"id": "u1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "alan"
    assert sent["page"] == "2"
    assert sent["page-size"] == "10"
    await client.aclose()


@respx.mock
async def test_get_user_member_profile(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/member-profile/u1").mock(
        return_value=httpx.Response(200, json={"userId": "u1"})
    )
    client = ClockifyClient(config)
    assert await users.get_user_member_profile(client, user_id="u1") == {"userId": "u1"}
    await client.aclose()


@respx.mock
async def test_find_user_team_manager(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/users/u1/managers").mock(
        return_value=httpx.Response(200, json=[{"id": "m1"}])
    )
    client = ClockifyClient(config)
    assert await users.find_user_team_manager(client, user_id="u1") == [{"id": "m1"}]
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_users.py -q`
Expected: FAIL — no module `domains.users`.

- [ ] **Step 3: Write `src/clockify_mcp/domains/users.py`**

```python
"""Users domain: find/filter workspace users and resolve managers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_users(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    email: str | None = None,
    status: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List workspace users, optionally filtered by name/email/status (paginated).

    ``status`` is one of ACTIVE, INACTIVE, PENDING, DECLINED, etc. Use page /
    page_size for large workspaces.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {"name": name, "email": email, "status": status, **page_params(page, page_size)}
    return await client.get(f"workspaces/{ws}/users", params=params)


async def get_user_member_profile(
    client: ClockifyClient, *, user_id: str, workspace_id: str | None = None
) -> Any:
    """Get a member's profile within the workspace."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/member-profile/{user_id}")


async def find_user_team_manager(
    client: ClockifyClient, *, user_id: str, workspace_id: str | None = None
) -> Any:
    """Find a user's team manager(s)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/users/{user_id}/managers")


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_users(
        workspace_id: str | None = None,
        name: str | None = None,
        email: str | None = None,
        status: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List workspace users, optionally filtered by name/email/status (paginated)."""
        return await list_users_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            email=email,
            status=status,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_user_member_profile(user_id: str, workspace_id: str | None = None) -> Any:
        """Get a member's profile within the workspace."""
        return await get_user_member_profile_fn(client, user_id=user_id, workspace_id=workspace_id)

    @mcp.tool()
    async def find_user_team_manager(user_id: str, workspace_id: str | None = None) -> Any:
        """Find a user's team manager(s)."""
        return await find_user_team_manager_fn(client, user_id=user_id, workspace_id=workspace_id)


list_users_fn = list_users
get_user_member_profile_fn = get_user_member_profile
find_user_team_manager_fn = find_user_team_manager
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_users.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/users.py tests/test_users.py
git commit -m "feat: users domain (list/filter, profile, manager)"
```

---

## Task 9: Domain — groups

**Files:**
- Create: `src/clockify_mcp/domains/groups.py`, `tests/test_groups.py`

Tool: `list_user_groups` (paginated + name filter).

- [ ] **Step 1: Write the failing tests `tests/test_groups.py`**

```python
import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import groups


@respx.mock
async def test_list_user_groups(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/user-groups").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Dev"}])
    )
    client = ClockifyClient(config)
    result = await groups.list_user_groups(client, name="Dev", page_size=5)
    assert result == [{"id": "g1", "name": "Dev"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "Dev"
    assert sent["page-size"] == "5"
    await client.aclose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_groups.py -q`
Expected: FAIL — no module `domains.groups`.

- [ ] **Step 3: Write `src/clockify_mcp/domains/groups.py`**

```python
"""User groups domain (read)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_user_groups(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List user groups on the workspace, optionally filtered by name (paginated)."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"name": name, **page_params(page, page_size)}
    return await client.get(f"workspaces/{ws}/user-groups", params=params)


def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_user_groups(
        workspace_id: str | None = None,
        name: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List user groups on the workspace, optionally filtered by name (paginated)."""
        return await list_user_groups_fn(
            client, workspace_id=workspace_id, name=name, page=page, page_size=page_size
        )


list_user_groups_fn = list_user_groups
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_groups.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite + lint**

Run: `uv run pytest tests/ -q && uv run ruff check src/ tests/`
Expected: all tests PASS, ruff clean. (This is where Task 6 Step 4 finally goes green.)

- [ ] **Step 6: Commit**

```bash
git add src/clockify_mcp/domains/groups.py tests/test_groups.py
git commit -m "feat: groups domain (list user groups)"
```

---

## Task 10: Docs & config template

**Files:**
- Create: `config.toml.example`, `README.md`, `CLAUDE.md`

- [ ] **Step 1: Create `config.toml.example`**

```toml
# Clockify MCP — configuration template
# Copy to: ~/.config/clockify-mcp/config.toml
#
#   mkdir -p ~/.config/clockify-mcp
#   cp config.toml.example ~/.config/clockify-mcp/config.toml
#
# Environment variables always override these values.

api_key = "your-clockify-api-key"

# region = "global"            # global | euc1 (EU) | use2 (USA) | euw2 (UK) | apse2 (AU)
# base_url = ""                # override for subdomain workspaces, e.g. https://acme.clockify.me
# default_workspace_id = ""    # optional; tools fall back to this when workspace_id is omitted

# enable_writes = false        # set true to register create/update/delete tools (later phases)

# telemetry_enabled = false    # OpenTelemetry traces/metrics/logs (ported in a later phase)
# telemetry_detail = "metadata"  # metadata (default) | ids | full
```

- [ ] **Step 2: Create `README.md`**

Write a README modeled on `/home/alan/proyectos/mcp_invgate/README.md`: title `# clockify-mcp`, one-line intro, a "What can it do?" domain table listing the implemented domains (Workspaces, Users, Groups) noting more land in later phases, Quick start (`uvx clockify-mcp`, Claude Desktop config block with `command: uvx`, `args: ["clockify-mcp"]`, env `CLOCKIFY_API_KEY`), Configuration (env vars + TOML), and a note that the server is read-only until `CLOCKIFY_ENABLE_WRITES=true`.

- [ ] **Step 3: Create `CLAUDE.md`**

Modeled on `/home/alan/proyectos/mcp_invgate/CLAUDE.md`: Project Overview (Clockify MCP), Architecture (FastMCP, per-domain `register(mcp, client)`, dual-host client, read-only/write opt-in), and Clockify API Notes (X-Api-Key, two hosts, regional prefixes, page/page-size + Last-Page, everything under `/workspaces/{id}`).

- [ ] **Step 4: Verify the package runs**

Run: `CLOCKIFY_API_KEY=dummy uv run clockify-mcp --help`
Expected: argparse help prints with `--transport` (no network call on `--help`).

- [ ] **Step 5: Commit**

```bash
git add config.toml.example README.md CLAUDE.md
git commit -m "docs: README, CLAUDE.md, config template"
```

---

## Phase 0+1 Done — Definition of Done

- `uv run pytest tests/ -q` green; `uv run ruff check src/ tests/` clean.
- `uvx`-style entrypoint works; server starts on stdio with a valid `CLOCKIFY_API_KEY`.
- Read-only discovery + base domains functional: workspaces, users, groups.
- Architecture seams in place for later phases: dual-host client, pagination,
  telemetry facade, per-domain `register()`, `resolve_workspace_id`, writes-opt-in gate.

## Next phases (separate plans, same patterns)

- **Phase 2:** projects, tasks, clients, tags (read) — reuse `resolve_workspace_id` + `page_params`.
- **Phase 3:** time_entries (read) + reports (via `client.report`).
- **Phase 4:** core writes opt-in (`_register_writes` gate) + live create/update/delete smoke tests.
- **Phase 5–7:** time_off/holidays, expenses/approvals, custom_fields/scheduling/invoices/webhooks.
- **Telemetry:** port `_otel.py` from invgate and swap the no-op `Telemetry`/`build_telemetry` for the OTel-backed impl (signatures unchanged).
```
