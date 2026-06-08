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
    respx.post(
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
