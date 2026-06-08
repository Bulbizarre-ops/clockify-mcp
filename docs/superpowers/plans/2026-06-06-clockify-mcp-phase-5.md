# Clockify MCP Phase 5 — Time Off + Holidays Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `time_off` and `holidays` domains (read + opt-in write tools) to the Clockify MCP server, following the established per-domain pattern.

**Architecture:** Two new domain modules (`domains/time_off.py`, `domains/holidays.py`), each exposing standalone async functions over `ClockifyClient` plus a `register(mcp, client)` that wires `@mcp.tool()` thunks and gates writes behind `_register_writes` when `client.writes_enabled`. Both domains live on the SAME regular host (`https://api.clockify.me/api/v1`) — no new base host or client method is needed. `time_off` request approve/reject reuse the existing `client.patch`; the "list requests" read is a POST (filter body). Nested JSON write bodies are assembled in-module and trimmed with `bodies.drop_none()` at each level.

**Tech Stack:** Python 3.12+, FastMCP (`mcp`), httpx, respx (tests), pytest-asyncio, uv, ruff.

**Verified API surface (from the official Clockify OpenAPI 3.0.1 spec, docs.clockify.me):**

| Operation | Method | Path (base `https://api.clockify.me/api/v1`) |
|---|---|---|
| List policies | GET | `workspaces/{ws}/time-off/policies` |
| Get policy | GET | `workspaces/{ws}/time-off/policies/{id}` |
| Balances per policy | GET | `workspaces/{ws}/time-off/balance/policy/{policyId}` |
| Balances per user | GET | `workspaces/{ws}/time-off/balance/user/{userId}` |
| List/filter requests | POST | `workspaces/{ws}/time-off/requests` |
| Create policy | POST | `workspaces/{ws}/time-off/policies` |
| Create request (self) | POST | `workspaces/{ws}/time-off/policies/{policyId}/requests` |
| Approve/Reject request | PATCH | `workspaces/{ws}/time-off/policies/{policyId}/requests/{requestId}` |
| Withdraw/cancel request | DELETE | `workspaces/{ws}/time-off/policies/{policyId}/requests/{requestId}` |
| List holidays | GET | `workspaces/{ws}/holidays` |
| Holidays in period | GET | `workspaces/{ws}/holidays/in-period` |
| Create holiday | POST | `workspaces/{ws}/holidays` |
| Update holiday | PUT | `workspaces/{ws}/holidays/{holidayId}` |
| Delete holiday | DELETE | `workspaces/{ws}/holidays/{holidayId}` |

Param spelling: GET list params are **hyphenated** (`page-size`, `sort-order`, `assigned-to`). The requests-filter POST body and all write bodies are **camelCase** (`pageSize`, `userGroups`, `datePeriod`, `startDate`, `occursAnnually`, `timeOffPeriod`, `isHalfDay`, `halfDayPeriod`). Approve/reject status enum is **only** `APPROVED` | `REJECTED`; there is no "withdrawn" status — withdrawal/cancel = DELETE. Holiday `update` requires `occursAnnually` (full-replace).

---

## File Structure

- Create: `src/clockify_mcp/domains/time_off.py` — time-off policies, balances, requests (read + write).
- Create: `src/clockify_mcp/domains/holidays.py` — holidays (read + write).
- Create: `tests/test_time_off.py` — respx unit tests for time_off.
- Create: `tests/test_holidays.py` — respx unit tests for holidays.
- Modify: `src/clockify_mcp/server.py` — import + register the two new domains.
- Modify: `tests/test_server.py` — assert new read + write tool names register.
- Modify: `tests/test_live_smoke.py` — add gated holiday + time-off-policy round-trips.
- Modify: `README.md`, `CLAUDE.md` — document the new tools.

**New tool inventory (15 tools):**
- `time_off` (5 read, 5 write): `list_time_off_policies`, `get_time_off_policy`, `list_time_off_balances_by_policy`, `list_time_off_balances_by_user`, `list_time_off_requests` · `create_time_off_policy`, `create_time_off_request`, `approve_time_off_request`, `reject_time_off_request`, `withdraw_time_off_request`
- `holidays` (2 read, 3 write): `list_holidays`, `list_holidays_in_period` · `create_holiday`, `update_holiday`, `delete_holiday`

After Phase 5: 27 read + 25 write = 52 tools across 11 domains.

---

## Task 1: time_off read — policies (list + get)

**Files:**
- Create: `src/clockify_mcp/domains/time_off.py`
- Test: `tests/test_time_off.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_time_off.py
import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import time_off


@respx.mock
async def test_list_time_off_policies_passes_filters(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies"
    ).mock(return_value=httpx.Response(200, json=[{"id": "p1"}]))
    client = ClockifyClient(config)
    result = await time_off.list_time_off_policies(
        client,
        name="Vacation",
        status="ACTIVE",
        sort_column="NAME",
        sort_order="ASCENDING",
        page=1,
        page_size=15,
    )
    assert result == [{"id": "p1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "Vacation"
    assert sent["status"] == "ACTIVE"
    assert sent["sort-column"] == "NAME"
    assert sent["sort-order"] == "ASCENDING"
    assert sent["page-size"] == "15"
    await client.aclose()


@respx.mock
async def test_get_time_off_policy(config):
    respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1"
    ).mock(return_value=httpx.Response(200, json={"id": "p1", "name": "Vacation"}))
    client = ClockifyClient(config)
    assert await time_off.get_time_off_policy(client, policy_id="p1") == {
        "id": "p1",
        "name": "Vacation",
    }
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: FAIL — `ModuleNotFoundError`/`ImportError: cannot import name 'time_off'`.

- [ ] **Step 3: Write the module with read functions**

```python
# src/clockify_mcp/domains/time_off.py
"""Time-off domain: policies, balances, and requests (read + write).

All endpoints live on the regular Clockify host under
``workspaces/{workspaceId}/time-off/...``. Listing requests is a POST (the
filter travels in the JSON body). Approve/reject PATCH the request status
(enum APPROVED|REJECTED); withdrawal/cancellation is a DELETE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_time_off_policies(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    status: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List time-off policies on the workspace (paginated).

    status is one of ACTIVE, ARCHIVED, ALL. sort_order is ASCENDING or DESCENDING.
    Time off is a paid Clockify feature; on plans without it the API returns an error.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "name": name,
        "status": status,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/time-off/policies", params=params)


async def get_time_off_policy(
    client: ClockifyClient, *, policy_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single time-off policy by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/time-off/policies/{policy_id}")


list_time_off_policies_fn = list_time_off_policies
get_time_off_policy_fn = get_time_off_policy
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/time_off.py tests/test_time_off.py
git commit -m "feat: time_off policies read (list, get)"
```

---

## Task 2: time_off read — balances (by policy + by user)

**Files:**
- Modify: `src/clockify_mcp/domains/time_off.py`
- Test: `tests/test_time_off.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_time_off.py`)

```python
@respx.mock
async def test_list_balances_by_policy_passes_params(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/balance/policy/p1"
    ).mock(return_value=httpx.Response(200, json={"balances": []}))
    client = ClockifyClient(config)
    result = await time_off.list_time_off_balances_by_policy(
        client, policy_id="p1", sort="BALANCE", sort_order="DESCENDING", page=2, page_size=10
    )
    assert result == {"balances": []}
    sent = dict(route.calls.last.request.url.params)
    assert sent["sort"] == "BALANCE"
    assert sent["sort-order"] == "DESCENDING"
    assert sent["page"] == "2"
    assert sent["page-size"] == "10"
    await client.aclose()


@respx.mock
async def test_list_balances_by_user_passes_params(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/balance/user/u1"
    ).mock(return_value=httpx.Response(200, json={"balances": []}))
    client = ClockifyClient(config)
    await time_off.list_time_off_balances_by_user(
        client, user_id="u1", sort="USER", sort_order="ASCENDING"
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["sort"] == "USER"
    assert sent["sort-order"] == "ASCENDING"
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'list_time_off_balances_by_policy'`.

- [ ] **Step 3: Add the balance functions** (insert after `get_time_off_policy`, before the `_fn` aliases)

```python
async def list_time_off_balances_by_policy(
    client: ClockifyClient,
    *,
    policy_id: str,
    workspace_id: str | None = None,
    sort: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List per-user time-off balances for a policy (paginated).

    sort is one of USER, POLICY, USED, BALANCE, TOTAL; sort_order ASCENDING/DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "sort": sort,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(
        f"workspaces/{ws}/time-off/balance/policy/{policy_id}", params=params
    )


async def list_time_off_balances_by_user(
    client: ClockifyClient,
    *,
    user_id: str,
    workspace_id: str | None = None,
    sort: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List a user's time-off balances across policies (paginated).

    sort is one of USER, POLICY, USED, BALANCE, TOTAL; sort_order ASCENDING/DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "sort": sort,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(
        f"workspaces/{ws}/time-off/balance/user/{user_id}", params=params
    )
```

Add to the `_fn` aliases block:

```python
list_time_off_balances_by_policy_fn = list_time_off_balances_by_policy
list_time_off_balances_by_user_fn = list_time_off_balances_by_user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/time_off.py tests/test_time_off.py
git commit -m "feat: time_off balances read (by policy, by user)"
```

---

## Task 3: time_off read — list requests (POST filter)

**Files:**
- Modify: `src/clockify_mcp/domains/time_off.py`
- Test: `tests/test_time_off.py`

- [ ] **Step 1: Write the failing test** (append)

```python
@respx.mock
async def test_list_time_off_requests_builds_body(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/requests"
    ).mock(return_value=httpx.Response(200, json={"requests": []}))
    client = ClockifyClient(config)
    result = await time_off.list_time_off_requests(
        client,
        start="2022-08-01T00:00:00Z",
        end="2022-08-31T23:59:59Z",
        statuses=["PENDING"],
        users=["u1"],
        user_groups=["g1"],
        page=1,
        page_size=50,
    )
    assert result == {"requests": []}
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "start": "2022-08-01T00:00:00Z",
        "end": "2022-08-31T23:59:59Z",
        "statuses": ["PENDING"],
        "users": ["u1"],
        "userGroups": ["g1"],
        "page": 1,
        "pageSize": 50,
    }
    await client.aclose()


@respx.mock
async def test_list_time_off_requests_omits_unset(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/requests"
    ).mock(return_value=httpx.Response(200, json={"requests": []}))
    client = ClockifyClient(config)
    await time_off.list_time_off_requests(client)
    assert json.loads(route.calls.last.request.content) == {}
    await client.aclose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: FAIL — `AttributeError: ... 'list_time_off_requests'`.

- [ ] **Step 3: Add the function** (after the balance functions)

```python
async def list_time_off_requests(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    statuses: list[str] | None = None,
    users: list[str] | None = None,
    user_groups: list[str] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List/filter time-off requests (the filter travels in a POST body).

    start/end are ISO-8601 timestamps. statuses items are PENDING, APPROVED,
    REJECTED, or ALL. users/user_groups filter by member or group id.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "statuses": statuses,
            "users": users,
            "userGroups": user_groups,
            "page": page,
            "pageSize": page_size,
        }
    )
    return await client.post(f"workspaces/{ws}/time-off/requests", json=body)
```

Add alias: `list_time_off_requests_fn = list_time_off_requests`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/time_off.py tests/test_time_off.py
git commit -m "feat: time_off list requests (POST filter)"
```

---

## Task 4: time_off read registration

**Files:**
- Modify: `src/clockify_mcp/domains/time_off.py`

- [ ] **Step 1: Add the `register` function** (append at the end of the module, after the read functions but the `_fn` aliases stay at the very bottom)

Place `register` directly after `list_time_off_requests` and keep all `_fn = ...` aliases as the final block of the file.

```python
def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_time_off_policies(
        workspace_id: str | None = None,
        name: str | None = None,
        status: str | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List time-off policies on the workspace (paginated)."""
        return await list_time_off_policies_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            status=status,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def get_time_off_policy(
        policy_id: str, workspace_id: str | None = None
    ) -> Any:
        """Get a single time-off policy by id."""
        return await get_time_off_policy_fn(
            client, policy_id=policy_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def list_time_off_balances_by_policy(
        policy_id: str,
        workspace_id: str | None = None,
        sort: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List per-user time-off balances for a policy (paginated)."""
        return await list_time_off_balances_by_policy_fn(
            client,
            policy_id=policy_id,
            workspace_id=workspace_id,
            sort=sort,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def list_time_off_balances_by_user(
        user_id: str,
        workspace_id: str | None = None,
        sort: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List a user's time-off balances across policies (paginated)."""
        return await list_time_off_balances_by_user_fn(
            client,
            user_id=user_id,
            workspace_id=workspace_id,
            sort=sort,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def list_time_off_requests(
        workspace_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        statuses: list[str] | None = None,
        users: list[str] | None = None,
        user_groups: list[str] | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List/filter time-off requests (filter sent as a POST body)."""
        return await list_time_off_requests_fn(
            client,
            workspace_id=workspace_id,
            start=start,
            end=end,
            statuses=statuses,
            users=users,
            user_groups=user_groups,
            page=page,
            page_size=page_size,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)
```

- [ ] **Step 2: Run the suite to verify nothing breaks**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: PASS (6 passed) — `register` is not yet exercised but must import cleanly. `_register_writes` is referenced; define a temporary stub now to keep the module importable:

Add this stub directly above the `_fn` aliases (it will be replaced in Task 6):

```python
def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:  # filled in Task 6
    pass
```

Run: `uv run pytest tests/test_time_off.py -q`
Expected: PASS (6 passed).

- [ ] **Step 3: Commit**

```bash
git add src/clockify_mcp/domains/time_off.py
git commit -m "feat: register time_off read tools"
```

---

## Task 5: time_off writes — create policy

**Files:**
- Modify: `src/clockify_mcp/domains/time_off.py`
- Test: `tests/test_time_off.py`

- [ ] **Step 1: Write the failing tests** (append; note `config_writes` fixture)

```python
@respx.mock
async def test_create_time_off_policy_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies"
    ).mock(return_value=httpx.Response(201, json={"id": "p1"}))
    client = ClockifyClient(config_writes)
    result = await time_off.create_time_off_policy(
        client,
        name="Mental health days",
        requires_approval=True,
        team_managers=True,
        approver_user_ids=["u1"],
        color="#8BC34A",
        icon="STETHOSCOPE",
        time_unit="DAYS",
        everyone_including_new=True,
    )
    assert result == {"id": "p1"}
    body = json.loads(route.calls.last.request.content)
    assert body["name"] == "Mental health days"
    assert body["color"] == "#8BC34A"
    assert body["icon"] == "STETHOSCOPE"
    assert body["timeUnit"] == "DAYS"
    assert body["everyoneIncludingNew"] is True
    assert body["approve"] == {
        "requiresApproval": True,
        "teamManagers": True,
        "specificMembers": False,
        "userIds": ["u1"],
    }
    await client.aclose()


@respx.mock
async def test_create_time_off_policy_minimal(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies"
    ).mock(return_value=httpx.Response(201, json={"id": "p1"}))
    client = ClockifyClient(config_writes)
    await time_off.create_time_off_policy(client, name="PTO")
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "name": "PTO",
        "approve": {
            "requiresApproval": False,
            "teamManagers": False,
            "specificMembers": False,
            "userIds": [],
        },
    }
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: FAIL — `AttributeError: ... 'create_time_off_policy'`.

- [ ] **Step 3: Add the function** (place with the other write functions, above the `register` definition)

```python
async def create_time_off_policy(
    client: ClockifyClient,
    *,
    name: str,
    workspace_id: str | None = None,
    requires_approval: bool = False,
    team_managers: bool = False,
    specific_members: bool = False,
    approver_user_ids: list[str] | None = None,
    color: str | None = None,
    icon: str | None = None,
    time_unit: str | None = None,
    allow_half_day: bool | None = None,
    allow_negative_balance: bool | None = None,
    everyone_including_new: bool | None = None,
) -> Any:
    """Create a time-off policy on the workspace.

    The approval rule is required by the API and is built from requires_approval,
    team_managers, specific_members, and approver_user_ids. time_unit is DAYS or
    HOURS; icon is one of the Clockify policy icons (e.g. UMBRELLA, PLANE,
    STETHOSCOPE). Time off is a paid feature; the API errors on plans without it.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "color": color,
            "icon": icon,
            "timeUnit": time_unit,
            "allowHalfDay": allow_half_day,
            "allowNegativeBalance": allow_negative_balance,
            "everyoneIncludingNew": everyone_including_new,
            "approve": {
                "requiresApproval": requires_approval,
                "teamManagers": team_managers,
                "specificMembers": specific_members,
                "userIds": approver_user_ids or [],
            },
        }
    )
    return await client.post(f"workspaces/{ws}/time-off/policies", json=body)
```

Add alias: `create_time_off_policy_fn = create_time_off_policy`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/time_off.py tests/test_time_off.py
git commit -m "feat: time_off create policy (write)"
```

---

## Task 6: time_off writes — requests (create / approve / reject / withdraw) + write registration

**Files:**
- Modify: `src/clockify_mcp/domains/time_off.py`
- Test: `tests/test_time_off.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
@respx.mock
async def test_create_time_off_request_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests"
    ).mock(return_value=httpx.Response(201, json={"id": "r1"}))
    client = ClockifyClient(config_writes)
    result = await time_off.create_time_off_request(
        client,
        policy_id="p1",
        start="2021-12-23",
        end="2021-12-25",
        days=3,
        note="Family vacation",
    )
    assert result == {"id": "r1"}
    body = json.loads(route.calls.last.request.content)
    assert body["note"] == "Family vacation"
    assert body["timeOffPeriod"] == {
        "period": {"start": "2021-12-23", "end": "2021-12-25", "days": 3}
    }
    await client.aclose()


@respx.mock
async def test_create_time_off_request_half_day(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests"
    ).mock(return_value=httpx.Response(201, json={"id": "r1"}))
    client = ClockifyClient(config_writes)
    await time_off.create_time_off_request(
        client, policy_id="p1", start="2021-12-23", end="2021-12-23", days=1,
        is_half_day=True, half_day_period="FIRST_HALF",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["timeOffPeriod"]["isHalfDay"] is True
    assert body["timeOffPeriod"]["halfDayPeriod"] == "FIRST_HALF"
    await client.aclose()


@respx.mock
async def test_approve_time_off_request(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests/r1"
    ).mock(return_value=httpx.Response(200, json={"id": "r1", "status": "APPROVED"}))
    client = ClockifyClient(config_writes)
    result = await time_off.approve_time_off_request(client, policy_id="p1", request_id="r1")
    assert result["status"] == "APPROVED"
    assert json.loads(route.calls.last.request.content) == {"status": "APPROVED"}
    await client.aclose()


@respx.mock
async def test_reject_time_off_request_with_note(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests/r1"
    ).mock(return_value=httpx.Response(200, json={"id": "r1", "status": "REJECTED"}))
    client = ClockifyClient(config_writes)
    await time_off.reject_time_off_request(
        client, policy_id="p1", request_id="r1", note="Insufficient balance"
    )
    assert json.loads(route.calls.last.request.content) == {
        "status": "REJECTED",
        "note": "Insufficient balance",
    }
    await client.aclose()


@respx.mock
async def test_withdraw_time_off_request(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/time-off/policies/p1/requests/r1"
    ).mock(return_value=httpx.Response(200, json={"id": "r1"}))
    client = ClockifyClient(config_writes)
    assert await time_off.withdraw_time_off_request(
        client, policy_id="p1", request_id="r1"
    ) == {"id": "r1"}
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: FAIL — `AttributeError: ... 'create_time_off_request'`.

- [ ] **Step 3: Add the request write functions**

```python
async def create_time_off_request(
    client: ClockifyClient,
    *,
    policy_id: str,
    start: str,
    end: str,
    days: int,
    workspace_id: str | None = None,
    note: str | None = None,
    is_half_day: bool | None = None,
    half_day_period: str | None = None,
) -> Any:
    """Create a time-off request for the authenticated user under a policy.

    start/end are dates (YYYY-MM-DD); days is the number of days requested.
    half_day_period is FIRST_HALF, SECOND_HALF, or NOT_DEFINED (only meaningful
    when is_half_day is True).
    """
    ws = resolve_workspace_id(client, workspace_id)
    time_off_period = drop_none(
        {
            "period": {"start": start, "end": end, "days": days},
            "isHalfDay": is_half_day,
            "halfDayPeriod": half_day_period,
        }
    )
    body = drop_none({"note": note, "timeOffPeriod": time_off_period})
    return await client.post(
        f"workspaces/{ws}/time-off/policies/{policy_id}/requests", json=body
    )


async def approve_time_off_request(
    client: ClockifyClient,
    *,
    policy_id: str,
    request_id: str,
    workspace_id: str | None = None,
    note: str | None = None,
) -> Any:
    """Approve a time-off request (sets status APPROVED)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"status": "APPROVED", "note": note})
    return await client.patch(
        f"workspaces/{ws}/time-off/policies/{policy_id}/requests/{request_id}", json=body
    )


async def reject_time_off_request(
    client: ClockifyClient,
    *,
    policy_id: str,
    request_id: str,
    workspace_id: str | None = None,
    note: str | None = None,
) -> Any:
    """Reject a time-off request (sets status REJECTED)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"status": "REJECTED", "note": note})
    return await client.patch(
        f"workspaces/{ws}/time-off/policies/{policy_id}/requests/{request_id}", json=body
    )


async def withdraw_time_off_request(
    client: ClockifyClient,
    *,
    policy_id: str,
    request_id: str,
    workspace_id: str | None = None,
) -> Any:
    """Withdraw/cancel a time-off request. IRREVERSIBLE — the request is deleted."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(
        f"workspaces/{ws}/time-off/policies/{policy_id}/requests/{request_id}"
    )
```

- [ ] **Step 4: Replace the `_register_writes` stub** with the real implementation

```python
def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_time_off_policy(
        name: str,
        workspace_id: str | None = None,
        requires_approval: bool = False,
        team_managers: bool = False,
        specific_members: bool = False,
        approver_user_ids: list[str] | None = None,
        color: str | None = None,
        icon: str | None = None,
        time_unit: str | None = None,
        allow_half_day: bool | None = None,
        allow_negative_balance: bool | None = None,
        everyone_including_new: bool | None = None,
    ) -> Any:
        """Create a time-off policy on the workspace."""
        return await create_time_off_policy_fn(
            client,
            name=name,
            workspace_id=workspace_id,
            requires_approval=requires_approval,
            team_managers=team_managers,
            specific_members=specific_members,
            approver_user_ids=approver_user_ids,
            color=color,
            icon=icon,
            time_unit=time_unit,
            allow_half_day=allow_half_day,
            allow_negative_balance=allow_negative_balance,
            everyone_including_new=everyone_including_new,
        )

    @mcp.tool()
    async def create_time_off_request(
        policy_id: str,
        start: str,
        end: str,
        days: int,
        workspace_id: str | None = None,
        note: str | None = None,
        is_half_day: bool | None = None,
        half_day_period: str | None = None,
    ) -> Any:
        """Create a time-off request for the authenticated user under a policy."""
        return await create_time_off_request_fn(
            client,
            policy_id=policy_id,
            start=start,
            end=end,
            days=days,
            workspace_id=workspace_id,
            note=note,
            is_half_day=is_half_day,
            half_day_period=half_day_period,
        )

    @mcp.tool()
    async def approve_time_off_request(
        policy_id: str,
        request_id: str,
        workspace_id: str | None = None,
        note: str | None = None,
    ) -> Any:
        """Approve a time-off request (sets status APPROVED)."""
        return await approve_time_off_request_fn(
            client,
            policy_id=policy_id,
            request_id=request_id,
            workspace_id=workspace_id,
            note=note,
        )

    @mcp.tool()
    async def reject_time_off_request(
        policy_id: str,
        request_id: str,
        workspace_id: str | None = None,
        note: str | None = None,
    ) -> Any:
        """Reject a time-off request (sets status REJECTED)."""
        return await reject_time_off_request_fn(
            client,
            policy_id=policy_id,
            request_id=request_id,
            workspace_id=workspace_id,
            note=note,
        )

    @mcp.tool()
    async def withdraw_time_off_request(
        policy_id: str, request_id: str, workspace_id: str | None = None
    ) -> Any:
        """Withdraw/cancel a time-off request. IRREVERSIBLE — the request is deleted."""
        return await withdraw_time_off_request_fn(
            client, policy_id=policy_id, request_id=request_id, workspace_id=workspace_id
        )
```

- [ ] **Step 5: Update the `_fn` aliases block** (at the bottom of the file) to include the request writes

```python
create_time_off_request_fn = create_time_off_request
approve_time_off_request_fn = approve_time_off_request
reject_time_off_request_fn = reject_time_off_request
withdraw_time_off_request_fn = withdraw_time_off_request
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_time_off.py -q`
Expected: PASS (13 passed).

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/time_off.py tests/test_time_off.py
git commit -m "feat: time_off request writes (create/approve/reject/withdraw)"
```

---

## Task 7: holidays read (list + in-period)

**Files:**
- Create: `src/clockify_mcp/domains/holidays.py`
- Test: `tests/test_holidays.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_holidays.py
import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import holidays


@respx.mock
async def test_list_holidays_passes_assigned_to(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays"
    ).mock(return_value=httpx.Response(200, json=[{"id": "h1"}]))
    client = ClockifyClient(config)
    result = await holidays.list_holidays(client, assigned_to="u1")
    assert result == [{"id": "h1"}]
    assert dict(route.calls.last.request.url.params)["assigned-to"] == "u1"
    await client.aclose()


@respx.mock
async def test_list_holidays_in_period_passes_params(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays/in-period"
    ).mock(return_value=httpx.Response(200, json=[{"id": "h1"}]))
    client = ClockifyClient(config)
    await holidays.list_holidays_in_period(
        client, assigned_to="u1", start="2023-01-01", end="2023-12-31"
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["assigned-to"] == "u1"
    assert sent["start"] == "2023-01-01"
    assert sent["end"] == "2023-12-31"
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_holidays.py -q`
Expected: FAIL — `ImportError: cannot import name 'holidays'`.

- [ ] **Step 3: Write the module read functions**

```python
# src/clockify_mcp/domains/holidays.py
"""Holidays domain (read + write).

Holidays live on the regular Clockify host under ``workspaces/{workspaceId}/
holidays``. Holidays are a paid Clockify feature; the API errors on plans
without it. ``update_holiday`` is a full replace and requires occurs_annually.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_holidays(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    assigned_to: str | None = None,
) -> Any:
    """List holidays on the workspace, optionally filtered to a user's assignments.

    assigned_to is a user id; when omitted all workspace holidays are returned.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {"assigned-to": assigned_to}
    return await client.get(f"workspaces/{ws}/holidays", params=params)


async def list_holidays_in_period(
    client: ClockifyClient,
    *,
    assigned_to: str,
    start: str,
    end: str,
    workspace_id: str | None = None,
) -> Any:
    """List holidays overlapping a date range for a user.

    assigned_to (user id), start, and end (YYYY-MM-DD) are all required by the API.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {"assigned-to": assigned_to, "start": start, "end": end}
    return await client.get(f"workspaces/{ws}/holidays/in-period", params=params)


list_holidays_fn = list_holidays
list_holidays_in_period_fn = list_holidays_in_period
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_holidays.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/holidays.py tests/test_holidays.py
git commit -m "feat: holidays read (list, in-period)"
```

---

## Task 8: holidays writes (create / update / delete) + registration

**Files:**
- Modify: `src/clockify_mcp/domains/holidays.py`
- Test: `tests/test_holidays.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
@respx.mock
async def test_create_holiday_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays"
    ).mock(return_value=httpx.Response(201, json={"id": "h1"}))
    client = ClockifyClient(config_writes)
    result = await holidays.create_holiday(
        client,
        name="Labour Day",
        start_date="2023-05-01",
        end_date="2023-05-01",
        color="#8BC34A",
        occurs_annually=True,
        everyone_including_new=True,
    )
    assert result == {"id": "h1"}
    body = json.loads(route.calls.last.request.content)
    assert body["name"] == "Labour Day"
    assert body["color"] == "#8BC34A"
    assert body["occursAnnually"] is True
    assert body["everyoneIncludingNew"] is True
    assert body["datePeriod"] == {"startDate": "2023-05-01", "endDate": "2023-05-01"}
    await client.aclose()


@respx.mock
async def test_create_holiday_minimal(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays"
    ).mock(return_value=httpx.Response(201, json={"id": "h1"}))
    client = ClockifyClient(config_writes)
    await holidays.create_holiday(
        client, name="One Off", start_date="2023-06-06", end_date="2023-06-06"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "name": "One Off",
        "datePeriod": {"startDate": "2023-06-06", "endDate": "2023-06-06"},
    }
    await client.aclose()


@respx.mock
async def test_update_holiday_builds_body(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays/h1"
    ).mock(return_value=httpx.Response(200, json={"id": "h1"}))
    client = ClockifyClient(config_writes)
    await holidays.update_holiday(
        client,
        holiday_id="h1",
        name="Labour Day",
        start_date="2023-05-01",
        end_date="2023-05-02",
        occurs_annually=False,
    )
    body = json.loads(route.calls.last.request.content)
    assert body["name"] == "Labour Day"
    assert body["occursAnnually"] is False
    assert body["datePeriod"] == {"startDate": "2023-05-01", "endDate": "2023-05-02"}
    await client.aclose()


@respx.mock
async def test_delete_holiday(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/holidays/h1"
    ).mock(return_value=httpx.Response(200, json={"id": "h1"}))
    client = ClockifyClient(config_writes)
    assert await holidays.delete_holiday(client, holiday_id="h1") == {"id": "h1"}
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_holidays.py -q`
Expected: FAIL — `AttributeError: ... 'create_holiday'`.

- [ ] **Step 3: Add the write functions** (after `list_holidays_in_period`, before the `_fn` aliases)

```python
async def create_holiday(
    client: ClockifyClient,
    *,
    name: str,
    start_date: str,
    end_date: str,
    workspace_id: str | None = None,
    color: str | None = None,
    occurs_annually: bool | None = None,
    everyone_including_new: bool | None = None,
) -> Any:
    """Create a holiday on the workspace.

    start_date/end_date are YYYY-MM-DD. occurs_annually repeats it every year;
    everyone_including_new assigns it to all current and future members.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "color": color,
            "occursAnnually": occurs_annually,
            "everyoneIncludingNew": everyone_including_new,
            "datePeriod": {"startDate": start_date, "endDate": end_date},
        }
    )
    return await client.post(f"workspaces/{ws}/holidays", json=body)


async def update_holiday(
    client: ClockifyClient,
    *,
    holiday_id: str,
    name: str,
    start_date: str,
    end_date: str,
    occurs_annually: bool,
    workspace_id: str | None = None,
    color: str | None = None,
    everyone_including_new: bool | None = None,
) -> Any:
    """Update a holiday (full replace). name, the date range, and occurs_annually
    are required by the API; start_date/end_date are YYYY-MM-DD.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "occursAnnually": occurs_annually,
            "color": color,
            "everyoneIncludingNew": everyone_including_new,
            "datePeriod": {"startDate": start_date, "endDate": end_date},
        }
    )
    return await client.put(f"workspaces/{ws}/holidays/{holiday_id}", json=body)


async def delete_holiday(
    client: ClockifyClient, *, holiday_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a holiday. IRREVERSIBLE — the holiday is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/holidays/{holiday_id}")
```

- [ ] **Step 4: Add `register` + `_register_writes`** (after `delete_holiday`, keeping `_fn` aliases as the final block)

```python
def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_holidays(
        workspace_id: str | None = None, assigned_to: str | None = None
    ) -> Any:
        """List holidays on the workspace, optionally filtered to a user."""
        return await list_holidays_fn(
            client, workspace_id=workspace_id, assigned_to=assigned_to
        )

    @mcp.tool()
    async def list_holidays_in_period(
        assigned_to: str, start: str, end: str, workspace_id: str | None = None
    ) -> Any:
        """List holidays overlapping a date range for a user."""
        return await list_holidays_in_period_fn(
            client, assigned_to=assigned_to, start=start, end=end, workspace_id=workspace_id
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_holiday(
        name: str,
        start_date: str,
        end_date: str,
        workspace_id: str | None = None,
        color: str | None = None,
        occurs_annually: bool | None = None,
        everyone_including_new: bool | None = None,
    ) -> Any:
        """Create a holiday on the workspace."""
        return await create_holiday_fn(
            client,
            name=name,
            start_date=start_date,
            end_date=end_date,
            workspace_id=workspace_id,
            color=color,
            occurs_annually=occurs_annually,
            everyone_including_new=everyone_including_new,
        )

    @mcp.tool()
    async def update_holiday(
        holiday_id: str,
        name: str,
        start_date: str,
        end_date: str,
        occurs_annually: bool,
        workspace_id: str | None = None,
        color: str | None = None,
        everyone_including_new: bool | None = None,
    ) -> Any:
        """Update a holiday (full replace; occurs_annually required)."""
        return await update_holiday_fn(
            client,
            holiday_id=holiday_id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            occurs_annually=occurs_annually,
            workspace_id=workspace_id,
            color=color,
            everyone_including_new=everyone_including_new,
        )

    @mcp.tool()
    async def delete_holiday(holiday_id: str, workspace_id: str | None = None) -> Any:
        """Delete a holiday. IRREVERSIBLE — the holiday is permanently removed."""
        return await delete_holiday_fn(
            client, holiday_id=holiday_id, workspace_id=workspace_id
        )
```

- [ ] **Step 5: Update the `_fn` aliases block** at the bottom of the file

```python
list_holidays_fn = list_holidays
list_holidays_in_period_fn = list_holidays_in_period
create_holiday_fn = create_holiday
update_holiday_fn = update_holiday
delete_holiday_fn = delete_holiday
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_holidays.py -q`
Expected: PASS (6 passed).

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/holidays.py tests/test_holidays.py
git commit -m "feat: holidays writes (create/update/delete)"
```

---

## Task 9: Register both domains in the server

**Files:**
- Modify: `src/clockify_mcp/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Extend the server tests** — add read-tool names to `test_build_server_registers_discovery_tools` and write-tool names to `test_writes_registered_when_enabled`.

In `tests/test_server.py`, inside `test_build_server_registers_discovery_tools`, add these entries to the asserted set (before the closing `} <= names`):

```python
        "list_time_off_policies",
        "get_time_off_policy",
        "list_time_off_balances_by_policy",
        "list_time_off_balances_by_user",
        "list_time_off_requests",
        "list_holidays",
        "list_holidays_in_period",
```

In `test_writes_registered_when_enabled`, add to the asserted set:

```python
        "create_time_off_policy", "create_time_off_request",
        "approve_time_off_request", "reject_time_off_request", "withdraw_time_off_request",
        "create_holiday", "update_holiday", "delete_holiday",
```

- [ ] **Step 2: Run the server tests to verify they fail**

Run: `uv run pytest tests/test_server.py -q`
Expected: FAIL — the new names are not registered yet.

- [ ] **Step 3: Register the domains in `server.py`**

Update the domains import block to include the two modules (keep alphabetical-ish ordering consistent with the file):

```python
from .domains import (
    clients,
    groups,
    holidays,
    projects,
    reports,
    tags,
    tasks,
    time_entries,
    time_off,
    users,
    workspaces,
)
```

Add the two `register` calls in `build_server` (after `reports.register(mcp, client)`):

```python
    reports.register(mcp, client)
    time_off.register(mcp, client)
    holidays.register(mcp, client)
    return mcp
```

- [ ] **Step 4: Run the server tests to verify they pass**

Run: `uv run pytest tests/test_server.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all unit tests pass (live smoke still skipped), ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/clockify_mcp/server.py tests/test_server.py
git commit -m "feat: register time_off and holidays domains"
```

---

## Task 10: Live smoke round-trips (gated)

**Files:**
- Modify: `tests/test_live_smoke.py`

These hit the real workspace and are skipped unless `CLOCKIFY_LIVE_TEST` is set. Time off and holidays are **paid features**; if the workspace plan lacks them the API returns 402/403/404 — the tests must `pytest.skip` on that rather than fail.

- [ ] **Step 1: Add the import** — extend the existing domains import line in `tests/test_live_smoke.py`:

```python
from clockify_mcp.domains import (
    clients,
    holidays,
    projects,
    tags,
    tasks,
    time_entries,
    time_off,
    workspaces,
)
```

Also import the API error type near the top (after the existing imports):

```python
from clockify_mcp.client import ClockifyAPIError
```

- [ ] **Step 2: Add a helper that skips when a feature is unavailable** (place after the `PREFIX` constant)

```python
def _skip_if_feature_unavailable(exc: ClockifyAPIError) -> None:
    """Time off / holidays are paid features; skip the round-trip when absent."""
    if exc.status_code in (402, 403, 404):
        pytest.skip(f"feature unavailable on this plan (HTTP {exc.status_code})")
    raise exc
```

- [ ] **Step 3: Add the holiday round-trip test** (append to the file)

```python
async def test_live_holiday_roundtrip(live):
    client, ws, _ = live
    try:
        created = await holidays.create_holiday(
            client, workspace_id=ws, name=PREFIX + "holiday",
            start_date="2020-01-01", end_date="2020-01-01",
        )
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
    hid = created["id"]
    try:
        updated = await holidays.update_holiday(
            client, workspace_id=ws, holiday_id=hid, name=PREFIX + "holiday",
            start_date="2020-01-01", end_date="2020-01-02", occurs_annually=False,
        )
        assert updated["id"] == hid
    finally:
        await holidays.delete_holiday(client, workspace_id=ws, holiday_id=hid)
```

- [ ] **Step 4: Add the time-off policy round-trip test** (append)

```python
async def test_live_time_off_policy_roundtrip(live):
    client, ws, _ = live
    try:
        created = await time_off.create_time_off_policy(
            client, workspace_id=ws, name=PREFIX + "policy",
        )
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
    pid = created["id"]
    try:
        fetched = await time_off.get_time_off_policy(client, workspace_id=ws, policy_id=pid)
        assert fetched["id"] == pid
        listed = await time_off.list_time_off_policies(client, workspace_id=ws)
        assert any(p.get("id") == pid for p in listed)
    finally:
        await time_off.list_time_off_requests(client, workspace_id=ws)  # smoke the POST read
        await _delete_policy(client, ws, pid)


async def _delete_policy(client, ws, policy_id):
    # Policies may need to be archived before deletion on some plans; try direct
    # delete and fall back to PATCH-archive then delete.
    try:
        await client.delete(f"workspaces/{ws}/time-off/policies/{policy_id}")
    except ClockifyAPIError:
        await client.patch(
            f"workspaces/{ws}/time-off/policies/{policy_id}", json={"status": "ARCHIVED"}
        )
        await client.delete(f"workspaces/{ws}/time-off/policies/{policy_id}")
```

- [ ] **Step 5: Run the live smoke locally (manual, optional)**

Run:
```bash
CLOCKIFY_LIVE_TEST=1 CLOCKIFY_API_KEY=... CLOCKIFY_ENABLE_WRITES=true \
    CLOCKIFY_LIVE_WORKSPACE_NAME="Alan Fuentes's workspace" \
    uv run pytest tests/test_live_smoke.py -q -s
```
Expected: existing 4 pass; the 2 new ones either pass (round-trip OK) or skip ("feature unavailable…"). If they fail with a different error, capture it — the body type / archive-before-delete behavior may differ and the cleanup helper may need adjusting (mirror the Phase 4 clients/projects archive-before-delete lesson).

- [ ] **Step 6: Confirm the default (non-live) run still passes**

Run: `uv run pytest -q`
Expected: all unit tests pass; live smoke (now 6 tests) all skipped.

- [ ] **Step 7: Commit**

```bash
git add tests/test_live_smoke.py
git commit -m "test: gated live smoke for holidays and time-off policy"
```

---

## Task 11: Docs

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `CLAUDE.md`** — bump the phase/tool counts and add the two domains.

In the Project Overview line, update to reflect Phase 0–5 with the new totals (27 read + 25 write across 11 domains) and add time_off/holidays to the "Writes register only when CLOCKIFY_ENABLE_WRITES=true" sentence. In the Architecture module list, add:

```
- `domains/time_off.py` — `list_time_off_policies`, `get_time_off_policy`, `list_time_off_balances_by_policy`, `list_time_off_balances_by_user`, `list_time_off_requests` (+ create_policy/create/approve/reject/withdraw_request when writes enabled)
- `domains/holidays.py` — `list_holidays`, `list_holidays_in_period` (+ create/update/delete when writes enabled)
```

Update the test-count expectation note (`uv run pytest -q`) to the new passing count (run the suite to get the exact number and use it).

- [ ] **Step 2: Update `README.md`** — add `time_off` and `holidays` rows to the tool/domain table, mirroring the verified surface, and note both are paid Clockify features. Keep the README accurate to implemented state only.

- [ ] **Step 3: Run the full suite + lint one final time**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass, ruff clean.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document Phase 5 time_off + holidays tools"
```

---

## Self-Review

**Spec coverage (spec §7 Phase 5 rows):**
- time_off read — `list_policies` (Task 1) ✓, `get_policy` (Task 1) ✓, `list_balances` → split into by-policy + by-user (Task 2) ✓, `list_time_off_requests` (Task 3) ✓.
- time_off write — `create_policy` (Task 5) ✓, `create/approve/reject/withdraw_request` (Task 6) ✓.
- holidays read — `list_holidays`, `list_holidays_in_period` (Task 7) ✓.
- holidays write — `create/update/delete_holiday` (Task 8) ✓.
- Registration (Task 9), live smoke (Task 10), docs (Task 11) ✓.

**Deviations from spec, justified by the verified API:**
- `list_balances` became two tools (`..._by_policy`, `..._by_user`) because Clockify exposes two distinct balance endpoints. Better coverage, same surface.
- "withdraw_request" is implemented as a DELETE (`withdraw_time_off_request`) — the status enum has no WITHDRAWN value; cancellation is deletion per the spec.

**Type/name consistency:** Each domain follows the established `*_fn = function` alias + `register`/`_register_writes` pattern (verified against `tags.py`). Tool names in Task 9's server-test asserts exactly match the `@mcp.tool()` function names defined in Tasks 4/6/8. Param keys: GET lists hyphenated (`page-size`, `sort-order`, `assigned-to`), write/filter bodies camelCase (`pageSize`, `userGroups`, `datePeriod`, `startDate`, `occursAnnually`, `timeOffPeriod`, `isHalfDay`, `halfDayPeriod`) — matches the verified spec.

**Placeholder scan:** No TBD/TODO/"handle edge cases" placeholders. Every code step shows complete code; every command step shows the exact command and expected result.
