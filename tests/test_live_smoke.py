"""Live smoke tests against a real Clockify workspace.

Skipped unless CLOCKIFY_LIVE_TEST is set and a real CLOCKIFY_API_KEY is present.
Each test creates real data and deletes it again (try/finally cleanup). Names are
prefixed with 'mcp-smoke-' so any leftover artifacts are easy to spot.

Run:
    CLOCKIFY_LIVE_TEST=1 CLOCKIFY_API_KEY=... CLOCKIFY_ENABLE_WRITES=true \
        CLOCKIFY_LIVE_WORKSPACE_NAME="Alan Fuentes's workspace" \
        uv run pytest tests/test_live_smoke.py -q -s
"""

from __future__ import annotations

import os

import pytest

from clockify_mcp.client import ClockifyAPIError, ClockifyClient
from clockify_mcp.config import Config
from clockify_mcp.domains import (
    approvals,
    clients,
    custom_fields,
    expenses,
    holidays,
    invoices,
    projects,
    reports,
    scheduling,
    shared_reports,
    tags,
    tasks,
    time_entries,
    time_off,
    webhooks,
    workspaces,
)
from clockify_mcp.server import build_server

pytestmark = pytest.mark.skipif(
    not os.environ.get("CLOCKIFY_LIVE_TEST"),
    reason="set CLOCKIFY_LIVE_TEST=1 (and CLOCKIFY_API_KEY) to run live smoke tests",
)

PREFIX = "mcp-smoke-"


def _skip_if_feature_unavailable(exc: ClockifyAPIError) -> None:
    """Time off, holidays, expenses, and approvals are paid Clockify features; skip
    the round-trip when the plan doesn't include them. Most return 402/403/404, but
    some (e.g. expenses) return 400 with a 'no active subscription' message."""
    msg = str(exc).lower()
    no_subscription = "suscrip" in msg or "subscription" in msg
    if exc.status_code in (402, 403, 404) or (exc.status_code == 400 and no_subscription):
        pytest.skip(f"feature unavailable on this plan (HTTP {exc.status_code})")
    raise exc


async def _purge_smoke_artifacts(client: ClockifyClient, ws: str) -> None:
    """Remove any leftover ``mcp-smoke-*`` clients and projects from prior runs.

    Clients and projects enforce unique names and reject deletion while active, so an
    interrupted run (or one predating the archive-before-delete fix) leaves orphans that
    make ``create_*`` fail with 400 "ya existe". Sweep them — active and archived — so
    each run starts clean. Projects are purged before clients (a project may reference a
    client). Only ``mcp-smoke-`` prefixed data is touched.

    Note: we do NOT rely on the server-side ``name`` filter (its match semantics vary)
    nor pass ``archived`` to the clients list (that param is string-typed and unreliable
    when given a bool). Instead we fetch a large page and match the prefix in Python.
    The ``archived=True`` pass for projects uses the proper boolean filter.
    """
    seen_project_ids: set[str] = set()
    project_pages = [
        await projects.list_projects(client, workspace_id=ws, page_size=200),
        await projects.list_projects(client, workspace_id=ws, archived=True, page_size=200),
    ]
    for page in project_pages:
        for proj in page or []:
            pid = proj.get("id")
            if pid in seen_project_ids or not str(proj.get("name", "")).startswith(PREFIX):
                continue
            seen_project_ids.add(pid)
            if not proj.get("archived"):
                await projects.update_project(
                    client, workspace_id=ws, project_id=pid, archived=True
                )
            await projects.delete_project(client, workspace_id=ws, project_id=pid)

    for cli in await clients.list_clients(client, workspace_id=ws, page_size=200) or []:
        if not str(cli.get("name", "")).startswith(PREFIX):
            continue
        if not cli.get("archived"):
            await clients.update_client(
                client, workspace_id=ws, client_id=cli["id"], name=cli["name"], archived=True
            )
        await clients.delete_client(client, workspace_id=ws, client_id=cli["id"])


@pytest.fixture
async def live():
    env = dict(os.environ)
    env.setdefault("CLOCKIFY_ENABLE_WRITES", "true")
    config = Config.load(env=env)
    client = ClockifyClient(config)
    me = await workspaces.get_current_user(client)
    ws_id = config.default_workspace_id or me.get("defaultWorkspace") or me.get("activeWorkspace")
    wanted = os.environ.get("CLOCKIFY_LIVE_WORKSPACE_NAME")
    if wanted:
        all_ws = await workspaces.list_workspaces(client)
        match = [w for w in all_ws if w.get("name") == wanted]
        assert match, (
            f"workspace named {wanted!r} not found; have {[w.get('name') for w in all_ws]}"
        )
        ws_id = match[0]["id"]
    assert ws_id, "could not resolve a workspace id"
    await _purge_smoke_artifacts(client, ws_id)
    yield client, ws_id, me["id"]
    await client.aclose()


async def test_live_client_roundtrip(live):
    client, ws, _ = live
    created = await clients.create_client(client, workspace_id=ws, name=PREFIX + "client")
    cid = created["id"]
    try:
        updated = await clients.update_client(
            client,
            workspace_id=ws,
            client_id=cid,
            name=PREFIX + "client",
            note="updated by smoke test",
        )
        assert updated["id"] == cid
        fetched = await clients.get_client(client, workspace_id=ws, client_id=cid)
        assert fetched["id"] == cid
    finally:
        # The API rejects deleting an active client — archive first, then delete.
        await clients.update_client(
            client, workspace_id=ws, client_id=cid, name=PREFIX + "client", archived=True
        )
        await clients.delete_client(client, workspace_id=ws, client_id=cid)


async def test_live_tag_roundtrip(live):
    client, ws, _ = live
    created = await tags.create_tag(client, workspace_id=ws, name=PREFIX + "tag")
    gid = created["id"]
    try:
        updated = await tags.update_tag(client, workspace_id=ws, tag_id=gid, name=PREFIX + "tag2")
        assert updated["id"] == gid
    finally:
        await tags.delete_tag(client, workspace_id=ws, tag_id=gid)


async def test_live_project_and_task_roundtrip(live):
    client, ws, _ = live
    project = await projects.create_project(client, workspace_id=ws, name=PREFIX + "project")
    pid = project["id"]
    try:
        task = await tasks.create_task(
            client, workspace_id=ws, project_id=pid, name=PREFIX + "task"
        )
        tid = task["id"]
        try:
            done = await tasks.update_task(
                client, workspace_id=ws, project_id=pid, task_id=tid,
                name=PREFIX + "task", status="DONE",
            )
            assert done["id"] == tid
        finally:
            await tasks.delete_task(client, workspace_id=ws, project_id=pid, task_id=tid)
        await projects.update_project(client, workspace_id=ws, project_id=pid, note="smoke")
    finally:
        # The API rejects deleting an active project — archive first, then delete.
        await projects.update_project(client, workspace_id=ws, project_id=pid, archived=True)
        await projects.delete_project(client, workspace_id=ws, project_id=pid)


async def test_live_time_entry_roundtrip(live):
    client, ws, _ = live
    entry = await time_entries.create_time_entry(
        client,
        workspace_id=ws,
        start="2020-01-01T09:00:00Z",
        end="2020-01-01T10:00:00Z",
        description=PREFIX + "entry",
    )
    eid = entry["id"]
    try:
        updated = await time_entries.update_time_entry(
            client, workspace_id=ws, time_entry_id=eid,
            start="2020-01-01T09:00:00Z", description=PREFIX + "entry-edited",
        )
        assert updated["id"] == eid
    finally:
        await time_entries.delete_time_entry(client, workspace_id=ws, time_entry_id=eid)


async def test_live_holiday_roundtrip(live):
    client, ws, _ = live
    try:
        created = await holidays.create_holiday(
            client, workspace_id=ws, name=PREFIX + "holiday",
            start_date="2020-01-01", end_date="2020-01-01", everyone_including_new=True,
        )
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
        return  # unreachable: _skip_if_feature_unavailable always raises
    hid = created["id"]
    try:
        updated = await holidays.update_holiday(
            client, workspace_id=ws, holiday_id=hid, name=PREFIX + "holiday",
            start_date="2020-01-01", end_date="2020-01-02", occurs_annually=False,
            everyone_including_new=True,
        )
        assert updated["id"] == hid
    finally:
        await holidays.delete_holiday(client, workspace_id=ws, holiday_id=hid)


async def test_live_time_off_policy_roundtrip(live):
    client, ws, _ = live
    try:
        created = await time_off.create_time_off_policy(
            client, workspace_id=ws, name=PREFIX + "policy", everyone_including_new=True,
        )
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
        return  # unreachable: _skip_if_feature_unavailable always raises
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
    # Clockify rejects text/plain receipts — use a real (1x1) PNG.
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00"
        b"\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
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
        # categories must be archived before deletion
        await expenses.archive_expense_category(
            client, workspace_id=ws, category_id=cid, archived=True
        )
        await expenses.delete_expense_category(client, workspace_id=ws, category_id=cid)


async def test_live_approval_requests_list(live):
    client, ws, _ = live
    try:
        result = await approvals.list_approval_requests(client, workspace_id=ws, page_size=1)
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
        return  # unreachable: _skip_if_feature_unavailable always raises
    assert result is not None


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


async def test_live_reports(live):
    client, ws, _ = live
    rng = {"date_range_start": "2026-06-01T00:00:00Z", "date_range_end": "2026-06-07T23:59:59Z"}
    assert isinstance(await reports.generate_detailed_report(client, workspace_id=ws, **rng), dict)
    assert isinstance(await reports.generate_summary_report(client, workspace_id=ws, **rng), dict)
    assert isinstance(await reports.generate_weekly_report(client, workspace_id=ws, **rng), dict)


async def test_live_invoice_roundtrip(live):
    client, ws, _ = live
    cli = await clients.create_client(client, workspace_id=ws, name=PREFIX + "inv-client")
    cid = cli["id"]
    inv_id = None
    try:
        try:
            inv = await invoices.create_invoice(
                client, workspace_id=ws, client_id=cid, currency="USD",
                issued_date="2026-06-01T00:00:00Z", due_date="2026-06-15T00:00:00Z",
                number=PREFIX + "smoke",
            )
        except ClockifyAPIError as exc:
            _skip_if_feature_unavailable(exc)  # always raises
        inv_id = inv["id"]
        fetched = await invoices.get_invoice(client, workspace_id=ws, invoice_id=inv_id)
        assert fetched["id"] == inv_id
        await invoices.add_invoice_item(
            client, workspace_id=ws, invoice_id=inv_id, apply_taxes="NONE",
            description=PREFIX + "item", item_type="Service", quantity=1, unit_price=100,
        )
    finally:
        if inv_id:
            await invoices.delete_invoice(client, workspace_id=ws, invoice_id=inv_id)
        await clients.update_client(
            client, workspace_id=ws, client_id=cid, name=PREFIX + "inv-client", archived=True
        )
        await clients.delete_client(client, workspace_id=ws, client_id=cid)


async def test_live_scheduling_roundtrip(live):
    client, ws, me_id = live
    project = await projects.create_project(client, workspace_id=ws, name=PREFIX + "sched-proj")
    pid = project["id"]
    asg_id = None
    try:
        try:
            asg = await scheduling.create_assignment(
                client, workspace_id=ws, user_id=me_id, project_id=pid,
                start="2026-06-01T00:00:00Z", end="2026-06-01T23:59:59Z", hours_per_day=1.0,
            )
        except ClockifyAPIError as exc:
            _skip_if_feature_unavailable(exc)  # always raises
        asg_id = asg["id"] if isinstance(asg, dict) else asg[0]["id"]
    finally:
        if asg_id:
            await scheduling.delete_assignment(client, workspace_id=ws, assignment_id=asg_id)
        await projects.update_project(client, workspace_id=ws, project_id=pid, archived=True)
        await projects.delete_project(client, workspace_id=ws, project_id=pid)


async def test_live_approval_submit_withdraw(live):
    import datetime

    client, ws, _ = live
    today = datetime.date.today()
    last_monday = today - datetime.timedelta(days=today.weekday() + 7)  # a complete past week
    period_start = last_monday.strftime("%Y-%m-%dT00:00:00Z")
    entry = await time_entries.create_time_entry(
        client, workspace_id=ws,
        start=last_monday.strftime("%Y-%m-%dT09:00:00Z"),
        end=last_monday.strftime("%Y-%m-%dT10:00:00Z"),
        description=PREFIX + "appr",
    )
    eid = entry["id"]
    try:
        try:
            req = await approvals.submit_approval_request(
                client, workspace_id=ws, period_start=period_start, period="WEEKLY"
            )
        except ClockifyAPIError as exc:
            _skip_if_feature_unavailable(exc)  # always raises
        req_id = req.get("id") if isinstance(req, dict) else None
        assert req_id, f"no approval request id in {req!r}"
        await approvals.update_approval_request(
            client, workspace_id=ws, approval_request_id=req_id, state="WITHDRAWN_SUBMISSION"
        )
    finally:
        await time_entries.delete_time_entry(client, workspace_id=ws, time_entry_id=eid)


async def test_live_export_report(live, tmp_path):
    """Phase 8a: export_report writes a real binary file. Reports are a free feature,
    so this runs on any plan. CSV is the smallest export — assert non-empty bytes."""
    client, ws, _ = live
    dest = tmp_path / "report.csv"
    meta = await reports.export_report(
        client, workspace_id=ws, report_type="detailed", fmt="CSV", save_path=str(dest),
        date_range_start="2026-06-01T00:00:00Z", date_range_end="2026-06-07T23:59:59Z",
    )
    assert meta["bytes"] > 0
    assert meta["format"] == "CSV"
    assert dest.exists() and dest.stat().st_size == meta["bytes"]


async def test_live_create_for_user_and_stop_timer(live):
    """Phase 8a (FULL mode): create_time_entry_for_user starts a running timer for a
    user (here ourselves — a free feature), then stop_running_timer ends it. Clean up
    by deleting the entry."""
    client, ws, me_id = live
    created = await time_entries.create_time_entry_for_user(
        client, workspace_id=ws, user_id=me_id,
        start="2020-01-03T09:00:00Z", description=PREFIX + "for-user",
    )
    eid = created["id"]
    try:
        assert created.get("timeInterval", {}).get("end") in (None, ""), "expected a running timer"
        await time_entries.stop_running_timer(
            client, workspace_id=ws, user_id=me_id, end="2020-01-03T10:00:00Z"
        )
        stopped = await time_entries.get_time_entry(client, workspace_id=ws, time_entry_id=eid)
        assert stopped["timeInterval"]["end"], "timer should be stopped (end set)"
    finally:
        await time_entries.delete_time_entry(client, workspace_id=ws, time_entry_id=eid)


async def test_live_attendance_and_expense_reports(live):
    """Phase 8b: attendance + detailed-expense report generators. Both need paid add-ons,
    so skip when the plan/workspace doesn't have them."""
    client, ws, _ = live
    rng = {"date_range_start": "2026-06-01T00:00:00Z", "date_range_end": "2026-06-07T23:59:59Z"}
    try:
        att = await reports.generate_attendance_report(client, workspace_id=ws, **rng)
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)  # always raises
    assert att is not None
    try:
        exp = await reports.generate_expense_report(client, workspace_id=ws, **rng)
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)  # always raises
    assert "expenses" in exp


def _report_dicts(resp) -> list:
    """Collect report dicts from an untyped shared-reports list response. The list lives
    under an unspecified key (the response shape is `*/*` in the OpenAPI), so gather dicts
    from every list-valued field rather than guessing the key name."""
    if isinstance(resp, list):
        return [r for r in resp if isinstance(r, dict)]
    if isinstance(resp, dict):
        out = []
        for value in resp.values():
            if isinstance(value, list):
                out.extend(r for r in value if isinstance(r, dict))
        return out
    return []


async def test_live_shared_report_roundtrip(live):
    """Phase 8b: shared-report CRUD (reports host). Create -> get-by-id -> update -> delete.
    Skip if the plan doesn't allow shared reports."""
    client, ws, _ = live
    try:
        created = await shared_reports.create_shared_report(
            client, workspace_id=ws, name=PREFIX + "shared", type="SUMMARY",
            date_range_start="2026-06-01T00:00:00Z", date_range_end="2026-06-07T23:59:59Z",
        )
    except ClockifyAPIError as exc:
        _skip_if_feature_unavailable(exc)
        return  # unreachable
    sr_id = created["id"]
    try:
        fetched = await shared_reports.get_shared_report(client, shared_report_id=sr_id)
        assert fetched is not None
        await shared_reports.update_shared_report(
            client, workspace_id=ws, shared_report_id=sr_id, name=PREFIX + "shared2",
        )
        listed = await shared_reports.list_shared_reports(client, workspace_id=ws)
        assert listed is not None
        assert any(r.get("id") == sr_id for r in _report_dicts(listed)), (
            "created shared report not found in list response; "
            f"keys={list(listed) if isinstance(listed, dict) else type(listed).__name__}"
        )
    finally:
        await shared_reports.delete_shared_report(client, workspace_id=ws, shared_report_id=sr_id)


async def test_live_fetch_all_pagination(live):
    """Phase 8b: fetch_all on a list tool returns a concatenated list (free feature).
    Create a client, then list with fetch_all=True and confirm it is included."""
    client, ws, _ = live
    created = await clients.create_client(client, workspace_id=ws, name=PREFIX + "fa-client")
    cid = created["id"]
    try:
        everything = await clients.list_clients(
            client, workspace_id=ws, fetch_all=True, page_size=5
        )
        assert isinstance(everything, list)
        assert any(c.get("id") == cid for c in everything)
    finally:
        await clients.update_client(
            client, workspace_id=ws, client_id=cid, name=PREFIX + "fa-client", archived=True
        )
        await clients.delete_client(client, workspace_id=ws, client_id=cid)


async def test_live_time_tracking_self_scoped(live):
    """End-to-end check of the CLOCKIFY_ACCESS_MODE=time-tracking tier against the real
    API: gating holds (only time-entry writes register), current_user_id() resolves
    live, and the self-scoped create/duplicate wrappers (no user_id) work — logging
    hours as the authenticated user. Time entries are a free feature, so this runs."""
    _full, ws, me_id = live
    env = dict(os.environ)
    env["CLOCKIFY_ACCESS_MODE"] = "time-tracking"
    env["CLOCKIFY_DEFAULT_WORKSPACE_ID"] = ws
    env.pop("CLOCKIFY_ENABLE_WRITES", None)  # access_mode must drive, not the alias
    tt = ClockifyClient(Config.load(env=env))
    desc = PREFIX + "tt"
    try:
        mcp = build_server(tt)
        names = {t.name for t in await mcp.list_tools()}
        assert {
            "create_time_entry", "update_time_entry", "delete_time_entry",
            "duplicate_time_entry", "bulk_update_time_entries",
        } <= names
        assert "create_client" not in names  # gating holds against a real server build
        assert "create_invoice" not in names
        assert await tt.current_user_id() == me_id  # resolves live

        # create via the registered tool, then exercise the self-scoped duplicate
        # wrapper (it takes no user_id and resolves the authenticated user itself).
        await mcp.call_tool(
            "create_time_entry",
            {"start": "2020-01-02T09:00:00Z", "end": "2020-01-02T10:00:00Z", "description": desc},
        )
        listed = await time_entries.list_time_entries(
            tt, workspace_id=ws, user_id=me_id, description=desc
        )
        assert listed, "created time entry not found"
        await mcp.call_tool("duplicate_time_entry", {"time_entry_id": listed[0]["id"]})
    finally:
        try:
            leftovers = await time_entries.list_time_entries(
                tt, workspace_id=ws, user_id=me_id, description=desc
            )
            for entry in leftovers or []:
                if str(entry.get("description", "")).startswith(PREFIX):
                    await time_entries.delete_time_entry(
                        tt, workspace_id=ws, time_entry_id=entry["id"]
                    )
        finally:
            await tt.aclose()
