# Clockify MCP — Access Mode ("time-tracking" / support tier) Design

**Date:** 2026-06-07
**Status:** Approved
**Author:** Alan (tracegazer)

## 1. Overview

Today the server has a binary write gate: `CLOCKIFY_ENABLE_WRITES` registers either **no** write tools (default, read-only) or **all** of them. This adds a third, intermediate tier — **time-tracking** (a "support"-style persona): full read access plus the ability to log hours (time-entry writes) and nothing else.

The capability is named after what it does (time tracking), not after a persona. It is configured by an access-mode enum, with the existing boolean kept working for backward compatibility.

This is a **server-side exposure guardrail** — it controls which MCP tools the server registers and (for two tools) scopes them to the authenticated user. It is **not** a real permission system: the Clockify API key's own permissions remain the ultimate boundary (an admin key is still admin at the API level).

## 2. Configuration

New config field `access_mode: str` with three values:

| `access_mode` | Tools registered |
|---|---|
| `read` (default) | All read tools only |
| `time-tracking` | All read tools + the time-entry write tools (see §4) |
| `full` | All read tools + all write tools (current `enable_writes=true` behavior) |

- Env var `CLOCKIFY_ACCESS_MODE`; TOML key `access_mode`. Env wins over TOML (consistent with the rest of `Config`).
- **Back-compat:** if `access_mode` is not provided and `CLOCKIFY_ENABLE_WRITES` / `enable_writes` is truthy, resolve to `full`. If `access_mode` *is* provided, it takes precedence over `enable_writes`.
- An unrecognized `access_mode` value degrades to `read` (the safest tier), mirroring how `telemetry_detail` falls back to `metadata`.
- `Config.enable_writes` is kept as a derived **property** returning `access_mode == "full"`, so existing references (repr, tests) keep working. `Config.access_mode` is the source of truth.
- `Config.__repr__` shows `access_mode` (drops the standalone `enable_writes` field display, since it's now derived).

## 3. Client

`ClockifyClient` gains:
- `writes_enabled` (property) → `self._config.access_mode == "full"` — unchanged meaning; still gates the 16 full-write domains.
- `time_tracking_enabled` (property) → `self._config.access_mode in ("time-tracking", "full")`.
- `current_user_id()` (async, cached) → returns the authenticated user's id via a single `GET user`, cached on the instance for the process lifetime. Used by the self-scoped time-entry wrappers (§4). Caching avoids one API call per duplicate/bulk invocation.

## 4. Time-entry write gating

Other 15 write domains are unchanged: `if client.writes_enabled: _register_writes(mcp, client)`.

`time_entries.register()` branches:

```python
if client.writes_enabled:               # full
    _register_writes(mcp, client)
elif client.time_tracking_enabled:      # time-tracking only
    _register_time_tracking_writes(mcp, client)
```

The module-level async write functions (`create_time_entry`, `update_time_entry`, `delete_time_entry`, `duplicate_time_entry`, `bulk_update_time_entries`) are unchanged and generic (they still accept `user_id` where the endpoint requires it). The difference is purely which `@mcp.tool()` wrappers get registered:

**`_register_writes` (full)** — registers all five wrappers exactly as today (duplicate/bulk expose `user_id`).

**`_register_time_tracking_writes` (time-tracking)** — registers:
- `create_time_entry` — identical wrapper (creates for the authenticated user; always self).
- `update_time_entry`, `delete_time_entry` — identical signatures, but their docstrings carry the **golden rule**: these act on an entry by id and the server cannot cheaply tell whose it is, so the agent must confirm with the human before editing/deleting an entry that may belong to another user.
- `duplicate_time_entry`, `bulk_update_time_entries` — **self-scoped** wrappers that do **not** expose a `user_id` parameter. They call `await client.current_user_id()` and pass that, so in time-tracking mode the agent cannot target another user. (The `userId` path segment bounds bulk edits to the caller's own entries.)

### Golden rule (hybrid enforcement)
- **Cheap enforce** where the user is explicit (`duplicate`, `bulk`): the time-tracking wrappers omit `user_id` and force the authenticated user — no way to point at someone else.
- **Instruction** where ownership isn't known without an extra GET (`update`, `delete` by entry id): docstrings + server `INSTRUCTIONS` tell the agent to confirm with the human first if the entry might be another user's. No per-call GET on the happy path.

## 5. Server INSTRUCTIONS

Add a short paragraph to `server.INSTRUCTIONS` describing the three access modes and the time-tracking golden rule, so the agent understands why only some write tools are present and when to confirm before editing/deleting an entry.

## 6. Testing

- **Config** (`tests/test_config.py`): `CLOCKIFY_ACCESS_MODE=time-tracking|full|read` resolves correctly; `CLOCKIFY_ENABLE_WRITES=true` with no access_mode → `full`; `access_mode` present overrides `enable_writes`; unknown value → `read`; `enable_writes` property reflects `access_mode == "full"`.
- **conftest**: add a `config_time_tracking` fixture (`CLOCKIFY_ACCESS_MODE=time-tracking`, default workspace `ws1`). Keep `config_writes` (still resolves to `full` via the back-compat path).
- **Server registration** (`tests/test_server.py`):
  - `read` (default `config`): no write tools (existing test).
  - `full` (`config_writes`): all write tools (existing test).
  - `time-tracking` (`config_time_tracking`): assert the five time-entry write tools are present (`create_time_entry`, `update_time_entry`, `delete_time_entry`, `duplicate_time_entry`, `bulk_update_time_entries`) AND that non-time-entry writes are absent (e.g. `create_client`, `create_project`).
- **Self-scoping** (`tests/test_time_entries.py`): with `config_time_tracking`, building the server and invoking the `duplicate_time_entry` / `bulk_update_time_entries` tools uses `current_user_id()` (mock `GET user` via respx) and hits the `/user/{me}/...` path — i.e. the wrapper has no `user_id` param and targets the authenticated user. Verify `current_user_id()` caches (one `GET user` across two calls).

## 7. Documentation

- **README**: add `CLOCKIFY_ACCESS_MODE` to the config table; a short "Access modes" note (read / time-tracking / full, back-compat with `CLOCKIFY_ENABLE_WRITES`, the time-tracking golden rule). Note `CLOCKIFY_ENABLE_WRITES` still works (= full).
- **CLAUDE.md**: update the writes description to mention the three modes and that time-tracking exposes only the time-entry writes (duplicate/bulk self-scoped).

## 8. Out of scope

- No per-domain or per-tool capability flags beyond the three-tier enum (YAGNI; the enum is extensible later if needed).
- No server-side ownership enforcement for `update`/`delete` by entry id (handled by the instruction half of the golden rule).
- No change to the API key's real permissions; this is purely which tools the MCP server exposes.
