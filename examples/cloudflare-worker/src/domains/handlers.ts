import type { ClockifyClient } from "../clockify/client.js";
import { backupTimeEntries } from "./backup.js";
import { resolveWorkspaceId } from "./workspace.js";

type Dict = Record<string, unknown>;

function dropUndefined<T extends Dict>(obj: T): Dict {
  const out: Dict = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value !== undefined) out[key] = value;
  }
  return out;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function asBool(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function asStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  return value.filter((v): v is string => typeof v === "string");
}

export type ToolArgs = Dict;
export type ToolHandler = (args: ToolArgs) => Promise<unknown>;
export type Handlers = Record<string, ToolHandler>;

function pageParams(args: Dict): Record<string, number | undefined> {
  return {
    page: asNumber(args.page),
    "page-size": asNumber(args.page_size),
  };
}

export function createHandlers(client: ClockifyClient): Handlers {
  return {
    get_current_user: async () => client.get("user"),

    list_workspaces: async () => client.get("workspaces"),

    get_workspace: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      return client.get(`workspaces/${ws}`);
    },

    list_users: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      return client.get(`workspaces/${ws}/users`, {
        name: asString(args.name),
        email: asString(args.email),
        status: asString(args.status),
        ...pageParams(args),
      });
    },

    list_clients: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      return client.get(`workspaces/${ws}/clients`, {
        name: asString(args.name),
        archived: asBool(args.archived),
        ...pageParams(args),
      });
    },

    get_client: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const clientId = asString(args.client_id);
      if (!clientId) throw new Error("client_id is required");
      return client.get(`workspaces/${ws}/clients/${clientId}`);
    },

    create_client: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const name = asString(args.name);
      if (!name) throw new Error("name is required");
      return client.post(
        `workspaces/${ws}/clients`,
        dropUndefined({
          name,
          email: asString(args.email),
          address: asString(args.address),
          note: asString(args.note),
        }),
      );
    },

    update_client: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const clientId = asString(args.client_id);
      const name = asString(args.name);
      if (!clientId) throw new Error("client_id is required");
      if (!name) throw new Error("name is required");
      return client.put(
        `workspaces/${ws}/clients/${clientId}`,
        dropUndefined({
          name,
          email: asString(args.email),
          address: asString(args.address),
          note: asString(args.note),
          archived: asBool(args.archived),
        }),
      );
    },

    delete_client: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const clientId = asString(args.client_id);
      if (!clientId) throw new Error("client_id is required");
      return client.delete(`workspaces/${ws}/clients/${clientId}`);
    },

    list_projects: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      return client.get(`workspaces/${ws}/projects`, {
        name: asString(args.name),
        archived: asBool(args.archived),
        billable: asBool(args.billable),
        hydrated: asBool(args.hydrated),
        ...pageParams(args),
      });
    },

    get_project: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const projectId = asString(args.project_id);
      if (!projectId) throw new Error("project_id is required");
      return client.get(`workspaces/${ws}/projects/${projectId}`, {
        hydrated: asBool(args.hydrated),
      });
    },

    create_project: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const name = asString(args.name);
      if (!name) throw new Error("name is required");
      return client.post(
        `workspaces/${ws}/projects`,
        dropUndefined({
          name,
          clientId: asString(args.client_id),
          color: asString(args.color),
          note: asString(args.note),
          billable: asBool(args.billable),
          isPublic: asBool(args.is_public),
        }),
      );
    },

    update_project: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const projectId = asString(args.project_id);
      if (!projectId) throw new Error("project_id is required");
      return client.put(
        `workspaces/${ws}/projects/${projectId}`,
        dropUndefined({
          name: asString(args.name),
          clientId: asString(args.client_id),
          color: asString(args.color),
          note: asString(args.note),
          billable: asBool(args.billable),
          isPublic: asBool(args.is_public),
          archived: asBool(args.archived),
        }),
      );
    },

    delete_project: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const projectId = asString(args.project_id);
      if (!projectId) throw new Error("project_id is required");
      return client.delete(`workspaces/${ws}/projects/${projectId}`);
    },

    list_tasks: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const projectId = asString(args.project_id);
      if (!projectId) throw new Error("project_id is required");
      return client.get(`workspaces/${ws}/projects/${projectId}/tasks`, {
        name: asString(args.name),
        "is-active": asBool(args.is_active),
        ...pageParams(args),
      });
    },

    get_task: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const projectId = asString(args.project_id);
      const taskId = asString(args.task_id);
      if (!projectId) throw new Error("project_id is required");
      if (!taskId) throw new Error("task_id is required");
      return client.get(`workspaces/${ws}/projects/${projectId}/tasks/${taskId}`);
    },

    create_task: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const projectId = asString(args.project_id);
      const name = asString(args.name);
      if (!projectId) throw new Error("project_id is required");
      if (!name) throw new Error("name is required");
      return client.post(
        `workspaces/${ws}/projects/${projectId}/tasks`,
        dropUndefined({
          name,
          assigneeIds: asStringArray(args.assignee_ids),
          estimate: asString(args.estimate),
          status: asString(args.status),
        }),
      );
    },

    update_task: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const projectId = asString(args.project_id);
      const taskId = asString(args.task_id);
      const name = asString(args.name);
      if (!projectId) throw new Error("project_id is required");
      if (!taskId) throw new Error("task_id is required");
      if (!name) throw new Error("name is required");
      return client.put(
        `workspaces/${ws}/projects/${projectId}/tasks/${taskId}`,
        dropUndefined({
          name,
          assigneeIds: asStringArray(args.assignee_ids),
          estimate: asString(args.estimate),
          status: asString(args.status),
          billable: asBool(args.billable),
        }),
      );
    },

    delete_task: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const projectId = asString(args.project_id);
      const taskId = asString(args.task_id);
      if (!projectId) throw new Error("project_id is required");
      if (!taskId) throw new Error("task_id is required");
      return client.delete(
        `workspaces/${ws}/projects/${projectId}/tasks/${taskId}`,
      );
    },

    list_tags: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      return client.get(`workspaces/${ws}/tags`, {
        name: asString(args.name),
        archived: asBool(args.archived),
        ...pageParams(args),
      });
    },

    get_tag: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const tagId = asString(args.tag_id);
      if (!tagId) throw new Error("tag_id is required");
      return client.get(`workspaces/${ws}/tags/${tagId}`);
    },

    create_tag: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const name = asString(args.name);
      if (!name) throw new Error("name is required");
      return client.post(`workspaces/${ws}/tags`, { name });
    },

    update_tag: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const tagId = asString(args.tag_id);
      if (!tagId) throw new Error("tag_id is required");
      return client.put(
        `workspaces/${ws}/tags/${tagId}`,
        dropUndefined({
          name: asString(args.name),
          archived: asBool(args.archived),
        }),
      );
    },

    delete_tag: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const tagId = asString(args.tag_id);
      if (!tagId) throw new Error("tag_id is required");
      return client.delete(`workspaces/${ws}/tags/${tagId}`);
    },

    list_time_entries: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const userId = asString(args.user_id);
      if (!userId) throw new Error("user_id is required");
      return client.get(`workspaces/${ws}/user/${userId}/time-entries`, {
        description: asString(args.description),
        start: asString(args.start),
        end: asString(args.end),
        project: asString(args.project),
        task: asString(args.task),
        hydrated: asBool(args.hydrated),
        "in-progress": asBool(args.in_progress),
        ...pageParams(args),
      });
    },

    get_time_entry: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const timeEntryId = asString(args.time_entry_id);
      if (!timeEntryId) throw new Error("time_entry_id is required");
      return client.get(`workspaces/${ws}/time-entries/${timeEntryId}`, {
        hydrated: asBool(args.hydrated),
      });
    },

    create_time_entry: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const start = asString(args.start);
      if (!start) throw new Error("start is required");
      return client.post(
        `workspaces/${ws}/time-entries`,
        dropUndefined({
          start,
          end: asString(args.end),
          description: asString(args.description),
          projectId: asString(args.project_id),
          taskId: asString(args.task_id),
          tagIds: asStringArray(args.tag_ids),
          billable: asBool(args.billable),
          type: asString(args.type),
        }),
      );
    },

    update_time_entry: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const timeEntryId = asString(args.time_entry_id);
      const start = asString(args.start);
      if (!timeEntryId) throw new Error("time_entry_id is required");
      if (!start) throw new Error("start is required");
      return client.put(
        `workspaces/${ws}/time-entries/${timeEntryId}`,
        dropUndefined({
          start,
          end: asString(args.end),
          description: asString(args.description),
          projectId: asString(args.project_id),
          taskId: asString(args.task_id),
          tagIds: asStringArray(args.tag_ids),
          billable: asBool(args.billable),
          type: asString(args.type),
        }),
      );
    },

    bulk_update_time_entries: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const userId = asString(args.user_id);
      if (!userId) throw new Error("user_id is required");
      if (!Array.isArray(args.entries) || args.entries.length === 0) {
        throw new Error("entries is required and must be a non-empty array");
      }
      const payload = args.entries.map((raw, index) => {
        if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
          throw new Error(`entries[${index}] must be an object`);
        }
        const entry = raw as Dict;
        const id = asString(entry.id);
        if (!id) throw new Error(`entries[${index}].id is required`);
        // Accept snake_case (MCP) or camelCase (Clockify / Python-style) fields.
        return dropUndefined({
          id,
          start: asString(entry.start),
          end: asString(entry.end),
          description: asString(entry.description),
          projectId:
            asString(entry.project_id) ?? asString(entry.projectId),
          taskId: asString(entry.task_id) ?? asString(entry.taskId),
          tagIds: asStringArray(entry.tag_ids) ?? asStringArray(entry.tagIds),
          billable: asBool(entry.billable),
          type: asString(entry.type),
        });
      });
      return client.put(`workspaces/${ws}/user/${userId}/time-entries`, payload);
    },

    delete_time_entry: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const timeEntryId = asString(args.time_entry_id);
      if (!timeEntryId) throw new Error("time_entry_id is required");
      return client.delete(`workspaces/${ws}/time-entries/${timeEntryId}`);
    },

    stop_running_timer: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const userId = asString(args.user_id);
      const end = asString(args.end);
      if (!userId) throw new Error("user_id is required");
      if (!end) throw new Error("end is required");
      return client.patch(`workspaces/${ws}/user/${userId}/time-entries`, { end });
    },

    generate_summary_report: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const start = asString(args.date_range_start);
      const end = asString(args.date_range_end);
      if (!start || !end) {
        throw new Error("date_range_start and date_range_end are required");
      }
      const groups = asStringArray(args.groups) ?? ["PROJECT"];
      return client.report(
        `workspaces/${ws}/reports/summary`,
        dropUndefined({
          dateRangeStart: start,
          dateRangeEnd: end,
          summaryFilter: dropUndefined({
            groups,
            sortColumn: asString(args.sort_column),
          }),
        }),
      );
    },

    generate_detailed_report: async (args) => {
      const ws = resolveWorkspaceId(client, args.workspace_id);
      const start = asString(args.date_range_start);
      const end = asString(args.date_range_end);
      if (!start || !end) {
        throw new Error("date_range_start and date_range_end are required");
      }
      return client.report(
        `workspaces/${ws}/reports/detailed`,
        dropUndefined({
          dateRangeStart: start,
          dateRangeEnd: end,
          detailedFilter: dropUndefined({
            page: asNumber(args.page),
            pageSize: asNumber(args.page_size),
            sortColumn: asString(args.sort_column),
          }),
        }),
      );
    },

    backup_time_entries: async (args) => backupTimeEntries(client, args),
  };
}
