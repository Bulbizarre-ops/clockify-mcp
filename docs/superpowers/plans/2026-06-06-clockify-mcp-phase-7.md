# Clockify MCP Phase 7 — Custom Fields + Scheduling + Invoices + Webhooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the final four domains — `custom_fields`, `scheduling`, `invoices`, `webhooks` — (read + opt-in write) to the Clockify MCP server, completing the design's ~17-domain surface.

**Architecture:** Four new domain modules following the established per-domain pattern (`register`/`_register_writes` gated by `client.writes_enabled`, `*_fn` aliases as the final block, `drop_none` JSON bodies, `resolve_workspace_id`, hyphenated GET params / camelCase bodies). All endpoints are on the regular `https://api.clockify.me/api/v1` host and are plain JSON — no multipart. Two reads (`scheduling` project/user totals) and one (`webhooks` logs) are POSTs whose filters travel in the body (like `list_time_off_requests`). One small client change is needed: `client.post()` gains an optional `params` argument so the webhook-logs endpoint can send `page`/`size` query params alongside its JSON filter body.

**Tech Stack:** Python 3.12+, FastMCP (`mcp`), httpx, respx (tests), pytest-asyncio, uv, ruff.

**Verified API surface (official Clockify OpenAPI 3.0.1; base `https://api.clockify.me/api/v1`):**

| Operation | Method | Path |
|---|---|---|
| List workspace custom fields | GET | `workspaces/{ws}/custom-fields` |
| List project custom fields | GET | `workspaces/{ws}/projects/{projectId}/custom-fields` |
| Create workspace custom field | POST | `workspaces/{ws}/custom-fields` |
| Update workspace custom field | PUT | `workspaces/{ws}/custom-fields/{id}` |
| Delete workspace custom field | DELETE | `workspaces/{ws}/custom-fields/{id}` |
| Set custom field on project | PATCH | `workspaces/{ws}/projects/{projectId}/custom-fields/{id}` |
| Remove custom field from project | DELETE | `workspaces/{ws}/projects/{projectId}/custom-fields/{id}` |
| List scheduled assignments | GET | `workspaces/{ws}/scheduling/assignments/all` |
| Project scheduling totals | POST | `workspaces/{ws}/scheduling/assignments/projects/totals` |
| User scheduling totals | POST | `workspaces/{ws}/scheduling/assignments/user-filter/totals` |
| Create assignment | POST | `workspaces/{ws}/scheduling/assignments/recurring` |
| Update assignment | PATCH | `workspaces/{ws}/scheduling/assignments/recurring/{id}` |
| Delete assignment | DELETE | `workspaces/{ws}/scheduling/assignments/recurring/{id}` |
| Publish assignments | PUT | `workspaces/{ws}/scheduling/assignments/publish` |
| Copy assignment | POST | `workspaces/{ws}/scheduling/assignments/{id}/copy` |
| List invoices | GET | `workspaces/{ws}/invoices` |
| Get invoice | GET | `workspaces/{ws}/invoices/{id}` |
| Get invoice payments | GET | `workspaces/{ws}/invoices/{id}/payments` |
| Create invoice | POST | `workspaces/{ws}/invoices` |
| Update invoice | PUT | `workspaces/{ws}/invoices/{id}` |
| Change invoice status | PATCH | `workspaces/{ws}/invoices/{id}/status` |
| Duplicate invoice | POST | `workspaces/{ws}/invoices/{id}/duplicate` |
| Delete invoice | DELETE | `workspaces/{ws}/invoices/{id}` |
| Add invoice item | POST | `workspaces/{ws}/invoices/{id}/items` |
| Import invoice items | POST | `workspaces/{ws}/invoices/{id}/items/import` |
| Add invoice payment | POST | `workspaces/{ws}/invoices/{id}/payments` |
| Delete invoice payment | DELETE | `workspaces/{ws}/invoices/{id}/payments/{paymentId}` |
| List webhooks | GET | `workspaces/{ws}/webhooks` |
| Get webhook | GET | `workspaces/{ws}/webhooks/{id}` |
| Get webhook logs | POST | `workspaces/{ws}/webhooks/{id}/logs` |
| Create webhook | POST | `workspaces/{ws}/webhooks` |
| Update webhook | PUT | `workspaces/{ws}/webhooks/{id}` |
| Delete webhook | DELETE | `workspaces/{ws}/webhooks/{id}` |
| Generate webhook token | PATCH | `workspaces/{ws}/webhooks/{id}/token` |

**Verified facts that shape the code:**
- Param spelling: GET keys hyphenated (`page-size`, `sort-column`, `sort-order`, `entity-type`); JSON bodies camelCase. POST-totals endpoints carry pagination in the body as `page`/`pageSize`. The webhook-logs POST uses query params `page` and **`size`** (NOT `page-size`).
- Custom field `type` enum: `TXT | NUMBER | DROPDOWN_SINGLE | DROPDOWN_MULTIPLE | CHECKBOX | LINK`. `entityType`: `TIMEENTRY | USER`. `status`: `INACTIVE | VISIBLE | INVISIBLE`. Create requires `name`+`type`; update (PUT) also requires `name`+`type` (full replace) and adds optional `required` (bool). Project apply = PATCH with `{defaultValue, status}`.
- Scheduling create lives at `.../assignments/recurring`; recurrence is the optional nested `recurringAssignment` object `{repeat, weeks}` (weeks required inside). Update/delete take `seriesUpdateOption` enum `THIS_ONE | THIS_AND_FOLLOWING | ALL`. `statusFilter` enum `PUBLISHED | UNPUBLISHED | ALL`. Required create fields: `userId, projectId, start, end, hoursPerDay`. Publish requires `start, end`. Copy requires `userId`.
- Invoice create requires `clientId, currency, issuedDate, dueDate, number` (no items in the create body — items are added separately). Update (PUT, full replace) requires `currency, number, issuedDate, dueDate, discountPercent, taxPercent, tax2Percent`. **Omit `taxType` and `visibleZeroFields`** from update — the spec's serialization for both is self-contradictory/unverified; they are optional, so we don't send them. Status change is a separate PATCH `.../status` `{invoiceStatus}` (enum `UNSENT|SENT|PAID|PARTIALLY_PAID|VOID|OVERDUE`). Duplicate is POST with no body.
- Invoice item add requires `applyTaxes` (`TAX1|TAX2|TAX1TAX2|NONE`), `description`, `itemType` (free-text string, NOT an enum), `quantity` (int), `unitPrice` (int, minor units). Import requires `from`, `to`, `importExpenses`, `projectFilter`, `timeEntryGroupType` (`SINGLE_ITEM|GROUPED|DETAILED`); `projectFilter` is the standard `{contains (CONTAINS|DOES_NOT_CONTAIN|CONTAINS_ONLY), ids[], status (ACTIVE|ARCHIVED|ALL)}` filter. Payment fields (`amount` int, `note`, `paymentDate`) are all optional.
- Webhook create/update require `url`, `triggerSource` (array of IDs), `triggerSourceType` (`PROJECT_ID|USER_ID|TAG_ID|TASK_ID|WORKSPACE_ID|ASSIGNMENT_ID|EXPENSE_ID`), `webhookEvent` (single string enum, ~51 values e.g. `NEW_TIME_ENTRY`, `NEW_INVOICE`); `name` optional. Token regen is PATCH `.../token` with no body. List filter `type` enum `USER_CREATED|SYSTEM|ADDON`. Logs filter body `{from, to, sortByNewest, status (ALL|SUCCEEDED|FAILED)}`.
- All four domains are paid/enterprise Clockify features — gated live smoke reuses Phase 5's `_skip_if_feature_unavailable` (402/403/404).

**Out of scope (verified but excluded):** invoice settings/export, `mark time entries invoiced`, addon webhooks, the deprecated GET project-totals, the user custom-field value upsert (belongs to the users domain), and the scheduling `series` period-edit PUT (covered functionally by update_assignment's `seriesUpdateOption`).

---

## File Structure

- Modify: `src/clockify_mcp/client.py` — `post()` gains an optional `params` argument (for webhook logs).
- Test: `tests/test_client.py` — cover `post` with params.
- Create: `src/clockify_mcp/domains/custom_fields.py`, `scheduling.py`, `invoices.py`, `webhooks.py`.
- Create: `tests/test_custom_fields.py`, `tests/test_scheduling.py`, `tests/test_invoices.py`, `tests/test_webhooks.py`.
- Modify: `src/clockify_mcp/server.py` — register the four domains.
- Modify: `tests/test_server.py` — assert new read + write tool names.
- Modify: `tests/test_live_smoke.py` — gated custom-field + webhook round-trips.
- Modify: `README.md`, `CLAUDE.md` — document the new tools.

**New tool inventory (34 tools):**
- `custom_fields` (2 read, 5 write): `list_workspace_custom_fields`, `list_project_custom_fields` · `create_workspace_custom_field`, `update_workspace_custom_field`, `delete_workspace_custom_field`, `set_project_custom_field`, `remove_project_custom_field`
- `scheduling` (3 read, 5 write): `list_scheduled_assignments`, `get_project_scheduling_totals`, `get_user_scheduling_totals` · `create_assignment`, `update_assignment`, `delete_assignment`, `publish_assignments`, `copy_assignment`
- `invoices` (3 read, 9 write): `list_invoices`, `get_invoice`, `get_invoice_payments` · `create_invoice`, `update_invoice`, `change_invoice_status`, `duplicate_invoice`, `delete_invoice`, `add_invoice_item`, `import_invoice_items`, `add_invoice_payment`, `delete_invoice_payment`
- `webhooks` (3 read, 4 write): `list_webhooks`, `get_webhook`, `get_webhook_logs` · `create_webhook`, `update_webhook`, `delete_webhook`, `generate_webhook_token`

After Phase 7: 43 read + 59 write = 102 tools across 17 domains. **This completes the v1 domain surface.**

**Pattern reference (read these before implementing):** `src/clockify_mcp/domains/tags.py` (canonical small domain), `expenses.py` (largest, nested bodies + register split), `time_off.py` (POST-body read). Every new module mirrors them: standalone `async def fn(client, *, ...)`, a `register(mcp, client)` that defines `@mcp.tool()` thunks delegating to `*_fn` aliases, `_register_writes(mcp, client)` called only under `if client.writes_enabled`, and the `name_fn = name` alias block as the FINAL block of the file. Tests use respx + the `config`/`config_writes` fixtures, asserting exact paths, hyphenated params, and JSON bodies.

---

## Task 1: custom_fields — reads

**Files:** Create `src/clockify_mcp/domains/custom_fields.py`, `tests/test_custom_fields.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_custom_fields.py
import json
import httpx
import respx
from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import custom_fields


@respx.mock
async def test_list_workspace_custom_fields_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/custom-fields").mock(
        return_value=httpx.Response(200, json=[{"id": "cf1"}])
    )
    client = ClockifyClient(config)
    result = await custom_fields.list_workspace_custom_fields(
        client, name="loc", status="VISIBLE", entity_type="TIMEENTRY"
    )
    assert result == [{"id": "cf1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "loc"
    assert sent["status"] == "VISIBLE"
    assert sent["entity-type"] == "TIMEENTRY"
    await client.aclose()


@respx.mock
async def test_list_project_custom_fields(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/custom-fields"
    ).mock(return_value=httpx.Response(200, json=[{"id": "cf1"}]))
    client = ClockifyClient(config)
    await custom_fields.list_project_custom_fields(client, project_id="p1", status="VISIBLE")
    assert dict(route.calls.last.request.url.params)["status"] == "VISIBLE"
    await client.aclose()
```

- [ ] **Step 2: Run → fail** (`uv run pytest tests/test_custom_fields.py -q`): `ImportError`.

- [ ] **Step 3: Write the module reads**

```python
# src/clockify_mcp/domains/custom_fields.py
"""Custom fields domain (read + write).

Workspace-level custom fields under ``workspaces/{ws}/custom-fields`` and the
per-project apply/override under ``.../projects/{projectId}/custom-fields``.
Custom fields are a paid Clockify feature; the API errors on plans without it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_workspace_custom_fields(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    status: str | None = None,
    entity_type: str | None = None,
) -> Any:
    """List workspace custom fields. status is INACTIVE/VISIBLE/INVISIBLE;
    entity_type filters by the entity the field attaches to (e.g. TIMEENTRY)."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"name": name, "status": status, "entity-type": entity_type}
    return await client.get(f"workspaces/{ws}/custom-fields", params=params)


async def list_project_custom_fields(
    client: ClockifyClient,
    *,
    project_id: str,
    workspace_id: str | None = None,
    status: str | None = None,
    entity_type: str | None = None,
) -> Any:
    """List a project's custom fields (status INACTIVE/VISIBLE/INVISIBLE)."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"status": status, "entity-type": entity_type}
    return await client.get(
        f"workspaces/{ws}/projects/{project_id}/custom-fields", params=params
    )


list_workspace_custom_fields_fn = list_workspace_custom_fields
list_project_custom_fields_fn = list_project_custom_fields
```

- [ ] **Step 4: Run → pass** (2 passed).

- [ ] **Step 5: Commit** `feat: custom_fields read (list workspace + project fields)`

---

## Task 2: custom_fields — writes + registration

**Files:** Modify `src/clockify_mcp/domains/custom_fields.py`, `tests/test_custom_fields.py`

- [ ] **Step 1: Write failing tests** (append)

```python
@respx.mock
async def test_create_workspace_custom_field_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/custom-fields").mock(
        return_value=httpx.Response(201, json={"id": "cf1"})
    )
    client = ClockifyClient(config_writes)
    await custom_fields.create_workspace_custom_field(
        client, name="location", type="DROPDOWN_MULTIPLE", entity_type="TIMEENTRY",
        allowed_values=["NY", "London"], status="VISIBLE",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["name"] == "location"
    assert body["type"] == "DROPDOWN_MULTIPLE"
    assert body["entityType"] == "TIMEENTRY"
    assert body["allowedValues"] == ["NY", "London"]
    assert body["status"] == "VISIBLE"
    await client.aclose()


@respx.mock
async def test_update_workspace_custom_field_builds_body(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/custom-fields/cf1"
    ).mock(return_value=httpx.Response(200, json={"id": "cf1"}))
    client = ClockifyClient(config_writes)
    await custom_fields.update_workspace_custom_field(
        client, custom_field_id="cf1", name="loc", type="TXT", required=True
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "loc", "type": "TXT", "required": True}
    await client.aclose()


@respx.mock
async def test_delete_workspace_custom_field(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/custom-fields/cf1"
    ).mock(return_value=httpx.Response(200, json={"id": "cf1"}))
    client = ClockifyClient(config_writes)
    await custom_fields.delete_workspace_custom_field(client, custom_field_id="cf1")
    assert route.called
    await client.aclose()


@respx.mock
async def test_set_project_custom_field_patches(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/custom-fields/cf1"
    ).mock(return_value=httpx.Response(200, json={"id": "cf1"}))
    client = ClockifyClient(config_writes)
    await custom_fields.set_project_custom_field(
        client, project_id="p1", custom_field_id="cf1", default_value="NY", status="VISIBLE"
    )
    assert json.loads(route.calls.last.request.content) == {
        "defaultValue": "NY", "status": "VISIBLE"
    }
    await client.aclose()


@respx.mock
async def test_remove_project_custom_field(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/projects/p1/custom-fields/cf1"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config_writes)
    await custom_fields.remove_project_custom_field(
        client, project_id="p1", custom_field_id="cf1"
    )
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run → fail** (`AttributeError`).

- [ ] **Step 3: Add write functions** (after the reads, before `_fn` aliases)

```python
async def create_workspace_custom_field(
    client: ClockifyClient,
    *,
    name: str,
    type: str,
    workspace_id: str | None = None,
    entity_type: str | None = None,
    allowed_values: list[str] | None = None,
    description: str | None = None,
    placeholder: str | None = None,
    status: str | None = None,
    only_admin_can_edit: bool | None = None,
    workspace_default_value: Any = None,
) -> Any:
    """Create a workspace custom field.

    type is TXT, NUMBER, DROPDOWN_SINGLE, DROPDOWN_MULTIPLE, CHECKBOX, or LINK.
    entity_type is TIMEENTRY or USER. allowed_values lists the options for
    dropdown types. status is INACTIVE/VISIBLE/INVISIBLE.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "type": type,
            "entityType": entity_type,
            "allowedValues": allowed_values,
            "description": description,
            "placeholder": placeholder,
            "status": status,
            "onlyAdminCanEdit": only_admin_can_edit,
            "workspaceDefaultValue": workspace_default_value,
        }
    )
    return await client.post(f"workspaces/{ws}/custom-fields", json=body)


async def update_workspace_custom_field(
    client: ClockifyClient,
    *,
    custom_field_id: str,
    name: str,
    type: str,
    workspace_id: str | None = None,
    allowed_values: list[str] | None = None,
    description: str | None = None,
    placeholder: str | None = None,
    status: str | None = None,
    only_admin_can_edit: bool | None = None,
    required: bool | None = None,
    workspace_default_value: Any = None,
) -> Any:
    """Update a workspace custom field (full replace; name and type required)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "type": type,
            "allowedValues": allowed_values,
            "description": description,
            "placeholder": placeholder,
            "status": status,
            "onlyAdminCanEdit": only_admin_can_edit,
            "required": required,
            "workspaceDefaultValue": workspace_default_value,
        }
    )
    return await client.put(f"workspaces/{ws}/custom-fields/{custom_field_id}", json=body)


async def delete_workspace_custom_field(
    client: ClockifyClient, *, custom_field_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a workspace custom field. IRREVERSIBLE — permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/custom-fields/{custom_field_id}")


async def set_project_custom_field(
    client: ClockifyClient,
    *,
    project_id: str,
    custom_field_id: str,
    workspace_id: str | None = None,
    default_value: Any = None,
    status: str | None = None,
) -> Any:
    """Apply/override a custom field on a project (per-project default + status)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"defaultValue": default_value, "status": status})
    return await client.patch(
        f"workspaces/{ws}/projects/{project_id}/custom-fields/{custom_field_id}", json=body
    )


async def remove_project_custom_field(
    client: ClockifyClient,
    *,
    project_id: str,
    custom_field_id: str,
    workspace_id: str | None = None,
) -> Any:
    """Remove a custom field from a project. IRREVERSIBLE for the project override."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(
        f"workspaces/{ws}/projects/{project_id}/custom-fields/{custom_field_id}"
    )
```

- [ ] **Step 4: Add `register` + `_register_writes`** mirroring `tags.py`/`expenses.py`: a `register(mcp, client)` that registers the 2 read tools (`list_workspace_custom_fields`, `list_project_custom_fields`) as `@mcp.tool()` thunks delegating to the `*_fn` aliases, then `if client.writes_enabled: _register_writes(mcp, client)`. `_register_writes` registers the 5 write tools (`create_workspace_custom_field`, `update_workspace_custom_field`, `delete_workspace_custom_field`, `set_project_custom_field`, `remove_project_custom_field`) with the SAME signatures as the standalone functions above (minus the `client` arg). Each thunk's docstring is the one-line summary from its function. Keep `workspace_default_value`/`default_value` typed `Any = None`.

- [ ] **Step 5: Add the `*_fn` alias block** as the final block of the file (all 7: the 2 reads from Task 1 plus the 5 writes).

- [ ] **Step 6: Run → pass** (7 passed). Then `uv run ruff check src/ tests/` clean.

- [ ] **Step 7: Commit** `feat: custom_fields writes (create/update/delete ws + set/remove project)`

---

## Task 3: scheduling — reads

**Files:** Create `src/clockify_mcp/domains/scheduling.py`, `tests/test_scheduling.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scheduling.py
import json
import httpx
import respx
from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import scheduling


@respx.mock
async def test_list_scheduled_assignments_passes_params(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/all"
    ).mock(return_value=httpx.Response(200, json=[{"id": "a1"}]))
    client = ClockifyClient(config)
    await scheduling.list_scheduled_assignments(
        client, start="2026-06-01T00:00:00Z", end="2026-06-30T00:00:00Z",
        name="x", sort_column="USER", sort_order="ASCENDING", page=1, page_size=20,
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["start"] == "2026-06-01T00:00:00Z"
    assert sent["end"] == "2026-06-30T00:00:00Z"
    assert sent["sort-column"] == "USER"
    assert sent["page-size"] == "20"
    await client.aclose()


@respx.mock
async def test_get_project_scheduling_totals_posts_body(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/projects/totals"
    ).mock(return_value=httpx.Response(200, json=[]))
    client = ClockifyClient(config)
    await scheduling.get_project_scheduling_totals(
        client, start="2026-06-01T00:00:00Z", end="2026-06-30T00:00:00Z",
        search="web", status_filter="ALL", page=1, page_size=50,
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "start": "2026-06-01T00:00:00Z", "end": "2026-06-30T00:00:00Z",
        "search": "web", "statusFilter": "ALL", "page": 1, "pageSize": 50,
    }
    await client.aclose()


@respx.mock
async def test_get_user_scheduling_totals_posts_body(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/user-filter/totals"
    ).mock(return_value=httpx.Response(200, json=[]))
    client = ClockifyClient(config)
    await scheduling.get_user_scheduling_totals(
        client, start="2026-06-01T00:00:00Z", end="2026-06-30T00:00:00Z"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"start": "2026-06-01T00:00:00Z", "end": "2026-06-30T00:00:00Z"}
    await client.aclose()
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Write the module reads**

```python
# src/clockify_mcp/domains/scheduling.py
"""Scheduling domain: assignments + capacity totals (read + write).

Endpoints under ``workspaces/{ws}/scheduling/assignments/...`` on the regular
host. The totals reads are POSTs (filters travel in the body). Create lives at
``.../recurring`` and makes one-off or recurring assignments via the optional
recurringAssignment object. Scheduling is a paid Clockify feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_scheduled_assignments(
    client: ClockifyClient,
    *,
    start: str,
    end: str,
    workspace_id: str | None = None,
    name: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List scheduled assignments in a date range (start/end ISO-8601, required).

    sort_column is PROJECT/USER/ID; sort_order is ASCENDING/DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "start": start,
        "end": end,
        "name": name,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/scheduling/assignments/all", params=params)


async def get_project_scheduling_totals(
    client: ClockifyClient,
    *,
    start: str,
    end: str,
    workspace_id: str | None = None,
    search: str | None = None,
    status_filter: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """Get scheduled-assignment totals per project (POST filter body).

    start/end required. status_filter is PUBLISHED/UNPUBLISHED/ALL.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "search": search,
            "statusFilter": status_filter,
            "page": page,
            "pageSize": page_size,
        }
    )
    return await client.post(
        f"workspaces/{ws}/scheduling/assignments/projects/totals", json=body
    )


async def get_user_scheduling_totals(
    client: ClockifyClient,
    *,
    start: str,
    end: str,
    workspace_id: str | None = None,
    search: str | None = None,
    status_filter: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """Get users' scheduling capacity totals (POST filter body).

    start/end required. status_filter is PUBLISHED/UNPUBLISHED/ALL.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "search": search,
            "statusFilter": status_filter,
            "page": page,
            "pageSize": page_size,
        }
    )
    return await client.post(
        f"workspaces/{ws}/scheduling/assignments/user-filter/totals", json=body
    )


list_scheduled_assignments_fn = list_scheduled_assignments
get_project_scheduling_totals_fn = get_project_scheduling_totals
get_user_scheduling_totals_fn = get_user_scheduling_totals
```

- [ ] **Step 4: Run → pass** (3 passed).

- [ ] **Step 5: Commit** `feat: scheduling read (list assignments + project/user totals)`

---

## Task 4: scheduling — writes + registration

**Files:** Modify `src/clockify_mcp/domains/scheduling.py`, `tests/test_scheduling.py`

- [ ] **Step 1: Write failing tests** (append)

```python
@respx.mock
async def test_create_assignment_one_off(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/recurring"
    ).mock(return_value=httpx.Response(201, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await scheduling.create_assignment(
        client, user_id="u1", project_id="p1", start="2026-06-01T00:00:00Z",
        end="2026-06-05T00:00:00Z", hours_per_day=7.5, billable=True,
    )
    body = json.loads(route.calls.last.request.content)
    assert body["userId"] == "u1"
    assert body["projectId"] == "p1"
    assert body["hoursPerDay"] == 7.5
    assert body["billable"] is True
    assert "recurringAssignment" not in body
    await client.aclose()


@respx.mock
async def test_create_assignment_recurring(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/recurring"
    ).mock(return_value=httpx.Response(201, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await scheduling.create_assignment(
        client, user_id="u1", project_id="p1", start="2026-06-01T00:00:00Z",
        end="2026-06-05T00:00:00Z", hours_per_day=8, repeat=True, weeks=5,
    )
    body = json.loads(route.calls.last.request.content)
    assert body["recurringAssignment"] == {"repeat": True, "weeks": 5}
    await client.aclose()


@respx.mock
async def test_update_assignment(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/recurring/a1"
    ).mock(return_value=httpx.Response(200, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await scheduling.update_assignment(
        client, assignment_id="a1", start="2026-06-01T00:00:00Z",
        end="2026-06-05T00:00:00Z", hours_per_day=6, series_update_option="ALL",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["hoursPerDay"] == 6
    assert body["seriesUpdateOption"] == "ALL"
    await client.aclose()


@respx.mock
async def test_delete_assignment_passes_series_option(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/recurring/a1"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config_writes)
    await scheduling.delete_assignment(
        client, assignment_id="a1", series_update_option="THIS_ONE"
    )
    assert dict(route.calls.last.request.url.params)["seriesUpdateOption"] == "THIS_ONE"
    await client.aclose()


@respx.mock
async def test_publish_assignments(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/publish"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config_writes)
    await scheduling.publish_assignments(
        client, start="2026-06-01T00:00:00Z", end="2026-06-30T00:00:00Z", notify_users=True,
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"start": "2026-06-01T00:00:00Z", "end": "2026-06-30T00:00:00Z", "notifyUsers": True}
    await client.aclose()


@respx.mock
async def test_copy_assignment(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/scheduling/assignments/a1/copy"
    ).mock(return_value=httpx.Response(201, json={"id": "a2"}))
    client = ClockifyClient(config_writes)
    await scheduling.copy_assignment(client, assignment_id="a1", user_id="u2")
    assert json.loads(route.calls.last.request.content) == {"userId": "u2"}
    await client.aclose()
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Add write functions**

```python
async def create_assignment(
    client: ClockifyClient,
    *,
    user_id: str,
    project_id: str,
    start: str,
    end: str,
    hours_per_day: float,
    workspace_id: str | None = None,
    task_id: str | None = None,
    note: str | None = None,
    billable: bool | None = None,
    include_non_working_days: bool | None = None,
    start_time: str | None = None,
    repeat: bool | None = None,
    weeks: int | None = None,
) -> Any:
    """Create a scheduled assignment. Pass weeks (and repeat) to make it recurring.

    start/end are ISO-8601; hours_per_day is the daily hours; start_time is hh:mm:ss.
    """
    ws = resolve_workspace_id(client, workspace_id)
    recurring = drop_none({"repeat": repeat, "weeks": weeks}) if weeks is not None else None
    body = drop_none(
        {
            "userId": user_id,
            "projectId": project_id,
            "start": start,
            "end": end,
            "hoursPerDay": hours_per_day,
            "taskId": task_id,
            "note": note,
            "billable": billable,
            "includeNonWorkingDays": include_non_working_days,
            "startTime": start_time,
            "recurringAssignment": recurring,
        }
    )
    return await client.post(f"workspaces/{ws}/scheduling/assignments/recurring", json=body)


async def update_assignment(
    client: ClockifyClient,
    *,
    assignment_id: str,
    start: str,
    end: str,
    workspace_id: str | None = None,
    hours_per_day: float | None = None,
    task_id: str | None = None,
    note: str | None = None,
    billable: bool | None = None,
    include_non_working_days: bool | None = None,
    start_time: str | None = None,
    series_update_option: str | None = None,
) -> Any:
    """Update an assignment (start/end required).

    series_update_option is THIS_ONE/THIS_AND_FOLLOWING/ALL — controls how the
    change propagates across a recurring series.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "hoursPerDay": hours_per_day,
            "taskId": task_id,
            "note": note,
            "billable": billable,
            "includeNonWorkingDays": include_non_working_days,
            "startTime": start_time,
            "seriesUpdateOption": series_update_option,
        }
    )
    return await client.patch(
        f"workspaces/{ws}/scheduling/assignments/recurring/{assignment_id}", json=body
    )


async def delete_assignment(
    client: ClockifyClient,
    *,
    assignment_id: str,
    workspace_id: str | None = None,
    series_update_option: str | None = None,
) -> Any:
    """Delete an assignment. IRREVERSIBLE. series_update_option is
    THIS_ONE/THIS_AND_FOLLOWING/ALL for recurring series."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"seriesUpdateOption": series_update_option}
    return await client.delete(
        f"workspaces/{ws}/scheduling/assignments/recurring/{assignment_id}", params=params
    )


async def publish_assignments(
    client: ClockifyClient,
    *,
    start: str,
    end: str,
    workspace_id: str | None = None,
    notify_users: bool | None = None,
    search: str | None = None,
    view_type: str | None = None,
) -> Any:
    """Publish scheduled assignments in a date range (start/end required).

    view_type is PROJECTS/TEAM/ALL.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "start": start,
            "end": end,
            "notifyUsers": notify_users,
            "search": search,
            "viewType": view_type,
        }
    )
    return await client.put(f"workspaces/{ws}/scheduling/assignments/publish", json=body)


async def copy_assignment(
    client: ClockifyClient,
    *,
    assignment_id: str,
    user_id: str,
    workspace_id: str | None = None,
    series_update_option: str | None = None,
) -> Any:
    """Copy an assignment to another user (user_id required)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"userId": user_id, "seriesUpdateOption": series_update_option})
    return await client.post(
        f"workspaces/{ws}/scheduling/assignments/{assignment_id}/copy", json=body
    )
```

- [ ] **Step 4: Add `register` + `_register_writes`** following the pattern: register the 3 reads; gate the 5 writes (`create_assignment`, `update_assignment`, `delete_assignment`, `publish_assignments`, `copy_assignment`) behind `client.writes_enabled`. Thunk signatures mirror the standalone functions (minus `client`).

- [ ] **Step 5: Add the `*_fn` alias block** (all 8) as the final block.

- [ ] **Step 6: Run → pass** (9 passed), ruff clean.

- [ ] **Step 7: Commit** `feat: scheduling writes (create/update/delete/publish/copy)`

---

## Task 5: invoices — reads

**Files:** Create `src/clockify_mcp/domains/invoices.py`, `tests/test_invoices.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_invoices.py
import json
import httpx
import respx
from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import invoices


@respx.mock
async def test_list_invoices_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/invoices").mock(
        return_value=httpx.Response(200, json=[{"id": "i1"}])
    )
    client = ClockifyClient(config)
    await invoices.list_invoices(
        client, statuses="SENT", sort_column="DUE_ON", sort_order="DESCENDING",
        page=1, page_size=10,
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["statuses"] == "SENT"
    assert sent["sort-column"] == "DUE_ON"
    assert sent["page-size"] == "10"
    await client.aclose()


@respx.mock
async def test_get_invoice(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1").mock(
        return_value=httpx.Response(200, json={"id": "i1"})
    )
    client = ClockifyClient(config)
    assert await invoices.get_invoice(client, invoice_id="i1") == {"id": "i1"}
    await client.aclose()


@respx.mock
async def test_get_invoice_payments(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1/payments"
    ).mock(return_value=httpx.Response(200, json=[]))
    client = ClockifyClient(config)
    await invoices.get_invoice_payments(client, invoice_id="i1", page_size=5)
    assert dict(route.calls.last.request.url.params)["page-size"] == "5"
    await client.aclose()
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Write the module reads**

```python
# src/clockify_mcp/domains/invoices.py
"""Invoices domain (read + write).

Endpoints under ``workspaces/{ws}/invoices`` on the regular host. Creating an
invoice yields an empty invoice (no line items in the create body); items are
added via add_invoice_item / import_invoice_items. Status changes go through a
dedicated PATCH. Invoices are a paid Clockify feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_invoices(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    statuses: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List invoices (paginated).

    statuses filters by UNSENT/SENT/PAID/PARTIALLY_PAID/VOID/OVERDUE. sort_column
    is ID/CLIENT/DUE_ON/ISSUE_DATE/AMOUNT/BALANCE; sort_order ASCENDING/DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "statuses": statuses,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/invoices", params=params)


async def get_invoice(
    client: ClockifyClient, *, invoice_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single invoice by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/invoices/{invoice_id}")


async def get_invoice_payments(
    client: ClockifyClient,
    *,
    invoice_id: str,
    workspace_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List an invoice's payments (paginated)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(
        f"workspaces/{ws}/invoices/{invoice_id}/payments", params=page_params(page, page_size)
    )


list_invoices_fn = list_invoices
get_invoice_fn = get_invoice
get_invoice_payments_fn = get_invoice_payments
```

- [ ] **Step 4: Run → pass** (3 passed).

- [ ] **Step 5: Commit** `feat: invoices read (list, get, payments)`

---

## Task 6: invoices — core writes (create/update/status/duplicate/delete) + registration

**Files:** Modify `src/clockify_mcp/domains/invoices.py`, `tests/test_invoices.py`

- [ ] **Step 1: Write failing tests** (append)

```python
@respx.mock
async def test_create_invoice_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/invoices").mock(
        return_value=httpx.Response(201, json={"id": "i1"})
    )
    client = ClockifyClient(config_writes)
    await invoices.create_invoice(
        client, client_id="c1", currency="USD", issued_date="2026-06-01T00:00:00Z",
        due_date="2026-07-01T00:00:00Z", number="INV-1", time_view_mode="TIME_SENSITIVE_VIEW",
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "clientId": "c1", "currency": "USD", "issuedDate": "2026-06-01T00:00:00Z",
        "dueDate": "2026-07-01T00:00:00Z", "number": "INV-1",
        "timeViewMode": "TIME_SENSITIVE_VIEW",
    }
    await client.aclose()


@respx.mock
async def test_update_invoice_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1").mock(
        return_value=httpx.Response(200, json={"id": "i1"})
    )
    client = ClockifyClient(config_writes)
    await invoices.update_invoice(
        client, invoice_id="i1", currency="USD", number="INV-1",
        issued_date="2026-06-01T00:00:00Z", due_date="2026-07-01T00:00:00Z",
        discount_percent=0, tax_percent=10, tax2_percent=0, note="hi",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["currency"] == "USD"
    assert body["discountPercent"] == 0
    assert body["taxPercent"] == 10
    assert body["tax2Percent"] == 0
    assert body["note"] == "hi"
    assert "taxType" not in body and "visibleZeroFields" not in body
    await client.aclose()


@respx.mock
async def test_change_invoice_status(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1/status"
    ).mock(return_value=httpx.Response(200, json={"id": "i1"}))
    client = ClockifyClient(config_writes)
    await invoices.change_invoice_status(client, invoice_id="i1", invoice_status="SENT")
    assert json.loads(route.calls.last.request.content) == {"invoiceStatus": "SENT"}
    await client.aclose()


@respx.mock
async def test_duplicate_invoice(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1/duplicate"
    ).mock(return_value=httpx.Response(201, json={"id": "i2"}))
    client = ClockifyClient(config_writes)
    assert await invoices.duplicate_invoice(client, invoice_id="i1") == {"id": "i2"}
    await client.aclose()


@respx.mock
async def test_delete_invoice(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1").mock(
        return_value=httpx.Response(200, json={})
    )
    client = ClockifyClient(config_writes)
    await invoices.delete_invoice(client, invoice_id="i1")
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Add the core write functions**

```python
async def create_invoice(
    client: ClockifyClient,
    *,
    client_id: str,
    currency: str,
    issued_date: str,
    due_date: str,
    number: str,
    workspace_id: str | None = None,
    time_view_mode: str | None = None,
) -> Any:
    """Create an invoice (empty — add items separately).

    Required: client_id, currency, issued_date, due_date, number (all ISO-8601
    for the dates). time_view_mode is TIME_SENSITIVE_VIEW or AGGREGATED_TIME_VIEW.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "clientId": client_id,
            "currency": currency,
            "issuedDate": issued_date,
            "dueDate": due_date,
            "number": number,
            "timeViewMode": time_view_mode,
        }
    )
    return await client.post(f"workspaces/{ws}/invoices", json=body)


async def update_invoice(
    client: ClockifyClient,
    *,
    invoice_id: str,
    currency: str,
    number: str,
    issued_date: str,
    due_date: str,
    discount_percent: float,
    tax_percent: float,
    tax2_percent: float,
    workspace_id: str | None = None,
    client_id: str | None = None,
    company_id: str | None = None,
    note: str | None = None,
    subject: str | None = None,
) -> Any:
    """Update an invoice (full replace). Required: currency, number, issued_date,
    due_date, discount_percent, tax_percent, tax2_percent."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "currency": currency,
            "number": number,
            "issuedDate": issued_date,
            "dueDate": due_date,
            "discountPercent": discount_percent,
            "taxPercent": tax_percent,
            "tax2Percent": tax2_percent,
            "clientId": client_id,
            "companyId": company_id,
            "note": note,
            "subject": subject,
        }
    )
    return await client.put(f"workspaces/{ws}/invoices/{invoice_id}", json=body)


async def change_invoice_status(
    client: ClockifyClient,
    *,
    invoice_id: str,
    invoice_status: str,
    workspace_id: str | None = None,
) -> Any:
    """Change an invoice's status: UNSENT/SENT/PAID/PARTIALLY_PAID/VOID/OVERDUE."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.patch(
        f"workspaces/{ws}/invoices/{invoice_id}/status", json={"invoiceStatus": invoice_status}
    )


async def duplicate_invoice(
    client: ClockifyClient, *, invoice_id: str, workspace_id: str | None = None
) -> Any:
    """Duplicate an invoice (creates a new draft copy)."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.post(f"workspaces/{ws}/invoices/{invoice_id}/duplicate")


async def delete_invoice(
    client: ClockifyClient, *, invoice_id: str, workspace_id: str | None = None
) -> Any:
    """Delete an invoice. IRREVERSIBLE — permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/invoices/{invoice_id}")
```

> NOTE: `duplicate_invoice` calls `client.post(path)` with no `json` — confirm `ClockifyClient.post` allows `json=None` (it does; it defaults to None and httpx sends no body).

- [ ] **Step 4: Add `register` + a stub `_register_writes`** — register the 3 reads; gate writes. Define `_register_writes` now registering the 5 core writes above (`create_invoice`, `update_invoice`, `change_invoice_status`, `duplicate_invoice`, `delete_invoice`); the item/payment writes are added to this same `_register_writes` in Task 7.

- [ ] **Step 5: Add the `*_fn` aliases** for the 3 reads + 5 core writes (final block).

- [ ] **Step 6: Run → pass** (8 passed), ruff clean.

- [ ] **Step 7: Commit** `feat: invoices core writes (create/update/status/duplicate/delete)`

---

## Task 7: invoices — item & payment writes

**Files:** Modify `src/clockify_mcp/domains/invoices.py`, `tests/test_invoices.py`

- [ ] **Step 1: Write failing tests** (append)

```python
@respx.mock
async def test_add_invoice_item_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1/items"
    ).mock(return_value=httpx.Response(200, json={"id": "i1"}))
    client = ClockifyClient(config_writes)
    await invoices.add_invoice_item(
        client, invoice_id="i1", apply_taxes="TAX1TAX2", description="Consulting",
        item_type="Service", quantity=10, unit_price=500,
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "applyTaxes": "TAX1TAX2", "description": "Consulting",
        "itemType": "Service", "quantity": 10, "unitPrice": 500,
    }
    await client.aclose()


@respx.mock
async def test_import_invoice_items_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1/items/import"
    ).mock(return_value=httpx.Response(200, json={"id": "i1"}))
    client = ClockifyClient(config_writes)
    await invoices.import_invoice_items(
        client, invoice_id="i1", from_="2026-06-01T00:00:00Z", to="2026-06-07T00:00:00Z",
        import_expenses=False, time_entry_group_type="GROUPED",
        project_ids=["p1"], project_filter_contains="CONTAINS", project_filter_status="ACTIVE",
        time_entry_primary_group_by="PROJECT",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["from"] == "2026-06-01T00:00:00Z"
    assert body["to"] == "2026-06-07T00:00:00Z"
    assert body["importExpenses"] is False
    assert body["timeEntryGroupType"] == "GROUPED"
    assert body["projectFilter"] == {"contains": "CONTAINS", "ids": ["p1"], "status": "ACTIVE"}
    assert body["timeEntryPrimaryGroupBy"] == "PROJECT"
    await client.aclose()


@respx.mock
async def test_add_invoice_payment(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1/payments"
    ).mock(return_value=httpx.Response(200, json={"id": "i1"}))
    client = ClockifyClient(config_writes)
    await invoices.add_invoice_payment(
        client, invoice_id="i1", amount=100, note="stripe", payment_date="2026-06-10T00:00:00Z"
    )
    assert json.loads(route.calls.last.request.content) == {
        "amount": 100, "note": "stripe", "paymentDate": "2026-06-10T00:00:00Z"
    }
    await client.aclose()


@respx.mock
async def test_delete_invoice_payment(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/invoices/i1/payments/pay1"
    ).mock(return_value=httpx.Response(200, json={}))
    client = ClockifyClient(config_writes)
    await invoices.delete_invoice_payment(client, invoice_id="i1", payment_id="pay1")
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Add the item/payment functions**

```python
async def add_invoice_item(
    client: ClockifyClient,
    *,
    invoice_id: str,
    apply_taxes: str,
    description: str,
    item_type: str,
    quantity: int,
    unit_price: int,
    workspace_id: str | None = None,
) -> Any:
    """Add a line item to an invoice.

    apply_taxes is TAX1/TAX2/TAX1TAX2/NONE. item_type is a free-text label (e.g.
    "Service"). quantity and unit_price are integers (unit_price in minor units).
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = {
        "applyTaxes": apply_taxes,
        "description": description,
        "itemType": item_type,
        "quantity": quantity,
        "unitPrice": unit_price,
    }
    return await client.post(f"workspaces/{ws}/invoices/{invoice_id}/items", json=body)


async def import_invoice_items(
    client: ClockifyClient,
    *,
    invoice_id: str,
    from_: str,
    to: str,
    import_expenses: bool,
    time_entry_group_type: str,
    workspace_id: str | None = None,
    project_ids: list[str] | None = None,
    project_filter_contains: str | None = None,
    project_filter_status: str | None = None,
    time_entry_primary_group_by: str | None = None,
    time_entry_secondary_group_by: str | None = None,
) -> Any:
    """Import time entries (and optionally expenses) into an invoice as items.

    from_/to are ISO-8601. time_entry_group_type is SINGLE_ITEM/GROUPED/DETAILED.
    project_filter_contains is CONTAINS/DOES_NOT_CONTAIN/CONTAINS_ONLY;
    project_filter_status is ACTIVE/ARCHIVED/ALL. The *_group_by options apply to
    GROUPED imports (PROJECT/USER/DATE etc.).
    """
    ws = resolve_workspace_id(client, workspace_id)
    project_filter = drop_none(
        {
            "contains": project_filter_contains,
            "ids": project_ids,
            "status": project_filter_status,
        }
    )
    body = drop_none(
        {
            "from": from_,
            "to": to,
            "importExpenses": import_expenses,
            "timeEntryGroupType": time_entry_group_type,
            "projectFilter": project_filter,
            "timeEntryPrimaryGroupBy": time_entry_primary_group_by,
            "timeEntrySecondaryGroupBy": time_entry_secondary_group_by,
        }
    )
    return await client.post(f"workspaces/{ws}/invoices/{invoice_id}/items/import", json=body)


async def add_invoice_payment(
    client: ClockifyClient,
    *,
    invoice_id: str,
    workspace_id: str | None = None,
    amount: int | None = None,
    note: str | None = None,
    payment_date: str | None = None,
) -> Any:
    """Record a payment against an invoice (amount in minor units; payment_date ISO-8601)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"amount": amount, "note": note, "paymentDate": payment_date})
    return await client.post(f"workspaces/{ws}/invoices/{invoice_id}/payments", json=body)


async def delete_invoice_payment(
    client: ClockifyClient,
    *,
    invoice_id: str,
    payment_id: str,
    workspace_id: str | None = None,
) -> Any:
    """Delete a recorded invoice payment. IRREVERSIBLE."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(
        f"workspaces/{ws}/invoices/{invoice_id}/payments/{payment_id}"
    )
```

> NOTE: `from_` (trailing underscore) maps to the JSON key `"from"` (Python keyword). `project_filter` may be `{}` when no filter args are given; the API requires the key, so it is always included (empty object is acceptable).

- [ ] **Step 4: Extend `_register_writes`** to also register the 4 new tools (`add_invoice_item`, `import_invoice_items`, `add_invoice_payment`, `delete_invoice_payment`). Use `from_` as the MCP parameter name in the `import_invoice_items` thunk too (consistent with the function).

- [ ] **Step 5: Add the 4 new `*_fn` aliases** to the final block.

- [ ] **Step 6: Run → pass** (12 passed), ruff clean.

- [ ] **Step 7: Commit** `feat: invoices item & payment writes (add item/import/add payment/delete payment)`

---

## Task 8: client — `post()` query params

**Files:** Modify `src/clockify_mcp/client.py`, `tests/test_client.py`

The webhook-logs endpoint is a POST whose filters travel in the JSON body while `page`/`size` are query params. `client.post` currently can't send query params; add an optional `params` argument.

- [ ] **Step 1: Write the failing test** (append to `tests/test_client.py`)

```python
@respx.mock
async def test_post_passes_query_params(config):
    route = respx.post("https://api.clockify.me/api/v1/things").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    client = ClockifyClient(config)
    await client.post("things", json={"a": 1}, params={"page": 2, "size": 5})
    sent = dict(route.calls.last.request.url.params)
    assert sent["page"] == "2"
    assert sent["size"] == "5"
    assert json.loads(route.calls.last.request.content) == {"a": 1}
    await client.aclose()
```

(Add `import json` at the top of `tests/test_client.py` if not already present.)

- [ ] **Step 2: Run → fail** (`post()` got an unexpected keyword argument 'params').

- [ ] **Step 3: Add `params` to `post`**

```python
    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            "POST", self._config.regular_base, path, params=params, json=json
        )
```

- [ ] **Step 4: Run → pass.** Then full suite `uv run pytest -q` (shared client change — confirm no regression), ruff clean.

- [ ] **Step 5: Commit** `feat: client post() accepts optional query params`

---

## Task 9: webhooks — reads + writes + registration

**Files:** Create `src/clockify_mcp/domains/webhooks.py`, `tests/test_webhooks.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_webhooks.py
import json
import httpx
import respx
from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import webhooks


@respx.mock
async def test_list_webhooks_passes_type(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/webhooks").mock(
        return_value=httpx.Response(200, json=[{"id": "w1"}])
    )
    client = ClockifyClient(config)
    await webhooks.list_webhooks(client, type="USER_CREATED")
    assert dict(route.calls.last.request.url.params)["type"] == "USER_CREATED"
    await client.aclose()


@respx.mock
async def test_get_webhook(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1").mock(
        return_value=httpx.Response(200, json={"id": "w1"})
    )
    client = ClockifyClient(config)
    assert await webhooks.get_webhook(client, webhook_id="w1") == {"id": "w1"}
    await client.aclose()


@respx.mock
async def test_get_webhook_logs_posts_body_and_query(config):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1/logs"
    ).mock(return_value=httpx.Response(200, json=[]))
    client = ClockifyClient(config)
    await webhooks.get_webhook_logs(
        client, webhook_id="w1", status="FAILED", sort_by_newest=True, page=1, size=20
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["page"] == "1"
    assert sent["size"] == "20"
    body = json.loads(route.calls.last.request.content)
    assert body["status"] == "FAILED"
    assert body["sortByNewest"] is True
    await client.aclose()


@respx.mock
async def test_create_webhook_builds_body(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/webhooks").mock(
        return_value=httpx.Response(201, json={"id": "w1"})
    )
    client = ClockifyClient(config_writes)
    await webhooks.create_webhook(
        client, url="https://e.com/h", trigger_source=["p1"],
        trigger_source_type="PROJECT_ID", webhook_event="NEW_TIME_ENTRY", name="My hook",
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "url": "https://e.com/h", "triggerSource": ["p1"],
        "triggerSourceType": "PROJECT_ID", "webhookEvent": "NEW_TIME_ENTRY", "name": "My hook",
    }
    await client.aclose()


@respx.mock
async def test_update_webhook_builds_body(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1").mock(
        return_value=httpx.Response(200, json={"id": "w1"})
    )
    client = ClockifyClient(config_writes)
    await webhooks.update_webhook(
        client, webhook_id="w1", url="https://e.com/h", trigger_source=["p1"],
        trigger_source_type="PROJECT_ID", webhook_event="NEW_TIME_ENTRY",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["url"] == "https://e.com/h"
    assert body["webhookEvent"] == "NEW_TIME_ENTRY"
    await client.aclose()


@respx.mock
async def test_delete_webhook(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1").mock(
        return_value=httpx.Response(200, json={})
    )
    client = ClockifyClient(config_writes)
    await webhooks.delete_webhook(client, webhook_id="w1")
    assert route.called
    await client.aclose()


@respx.mock
async def test_generate_webhook_token_patches(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/webhooks/w1/token"
    ).mock(return_value=httpx.Response(200, json={"id": "w1"}))
    client = ClockifyClient(config_writes)
    await webhooks.generate_webhook_token(client, webhook_id="w1")
    assert route.called
    await client.aclose()
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Write the module** (reads + writes + register)

```python
# src/clockify_mcp/domains/webhooks.py
"""Webhooks domain (read + write).

Workspace-scoped webhooks under ``workspaces/{ws}/webhooks`` on the regular host.
Logs are fetched via POST (filters in the body, page/size as query params). This
server only manages Clockify webhook definitions — it is not a webhook receiver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_webhooks(
    client: ClockifyClient, *, workspace_id: str | None = None, type: str | None = None
) -> Any:
    """List webhooks. type filters by USER_CREATED, SYSTEM, or ADDON."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/webhooks", params={"type": type})


async def get_webhook(
    client: ClockifyClient, *, webhook_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single webhook by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/webhooks/{webhook_id}")


async def get_webhook_logs(
    client: ClockifyClient,
    *,
    webhook_id: str,
    workspace_id: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    sort_by_newest: bool | None = None,
    status: str | None = None,
    page: int | None = None,
    size: int | None = None,
) -> Any:
    """Get a webhook's delivery logs (POST filter body; page/size are query params).

    from_/to are ISO-8601. status filters by ALL/SUCCEEDED/FAILED.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {"from": from_, "to": to, "sortByNewest": sort_by_newest, "status": status}
    )
    params = drop_none({"page": page, "size": size})
    return await client.post(
        f"workspaces/{ws}/webhooks/{webhook_id}/logs", json=body, params=params or None
    )


async def create_webhook(
    client: ClockifyClient,
    *,
    url: str,
    trigger_source: list[str],
    trigger_source_type: str,
    webhook_event: str,
    workspace_id: str | None = None,
    name: str | None = None,
) -> Any:
    """Create a webhook.

    trigger_source is a list of entity IDs whose type matches trigger_source_type
    (PROJECT_ID/USER_ID/TAG_ID/TASK_ID/WORKSPACE_ID/ASSIGNMENT_ID/EXPENSE_ID).
    webhook_event is a single event name (e.g. NEW_TIME_ENTRY, NEW_INVOICE).
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "url": url,
            "triggerSource": trigger_source,
            "triggerSourceType": trigger_source_type,
            "webhookEvent": webhook_event,
            "name": name,
        }
    )
    return await client.post(f"workspaces/{ws}/webhooks", json=body)


async def update_webhook(
    client: ClockifyClient,
    *,
    webhook_id: str,
    url: str,
    trigger_source: list[str],
    trigger_source_type: str,
    webhook_event: str,
    workspace_id: str | None = None,
    name: str | None = None,
) -> Any:
    """Update a webhook (full replace; same fields as create)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "url": url,
            "triggerSource": trigger_source,
            "triggerSourceType": trigger_source_type,
            "webhookEvent": webhook_event,
            "name": name,
        }
    )
    return await client.put(f"workspaces/{ws}/webhooks/{webhook_id}", json=body)


async def delete_webhook(
    client: ClockifyClient, *, webhook_id: str, workspace_id: str | None = None
) -> Any:
    """Delete a webhook. IRREVERSIBLE — permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/webhooks/{webhook_id}")


async def generate_webhook_token(
    client: ClockifyClient, *, webhook_id: str, workspace_id: str | None = None
) -> Any:
    """Regenerate a webhook's signing token. The old token stops working."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.patch(f"workspaces/{ws}/webhooks/{webhook_id}/token")
```

> NOTE: `generate_webhook_token` calls `client.patch(path)` with no body — confirm `patch` allows `json=None` (it does).

- [ ] **Step 4: Add `register` + `_register_writes`** — register the 3 reads (`list_webhooks`, `get_webhook`, `get_webhook_logs`); gate the 4 writes (`create_webhook`, `update_webhook`, `delete_webhook`, `generate_webhook_token`). Thunks mirror the function signatures; use `from_` as the param name in the `get_webhook_logs` thunk.

- [ ] **Step 5: Add the `*_fn` alias block** (all 7) as the final block.

- [ ] **Step 6: Run → pass** (8 passed), ruff clean.

- [ ] **Step 7: Commit** `feat: webhooks read + write (list/get/logs, create/update/delete/token)`

---

## Task 10: Register the four domains in the server

**Files:** Modify `src/clockify_mcp/server.py`, `tests/test_server.py`

- [ ] **Step 1: Extend the server tests.** Add to the read-tools set in `test_build_server_registers_discovery_tools`:

```python
        "list_workspace_custom_fields", "list_project_custom_fields",
        "list_scheduled_assignments", "get_project_scheduling_totals",
        "get_user_scheduling_totals",
        "list_invoices", "get_invoice", "get_invoice_payments",
        "list_webhooks", "get_webhook", "get_webhook_logs",
```

Add to the write-tools set in `test_writes_registered_when_enabled`:

```python
        "create_workspace_custom_field", "update_workspace_custom_field",
        "delete_workspace_custom_field", "set_project_custom_field",
        "remove_project_custom_field",
        "create_assignment", "update_assignment", "delete_assignment",
        "publish_assignments", "copy_assignment",
        "create_invoice", "update_invoice", "change_invoice_status",
        "duplicate_invoice", "delete_invoice", "add_invoice_item",
        "import_invoice_items", "add_invoice_payment", "delete_invoice_payment",
        "create_webhook", "update_webhook", "delete_webhook", "generate_webhook_token",
```

Add two names to `test_writes_not_registered_by_default`:

```python
    assert "create_invoice" not in names
    assert "create_webhook" not in names
```

- [ ] **Step 2: Run server tests → fail.**

- [ ] **Step 3: Register in `server.py`.** Add `custom_fields, invoices, scheduling, webhooks` to the `from .domains import (...)` block (alphabetical), and after `approvals.register(mcp, client)` add:

```python
    custom_fields.register(mcp, client)
    scheduling.register(mcp, client)
    invoices.register(mcp, client)
    webhooks.register(mcp, client)
    return mcp
```

- [ ] **Step 4: Run server tests → pass.**

- [ ] **Step 5: Full suite + lint** `uv run pytest -q && uv run ruff check src/ tests/` — all pass, ruff clean.

- [ ] **Step 6: Commit** `feat: register custom_fields, scheduling, invoices, webhooks domains`

---

## Task 11: Live smoke round-trips (gated)

**Files:** Modify `tests/test_live_smoke.py`

All four domains are paid features; reuse `_skip_if_feature_unavailable` (skip on 402/403/404). Add two round-trips — a workspace custom field and a webhook — both safe to create/delete. (Scheduling and invoices need referenced entities and real money/period semantics, so they are covered by unit tests only; do not create them live.)

- [ ] **Step 1: Extend the domains import** in `tests/test_live_smoke.py` to add `custom_fields` and `webhooks`.

- [ ] **Step 2: Add the custom-field round-trip** (append)

```python
async def test_live_custom_field_roundtrip(live):
    client, ws, _ = live
    try:
        created = await custom_fields.create_workspace_custom_field(
            client, workspace_id=ws, name=PREFIX + "cf", type="TXT", entity_type="TIMEENTRY",
        )
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
        return  # unreachable: _skip_if_feature_unavailable always raises
    cf_id = created["id"]
    try:
        updated = await custom_fields.update_workspace_custom_field(
            client, workspace_id=ws, custom_field_id=cf_id, name=PREFIX + "cf2", type="TXT",
        )
        assert updated["id"] == cf_id
    finally:
        await custom_fields.delete_workspace_custom_field(
            client, workspace_id=ws, custom_field_id=cf_id
        )
```

- [ ] **Step 3: Add the webhook round-trip** (append)

```python
async def test_live_webhook_roundtrip(live):
    client, ws, _ = live
    try:
        created = await webhooks.create_webhook(
            client, workspace_id=ws, name=PREFIX + "hook",
            url="https://example.com/clockify-smoke",
            trigger_source=[ws], trigger_source_type="WORKSPACE_ID",
            webhook_event="NEW_TIME_ENTRY",
        )
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
        return  # unreachable: _skip_if_feature_unavailable always raises
    wh_id = created["id"]
    try:
        fetched = await webhooks.get_webhook(client, workspace_id=ws, webhook_id=wh_id)
        assert fetched["id"] == wh_id
        await webhooks.generate_webhook_token(client, workspace_id=ws, webhook_id=wh_id)
    finally:
        await webhooks.delete_webhook(client, workspace_id=ws, webhook_id=wh_id)
```

- [ ] **Step 4: Confirm the default (non-live) run still passes** `uv run pytest -q` — live-smoke skip count goes from 9 to 11.

- [ ] **Step 5: Run live locally (manual, optional)** with the gated env (see the file's header). The webhook `trigger_source=[ws]` with `WORKSPACE_ID` is the most broadly-valid trigger. If create fails on a non-feature error (e.g. 400 invalid event), capture it and adjust `webhook_event` to a value valid for the workspace.

- [ ] **Step 6: Commit** `test: gated live smoke for custom fields and webhooks`

---

## Task 12: Docs

**Files:** Modify `README.md`, `CLAUDE.md`

- [ ] **Step 1: Update `CLAUDE.md`:**
  - Project Overview: Phase 0–6 → **Phase 0–7 (v1 complete)**; counts → **43 read + 59 write = 102 tools across 17 domains**; add Custom fields, Scheduling, Invoices, Webhooks to the domain list and the writes-gated sentence; replace the "Remaining domains … arrive in later phases" sentence with a note that all planned v1 domains are implemented (telemetry OTel port may remain).
  - Architecture "Key modules": add the four module bullets:
    - `domains/custom_fields.py` — `list_workspace_custom_fields`, `list_project_custom_fields` (+ create/update/delete workspace field and set/remove on project when writes enabled)
    - `domains/scheduling.py` — `list_scheduled_assignments`, `get_project_scheduling_totals`, `get_user_scheduling_totals` (+ create/update/delete/publish/copy assignment when writes enabled)
    - `domains/invoices.py` — `list_invoices`, `get_invoice`, `get_invoice_payments` (+ create/update/change-status/duplicate/delete and item/payment management when writes enabled)
    - `domains/webhooks.py` — `list_webhooks`, `get_webhook`, `get_webhook_logs` (+ create/update/delete/generate-token when writes enabled)
  - Development Conventions: update the `uv run pytest -q` expected count — run the suite and use the exact "X passed, Y skipped" printed.

- [ ] **Step 2: Update `README.md`:** add `custom_fields`, `scheduling`, `invoices`, `webhooks` rows to the tool/domain table(s); note all four are paid features; update running totals (43 read + 59 write, 17 domains, Phase 0–7 / v1 complete). README accurate to implemented state.

- [ ] **Step 3: Full suite + lint** `uv run pytest -q && uv run ruff check src/ tests/` — all pass, ruff clean.

- [ ] **Step 4: Commit** `docs: document Phase 7 custom_fields/scheduling/invoices/webhooks`

---

## Self-Review

**Spec coverage (design §7 Phase 7 rows + the two user decisions):**
- custom_fields — list ws/project (T1) ✓; create/update/delete ws + set/remove project (T2) ✓.
- scheduling — list + project/user totals (T3) ✓; create/update/delete + (extended) publish/copy (T4) ✓.
- invoices — list/get/payments (T5) ✓; create/update/status/duplicate/delete (T6) ✓; (extended full-lifecycle) item add/import + payment add/delete (T7) ✓.
- webhooks — list/get/logs + create/update/delete/token (T9) ✓; client.post params enabler (T8) ✓.
- Registration (T10), live smoke (T11), docs (T12) ✓.

**Decisions/deviations, justified:**
- `project_totals` and `get_user_scheduling_totals` use the POST "all"-style endpoints (more useful overview) — POST reads, consistent with `list_time_off_requests`.
- `update_invoice` omits `taxType` and `visibleZeroFields` — both are optional and have self-contradictory serialization in the spec (string vs object / string vs array); we don't send unverified shapes. A follow-up can add them once tested live.
- Extended scheduling (publish/copy/user-totals) and full invoice lifecycle (items/payments) included per the user's explicit choices.
- Excluded (verified but out of scope): invoice settings/export, mark-invoiced, addon webhooks, deprecated GET totals, user custom-field value upsert, the scheduling `series` PUT (covered by update's `seriesUpdateOption`).

**Type/name consistency:** Every `@mcp.tool()` name in Tasks 2/4/6/7/9 matches the names asserted in Task 10's server tests and the `*_fn` aliases. The client `post(params=...)` added in Task 8 is consumed by `get_webhook_logs` in Task 9. `from_` consistently maps to the JSON/`"from"` key in import and logs. Param keys: GET hyphenated (`page-size`, `sort-column`, `sort-order`, `entity-type`; webhook logs `size`); bodies camelCase (`entityType`, `allowedValues`, `recurringAssignment`, `seriesUpdateOption`, `statusFilter`, `invoiceStatus`, `applyTaxes`, `projectFilter`, `triggerSource`, `webhookEvent`).

**Placeholder scan:** No TBD/TODO placeholders. Function bodies are complete with exact paths/params/bodies. The `register`/`_register_writes` thunks for each domain are specified by an explicit tool list + "mirror the standalone signatures and the tags.py/expenses.py pattern" — the same mechanical thunk pattern proven across Phases 1–6; the spec/quality reviews verify name-matching. The two `return` lines after `_skip_if_feature_unavailable` are intentional (defensive; the helper always raises), matching the Phase 5/6 live-smoke convention.
