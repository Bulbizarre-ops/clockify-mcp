"""MCP server entrypoint for the Clockify API.

Each domain module owns its tools and registers them via register(mcp, client),
keeping this layer thin. Read-only by default; write tools register only when the
operator sets CLOCKIFY_ENABLE_WRITES.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Literal

from .client import ClockifyClient
from .config import Config
from .telemetry import InstrumentedFastMCP, Telemetry, build_telemetry
from .domains import (
    approvals,
    clients,
    custom_fields,
    expenses,
    groups,
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
    users,
    webhooks,
    workspaces,
)

INSTRUCTIONS = """\
Tools for the Clockify time-tracking API. Read-only by default; write tools are \
registered only when the operator sets CLOCKIFY_ENABLE_WRITES.

Almost every Clockify operation is scoped to a workspace. Tools accept an \
optional workspace_id; when omitted they use the configured default workspace. \
If there is no default and none is given, the tool returns an error asking you \
to resolve one first.

ACCESS MODES: write tools register based on CLOCKIFY_ACCESS_MODE — `read` (default, \
no writes), `time-tracking` (only time-entry writes, for logging hours), or `full` \
(all writes). CLOCKIFY_ENABLE_WRITES=true is equivalent to `full`. In time-tracking \
mode, duplicate/bulk time-entry tools always act on the authenticated user; for \
update/delete by entry id, confirm with the user before changing an entry that may \
belong to someone else.

DISCOVERY: Call get_current_user and list_workspaces to resolve the workspace, \
list_users to resolve people, and the list_* tools to resolve projects, tasks, \
clients, and tags before filtering or (in later phases) creating anything.

ERRORS: when a tool fails, a ClockifyAPIError carries a category that tells you what \
to do. PLAN_REQUIRED (402, or a "subscription" message) — the workspace's plan does \
not include this feature; tell the user to upgrade it (e.g. Standard/Pro); do not \
retry. ACCESS_DENIED (403) — the feature is not enabled for this workspace (an admin \
must enable it in Clockify → Workspace Settings) OR the API key's user lacks the \
required role; surface both possibilities; do not retry. AUTH (401) — the API key is \
missing, invalid, or revoked. Always relay the cause to the user instead of retrying \
blindly.

DISAMBIGUATION: When a name search returns multiple matches, NEVER choose on \
your own. Present ALL matching options with their IDs and names and ask the user \
to choose.\
"""


def build_server(client: ClockifyClient, telemetry: Telemetry | None = None) -> InstrumentedFastMCP:
    """Build the MCP server and register all enabled domain tools."""
    mcp = InstrumentedFastMCP(
        name="clockify",
        instructions=INSTRUCTIONS,
        telemetry=telemetry or Telemetry(),
    )
    workspaces.register(mcp, client)
    users.register(mcp, client)
    groups.register(mcp, client)
    clients.register(mcp, client)
    projects.register(mcp, client)
    tags.register(mcp, client)
    tasks.register(mcp, client)
    time_entries.register(mcp, client)
    reports.register(mcp, client)
    shared_reports.register(mcp, client)
    time_off.register(mcp, client)
    holidays.register(mcp, client)
    expenses.register(mcp, client)
    approvals.register(mcp, client)
    custom_fields.register(mcp, client)
    scheduling.register(mcp, client)
    invoices.register(mcp, client)
    webhooks.register(mcp, client)
    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="clockify-mcp")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio).",
    )
    args = parser.parse_args()

    warning = insecure_transport_warning(args.transport)
    if warning:
        print(warning, file=sys.stderr)

    config = Config.load(env=os.environ)
    telemetry = build_telemetry(config)
    client = ClockifyClient(config, telemetry=telemetry)
    mcp = build_server(client, telemetry=telemetry)
    try:
        mcp.run(transport=_transport(args.transport))
    finally:
        telemetry.shutdown()


def insecure_transport_warning(transport: str) -> str | None:
    if transport == "stdio":
        return None
    return (
        f"WARNING: transport '{transport}' has no built-in auth. It exposes every "
        "Clockify operation through the server's stored API key. Bind it to loopback "
        "or run it behind an authenticated reverse proxy; never expose it directly "
        "to an untrusted network."
    )


def _transport(value: str) -> Literal["stdio", "sse", "streamable-http"]:
    return value  # type: ignore[return-value]


if __name__ == "__main__":
    main()
