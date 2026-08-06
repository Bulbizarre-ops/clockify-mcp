import type { AccessMode } from "../clockify/access-mode.js";
import { timeTrackingEnabled, writesEnabled } from "../clockify/access-mode.js";
import {
  planIncludes,
  type ClockifyPlan,
  type ToolMinPlan,
} from "../clockify/plan.js";

export type ToolTier = "read" | "time-tracking" | "full";

export type ToolDefinition = {
  name: string;
  tier: ToolTier;
  wave: 1 | 2 | 3;
  /** Minimum Clockify workspace plan that includes this tool. */
  minPlan: ToolMinPlan;
  description: string;
};

function tool(
  name: string,
  tier: ToolTier,
  wave: 1 | 2 | 3,
  description: string,
  minPlan: ToolMinPlan = "free",
): ToolDefinition {
  return { name, tier, wave, minPlan, description };
}

/**
 * Tool catalog (wave 1 core + selected wave 2 ops).
 * Access tiers match the Python server where applicable.
 * All current tools are Free-compatible (`minPlan: "free"`).
 */
export const WAVE1_TOOLS: ToolDefinition[] = [
  tool("get_current_user", "read", 1, "Get the authenticated Clockify user."),
  tool("list_workspaces", "read", 1, "List workspaces for the authenticated user."),
  tool("get_workspace", "read", 1, "Get a workspace by id."),
  tool("list_users", "read", 1, "List users in a workspace."),
  tool("list_clients", "read", 1, "List clients in a workspace."),
  tool("get_client", "read", 1, "Get a client by id."),
  tool("list_projects", "read", 1, "List projects in a workspace."),
  tool("get_project", "read", 1, "Get a project by id."),
  tool("list_tasks", "read", 1, "List tasks for a project."),
  tool("get_task", "read", 1, "Get a task by id."),
  tool("list_tags", "read", 1, "List tags in a workspace."),
  tool("get_tag", "read", 1, "Get a tag by id."),
  tool("list_time_entries", "read", 1, "List time entries for a user."),
  tool("get_time_entry", "read", 1, "Get a time entry by id."),
  tool("generate_summary_report", "read", 1, "Generate a summary report for a date range."),
  tool("generate_detailed_report", "read", 1, "Generate a detailed report for a date range."),
  tool("create_time_entry", "time-tracking", 1, "Create a time entry for the authenticated user."),
  tool("update_time_entry", "time-tracking", 1, "Update a time entry by id."),
  tool("delete_time_entry", "time-tracking", 1, "Delete a time entry by id."),
  tool(
    "bulk_update_time_entries",
    "time-tracking",
    2,
    "Bulk-edit several of a user's time entries (reclassify project/task/tags). Each entry needs id plus fields to change.",
  ),
  tool("stop_running_timer", "full", 1, "Stop a user's currently running timer."),
  tool("create_client", "full", 1, "Create a client."),
  tool("update_client", "full", 1, "Update a client."),
  tool("delete_client", "full", 1, "Delete a client."),
  tool("create_project", "full", 1, "Create a project."),
  tool("update_project", "full", 1, "Update a project."),
  tool("delete_project", "full", 1, "Delete a project."),
  tool("create_task", "full", 1, "Create a task on a project."),
  tool("update_task", "full", 1, "Update a task."),
  tool("delete_task", "full", 1, "Delete a task."),
  tool("create_tag", "full", 1, "Create a tag."),
  tool("update_tag", "full", 1, "Update a tag."),
  tool("delete_tag", "full", 1, "Delete a tag."),
  tool(
    "backup_time_entries",
    "full",
    2,
    "Backup completed time entries into a dedicated workspace (idempotent: skips duplicates via [clk-backup:id] marker / fingerprint). Pass destination_workspace_id or destination_workspace_name.",
  ),
];

function isAllowed(tier: ToolTier, mode: AccessMode): boolean {
  if (tier === "read") return true;
  if (tier === "time-tracking") return timeTrackingEnabled(mode);
  return writesEnabled(mode);
}

export function listToolsForMode(
  mode: AccessMode,
  plan: ClockifyPlan = "all",
): ToolDefinition[] {
  return WAVE1_TOOLS.filter(
    (t) => isAllowed(t.tier, mode) && planIncludes(plan, t.minPlan),
  );
}
