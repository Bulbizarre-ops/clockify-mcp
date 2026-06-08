# tests/test_expenses.py
import json

import httpx
import pytest
import respx

from clockify_mcp.client import ClockifyClient
from clockify_mcp.domains import expenses


async def test_create_expense_missing_receipt_raises_clear_error(config_writes):
    client = ClockifyClient(config_writes)
    with pytest.raises(FileNotFoundError, match="receipt_path not found"):
        await expenses.create_expense(
            client, amount=1.0, category_id="c1", date="2026-06-01T00:00:00Z",
            project_id="p1", user_id="u1", receipt_path="/no/such/receipt.pdf",
        )
    await client.aclose()


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
