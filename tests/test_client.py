import json

import httpx
import pytest
import respx

from clockify_mcp.client import ClockifyAPIError, ClockifyClient
from clockify_mcp.config import Config
from clockify_mcp.errors import ErrorCategory


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


@respx.mock
async def test_error_body_is_sanitized(config):
    respx.get("https://api.clockify.me/api/v1/workspaces").mock(
        return_value=httpx.Response(403, json={"message": "denied", "detail": "key=test-key"})
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as exc:
        await client.get("workspaces")
    assert "test-key" not in str(exc.value.body)
    await client.aclose()


@respx.mock
async def test_429_retry_exhaustion_raises(config):
    route = respx.get("https://api.clockify.me/api/v1/workspaces").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, text="Too many requests")
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as exc:
        await client.get("workspaces")
    assert exc.value.status_code == 429
    assert route.call_count == 4  # 1 initial + 3 retries
    await client.aclose()


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
async def test_post_multipart_coerces_bool_and_list(config):
    route = respx.post("https://api.clockify.me/api/v1/workspaces/ws1/expenses").mock(
        return_value=httpx.Response(201, json={"id": "e1"})
    )
    client = ClockifyClient(config)
    await client.post_multipart(
        "workspaces/ws1/expenses",
        data={"billable": True, "changeFields": ["amount", "notes"]},
    )
    body = route.calls.last.request.content
    assert b"true" in body and b"True" not in body  # bool → lowercase
    # list value expands into repeated parts
    assert body.count(b'name="changeFields"') == 2
    assert b"amount" in body and b"notes" in body
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


async def test_access_mode_client_flags():
    tt = ClockifyClient(
        Config.load(env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ACCESS_MODE": "time-tracking"})
    )
    assert tt.time_tracking_enabled is True
    assert tt.writes_enabled is False
    await tt.aclose()
    full = ClockifyClient(
        Config.load(env={"CLOCKIFY_API_KEY": "k", "CLOCKIFY_ACCESS_MODE": "full"})
    )
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


@respx.mock
async def test_403_error_is_access_denied_with_hint(config):
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/x").mock(
        return_value=httpx.Response(403, json={"message": "Access Denied", "code": 501})
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as ei:
        await client.get("workspaces/ws1/x")
    exc = ei.value
    assert exc.category is ErrorCategory.ACCESS_DENIED
    assert exc.hint and "Workspace Settings" in exc.hint
    assert "[ACCESS_DENIED]" in str(exc)
    assert "Access Denied" in str(exc)  # original message preserved
    await client.aclose()


@respx.mock
async def test_400_subscription_is_plan_required(config):
    respx.post("https://api.clockify.me/api/v1/workspaces/ws1/expenses/categories").mock(
        return_value=httpx.Response(400, json={"message": "Sin suscripción activa."})
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as ei:
        await client.post("workspaces/ws1/expenses/categories", json={"name": "x"})
    assert ei.value.category is ErrorCategory.PLAN_REQUIRED
    await client.aclose()


@respx.mock
async def test_plain_validation_error_has_no_category(config):
    respx.put("https://api.clockify.me/api/v1/workspaces/ws1/clients/c1").mock(
        return_value=httpx.Response(400, json={"message": "Se requiere el nombre del cliente"})
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as ei:
        await client.put("workspaces/ws1/clients/c1", json={})
    exc = ei.value
    assert exc.category is None
    assert exc.hint is None
    assert str(exc) == "Clockify API error 400: Se requiere el nombre del cliente"
    await client.aclose()


@respx.mock
async def test_non_string_error_message_still_raises_cleanly(config):
    # a malformed error body (non-string message) must surface a ClockifyAPIError,
    # not crash the error path with AttributeError
    respx.get("https://api.clockify.me/api/v1/workspaces/ws1/x").mock(
        return_value=httpx.Response(400, json={"message": {"nested": "oops"}})
    )
    client = ClockifyClient(config)
    with pytest.raises(ClockifyAPIError) as ei:
        await client.get("workspaces/ws1/x")
    assert ei.value.status_code == 400
    assert ei.value.category is None
    await client.aclose()


@respx.mock
async def test_report_bytes_returns_raw_bytes(config):
    route = respx.post(
        "https://reports.api.clockify.me/v1/workspaces/ws1/reports/detailed"
    ).mock(return_value=httpx.Response(200, content=b"%PDF-1.4 fake"))
    client = ClockifyClient(config)
    data = await client.report_bytes(
        "workspaces/ws1/reports/detailed", {"exportType": "PDF"}
    )
    assert data == b"%PDF-1.4 fake"
    assert route.called
    await client.aclose()
