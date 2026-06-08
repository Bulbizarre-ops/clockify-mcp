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


async def test_build_server_registers_discovery_tools(config):
    from clockify_mcp.client import ClockifyClient
    from clockify_mcp.server import build_server

    client = ClockifyClient(config)
    mcp = build_server(client)
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert {
        "get_current_user",
        "list_workspaces",
        "get_workspace",
        "list_users",
        "get_user_member_profile",
        "find_user_team_manager",
        "list_user_groups",
        "list_clients",
        "get_client",
        "list_projects",
        "get_project",
        "list_tags",
        "get_tag",
        "list_tasks",
        "get_task",
        "list_time_entries",
        "get_time_entry",
        "generate_detailed_report",
        "generate_summary_report",
        "generate_weekly_report",
        "export_report",
        "list_time_off_policies",
        "get_time_off_policy",
        "list_time_off_balances_by_policy",
        "list_time_off_balances_by_user",
        "list_time_off_requests",
        "list_holidays",
        "list_holidays_in_period",
        "list_expenses",
        "get_expense",
        "list_expense_categories",
        "download_expense_receipt",
        "list_approval_requests",
        "list_workspace_custom_fields",
        "list_project_custom_fields",
        "list_scheduled_assignments",
        "get_project_scheduling_totals",
        "get_user_scheduling_totals",
        "list_invoices",
        "get_invoice",
        "get_invoice_payments",
        "list_webhooks",
        "get_webhook",
        "get_webhook_logs",
    } <= names


def test_insecure_transport_warning():
    from clockify_mcp.server import insecure_transport_warning

    assert insecure_transport_warning("stdio") is None
    assert "auth" in insecure_transport_warning("sse")
    assert insecure_transport_warning("streamable-http")


async def test_writes_not_registered_by_default(config):
    from clockify_mcp.client import ClockifyClient
    from clockify_mcp.server import build_server

    client = ClockifyClient(config)
    mcp = build_server(client)
    names = {t.name for t in await mcp.list_tools()}
    assert "create_client" not in names
    assert "delete_client" not in names
    assert "create_holiday" not in names
    assert "create_time_off_policy" not in names
    assert "create_expense" not in names
    assert "submit_approval_request" not in names
    assert "create_workspace_custom_field" not in names


async def test_writes_registered_when_enabled(config_writes):
    from clockify_mcp.client import ClockifyClient
    from clockify_mcp.server import build_server

    client = ClockifyClient(config_writes)
    mcp = build_server(client)
    names = {t.name for t in await mcp.list_tools()}
    assert {
        "create_client", "update_client", "delete_client",
        "create_project", "update_project", "delete_project",
        "create_task", "update_task", "delete_task",
        "create_tag", "update_tag", "delete_tag",
        "create_time_entry", "update_time_entry", "delete_time_entry",
        "duplicate_time_entry", "bulk_update_time_entries",
        "create_time_entry_for_user", "stop_running_timer",
        "create_time_off_policy", "create_time_off_request",
        "approve_time_off_request", "reject_time_off_request", "withdraw_time_off_request",
        "create_holiday", "update_holiday", "delete_holiday",
        "create_expense", "update_expense", "delete_expense",
        "create_expense_category", "update_expense_category",
        "delete_expense_category", "archive_expense_category",
        "submit_approval_request", "submit_approval_request_for_user",
        "resubmit_approval_entries", "update_approval_request",
        "create_workspace_custom_field", "update_workspace_custom_field",
        "delete_workspace_custom_field",
        "set_project_custom_field", "remove_project_custom_field",
        "create_assignment", "update_assignment", "delete_assignment",
        "publish_assignments", "copy_assignment",
        "create_invoice", "update_invoice", "change_invoice_status",
        "duplicate_invoice", "delete_invoice",
        "add_invoice_item", "import_invoice_items",
        "add_invoice_payment", "delete_invoice_payment",
        "create_webhook", "update_webhook", "delete_webhook", "generate_webhook_token",
    } <= names


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
    assert "create_time_entry_for_user" not in names
    assert "stop_running_timer" not in names


def test_instructions_describe_access_modes():
    from clockify_mcp.server import INSTRUCTIONS

    assert "time-tracking" in INSTRUCTIONS
    assert "CLOCKIFY_ACCESS_MODE" in INSTRUCTIONS


def test_instructions_describe_error_categories():
    from clockify_mcp.server import INSTRUCTIONS

    assert "PLAN_REQUIRED" in INSTRUCTIONS
    assert "ACCESS_DENIED" in INSTRUCTIONS
    assert "Workspace Settings" in INSTRUCTIONS
