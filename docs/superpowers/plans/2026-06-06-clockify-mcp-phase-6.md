# Clockify MCP Phase 6 — Expenses + Approvals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `expenses` and `approvals` domains (read + opt-in write tools) to the Clockify MCP server, including the client infrastructure for multipart receipt upload and binary receipt download.

**Architecture:** Expenses require capabilities the JSON-only `ClockifyClient` lacks: create/update expense are `multipart/form-data` (optional receipt file), and the receipt download is a raw binary GET. So Phase 6 first extends `client.py` with `post_multipart()`, `put_multipart()`, and `get_bytes()` (a `raw` response path that returns `bytes`), then builds two new domain modules (`domains/expenses.py`, `domains/approvals.py`) following the established per-domain pattern (`register`/`_register_writes`, `*_fn` aliases, `drop_none` bodies). Expense categories and all approval endpoints are plain JSON. Everything lives on the regular `https://api.clockify.me/api/v1` host.

**Tech Stack:** Python 3.12+, FastMCP (`mcp`), httpx (multipart via `files=`/`data=`, binary via `response.content`), respx (tests), pytest-asyncio, uv, ruff.

**Verified API surface (official Clockify OpenAPI 3.0.1, docs.developer.clockify.me; base `https://api.clockify.me/api/v1`):**

| Operation | Method | Path | Body |
|---|---|---|---|
| List expenses | GET | `workspaces/{ws}/expenses` | params `page`,`page-size`,`user-id` |
| Get expense | GET | `workspaces/{ws}/expenses/{expenseId}` | — |
| Download receipt | GET | `workspaces/{ws}/expenses/{expenseId}/files/{fileId}` | raw bytes (`*/*`) |
| Create expense | POST | `workspaces/{ws}/expenses` | **multipart/form-data** |
| Update expense | PUT | `workspaces/{ws}/expenses/{expenseId}` | **multipart/form-data** (+ `changeFields`) |
| Delete expense | DELETE | `workspaces/{ws}/expenses/{expenseId}` | — |
| List categories | GET | `workspaces/{ws}/expenses/categories` | params `name`,`archived`,`sort-column`,`sort-order`,`page`,`page-size` |
| Create category | POST | `workspaces/{ws}/expenses/categories` | JSON |
| Update category | PUT | `workspaces/{ws}/expenses/categories/{categoryId}` | JSON |
| Delete category | DELETE | `workspaces/{ws}/expenses/categories/{categoryId}` | — |
| Archive category | PATCH | `workspaces/{ws}/expenses/categories/{categoryId}/status` | JSON `{archived}` |
| List approval requests | GET | `workspaces/{ws}/approval-requests` | params `status`,`sort-column`,`sort-order`,`page`,`page-size` |
| Submit approval (self) | POST | `workspaces/{ws}/approval-requests` | JSON `{periodStart,period}` |
| Submit approval (user) | POST | `workspaces/{ws}/approval-requests/users/{userId}` | JSON `{periodStart,period}` |
| Resubmit entries (self) | POST | `workspaces/{ws}/approval-requests/resubmit-entries-for-approval` | JSON `{periodStart,period}` |
| Update approval status | PATCH | `workspaces/{ws}/approval-requests/{approvalRequestId}` | JSON `{state,note}` |

**Verified facts that shape the code:**
- Create/update expense are **multipart only** (no JSON variant). Form field names are **camelCase** per the OpenAPI spec (`userId`, `categoryId`, `projectId`, `taskId`, `amount`, `date`, `billable`, `notes`, `file`). (A Clockify help article shows snake_case keys — a known doc discrepancy; we send camelCase per the machine-readable spec, and the live smoke test in Task 12 confirms it.)
- The receipt is **optional** on create (omit the `file` part); the spec's "`file` required" flag contradicts the help example and the `required:false` body — treat receipt as optional.
- Update expense additionally requires **`changeFields`** (array of the field names being changed). We derive it automatically from which optional fields the caller passes.
- Receipt download is a real binary endpoint (`type: string, format: byte` / content-type `*/*`) — return raw bytes, write them to a caller-supplied path.
- Category **archive** is a dedicated `PATCH .../status` with `{archived: bool}`, NOT the PUT.
- Approval `state` enum: `PENDING | APPROVED | WITHDRAWN_SUBMISSION | WITHDRAWN_APPROVAL | REJECTED`. The list `status` filter only accepts `PENDING | APPROVED | WITHDRAWN_APPROVAL`.
- Approval submit/resubmit body: `periodStart` (string) + `period` enum `WEEKLY | SEMI_MONTHLY | MONTHLY`.
- Param spelling: GET query keys hyphenated (`page-size`, `user-id`, `sort-column`, `sort-order`); JSON bodies camelCase.

**Out of scope (not in the spec's Phase 6 inventory / unverified):** the `POST .../reports/expenses/detailed` expense report (its host is unverified — regular vs Reports — and it isn't in the design's tool table). Do NOT implement it.

---

## File Structure

- Modify: `src/clockify_mcp/client.py` — add `post_multipart()`, `put_multipart()`, `get_bytes()`; extend `_request`/`_send_with_retry` for `data`/`files`/`raw`; extract error-raising into a shared helper.
- Test: `tests/test_client.py` — cover multipart send + binary GET + binary error.
- Create: `src/clockify_mcp/domains/expenses.py` — expenses + categories (read + write).
- Create: `src/clockify_mcp/domains/approvals.py` — approval requests (read + write).
- Create: `tests/test_expenses.py`, `tests/test_approvals.py`.
- Modify: `src/clockify_mcp/server.py` — register both domains.
- Modify: `tests/test_server.py` — assert new read + write tool names.
- Modify: `tests/test_live_smoke.py` — gated expense/category/approval round-trips.
- Modify: `README.md`, `CLAUDE.md` — document the new tools.

**New tool inventory (16 tools):**
- `expenses` (4 read, 7 write): `list_expenses`, `get_expense`, `list_expense_categories`, `download_expense_receipt` · `create_expense`, `update_expense`, `delete_expense`, `create_expense_category`, `update_expense_category`, `delete_expense_category`, `archive_expense_category`
- `approvals` (1 read, 4 write): `list_approval_requests` · `submit_approval_request`, `submit_approval_request_for_user`, `resubmit_approval_entries`, `update_approval_request`

After Phase 6: 32 read + 36 write = 68 tools across 13 domains.

---

## Task 1: Client — multipart send (`post_multipart`, `put_multipart`)

**Files:**
- Modify: `src/clockify_mcp/client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_client.py`)

```python
@respx.mock
async def test_post_multipart_sends_data_and_file(config):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/expenses").mock(
        return_value=httpx.Response(201, json={"id": "e1"})
    )
    client = ClockifyClient(config)
    result = await client.post_multipart(
        "workspaces/ws1/expenses",
        data={"amount": "10.5", "categoryId": "c1"},
        files={"file": ("r.txt", b"hello", "text/plain")},
    )
    assert result == {"id": "e1"}
    sent = route.calls.last.request
    body = sent.content
    assert b'name="amount"' in body and b"10.5" in body
    assert b'name="categoryId"' in body
    assert b'name="file"' in body and b"hello" in body
    assert sent.headers["content-type"].startswith("multipart/form-data")
    await client.aclose()


@respx.mock
async def test_post_multipart_without_file(config):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/expenses").mock(
        return_value=httpx.Response(201, json={"id": "e1"})
    )
    client = ClockifyClient(config)
    await client.post_multipart("workspaces/ws1/expenses", data={"amount": "10.5"})
    assert b'name="amount"' in route.calls.last.request.content
    await client.aclose()


@respx.mock
async def test_put_multipart_sends_to_put(config):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/expenses/e1").mock(
        return_value=httpx.Response(200, json={"id": "e1"})
    )
    client = ClockifyClient(config)
    await client.put_multipart(
        "workspaces/ws1/expenses/e1", data={"amount": "12"}, files=None
    )
    assert route.calls.last.request.method == "PUT"
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client.py -q`
Expected: FAIL — `AttributeError: 'ClockifyClient' object has no attribute 'post_multipart'`.

- [ ] **Step 3: Extend the client**

> **IMPORTANT (httpx multipart semantics):** httpx only emits `multipart/form-data` when its `files=` argument is non-empty. Passing `data=` with `files=None` produces `application/x-www-form-urlencoded`, which Clockify's expense create/update endpoints reject. So we must ALWAYS route multipart through httpx's `files=` argument: scalar form fields are converted to `(name, (None, value))` parts (no real file needed), and list-valued fields (e.g. `changeFields`) expand into repeated parts. The `_multipart_parts` helper below does this.

In `src/clockify_mcp/client.py`, add the two public methods (place them after the existing `report()` method):

```python
    async def post_multipart(
        self,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        """POST multipart/form-data (e.g. an expense with an optional receipt file)."""
        return await self._request(
            "POST", self._config.regular_base, path, data=data, files=files
        )

    async def put_multipart(
        self,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        """PUT multipart/form-data (expense update with an optional receipt file)."""
        return await self._request(
            "PUT", self._config.regular_base, path, data=data, files=files
        )
```

Add the multipart-parts builder as a `@staticmethod` on `ClockifyClient` (near `_clean`):

```python
    @staticmethod
    def _multipart_parts(
        data: dict[str, Any] | None, files: dict[str, Any] | None
    ) -> list[tuple[str, Any]]:
        """Build an httpx multipart 'files' list from scalar fields + file parts.

        Scalar fields become ``(name, (None, str_value))`` parts so the request is
        always multipart/form-data even with no file attached. List/tuple values
        expand into repeated parts (e.g. ``changeFields``). Real files pass through
        as ``(name, (filename, content, content_type))``. None values are dropped.
        """
        parts: list[tuple[str, Any]] = []
        for key, value in (data or {}).items():
            if value is None:
                continue
            items = value if isinstance(value, (list, tuple)) else [value]
            for item in items:
                parts.append((key, (None, str(item))))
        for key, file_part in (files or {}).items():
            parts.append((key, file_part))
        return parts
```

Extend `_request` to convert `data`/`files` into multipart parts and route them through httpx's `files=` (keep `json` working unchanged):

```python
    async def _request(
        self,
        method: str,
        base: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{base}/{path.lstrip('/')}"
        multipart = (
            self._multipart_parts(data, files)
            if data is not None or files is not None
            else None
        )
        with self._telemetry.client_span(method, path, params or json or data) as span:
            response = await self._send_with_retry(
                method, url, params=self._clean(params), json=json, files=multipart
            )
            span.set_status_code(response.status_code)
            result = self._handle(response)
            span.set_result(result)
            return result
```

Extend `_send_with_retry` to pass the multipart `files` list to httpx:

```python
    async def _send_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any],
        json: dict[str, Any] | None,
        files: list[tuple[str, Any]] | None = None,
    ) -> httpx.Response:
        """Send, retrying 429 with light exponential backoff (honors Retry-After).

        Up to _MAX_RETRIES retries AFTER the initial attempt (so a persistently
        rate-limited request makes 1 + _MAX_RETRIES total calls before the final
        429 is returned to the caller).
        """
        attempt = 0
        while True:
            response = await self._client.request(
                method, url, params=params or None, json=json, files=files
            )
            if response.status_code != 429 or attempt >= _MAX_RETRIES:
                return response
            delay = self._retry_delay(response, attempt)
            await asyncio.sleep(delay)
            attempt += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -q`
Expected: PASS (all prior client tests + the 3 new ones).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/client.py tests/test_client.py
git commit -m "feat: client multipart/form-data POST and PUT support"
```

---

## Task 2: Client — binary GET (`get_bytes`)

**Files:**
- Modify: `src/clockify_mcp/client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
@respx.mock
async def test_get_bytes_returns_raw_content(config):
    respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/expenses/e1/files/f1"
    ).mock(return_value=httpx.Response(200, content=b"\x89PNG\r\n receipt bytes"))
    client = ClockifyClient(config)
    result = await client.get_bytes("workspaces/ws1/expenses/e1/files/f1")
    assert result == b"\x89PNG\r\n receipt bytes"
    assert isinstance(result, bytes)
    await client.aclose()


@respx.mock
async def test_get_bytes_raises_sanitized_on_error(config):
    respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/expenses/e1/files/f1"
    ).mock(return_value=httpx.Response(404, json={"message": "no file for key test-key"}))
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as exc:
        await client.get_bytes("workspaces/ws1/expenses/e1/files/f1")
    assert exc.value.status_code == 404
    assert "test-key" not in str(exc.value)
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client.py -q`
Expected: FAIL — `AttributeError: ... 'get_bytes'`.

- [ ] **Step 3: Add `get_bytes` + a raw response path**

Add the public method (after `get`):

```python
    async def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        """GET raw bytes (binary downloads such as expense receipt files)."""
        return await self._request(
            "GET", self._config.regular_base, path, params=params, raw=True
        )
```

Add a `raw` flag to `_request` and branch the response handling (the multipart conversion from Task 1 stays — only the response side changes):

```python
    async def _request(
        self,
        method: str,
        base: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        url = f"{base}/{path.lstrip('/')}"
        multipart = (
            self._multipart_parts(data, files)
            if data is not None or files is not None
            else None
        )
        with self._telemetry.client_span(method, path, params or json or data) as span:
            response = await self._send_with_retry(
                method, url, params=self._clean(params), json=json, files=multipart
            )
            span.set_status_code(response.status_code)
            if raw:
                result = self._handle_bytes(response)
                span.set_result({"bytes": len(result)})
                return result
            result = self._handle(response)
            span.set_result(result)
            return result
```

Refactor the error branch out of `_handle` into a shared `_raise_for_error`, and add `_handle_bytes`:

```python
    def _handle(self, response: httpx.Response) -> Any:
        if response.is_success:
            if not response.content:
                return None
            return response.json()
        self._raise_for_error(response)

    def _handle_bytes(self, response: httpx.Response) -> bytes:
        if response.is_success:
            return response.content
        self._raise_for_error(response)

    def _raise_for_error(self, response: httpx.Response) -> None:
        try:
            body = response.json()
            message = body.get("message") or body.get("error") or response.text
        except Exception:
            body = response.text
            message = response.text
        raise ClockifyAPIError(
            response.status_code, self._sanitize(message), self._sanitize(body)
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -q`
Expected: PASS (all client tests).

- [ ] **Step 5: Run the full suite to confirm no regression** (the `_handle` refactor touches shared code)

Run: `uv run pytest -q`
Expected: all prior tests still pass (live smoke still skipped).

- [ ] **Step 6: Commit**

```bash
git add src/clockify_mcp/client.py tests/test_client.py
git commit -m "feat: client get_bytes for binary downloads"
```

---

## Task 3: expenses read — list + get + list categories

**Files:**
- Create: `src/clockify_mcp/domains/expenses.py`
- Test: `tests/test_expenses.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_expenses.py
import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import expenses


@respx.mock
async def test_list_expenses_passes_filters(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces/ws1/expenses").mock(
        return_value=httpx.Response(200, json={"expenses": {"count": 0, "expenses": []}})
    )
    client = ClockifyClient(config)
    result = await expenses.list_expenses(client, user_id="u1", page=2, page_size=10)
    assert result == {"expenses": {"count": 0, "expenses": []}}
    sent = dict(route.calls.last.request.url.params)
    assert sent["user-id"] == "u1"
    assert sent["page"] == "2"
    assert sent["page-size"] == "10"
    await client.aclose()


@respx.mock
async def test_get_expense(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/expenses/e1").mock(
        return_value=httpx.Response(200, json={"id": "e1"})
    )
    client = ClockifyClient(config)
    assert await expenses.get_expense(client, expense_id="e1") == {"id": "e1"}
    await client.aclose()


@respx.mock
async def test_list_expense_categories_passes_filters(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/expenses/categories"
    ).mock(return_value=httpx.Response(200, json={"count": 0, "categories": []}))
    client = ClockifyClient(config)
    await expenses.list_expense_categories(
        client, name="Travel", archived=False, sort_column="NAME",
        sort_order="ASCENDING", page=1, page_size=20,
    )
    sent = dict(route.calls.last.request.url.params)
    assert sent["name"] == "Travel"
    assert sent["archived"] == "false"
    assert sent["sort-column"] == "NAME"
    assert sent["sort-order"] == "ASCENDING"
    assert sent["page-size"] == "20"
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_expenses.py -q`
Expected: FAIL — `ImportError: cannot import name 'expenses'`.

- [ ] **Step 3: Write the module read functions**

```python
# src/clockify_mcp/domains/expenses.py
"""Expenses domain: expenses + expense categories (read + write).

All endpoints are on the regular Clockify host under
``workspaces/{workspaceId}/expenses``. Creating and updating an expense use
multipart/form-data (the receipt file is optional); the receipt download is a
raw binary GET. Categories are plain JSON. Expenses are a paid Clockify feature;
the API errors on plans without it.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_expenses(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List expenses on the workspace (paginated), optionally for one user."""
    ws = resolve_workspace_id(client, workspace_id)
    params = {"user-id": user_id, **page_params(page, page_size)}
    return await client.get(f"workspaces/{ws}/expenses", params=params)


async def get_expense(
    client: ClockifyClient, *, expense_id: str, workspace_id: str | None = None
) -> Any:
    """Get a single expense by id."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.get(f"workspaces/{ws}/expenses/{expense_id}")


async def list_expense_categories(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    archived: bool | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List expense categories (paginated).

    sort_column is NAME; sort_order is ASCENDING or DESCENDING; archived=True
    includes archived categories.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "name": name,
        "archived": archived,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/expenses/categories", params=params)


list_expenses_fn = list_expenses
get_expense_fn = get_expense
list_expense_categories_fn = list_expense_categories
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_expenses.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/expenses.py tests/test_expenses.py
git commit -m "feat: expenses read (list, get, list categories)"
```

---

## Task 4: expenses read — download receipt (binary → file)

**Files:**
- Modify: `src/clockify_mcp/domains/expenses.py`
- Test: `tests/test_expenses.py`

- [ ] **Step 1: Write the failing test** (append; uses `tmp_path`)

```python
@respx.mock
async def test_download_expense_receipt_writes_file(config, tmp_path):
    respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/expenses/e1/files/f1"
    ).mock(return_value=httpx.Response(200, content=b"PDFDATA"))
    client = ClockifyClient(config)
    dest = tmp_path / "receipt.pdf"
    result = await expenses.download_expense_receipt(
        client, expense_id="e1", file_id="f1", save_path=str(dest)
    )
    assert dest.read_bytes() == b"PDFDATA"
    assert result == {"path": str(dest), "bytes": 7, "file_id": "f1"}
    await client.aclose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_expenses.py -q`
Expected: FAIL — `AttributeError: ... 'download_expense_receipt'`.

- [ ] **Step 3: Add the function** (after `list_expense_categories`)

```python
async def download_expense_receipt(
    client: ClockifyClient,
    *,
    expense_id: str,
    file_id: str,
    save_path: str,
    workspace_id: str | None = None,
) -> Any:
    """Download an expense's receipt file to save_path (local filesystem).

    file_id is the expense's ``fileId``. Returns the path written, the byte
    count, and the file_id. The raw bytes are written to disk rather than
    returned inline so large binaries never enter the model context.
    """
    ws = resolve_workspace_id(client, workspace_id)
    content = await client.get_bytes(
        f"workspaces/{ws}/expenses/{expense_id}/files/{file_id}"
    )
    Path(save_path).write_bytes(content)
    return {"path": save_path, "bytes": len(content), "file_id": file_id}
```

Add alias: `download_expense_receipt_fn = download_expense_receipt`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_expenses.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/expenses.py tests/test_expenses.py
git commit -m "feat: expenses download receipt to local file"
```

---

## Task 5: expenses read registration

**Files:**
- Modify: `src/clockify_mcp/domains/expenses.py`

- [ ] **Step 1: Add `register`** (after the read functions; keep `_fn` aliases as the final block). Add a temporary `_register_writes` stub (filled in Task 7):

```python
def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_expenses(
        workspace_id: str | None = None,
        user_id: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List expenses on the workspace (paginated), optionally for one user."""
        return await list_expenses_fn(
            client, workspace_id=workspace_id, user_id=user_id, page=page, page_size=page_size
        )

    @mcp.tool()
    async def get_expense(expense_id: str, workspace_id: str | None = None) -> Any:
        """Get a single expense by id."""
        return await get_expense_fn(client, expense_id=expense_id, workspace_id=workspace_id)

    @mcp.tool()
    async def list_expense_categories(
        workspace_id: str | None = None,
        name: str | None = None,
        archived: bool | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List expense categories (paginated)."""
        return await list_expense_categories_fn(
            client,
            workspace_id=workspace_id,
            name=name,
            archived=archived,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    async def download_expense_receipt(
        expense_id: str,
        file_id: str,
        save_path: str,
        workspace_id: str | None = None,
    ) -> Any:
        """Download an expense's receipt file to a local path."""
        return await download_expense_receipt_fn(
            client,
            expense_id=expense_id,
            file_id=file_id,
            save_path=save_path,
            workspace_id=workspace_id,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:  # filled in Task 7
    pass
```

- [ ] **Step 2: Run the file's tests to confirm it imports cleanly**

Run: `uv run pytest tests/test_expenses.py -q`
Expected: PASS (4 passed).

- [ ] **Step 3: Commit**

```bash
git add src/clockify_mcp/domains/expenses.py
git commit -m "feat: register expenses read tools"
```

---

## Task 6: expenses write — create + update (multipart)

**Files:**
- Modify: `src/clockify_mcp/domains/expenses.py`
- Test: `tests/test_expenses.py`

- [ ] **Step 1: Write the failing tests** (append; `config_writes`, `tmp_path`)

```python
def _multipart_body(route) -> bytes:
    return route.calls.last.request.content


@respx.mock
async def test_create_expense_builds_multipart_no_file(config_writes):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/expenses").mock(
        return_value=httpx.Response(201, json={"id": "e1"})
    )
    client = ClockifyClient(config_writes)
    result = await expenses.create_expense(
        client, amount=42.5, category_id="c1", date="2026-06-01T00:00:00Z",
        project_id="p1", user_id="u1", billable=True, notes="lunch",
    )
    assert result == {"id": "e1"}
    body = _multipart_body(route)
    assert b'name="amount"' in body and b"42.5" in body
    assert b'name="categoryId"' in body and b"c1" in body
    assert b'name="projectId"' in body and b"p1" in body
    assert b'name="userId"' in body and b"u1" in body
    assert b'name="billable"' in body and b"true" in body
    assert b'name="notes"' in body
    assert b'name="file"' not in body  # no receipt
    await client.aclose()


@respx.mock
async def test_create_expense_with_receipt_attaches_file(config_writes, tmp_path):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/expenses").mock(
        return_value=httpx.Response(201, json={"id": "e1"})
    )
    receipt = tmp_path / "receipt.txt"
    receipt.write_bytes(b"RECEIPT")
    client = ClockifyClient(config_writes)
    await expenses.create_expense(
        client, amount=1.0, category_id="c1", date="2026-06-01T00:00:00Z",
        project_id="p1", user_id="u1", receipt_path=str(receipt),
    )
    body = _multipart_body(route)
    assert b'name="file"' in body
    assert b"RECEIPT" in body
    assert b"receipt.txt" in body
    await client.aclose()


@respx.mock
async def test_update_expense_derives_change_fields(config_writes):
    route = respx.put("https://api.clockify.me/api/v1/workspaces/ws1/expenses/e1").mock(
        return_value=httpx.Response(200, json={"id": "e1"})
    )
    client = ClockifyClient(config_writes)
    await expenses.update_expense(
        client, expense_id="e1", amount=5.0, category_id="c1",
        date="2026-06-01T00:00:00Z", user_id="u1", notes="edited",
    )
    body = _multipart_body(route)
    assert b'name="changeFields"' in body
    assert b"notes" in body  # 'notes' listed as a changed field
    assert b'name="amount"' in body and b"5.0" in body
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_expenses.py -q`
Expected: FAIL — `AttributeError: ... 'create_expense'`.

- [ ] **Step 3: Add a form-building helper + the two write functions** (place above `register`)

```python
def _form_value(value: Any) -> str | None:
    """Coerce a scalar form-field value to a string (booleans → 'true'/'false')."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _receipt_files(receipt_path: str | None) -> dict[str, Any] | None:
    if not receipt_path:
        return None
    path = Path(receipt_path)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {"file": (path.name, path.read_bytes(), mime)}


async def create_expense(
    client: ClockifyClient,
    *,
    amount: float,
    category_id: str,
    date: str,
    project_id: str,
    user_id: str,
    workspace_id: str | None = None,
    billable: bool | None = None,
    notes: str | None = None,
    task_id: str | None = None,
    receipt_path: str | None = None,
) -> Any:
    """Create an expense (multipart/form-data).

    amount, category_id, date (ISO-8601), project_id, and user_id are required.
    receipt_path is an optional local file to attach as the receipt. Field names
    are sent camelCase per the Clockify OpenAPI spec.
    """
    ws = resolve_workspace_id(client, workspace_id)
    data = drop_none(
        {
            "amount": _form_value(amount),
            "categoryId": category_id,
            "date": date,
            "projectId": project_id,
            "userId": user_id,
            "billable": _form_value(billable),
            "notes": notes,
            "taskId": task_id,
        }
    )
    files = _receipt_files(receipt_path)
    return await client.post_multipart(f"workspaces/{ws}/expenses", data=data, files=files)


async def update_expense(
    client: ClockifyClient,
    *,
    expense_id: str,
    amount: float,
    category_id: str,
    date: str,
    user_id: str,
    workspace_id: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
    billable: bool | None = None,
    notes: str | None = None,
    receipt_path: str | None = None,
) -> Any:
    """Update an expense (multipart/form-data; full update).

    amount, category_id, date, and user_id are required by the API. changeFields
    (the list of fields being changed) is derived automatically from the optional
    fields you pass (project_id, task_id, billable, notes, receipt). receipt_path
    attaches a new receipt file.
    """
    ws = resolve_workspace_id(client, workspace_id)
    optional = {
        "projectId": project_id,
        "taskId": task_id,
        "billable": _form_value(billable),
        "notes": notes,
    }
    change_fields = [key for key, value in optional.items() if value is not None]
    if receipt_path:
        change_fields.append("file")
    data = drop_none(
        {
            "amount": _form_value(amount),
            "categoryId": category_id,
            "date": date,
            "userId": user_id,
            **optional,
        }
    )
    data["changeFields"] = change_fields
    files = _receipt_files(receipt_path)
    return await client.put_multipart(
        f"workspaces/{ws}/expenses/{expense_id}", data=data, files=files
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_expenses.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/expenses.py tests/test_expenses.py
git commit -m "feat: expenses create/update (multipart with optional receipt)"
```

---

## Task 7: expenses write — delete + category writes + write registration

**Files:**
- Modify: `src/clockify_mcp/domains/expenses.py`
- Test: `tests/test_expenses.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
@respx.mock
async def test_delete_expense(config_writes):
    route = respx.delete("https://api.clockify.me/api/v1/workspaces/ws1/expenses/e1").mock(
        return_value=httpx.Response(200, json={"id": "e1"})
    )
    client = ClockifyClient(config_writes)
    assert await expenses.delete_expense(client, expense_id="e1") == {"id": "e1"}
    assert route.called
    await client.aclose()


@respx.mock
async def test_create_expense_category_builds_json(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/expenses/categories"
    ).mock(return_value=httpx.Response(201, json={"id": "c1"}))
    client = ClockifyClient(config_writes)
    await expenses.create_expense_category(
        client, name="Travel", has_unit_price=True, price_in_cents=500, unit="km"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "Travel", "hasUnitPrice": True, "priceInCents": 500, "unit": "km"}
    await client.aclose()


@respx.mock
async def test_update_expense_category_builds_json(config_writes):
    route = respx.put(
        "https://api.clockify.me/api/v1/workspaces/ws1/expenses/categories/c1"
    ).mock(return_value=httpx.Response(200, json={"id": "c1"}))
    client = ClockifyClient(config_writes)
    await expenses.update_expense_category(client, category_id="c1", name="Travel2")
    assert json.loads(route.calls.last.request.content) == {"name": "Travel2"}
    await client.aclose()


@respx.mock
async def test_delete_expense_category(config_writes):
    route = respx.delete(
        "https://api.clockify.me/api/v1/workspaces/ws1/expenses/categories/c1"
    ).mock(return_value=httpx.Response(204))
    client = ClockifyClient(config_writes)
    await expenses.delete_expense_category(client, category_id="c1")
    assert route.called
    await client.aclose()


@respx.mock
async def test_archive_expense_category_patches_status(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/expenses/categories/c1/status"
    ).mock(return_value=httpx.Response(200, json={"id": "c1", "archived": True}))
    client = ClockifyClient(config_writes)
    result = await expenses.archive_expense_category(client, category_id="c1", archived=True)
    assert result["archived"] is True
    assert json.loads(route.calls.last.request.content) == {"archived": True}
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_expenses.py -q`
Expected: FAIL — `AttributeError: ... 'delete_expense'`.

- [ ] **Step 3: Add the remaining write functions** (after `update_expense`)

```python
async def delete_expense(
    client: ClockifyClient, *, expense_id: str, workspace_id: str | None = None
) -> Any:
    """Delete an expense. IRREVERSIBLE — the expense is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/expenses/{expense_id}")


async def create_expense_category(
    client: ClockifyClient,
    *,
    name: str,
    workspace_id: str | None = None,
    has_unit_price: bool | None = None,
    price_in_cents: int | None = None,
    unit: str | None = None,
) -> Any:
    """Create an expense category. Set has_unit_price + price_in_cents + unit for
    unit-priced categories (e.g. mileage).
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "hasUnitPrice": has_unit_price,
            "priceInCents": price_in_cents,
            "unit": unit,
        }
    )
    return await client.post(f"workspaces/{ws}/expenses/categories", json=body)


async def update_expense_category(
    client: ClockifyClient,
    *,
    category_id: str,
    name: str,
    workspace_id: str | None = None,
    has_unit_price: bool | None = None,
    price_in_cents: int | None = None,
    unit: str | None = None,
) -> Any:
    """Update an expense category (name is required)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none(
        {
            "name": name,
            "hasUnitPrice": has_unit_price,
            "priceInCents": price_in_cents,
            "unit": unit,
        }
    )
    return await client.put(f"workspaces/{ws}/expenses/categories/{category_id}", json=body)


async def delete_expense_category(
    client: ClockifyClient, *, category_id: str, workspace_id: str | None = None
) -> Any:
    """Delete an expense category. IRREVERSIBLE — the category is permanently removed."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.delete(f"workspaces/{ws}/expenses/categories/{category_id}")


async def archive_expense_category(
    client: ClockifyClient,
    *,
    category_id: str,
    archived: bool,
    workspace_id: str | None = None,
) -> Any:
    """Archive (archived=True) or restore (archived=False) an expense category."""
    ws = resolve_workspace_id(client, workspace_id)
    return await client.patch(
        f"workspaces/{ws}/expenses/categories/{category_id}/status",
        json={"archived": archived},
    )
```

- [ ] **Step 4: Replace the `_register_writes` stub** with the real implementation

```python
def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def create_expense(
        amount: float,
        category_id: str,
        date: str,
        project_id: str,
        user_id: str,
        workspace_id: str | None = None,
        billable: bool | None = None,
        notes: str | None = None,
        task_id: str | None = None,
        receipt_path: str | None = None,
    ) -> Any:
        """Create an expense; receipt_path optionally attaches a local receipt file."""
        return await create_expense_fn(
            client,
            amount=amount,
            category_id=category_id,
            date=date,
            project_id=project_id,
            user_id=user_id,
            workspace_id=workspace_id,
            billable=billable,
            notes=notes,
            task_id=task_id,
            receipt_path=receipt_path,
        )

    @mcp.tool()
    async def update_expense(
        expense_id: str,
        amount: float,
        category_id: str,
        date: str,
        user_id: str,
        workspace_id: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        billable: bool | None = None,
        notes: str | None = None,
        receipt_path: str | None = None,
    ) -> Any:
        """Update an expense (multipart; changeFields derived from passed fields)."""
        return await update_expense_fn(
            client,
            expense_id=expense_id,
            amount=amount,
            category_id=category_id,
            date=date,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            task_id=task_id,
            billable=billable,
            notes=notes,
            receipt_path=receipt_path,
        )

    @mcp.tool()
    async def delete_expense(expense_id: str, workspace_id: str | None = None) -> Any:
        """Delete an expense. IRREVERSIBLE — the expense is permanently removed."""
        return await delete_expense_fn(
            client, expense_id=expense_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def create_expense_category(
        name: str,
        workspace_id: str | None = None,
        has_unit_price: bool | None = None,
        price_in_cents: int | None = None,
        unit: str | None = None,
    ) -> Any:
        """Create an expense category."""
        return await create_expense_category_fn(
            client,
            name=name,
            workspace_id=workspace_id,
            has_unit_price=has_unit_price,
            price_in_cents=price_in_cents,
            unit=unit,
        )

    @mcp.tool()
    async def update_expense_category(
        category_id: str,
        name: str,
        workspace_id: str | None = None,
        has_unit_price: bool | None = None,
        price_in_cents: int | None = None,
        unit: str | None = None,
    ) -> Any:
        """Update an expense category (name required)."""
        return await update_expense_category_fn(
            client,
            category_id=category_id,
            name=name,
            workspace_id=workspace_id,
            has_unit_price=has_unit_price,
            price_in_cents=price_in_cents,
            unit=unit,
        )

    @mcp.tool()
    async def delete_expense_category(
        category_id: str, workspace_id: str | None = None
    ) -> Any:
        """Delete an expense category. IRREVERSIBLE — permanently removed."""
        return await delete_expense_category_fn(
            client, category_id=category_id, workspace_id=workspace_id
        )

    @mcp.tool()
    async def archive_expense_category(
        category_id: str, archived: bool, workspace_id: str | None = None
    ) -> Any:
        """Archive (archived=True) or restore (archived=False) an expense category."""
        return await archive_expense_category_fn(
            client, category_id=category_id, archived=archived, workspace_id=workspace_id
        )
```

- [ ] **Step 5: Update the `_fn` aliases block** (final block of the file) to add the write aliases

```python
create_expense_fn = create_expense
update_expense_fn = update_expense
delete_expense_fn = delete_expense
create_expense_category_fn = create_expense_category
update_expense_category_fn = update_expense_category
delete_expense_category_fn = delete_expense_category
archive_expense_category_fn = archive_expense_category
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_expenses.py -q`
Expected: PASS (12 passed).

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/expenses.py tests/test_expenses.py
git commit -m "feat: expenses delete + category writes (create/update/delete/archive)"
```

---

## Task 8: approvals read + module

**Files:**
- Create: `src/clockify_mcp/domains/approvals.py`
- Test: `tests/test_approvals.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_approvals.py
import json

import httpx
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import approvals


@respx.mock
async def test_list_approval_requests_passes_filters(config):
    route = respx.get(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests"
    ).mock(return_value=httpx.Response(200, json=[{"id": "a1"}]))
    client = ClockifyClient(config)
    result = await approvals.list_approval_requests(
        client, status="PENDING", sort_column="START", sort_order="DESCENDING",
        page=1, page_size=25,
    )
    assert result == [{"id": "a1"}]
    sent = dict(route.calls.last.request.url.params)
    assert sent["status"] == "PENDING"
    assert sent["sort-column"] == "START"
    assert sent["sort-order"] == "DESCENDING"
    assert sent["page-size"] == "25"
    await client.aclose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_approvals.py -q`
Expected: FAIL — `ImportError: cannot import name 'approvals'`.

- [ ] **Step 3: Write the module read function**

```python
# src/clockify_mcp/domains/approvals.py
"""Approvals domain: timesheet/expense approval requests (read + write).

Endpoints are on the regular Clockify host under
``workspaces/{workspaceId}/approval-requests``. Submitting and resubmitting
reference a period start + period type (WEEKLY/SEMI_MONTHLY/MONTHLY). Status is
changed via PATCH with the state enum
(PENDING/APPROVED/WITHDRAWN_SUBMISSION/WITHDRAWN_APPROVAL/REJECTED). Approvals
are a paid Clockify feature; the API errors on plans without it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..bodies import drop_none
from ..client import ClockifyClient
from ..pagination import page_params
from .workspaces import resolve_workspace_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


async def list_approval_requests(
    client: ClockifyClient,
    *,
    workspace_id: str | None = None,
    status: str | None = None,
    sort_column: str | None = None,
    sort_order: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List approval requests (paginated).

    status filters by PENDING, APPROVED, or WITHDRAWN_APPROVAL (REJECTED requests
    are not returned by this filter — a Clockify limitation). sort_column is one
    of ID, USER_ID, START, UPDATED_AT; sort_order is ASCENDING or DESCENDING.
    """
    ws = resolve_workspace_id(client, workspace_id)
    params = {
        "status": status,
        "sort-column": sort_column,
        "sort-order": sort_order,
        **page_params(page, page_size),
    }
    return await client.get(f"workspaces/{ws}/approval-requests", params=params)


list_approval_requests_fn = list_approval_requests
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_approvals.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_mcp/domains/approvals.py tests/test_approvals.py
git commit -m "feat: approvals read (list approval requests)"
```

---

## Task 9: approvals writes + registration

**Files:**
- Modify: `src/clockify_mcp/domains/approvals.py`
- Test: `tests/test_approvals.py`

- [ ] **Step 1: Write the failing tests** (append; `config_writes`)

```python
@respx.mock
async def test_submit_approval_request_builds_body(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests"
    ).mock(return_value=httpx.Response(201, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await approvals.submit_approval_request(
        client, period_start="2026-06-01T00:00:00Z", period="WEEKLY"
    )
    assert json.loads(route.calls.last.request.content) == {
        "periodStart": "2026-06-01T00:00:00Z",
        "period": "WEEKLY",
    }
    await client.aclose()


@respx.mock
async def test_submit_approval_request_for_user(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests/users/u1"
    ).mock(return_value=httpx.Response(201, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await approvals.submit_approval_request_for_user(
        client, user_id="u1", period_start="2026-06-01T00:00:00Z", period="MONTHLY"
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"periodStart": "2026-06-01T00:00:00Z", "period": "MONTHLY"}
    await client.aclose()


@respx.mock
async def test_resubmit_approval_entries(config_writes):
    route = respx.post(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests/resubmit-entries-for-approval"
    ).mock(return_value=httpx.Response(200, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await approvals.resubmit_approval_entries(
        client, period_start="2026-06-01T00:00:00Z", period="WEEKLY"
    )
    assert json.loads(route.calls.last.request.content) == {
        "periodStart": "2026-06-01T00:00:00Z",
        "period": "WEEKLY",
    }
    await client.aclose()


@respx.mock
async def test_update_approval_request_builds_body(config_writes):
    route = respx.patch(
        "https://api.clockify.me/api/v1/workspaces/ws1/approval-requests/a1"
    ).mock(return_value=httpx.Response(200, json={"id": "a1"}))
    client = ClockifyClient(config_writes)
    await approvals.update_approval_request(
        client, approval_request_id="a1", state="APPROVED", note="ok"
    )
    assert json.loads(route.calls.last.request.content) == {"state": "APPROVED", "note": "ok"}
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_approvals.py -q`
Expected: FAIL — `AttributeError: ... 'submit_approval_request'`.

- [ ] **Step 3: Add the write functions** (after `list_approval_requests`)

```python
async def submit_approval_request(
    client: ClockifyClient,
    *,
    period_start: str,
    period: str,
    workspace_id: str | None = None,
) -> Any:
    """Submit an approval request for the authenticated user.

    period_start is the ISO-8601 start of the period; period is WEEKLY,
    SEMI_MONTHLY, or MONTHLY.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = {"periodStart": period_start, "period": period}
    return await client.post(f"workspaces/{ws}/approval-requests", json=body)


async def submit_approval_request_for_user(
    client: ClockifyClient,
    *,
    user_id: str,
    period_start: str,
    period: str,
    workspace_id: str | None = None,
) -> Any:
    """Submit an approval request on behalf of another user (manager action)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = {"periodStart": period_start, "period": period}
    return await client.post(
        f"workspaces/{ws}/approval-requests/users/{user_id}", json=body
    )


async def resubmit_approval_entries(
    client: ClockifyClient,
    *,
    period_start: str,
    period: str,
    workspace_id: str | None = None,
) -> Any:
    """Resubmit rejected/withdrawn entries for approval (authenticated user)."""
    ws = resolve_workspace_id(client, workspace_id)
    body = {"periodStart": period_start, "period": period}
    return await client.post(
        f"workspaces/{ws}/approval-requests/resubmit-entries-for-approval", json=body
    )


async def update_approval_request(
    client: ClockifyClient,
    *,
    approval_request_id: str,
    state: str,
    workspace_id: str | None = None,
    note: str | None = None,
) -> Any:
    """Change an approval request's state.

    state is one of APPROVED, REJECTED, PENDING, WITHDRAWN_SUBMISSION,
    WITHDRAWN_APPROVAL. note is an optional reason.
    """
    ws = resolve_workspace_id(client, workspace_id)
    body = drop_none({"state": state, "note": note})
    return await client.patch(
        f"workspaces/{ws}/approval-requests/{approval_request_id}", json=body
    )
```

- [ ] **Step 4: Add `register` + `_register_writes`** (after `update_approval_request`, keeping `_fn` aliases as the final block)

```python
def register(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def list_approval_requests(
        workspace_id: str | None = None,
        status: str | None = None,
        sort_column: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        """List approval requests (paginated)."""
        return await list_approval_requests_fn(
            client,
            workspace_id=workspace_id,
            status=status,
            sort_column=sort_column,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    if client.writes_enabled:
        _register_writes(mcp, client)


def _register_writes(mcp: "FastMCP", client: ClockifyClient) -> None:
    @mcp.tool()
    async def submit_approval_request(
        period_start: str, period: str, workspace_id: str | None = None
    ) -> Any:
        """Submit an approval request for the authenticated user."""
        return await submit_approval_request_fn(
            client, period_start=period_start, period=period, workspace_id=workspace_id
        )

    @mcp.tool()
    async def submit_approval_request_for_user(
        user_id: str, period_start: str, period: str, workspace_id: str | None = None
    ) -> Any:
        """Submit an approval request on behalf of another user (manager action)."""
        return await submit_approval_request_for_user_fn(
            client,
            user_id=user_id,
            period_start=period_start,
            period=period,
            workspace_id=workspace_id,
        )

    @mcp.tool()
    async def resubmit_approval_entries(
        period_start: str, period: str, workspace_id: str | None = None
    ) -> Any:
        """Resubmit rejected/withdrawn entries for approval (authenticated user)."""
        return await resubmit_approval_entries_fn(
            client, period_start=period_start, period=period, workspace_id=workspace_id
        )

    @mcp.tool()
    async def update_approval_request(
        approval_request_id: str,
        state: str,
        workspace_id: str | None = None,
        note: str | None = None,
    ) -> Any:
        """Change an approval request's state (APPROVED/REJECTED/PENDING/WITHDRAWN_*)."""
        return await update_approval_request_fn(
            client,
            approval_request_id=approval_request_id,
            state=state,
            workspace_id=workspace_id,
            note=note,
        )
```

- [ ] **Step 5: Update the `_fn` aliases block** at the bottom of the file

```python
list_approval_requests_fn = list_approval_requests
submit_approval_request_fn = submit_approval_request
submit_approval_request_for_user_fn = submit_approval_request_for_user
resubmit_approval_entries_fn = resubmit_approval_entries
update_approval_request_fn = update_approval_request
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_approvals.py -q`
Expected: PASS (5 passed).

- [ ] **Step 7: Commit**

```bash
git add src/clockify_mcp/domains/approvals.py tests/test_approvals.py
git commit -m "feat: approvals writes (submit/submit-for-user/resubmit/update)"
```

---

## Task 10: Register both domains in the server

**Files:**
- Modify: `src/clockify_mcp/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Extend the server tests** — in `tests/test_server.py`, add to the read-tools set in `test_build_server_registers_discovery_tools`:

```python
        "list_expenses",
        "get_expense",
        "list_expense_categories",
        "download_expense_receipt",
        "list_approval_requests",
```

Add to the write-tools set in `test_writes_registered_when_enabled`:

```python
        "create_expense", "update_expense", "delete_expense",
        "create_expense_category", "update_expense_category",
        "delete_expense_category", "archive_expense_category",
        "submit_approval_request", "submit_approval_request_for_user",
        "resubmit_approval_entries", "update_approval_request",
```

Also add two names to the negative assertion in `test_writes_not_registered_by_default`:

```python
    assert "create_expense" not in names
    assert "submit_approval_request" not in names
```

- [ ] **Step 2: Run the server tests to verify they fail**

Run: `uv run pytest tests/test_server.py -q`
Expected: FAIL — new names not registered yet.

- [ ] **Step 3: Register in `server.py`** — add to the `from .domains import (...)` block (keep ordering tidy):

```python
from .domains import (
    approvals,
    clients,
    expenses,
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

Add the two `register` calls in `build_server` (after `holidays.register(mcp, client)`):

```python
    time_off.register(mcp, client)
    holidays.register(mcp, client)
    expenses.register(mcp, client)
    approvals.register(mcp, client)
    return mcp
```

- [ ] **Step 4: Run the server tests to verify they pass**

Run: `uv run pytest tests/test_server.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all unit tests pass (live smoke still skipped), ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/clockify_mcp/server.py tests/test_server.py
git commit -m "feat: register expenses and approvals domains"
```

---

## Task 11: Live smoke round-trips (gated)

**Files:**
- Modify: `tests/test_live_smoke.py`

Expenses and approvals are paid features; the `_skip_if_feature_unavailable` helper added in Phase 5 already skips on 402/403/404. Reuse it.

- [ ] **Step 1: Extend the imports** in `tests/test_live_smoke.py` — add `approvals` and `expenses` to the `from clockify_mcp.domains import (...)` block.

- [ ] **Step 2: Add the expense-category round-trip** (append). This needs no receipt and no paid expense entry, so it is the most reliable expense write to smoke.

```python
async def test_live_expense_category_roundtrip(live):
    client, ws, _ = live
    try:
        created = await expenses.create_expense_category(
            client, workspace_id=ws, name=PREFIX + "cat"
        )
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
        return  # unreachable: _skip_if_feature_unavailable always raises
    cid = created["id"]
    try:
        updated = await expenses.update_expense_category(
            client, workspace_id=ws, category_id=cid, name=PREFIX + "cat2"
        )
        assert updated["id"] == cid
        await expenses.archive_expense_category(
            client, workspace_id=ws, category_id=cid, archived=True
        )
        listed = await expenses.list_expense_categories(client, workspace_id=ws, archived=True)
        cats = listed.get("categories", []) if isinstance(listed, dict) else listed
        assert any(c.get("id") == cid for c in cats)
    finally:
        await expenses.delete_expense_category(client, workspace_id=ws, category_id=cid)
```

- [ ] **Step 3: Add an expense round-trip with a receipt** (append). Creates a category, then an expense with a small receipt file, downloads the receipt back, then deletes both. Uses `tmp_path`.

```python
async def test_live_expense_with_receipt_roundtrip(live, tmp_path):
    client, ws, me_id = live
    try:
        category = await expenses.create_expense_category(
            client, workspace_id=ws, name=PREFIX + "exp-cat"
        )
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
        return  # unreachable: _skip_if_feature_unavailable always raises
    cid = category["id"]
    receipt = tmp_path / "receipt.txt"
    receipt.write_bytes(b"smoke-receipt")
    expense_id = None
    try:
        project = await projects.create_project(client, workspace_id=ws, name=PREFIX + "exp-proj")
        pid = project["id"]
        try:
            created = await expenses.create_expense(
                client, workspace_id=ws, amount=1.0, category_id=cid,
                date="2026-06-01T00:00:00Z", project_id=pid, user_id=me_id,
                notes=PREFIX + "exp", receipt_path=str(receipt),
            )
            expense_id = created["id"]
            file_id = created.get("fileId")
            if file_id:
                dest = tmp_path / "out.bin"
                meta = await expenses.download_expense_receipt(
                    client, workspace_id=ws, expense_id=expense_id,
                    file_id=file_id, save_path=str(dest),
                )
                assert meta["bytes"] > 0
        finally:
            if expense_id:
                await expenses.delete_expense(client, workspace_id=ws, expense_id=expense_id)
            await projects.update_project(client, workspace_id=ws, project_id=pid, archived=True)
            await projects.delete_project(client, workspace_id=ws, project_id=pid)
    finally:
        await expenses.delete_expense_category(client, workspace_id=ws, category_id=cid)
```

- [ ] **Step 4: Add an approval list smoke** (append). Submitting/approving a real period is intrusive (it locks time entries), so the live smoke only exercises the read plus the feature-availability guard; the write paths are covered by unit tests.

```python
async def test_live_approval_requests_list(live):
    client, ws, _ = live
    try:
        result = await approvals.list_approval_requests(client, workspace_id=ws, page_size=1)
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
        return  # unreachable: _skip_if_feature_unavailable always raises
    assert result is not None
```

- [ ] **Step 5: Confirm the default (non-live) run still passes**

Run: `uv run pytest -q`
Expected: all unit tests pass; live smoke now collects 3 more skipped tests.

- [ ] **Step 6: Run the live smoke locally (manual, optional)**

```bash
CLOCKIFY_LIVE_TEST=1 CLOCKIFY_API_KEY=... CLOCKIFY_ENABLE_WRITES=true \
    CLOCKIFY_LIVE_WORKSPACE_NAME="Alan Fuentes's workspace" \
    uv run pytest tests/test_live_smoke.py -q -s
```
Expected: prior tests pass; the 3 new ones pass or skip ("feature unavailable…"). If the expense create fails with a 400 about field names, the camelCase-vs-snake_case discrepancy is real — switch the `_form_value` keys in `create_expense`/`update_expense` to snake_case (`user_id`, `project_id`, `category_id`, `task_id`) and re-run. Capture the exact error first.

- [ ] **Step 7: Commit**

```bash
git add tests/test_live_smoke.py
git commit -m "test: gated live smoke for expenses, categories, and approvals"
```

---

## Task 12: Docs

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `CLAUDE.md`** — bump phase/tool counts and add the two domains.
  - Project Overview: Phase 0–5 → **Phase 0–6**; counts 27 read + 25 write / 11 domains → **32 read + 36 write / 13 domains**; add expenses/approvals to the writes-gated sentence; update "Remaining domains" to drop expenses + approvals (remaining: custom_fields, scheduling, invoices, webhooks).
  - Architecture "Key modules": add
    - `domains/expenses.py` — `list_expenses`, `get_expense`, `list_expense_categories`, `download_expense_receipt` (+ create/update/delete expense and create/update/delete/archive category when writes enabled; create/update use multipart with an optional receipt)
    - `domains/approvals.py` — `list_approval_requests` (+ submit/submit-for-user/resubmit/update when writes enabled)
  - Add a short bullet under the client description noting the new `post_multipart`/`put_multipart`/`get_bytes` methods (multipart receipt upload + binary download).
  - Development Conventions: update the `uv run pytest -q` expected count. Run the suite and use the exact "X passed, Y skipped" it prints.

- [ ] **Step 2: Update `README.md`** — add `expenses` and `approvals` rows to the tool/domain table mirroring the implemented tools; note both are paid Clockify features and that expense create/update support an optional local receipt file. Update any running totals (32 read + 36 write, 13 domains, Phase 0–6). README accurate to implemented state only.

- [ ] **Step 3: Full suite + lint one final time**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all pass, ruff clean.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document Phase 6 expenses + approvals tools"
```

---

## Self-Review

**Spec coverage (design §7 Phase 6 rows + the two user decisions):**
- expenses read — `list_expenses` (T3), `get_expense` (T3), `list_categories`→`list_expense_categories` (T3), `download_receipt`→`download_expense_receipt` (T4) ✓
- expenses write — `create/update/delete_expense` (T6, T7), `create/update/delete/archive_category` (T7) ✓
- approvals read — `list_approval_requests` (T8) ✓
- approvals write — `submit_approval_request` + (decision: extended) `submit_approval_request_for_user`, `resubmit_approval_entries`, `update_approval_request` (T9) ✓
- Client infra for the receipt decision: multipart (T1) + binary download (T2); receipt handled by local path on upload (T6) and download (T4) ✓
- Registration (T10), live smoke (T11), docs (T12) ✓

**Deviations from the original design table, justified:**
- `download_receipt` returns `{path, bytes, file_id}` after writing the file locally (user chose "full path-based") rather than returning inline bytes — keeps binaries out of model context.
- approvals gains two extra writes (`submit_approval_request_for_user`, `resubmit_approval_entries`) per the user's "extended coverage" choice; all verified in the OpenAPI spec.
- The `POST .../reports/expenses/detailed` expense report is intentionally NOT implemented (unverified host, not in the design's tool table).

**Type/name consistency:** Every `@mcp.tool()` function name in Tasks 5/7/9 matches the names asserted in Task 10's server tests and the `*_fn` aliases. Client signature additions (`data`/`files`/`raw`) are introduced in Task 1/2 and consumed in Tasks 4/6. Param keys: GET lists hyphenated (`user-id`, `page-size`, `sort-column`, `sort-order`, `archived`, `name`); JSON bodies camelCase (`hasUnitPrice`, `priceInCents`, `periodStart`, `state`, `archived`); multipart fields camelCase (`categoryId`, `projectId`, `userId`, `taskId`, `changeFields`, `file`).

**Placeholder scan:** No TBD/TODO/"handle edge cases" placeholders. Every code step shows complete code; the one conditional path (camelCase→snake_case fallback) is a documented contingency tied to a specific observable error, not a placeholder. The `return` after `_skip_if_feature_unavailable` is intentional (defensive; the helper always raises) and mirrors the Phase 5 live-smoke convention.
