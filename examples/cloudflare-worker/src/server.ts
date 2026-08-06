import { McpServer } from "@modelcontextprotocol/server";
import { z } from "zod";
import type { AccessMode } from "./clockify/access-mode.js";
import type { ClockifyClient } from "./clockify/client.js";
import { ClockifyAPIError } from "./clockify/client.js";
import type { ClockifyPlan } from "./clockify/plan.js";
import { createHandlers } from "./domains/handlers.js";
import { listToolsForMode } from "./domains/registry.js";

const INSTRUCTIONS = `\
Tools for the Clockify time-tracking API over Streamable HTTP (Cloudflare Worker).

Wave 1 tools (workspaces, users, clients, projects, tasks, tags, time entries, \
summary/detailed reports, backup) work on the Free Clockify plan. Paid domains \
(time off, holidays, expenses, approvals, custom fields, scheduling, invoices) \
are not registered yet; when added they require Standard/Pro and may be gated by \
DEFAULT_PLAN / X-Clockify-Plan.

ACCESS MODES: write tools register based on access mode — read (default, no writes), \
time-tracking (only time-entry create/update/delete), or full (all writes including \
clients/projects/tasks/tags and backup).

ERRORS: when a tool fails, the message may be prefixed with a category. \
PLAN_REQUIRED — the workspace plan does not include this feature; tell the user to \
upgrade (e.g. Standard/Pro); do not retry. ACCESS_DENIED — the feature is not enabled \
in Clockify → Workspace Settings OR the API key's user lacks the required role; \
surface both possibilities; do not retry. AUTH — the API key is missing, invalid, or \
revoked. Always relay the cause to the user instead of retrying blindly.

DISCOVERY: Call get_current_user and list_workspaces to resolve the workspace, \
list_users to resolve people, and the list_* tools to resolve projects, tasks, \
clients, and tags before filtering or creating anything.\
`;

const workspaceId = z
  .string()
  .optional()
  .describe(
    "Workspace id; omit to use X-Clockify-Workspace-Id when provided.",
  );

function jsonResult(data: unknown) {
  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(data, null, 2),
      },
    ],
  };
}

function errorResult(error: unknown) {
  if (error instanceof ClockifyAPIError) {
    const lines = [error.message];
    if (error.category) {
      lines[0] = `[${error.category}] ${error.message}`;
      if (error.hint) lines.push(error.hint);
    }
    return {
      content: [{ type: "text" as const, text: lines.join("\n") }],
      isError: true,
    };
  }
  const message = error instanceof Error ? error.message : String(error);
  return {
    content: [{ type: "text" as const, text: message }],
    isError: true,
  };
}

type SchemaMap = Record<string, Record<string, z.ZodTypeAny>>;

const SCHEMAS: SchemaMap = {
  get_current_user: {},
  list_workspaces: {},
  get_workspace: { workspace_id: workspaceId },
  list_users: {
    workspace_id: workspaceId,
    name: z.string().optional(),
    email: z.string().optional(),
    status: z.string().optional(),
    page: z.number().int().optional(),
    page_size: z.number().int().optional(),
  },
  list_clients: {
    workspace_id: workspaceId,
    name: z.string().optional(),
    archived: z.boolean().optional(),
    page: z.number().int().optional(),
    page_size: z.number().int().optional(),
  },
  get_client: {
    client_id: z.string().describe("Client id."),
    workspace_id: workspaceId,
  },
  create_client: {
    name: z.string().describe("Client name."),
    workspace_id: workspaceId,
    email: z.string().optional(),
    address: z.string().optional(),
    note: z.string().optional(),
  },
  update_client: {
    client_id: z.string(),
    name: z.string(),
    workspace_id: workspaceId,
    email: z.string().optional(),
    address: z.string().optional(),
    note: z.string().optional(),
    archived: z.boolean().optional(),
  },
  delete_client: {
    client_id: z.string(),
    workspace_id: workspaceId,
  },
  list_projects: {
    workspace_id: workspaceId,
    name: z.string().optional(),
    archived: z.boolean().optional(),
    billable: z.boolean().optional(),
    hydrated: z.boolean().optional(),
    page: z.number().int().optional(),
    page_size: z.number().int().optional(),
  },
  get_project: {
    project_id: z.string(),
    workspace_id: workspaceId,
    hydrated: z.boolean().optional(),
  },
  create_project: {
    name: z.string(),
    workspace_id: workspaceId,
    client_id: z.string().optional(),
    color: z.string().optional(),
    note: z.string().optional(),
    billable: z.boolean().optional(),
    is_public: z.boolean().optional(),
  },
  update_project: {
    project_id: z.string(),
    workspace_id: workspaceId,
    name: z.string().optional(),
    client_id: z.string().optional(),
    color: z.string().optional(),
    note: z.string().optional(),
    billable: z.boolean().optional(),
    is_public: z.boolean().optional(),
    archived: z.boolean().optional(),
  },
  delete_project: {
    project_id: z.string(),
    workspace_id: workspaceId,
  },
  list_tasks: {
    project_id: z.string(),
    workspace_id: workspaceId,
    name: z.string().optional(),
    is_active: z.boolean().optional(),
    page: z.number().int().optional(),
    page_size: z.number().int().optional(),
  },
  get_task: {
    project_id: z.string(),
    task_id: z.string(),
    workspace_id: workspaceId,
  },
  create_task: {
    project_id: z.string(),
    name: z.string(),
    workspace_id: workspaceId,
    assignee_ids: z.array(z.string()).optional(),
    estimate: z.string().optional(),
    status: z.string().optional(),
  },
  update_task: {
    project_id: z.string(),
    task_id: z.string(),
    name: z.string(),
    workspace_id: workspaceId,
    assignee_ids: z.array(z.string()).optional(),
    estimate: z.string().optional(),
    status: z.string().optional(),
    billable: z.boolean().optional(),
  },
  delete_task: {
    project_id: z.string(),
    task_id: z.string(),
    workspace_id: workspaceId,
  },
  list_tags: {
    workspace_id: workspaceId,
    name: z.string().optional(),
    archived: z.boolean().optional(),
    page: z.number().int().optional(),
    page_size: z.number().int().optional(),
  },
  get_tag: {
    tag_id: z.string(),
    workspace_id: workspaceId,
  },
  create_tag: {
    name: z.string(),
    workspace_id: workspaceId,
  },
  update_tag: {
    tag_id: z.string(),
    workspace_id: workspaceId,
    name: z.string().optional(),
    archived: z.boolean().optional(),
  },
  delete_tag: {
    tag_id: z.string(),
    workspace_id: workspaceId,
  },
  list_time_entries: {
    user_id: z.string(),
    workspace_id: workspaceId,
    description: z.string().optional(),
    start: z.string().optional(),
    end: z.string().optional(),
    project: z.string().optional(),
    task: z.string().optional(),
    hydrated: z.boolean().optional(),
    in_progress: z.boolean().optional(),
    page: z.number().int().optional(),
    page_size: z.number().int().optional(),
  },
  get_time_entry: {
    time_entry_id: z.string(),
    workspace_id: workspaceId,
    hydrated: z.boolean().optional(),
  },
  create_time_entry: {
    start: z.string().describe("ISO-8601 start; omit end to start a timer."),
    workspace_id: workspaceId,
    end: z.string().optional(),
    description: z.string().optional(),
    project_id: z.string().optional(),
    task_id: z.string().optional(),
    tag_ids: z.array(z.string()).optional(),
    billable: z.boolean().optional(),
    type: z.string().optional(),
  },
  update_time_entry: {
    time_entry_id: z.string(),
    start: z.string(),
    workspace_id: workspaceId,
    end: z.string().optional(),
    description: z.string().optional(),
    project_id: z.string().optional(),
    task_id: z.string().optional(),
    tag_ids: z.array(z.string()).optional(),
    billable: z.boolean().optional(),
    type: z.string().optional(),
  },
  bulk_update_time_entries: {
    user_id: z
      .string()
      .describe(
        "User whose entries to edit; resolve with get_current_user or list_users.",
      ),
    entries: z
      .array(
        z.object({
          id: z.string().describe("Time entry id to update."),
          start: z.string().optional(),
          end: z.string().optional(),
          description: z.string().optional(),
          project_id: z.string().optional(),
          task_id: z.string().optional(),
          tag_ids: z.array(z.string()).optional(),
          billable: z.boolean().optional(),
          type: z.string().optional(),
        }),
      )
      .min(1)
      .describe(
        "Entries to edit; each needs id plus fields to change (project_id, task_id, tag_ids, …).",
      ),
    workspace_id: workspaceId,
  },
  delete_time_entry: {
    time_entry_id: z.string(),
    workspace_id: workspaceId,
  },
  stop_running_timer: {
    user_id: z.string(),
    end: z.string().describe("ISO-8601 end time for the running timer."),
    workspace_id: workspaceId,
  },
  generate_summary_report: {
    date_range_start: z.string(),
    date_range_end: z.string(),
    workspace_id: workspaceId,
    groups: z.array(z.string()).optional(),
    sort_column: z.string().optional(),
  },
  generate_detailed_report: {
    date_range_start: z.string(),
    date_range_end: z.string(),
    workspace_id: workspaceId,
    page: z.number().int().optional(),
    page_size: z.number().int().optional(),
    sort_column: z.string().optional(),
  },
  backup_time_entries: {
    destination_workspace_id: z
      .string()
      .optional()
      .describe(
        "Existing dedicated backup workspace id. Omit if using destination_workspace_name.",
      ),
    destination_workspace_name: z
      .string()
      .optional()
      .describe(
        "Backup workspace name: reuse if it exists, otherwise create it (POST /workspaces with Cake organizationId).",
      ),
    organization_id: z
      .string()
      .optional()
      .describe(
        "Cake organization id required by Clockify when creating a workspace. Defaults to source workspace cakeOrganizationId.",
      ),
    source_workspace_id: workspaceId.describe(
      "Workspace to read from; omit to use X-Clockify-Workspace-Id / default.",
    ),
    user_id: z
      .string()
      .optional()
      .describe("User whose entries to backup; defaults to the authenticated user."),
    start: z
      .string()
      .optional()
      .describe("Optional ISO-8601 lower bound filter on time entries."),
    end: z
      .string()
      .optional()
      .describe("Optional ISO-8601 upper bound filter on time entries."),
    dry_run: z
      .boolean()
      .optional()
      .describe("When true, report what would be copied without writing."),
    force: z
      .boolean()
      .optional()
      .describe(
        "When true, skip idempotence checks and re-copy even if the destination already has matching entries.",
      ),
  },
};

export function createClockifyMcpServer(
  client: ClockifyClient,
  accessMode: AccessMode,
  plan: ClockifyPlan = "all",
): McpServer {
  const server = new McpServer(
    {
      name: "clockify-mcp",
      version: "0.1.0",
    },
    { instructions: INSTRUCTIONS },
  );
  const handlers = createHandlers(client);
  const tools = listToolsForMode(accessMode, plan);

  for (const tool of tools) {
    const handler = handlers[tool.name];
    const inputSchema = SCHEMAS[tool.name];
    if (!handler || !inputSchema) {
      throw new Error(`Missing schema/handler for tool ${tool.name}`);
    }
    server.registerTool(
      tool.name,
      {
        description: tool.description,
        inputSchema,
      },
      async (args) => {
        try {
          const data = await handler(args as Record<string, unknown>);
          return jsonResult(data);
        } catch (error) {
          return errorResult(error);
        }
      },
    );
  }

  return server;
}
