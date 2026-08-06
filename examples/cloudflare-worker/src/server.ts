import { McpServer } from "@modelcontextprotocol/server";
import { z } from "zod";
import type { AccessMode } from "./clockify/access-mode.js";
import type { ClockifyClient } from "./clockify/client.js";
import { ClockifyAPIError } from "./clockify/client.js";
import { createHandlers } from "./domains/handlers.js";
import { listToolsForMode } from "./domains/registry.js";

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
  const message =
    error instanceof ClockifyAPIError
      ? error.message
      : error instanceof Error
        ? error.message
        : String(error);
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
};

export function createClockifyMcpServer(
  client: ClockifyClient,
  accessMode: AccessMode,
): McpServer {
  const server = new McpServer({
    name: "clockify-mcp",
    version: "0.1.0",
  });
  const handlers = createHandlers(client);
  const tools = listToolsForMode(accessMode);

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
