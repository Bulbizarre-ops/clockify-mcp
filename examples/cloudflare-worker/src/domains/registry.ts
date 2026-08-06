import type { AccessMode } from "../clockify/access-mode.js";
import { timeTrackingEnabled, writesEnabled } from "../clockify/access-mode.js";

export type ToolTier = "read" | "time-tracking" | "full";

export type ToolDefinition = {
  name: string;
  tier: ToolTier;
  wave: 1 | 2 | 3;
  description: string;
};

/**
 * Wave 1 tool catalog. Names and access tiers match the Python server:
 * - reads always registered
 * - time-tracking adds create/update/delete_time_entry
 * - full adds stop_running_timer + CRUD for clients/projects/tasks/tags
 */
export const WAVE1_TOOLS: ToolDefinition[] = [
  { name: "get_current_user", tier: "read", wave: 1, description: "Get the authenticated Clockify user." },
  { name: "list_workspaces", tier: "read", wave: 1, description: "List workspaces for the authenticated user." },
  { name: "get_workspace", tier: "read", wave: 1, description: "Get a workspace by id." },
  { name: "list_users", tier: "read", wave: 1, description: "List users in a workspace." },
  { name: "list_clients", tier: "read", wave: 1, description: "List clients in a workspace." },
  { name: "get_client", tier: "read", wave: 1, description: "Get a client by id." },
  { name: "list_projects", tier: "read", wave: 1, description: "List projects in a workspace." },
  { name: "get_project", tier: "read", wave: 1, description: "Get a project by id." },
  { name: "list_tasks", tier: "read", wave: 1, description: "List tasks for a project." },
  { name: "get_task", tier: "read", wave: 1, description: "Get a task by id." },
  { name: "list_tags", tier: "read", wave: 1, description: "List tags in a workspace." },
  { name: "get_tag", tier: "read", wave: 1, description: "Get a tag by id." },
  { name: "list_time_entries", tier: "read", wave: 1, description: "List time entries for a user." },
  { name: "get_time_entry", tier: "read", wave: 1, description: "Get a time entry by id." },
  { name: "generate_summary_report", tier: "read", wave: 1, description: "Generate a summary report for a date range." },
  { name: "generate_detailed_report", tier: "read", wave: 1, description: "Generate a detailed report for a date range." },
  { name: "create_time_entry", tier: "time-tracking", wave: 1, description: "Create a time entry for the authenticated user." },
  { name: "update_time_entry", tier: "time-tracking", wave: 1, description: "Update a time entry by id." },
  { name: "delete_time_entry", tier: "time-tracking", wave: 1, description: "Delete a time entry by id." },
  { name: "stop_running_timer", tier: "full", wave: 1, description: "Stop a user's currently running timer." },
  { name: "create_client", tier: "full", wave: 1, description: "Create a client." },
  { name: "update_client", tier: "full", wave: 1, description: "Update a client." },
  { name: "delete_client", tier: "full", wave: 1, description: "Delete a client." },
  { name: "create_project", tier: "full", wave: 1, description: "Create a project." },
  { name: "update_project", tier: "full", wave: 1, description: "Update a project." },
  { name: "delete_project", tier: "full", wave: 1, description: "Delete a project." },
  { name: "create_task", tier: "full", wave: 1, description: "Create a task on a project." },
  { name: "update_task", tier: "full", wave: 1, description: "Update a task." },
  { name: "delete_task", tier: "full", wave: 1, description: "Delete a task." },
  { name: "create_tag", tier: "full", wave: 1, description: "Create a tag." },
  { name: "update_tag", tier: "full", wave: 1, description: "Update a tag." },
  { name: "delete_tag", tier: "full", wave: 1, description: "Delete a tag." },
];

function isAllowed(tier: ToolTier, mode: AccessMode): boolean {
  if (tier === "read") return true;
  if (tier === "time-tracking") return timeTrackingEnabled(mode);
  return writesEnabled(mode);
}

export function listToolsForMode(mode: AccessMode): ToolDefinition[] {
  return WAVE1_TOOLS.filter((tool) => isAllowed(tool.tier, mode));
}
