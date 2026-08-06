import { describe, expect, it } from "vitest";
import { listToolsForMode, WAVE1_TOOLS } from "../src/domains/registry.js";

describe("WAVE1_TOOLS", () => {
  it("declares 33 tools including backup_time_entries", () => {
    expect(WAVE1_TOOLS).toHaveLength(33);
    expect(WAVE1_TOOLS.map((t) => t.name)).toContain("backup_time_entries");
  });

  it("uses exact Python-aligned tool names for core coverage", () => {
    const names = WAVE1_TOOLS.map((t) => t.name);
    for (const name of [
      "get_current_user",
      "list_workspaces",
      "get_workspace",
      "list_users",
      "list_clients",
      "get_client",
      "create_client",
      "update_client",
      "delete_client",
      "list_projects",
      "get_project",
      "create_project",
      "update_project",
      "delete_project",
      "list_tasks",
      "get_task",
      "create_task",
      "update_task",
      "delete_task",
      "list_tags",
      "get_tag",
      "create_tag",
      "update_tag",
      "delete_tag",
      "list_time_entries",
      "get_time_entry",
      "create_time_entry",
      "update_time_entry",
      "delete_time_entry",
      "stop_running_timer",
      "generate_summary_report",
      "generate_detailed_report",
    ]) {
      expect(names).toContain(name);
    }
  });
});

describe("listToolsForMode", () => {
  it("exposes only reads in read mode", () => {
    const names = listToolsForMode("read").map((t) => t.name);
    expect(names).toContain("get_current_user");
    expect(names).toContain("generate_detailed_report");
    expect(names).not.toContain("create_time_entry");
    expect(names).not.toContain("create_client");
    expect(names).not.toContain("stop_running_timer");
    expect(names).toHaveLength(16);
  });

  it("adds self-scoped time-entry writes in time-tracking mode", () => {
    const names = listToolsForMode("time-tracking").map((t) => t.name);
    expect(names).toContain("create_time_entry");
    expect(names).toContain("update_time_entry");
    expect(names).toContain("delete_time_entry");
    // Matches Python: stop_running_timer is full-only
    expect(names).not.toContain("stop_running_timer");
    expect(names).not.toContain("create_client");
    expect(names).toHaveLength(19);
  });

  it("exposes all tools including backup in full mode", () => {
    const names = listToolsForMode("full").map((t) => t.name);
    expect(names).toContain("stop_running_timer");
    expect(names).toContain("delete_project");
    expect(names).toContain("backup_time_entries");
    expect(names).toHaveLength(33);
  });

  it("keeps backup_time_entries full-only", () => {
    expect(listToolsForMode("time-tracking").map((t) => t.name)).not.toContain(
      "backup_time_entries",
    );
  });
});
