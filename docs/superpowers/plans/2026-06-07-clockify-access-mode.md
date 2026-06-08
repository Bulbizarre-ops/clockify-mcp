# Access Mode (time-tracking / support tier) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a three-tier access mode (`read` / `time-tracking` / `full`) so the server can expose full read access plus only time-entry writes ("log hours"), between today's read-only and full-write.

**Architecture:** A new `Config.access_mode` enum is the source of truth; `enable_writes` becomes a derived property (`== "full"`) and `CLOCKIFY_ENABLE_WRITES=true` still maps to `full`. The client gains `time_tracking_enabled` and a cached `current_user_id()`. Only `time_entries.register()` changes its gate: in `time-tracking` mode it registers a tailored write set where `duplicate`/`bulk` are self-scoped (no `user_id`) and `update`/`delete` carry a golden-rule docstring. The other 15 write domains stay full-only.

**Tech Stack:** Python 3.12+, FastMCP (`mcp`), httpx, respx + pytest-asyncio, `uv`, ruff.

---

## Background — verified current state

- `Config` (frozen dataclass) currently has a `enable_writes: bool = False` field, set in `load()` via `_resolve_truthy(env, file_values, "CLOCKIFY_ENABLE_WRITES", "enable_writes")`, and a custom `__repr__`. `telemetry_detail` already shows the "validate enum, else fall back" pattern.
- `ClockifyClient.writes_enabled` returns `self._config.enable_writes`. `client.get("user")` returns the current user object (has `id`). `client.default_workspace_id` exists.
- `time_entries.register()` ends with `if client.writes_enabled: _register_writes(mcp, client)`. `_register_writes` registers `create/update/delete/duplicate/bulk` (duplicate/bulk take `user_id`). Module-level `*_fn` aliases at the bottom; the generic module fns `duplicate_time_entry(client, *, user_id, time_entry_id, ...)` and `bulk_update_time_entries(client, *, user_id, entries, ...)` are unchanged by this plan.
- conftest has `config` (read-only, ws1) and `config_writes` (`CLOCKIFY_ENABLE_WRITES=true`, ws1).
- Existing config tests assert `cfg.enable_writes is False/True` — these keep passing because `enable_writes` stays readable (as a property).

**Baseline:** `uv run pytest -q` → 162 passed, 11 skipped, ruff clean.

---

## File Structure

- Modify: `src/clockify_mcp/config.py` — `access_mode` field + resolution + `enable_writes` property
- Modify: `src/clockify_mcp/client.py` — `time_tracking_enabled` property + cached `current_user_id()`
- Modify: `src/clockify_mcp/domains/time_entries.py` — gate branch + `_register_time_tracking_writes`
- Modify: `src/clockify_mcp/server.py` — INSTRUCTIONS paragraph
- Modify: `tests/conftest.py` — `config_time_tracking` fixture
- Modify: `tests/test_config.py`, `tests/test_client.py`, `tests/test_time_entries.py`, `tests/test_server.py`
- Modify: `README.md`, `CLAUDE.md`

---

## Task 1: Config access_mode

**Files:** Modify `src/clockify_mcp/config.py`; Test `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_config.py` (before `_missing_path`):

```python
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


def test_invalid_access_mode_defaults_to_read():
    cfg = Config.load(
        env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ACCESS_MODE": "bogus"},
        config_path=_missing_path(),
    )
    assert cfg.access_mode == "read"
    assert cfg.enable_writes is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_config.py -q`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'access_mode'`.

- [ ] **Step 3: Add the access-mode constant**

In `src/clockify_mcp/config.py`, after the line `_TELEMETRY_DETAILS = {"metadata", "ids", "full"}` add:

```python
_ACCESS_MODES = {"read", "time-tracking", "full"}
```

- [ ] **Step 4: Swap the dataclass field for access_mode + add property**

In the `Config` dataclass, replace the field line:

```python
    enable_writes: bool = False
```

with:

```python
    access_mode: str = "read"
```

Then, immediately after the `__repr__` method (still inside the class), add the derived property:

```python
    @property
    def enable_writes(self) -> bool:
        return self.access_mode == "full"
```

And in `__repr__`, replace:

```python
            f"enable_writes={self.enable_writes}, telemetry_enabled={self.telemetry_enabled}, "
```

with:

```python
            f"access_mode={self.access_mode!r}, telemetry_enabled={self.telemetry_enabled}, "
```

- [ ] **Step 5: Resolve access_mode in load()**

In `Config.load`, replace this line:

```python
        enable_writes = _resolve_truthy(env, file_values, "CLOCKIFY_ENABLE_WRITES", "enable_writes")
```

with:

```python
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
```

And in the `return cls(...)` call, replace `enable_writes=enable_writes,` with `access_mode=access_mode,`.

- [ ] **Step 6: Run config tests**

Run: `uv run pytest tests/test_config.py -q`
Expected: PASS (existing + 6 new tests all pass).

- [ ] **Step 7: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (168 passed, 11 skipped) and ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/clockify_mcp/config.py tests/test_config.py
git commit -m "feat: add Config.access_mode (read/time-tracking/full); enable_writes derived from it"
```

---

## Task 2: Client time_tracking_enabled + cached current_user_id

**Files:** Modify `src/clockify_mcp/client.py`; Test `tests/test_client.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_client.py` (it already imports `httpx`, `respx`, `ClockifyClient`; add `from clockify_mcp.config import Config` if not present):

```python
async def test_access_mode_client_flags():
    tt = ClockifyClient(Config.load(env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ACCESS_MODE": "time-tracking"}))
    assert tt.time_tracking_enabled is True
    assert tt.writes_enabled is False
    await tt.aclose()
    full = ClockifyClient(Config.load(env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ACCESS_MODE": "full"}))
    assert full.time_tracking_enabled is True
    assert full.writes_enabled is True
    await full.aclose()
    ro = ClockifyClient(Config.load(env={"CLOCKIFY_API_KEY": "k"}))
    assert ro.time_tracking_enabled is False
    assert ro.writes_enabled is False
    await ro.aclose()


@respx.mock
async def test_current_user_id_resolves_and_caches(config):
    route = respx.get("https://api.clockify.me/api/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "me1", "email": "x@y.z"})
    )
    client = ClockifyClient(config)
    assert await client.current_user_id() == "me1"
    assert await client.current_user_id() == "me1"
    assert route.call_count == 1  # cached after the first GET
    await client.aclose()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_client.py -q`
Expected: FAIL — `AttributeError: 'ClockifyClient' object has no attribute 'time_tracking_enabled'`.

- [ ] **Step 3: Add the cache slot in `__init__`**

In `src/clockify_mcp/client.py`, in `ClockifyClient.__init__`, after the line `self._secrets = [s for s in (config.api_key,) if s]` add:

```python
        self._current_user_id: str | None = None
```

- [ ] **Step 4: Add property + resolver**

Immediately after the existing `default_workspace_id` property (the block that returns `self._config.default_workspace_id`), add:

```python
    @property
    def time_tracking_enabled(self) -> bool:
        return self._config.access_mode in ("time-tracking", "full")

    async def current_user_id(self) -> str:
        """Return the authenticated user's id (cached after the first call)."""
        if self._current_user_id is None:
            user = await self.get("user")
            self._current_user_id = user["id"]
        return self._current_user_id
```

(Leave `writes_enabled` as-is — it returns `self._config.enable_writes`, which is now the `== "full"` property.)

- [ ] **Step 5: Run client tests**

Run: `uv run pytest tests/test_client.py -q`
Expected: PASS.

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (170 passed, 11 skipped) and ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/client.py tests/test_client.py
git commit -m "feat: client.time_tracking_enabled + cached current_user_id()"
```

---

## Task 3: time_entries time-tracking gate + self-scoped wrappers

**Files:** Modify `src/clockify_mcp/domains/time_entries.py`, `tests/conftest.py`, `tests/test_time_entries.py`, `tests/test_server.py`

- [ ] **Step 1: Add the `config_time_tracking` fixture**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def config_time_tracking() -> Config:
    return Config.load(
        env={
            "CLOCKIFY_API_KEY": "test-key",
            "CLOCKIFY_ACCESS_MODE": "time-tracking",
            "CLOCKIFY_DEFAULT_WORKSPACE_ID": "ws1",
        }
    )
```

- [ ] **Step 2: Write failing tests**

Append to `tests/test_time_entries.py`:

```python
from clockify_mcp.server import build_server


async def test_time_tracking_registers_time_entry_writes_only(config_time_tracking):
    client = ClockifyClient(config_time_tracking)
    mcp = build_server(client)
    names = {t.name for t in await mcp.list_tools()}
    assert {
        "create_time_entry", "update_time_entry", "delete_time_entry",
        "duplicate_time_entry", "bulk_update_time_entries",
    } <= names
    assert "create_client" not in names
    assert "create_project" not in names
    await client.aclose()


@respx.mock
async def test_time_tracking_duplicate_is_self_scoped(config_time_tracking):
    user = respx.get("https://api.clockify.me/api/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "me1"})
    )
    dup = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/me1/time-entries/te1/duplicate"
    ).mock(return_value=httpx.Response(201, json={"id": "te2"}))
    client = ClockifyClient(config_time_tracking)
    mcp = build_server(client)
    await mcp.call_tool("duplicate_time_entry", {"time_entry_id": "te1"})
    assert user.called and dup.called
    await client.aclose()


@respx.mock
async def test_time_tracking_bulk_is_self_scoped(config_time_tracking):
    user = respx.get("https://api.clockify.me/api/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "me1"})
    )
    bulk = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/user/me1/time-entries"
    ).mock(return_value=httpx.Response(200, json=[{"id": "te1"}]))
    client = ClockifyClient(config_time_tracking)
    mcp = build_server(client)
    await mcp.call_tool(
        "bulk_update_time_entries", {"entries": [{"id": "te1", "description": "a"}]}
    )
    assert user.called and bulk.called
    await client.aclose()
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_time_entries.py -q`
Expected: FAIL — `test_time_tracking_*` fail because in time-tracking mode no write tools are registered yet (the gate only handles `writes_enabled`).

- [ ] **Step 4: Branch the gate in `register()`**

In `src/clockify_mcp/domains/time_entries.py`, replace the block at the end of `register()`:

```python
    if client.writes_enabled:
        _register_writes(mcp, client)
```

with:

```python
    if client.writes_enabled:
        _register_writes(mcp, client)
    elif client.time_tracking_enabled:
        _register_time_tracking_writes(mcp, client)
```

- [ ] **Step 5: Add `_register_time_tracking_writes`**

In `src/clockify_mcp/domains/time_entries.py`, add this function immediately after `_register_writes` (before the `*_fn` alias block at the bottom):

```python
def _register_time_tracking_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    """Write tools for the 'time-tracking' access tier: log/manage time entries only.

    create/update/delete are the same as full mode (update/delete act on an entry by
    id; the golden rule lives in their docstrings). duplicate/bulk are self-scoped:
    they take no user_id and always target the authenticated user.
    """

    @mcp.tool()
    async def create_time_entry(
        start: str,
        workspace_id: str | None = None,
        end: str | None = None,
        description: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        tag_ids: list[str] | None = None,
        billable: bool | None = None,
        type: str | None = None,
    ) -> Any:
        """Create a time entry for the authenticated user. Omit end for a running timer."""
        return await create_time_entry_fn(
            client,
            start=start,
            workspace_id=workspace_id,
            end=end,
            description=description,
            project_id=project_id,
            task_id=task_id,
            tag_ids=tag_ids,
            billable=billable,
            type=type,
        )

    @mcp.tool()
    async def update_time_entry(
        time_entry_id: str,
        start: str,
        workspace_id: str | None = None,
        end: str | None = None,
        description: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        tag_ids: list[str] | None = None,
        billable: bool | None = None,
        type: str | None = None,
    ) -> Any:
        """Update a time entry (by id). start is required by the API (pass the existing
        start if unchanged). GOLDEN RULE: in time-tracking mode you should only edit
        YOUR OWN entries — this acts on an entry by id and the server cannot tell whose
        it is, so confirm with the user before editing an entry that may be someone
        else's."""
        return await update_time_entry_fn(
            client,
            time_entry_id=time_entry_id,
            start=start,
            workspace_id=workspace_id,
            end=end,
            description=description,
            project_id=project_id,
            task_id=task_id,
            tag_ids=tag_ids,
            billable=billable,
            type=type,
        )

    @mcp.tool()
    async def delete_time_entry(
        time_entry_id: str, workspace_id: str | None = None
    ) -> Any:
        """Delete a time entry (by id). IRREVERSIBLE. GOLDEN RULE: in time-tracking
        mode you should only delete YOUR OWN entries — this acts on an entry by id and
        the server cannot tell whose it is, so confirm with the user before deleting an
        entry that may be someone else's."""
        return await delete_time_entry_fn(
            client, time_entry_id=time_entry_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def duplicate_time_entry(
        time_entry_id: str, workspace_id: str | None = None
    ) -> Any:
        """Duplicate one of YOUR OWN time entries (time-tracking mode always targets
        the authenticated user)."""
        user_id = await client.current_user_id()
        return await duplicate_time_entry_fn(
            client, user_id=user_id, time_entry_id=time_entry_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def bulk_update_time_entries(
        entries: list[dict[str, Any]], workspace_id: str | None = None
    ) -> Any:
        """Bulk-edit YOUR OWN time entries (time-tracking mode always targets the
        authenticated user). Each entry dict MUST include its 'id'."""
        user_id = await client.current_user_id()
        return await bulk_update_time_entries_fn(
            client, user_id=user_id, entries=entries, workspace_id=workspace_id
        )
```

- [ ] **Step 6: Run the time-entry tests**

Run: `uv run pytest tests/test_time_entries.py -q`
Expected: PASS (existing + 3 new tests).

- [ ] **Step 7: Add the server-registration test for time-tracking**

In `tests/test_server.py`, append:

```python
async def test_time_tracking_mode_registers_only_time_entry_writes(config_time_tracking):
    from clockify_mcp.client import ClockifyClient
    from clockify_mcp.server import build_server

    client = ClockifyClient(config_time_tracking)
    mcp = build_server(client)
    names = {t.name for t in await mcp.list_tools()}
    assert {
        "create_time_entry", "update_time_entry", "delete_time_entry",
        "duplicate_time_entry", "bulk_update_time_entries",
    } <= names
    # no other domain's writes
    assert "create_client" not in names
    assert "create_project" not in names
    assert "create_tag" not in names
    assert "create_invoice" not in names
```

- [ ] **Step 8: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (174 passed, 11 skipped) and ruff clean.

- [ ] **Step 9: Commit**

```bash
git add src/clockify_mcp/domains/time_entries.py tests/conftest.py tests/test_time_entries.py tests/test_server.py
git commit -m "feat: time-tracking access tier registers only time-entry writes (duplicate/bulk self-scoped)"
```

---

## Task 4: Server INSTRUCTIONS

**Files:** Modify `src/clockify_mcp/server.py`; Test `tests/test_server.py`

- [ ] **Step 1: Write a failing test**

In `tests/test_server.py`, append:

```python
def test_instructions_describe_access_modes():
    from clockify_mcp.server import INSTRUCTIONS

    assert "time-tracking" in INSTRUCTIONS
    assert "CLOCKIFY_ACCESS_MODE" in INSTRUCTIONS
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_server.py::test_instructions_describe_access_modes -q`
Expected: FAIL — assertion error (`time-tracking` not in INSTRUCTIONS).

- [ ] **Step 3: Extend INSTRUCTIONS**

In `src/clockify_mcp/server.py`, the `INSTRUCTIONS` string currently has a paragraph beginning `DISCOVERY:` and one beginning `DISAMBIGUATION:`. Insert a new paragraph between the workspace paragraph and `DISCOVERY:` (keep the existing backslash-continued style — each line ends with `\`):

```python
ACCESS MODES: write tools register based on CLOCKIFY_ACCESS_MODE — `read` (default, \
no writes), `time-tracking` (only time-entry writes, for logging hours), or `full` \
(all writes). CLOCKIFY_ENABLE_WRITES=true is equivalent to `full`. In time-tracking \
mode, duplicate/bulk time-entry tools always act on the authenticated user; for \
update/delete by entry id, confirm with the user before changing an entry that may \
belong to someone else.

```

(Place it so the assembled text keeps reading naturally; ensure the line before it still ends with `\` and there's a blank line separating paragraphs as elsewhere.)

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_server.py::test_instructions_describe_access_modes -q`
Expected: PASS.

- [ ] **Step 5: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass (175 passed, 11 skipped) and ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/clockify_mcp/server.py tests/test_server.py
git commit -m "docs: describe access modes + time-tracking golden rule in server INSTRUCTIONS"
```

---

## Task 5: Docs

**Files:** Modify `README.md`, `CLAUDE.md`

- [ ] **Step 1: Update README config table + add Access modes note**

In `README.md`, in the configuration table, add a row above the `CLOCKIFY_ENABLE_WRITES` row:

```markdown
| `CLOCKIFY_ACCESS_MODE` | `access_mode` | `read` (default) \| `time-tracking` (read + log hours) \| `full` (all writes) |
```

And change the existing `CLOCKIFY_ENABLE_WRITES` row description to note back-compat:

```markdown
| `CLOCKIFY_ENABLE_WRITES` | `enable_writes` | Back-compat alias: `true` = `access_mode=full`. `CLOCKIFY_ACCESS_MODE` takes precedence. |
```

Then, right after that table, add a short note:

```markdown
**Access modes:** `read` exposes only read tools. `time-tracking` adds the time-entry write tools (create/update/delete/duplicate/bulk) for logging hours and nothing else — `duplicate`/`bulk` always act on the authenticated user, and for `update`/`delete` by id the assistant is told to confirm before touching an entry that may belong to someone else. `full` exposes all write tools. This gates which MCP tools the server registers; it is not a replacement for the API key's own permissions.
```

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`, find the sentence in the Project Overview that says writes "register only when CLOCKIFY_ENABLE_WRITES=true" and replace that clause with:

```markdown
register according to CLOCKIFY_ACCESS_MODE: `read` (default, none), `time-tracking` (only time-entry writes — duplicate/bulk self-scoped to the authenticated user), or `full` (all writes; CLOCKIFY_ENABLE_WRITES=true is an alias for `full`).
```

Also update the `Read-only by default; write tools will register only when CLOCKIFY_ENABLE_WRITES=true (gated in each domain's register()).` line in the Architecture section to:

```markdown
Read-only by default; write tools register per CLOCKIFY_ACCESS_MODE (gated in each domain's `register()` via `client.writes_enabled` / `client.time_tracking_enabled`).
```

- [ ] **Step 3: Run full suite + lint (docs-only, sanity)**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: 175 passed, 11 skipped, ruff clean (unchanged).

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document CLOCKIFY_ACCESS_MODE (read/time-tracking/full)"
```

---

## Self-Review

**Spec coverage:**
- §2 Config enum + back-compat + invalid→read + `enable_writes` property → Task 1 ✓
- §3 Client `time_tracking_enabled` + cached `current_user_id` (`writes_enabled` unchanged) → Task 2 ✓
- §4 gate branch + `_register_time_tracking_writes` (self-scoped duplicate/bulk; golden-rule docstrings on update/delete) → Task 3 ✓
- §5 server INSTRUCTIONS → Task 4 ✓
- §6 tests: config resolution, registration per mode, self-scoping + caching, `config_time_tracking` fixture → Tasks 1–3 ✓
- §7 docs → Task 5 ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; commands show expected output.

**Type/name consistency:** `access_mode` (field) vs `enable_writes` (property) consistent across config + client + tests; `time_tracking_enabled`, `current_user_id()` names consistent; the time-tracking `duplicate_time_entry`/`bulk_update_time_entries` wrappers drop `user_id` and call `current_user_id()`, reusing the unchanged module-level `*_fn` which still take `user_id`. Test counts are cumulative estimates (162 baseline → ~175); the implementer verifies the actual count at each Step and adjusts the docs count in Task 1 of any later phase if needed — here the only doc count is informational.

**Out of scope (per spec §8):** no per-tool capability flags; no ownership GET-enforcement for update/delete by id; no change to API-key permissions.
