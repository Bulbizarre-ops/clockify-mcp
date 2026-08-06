import { describe, expect, it, vi } from "vitest";
import { backupTimeEntries } from "../src/domains/backup.js";
import type { ClockifyClient } from "../src/clockify/client.js";

function mockClient(overrides: Partial<ClockifyClient> = {}): ClockifyClient {
  return {
    defaultWorkspaceId: "src-ws",
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    report: vi.fn(),
    ...overrides,
  } as unknown as ClockifyClient;
}

describe("backupTimeEntries", () => {
  it("requires destination_workspace_id or destination_workspace_name", async () => {
    await expect(
      backupTimeEntries(mockClient(), {}),
    ).rejects.toThrow(/destination_workspace/);
  });

  it("creates a destination workspace with Cake organizationId", async () => {
    const get = vi.fn(async (path: string, params?: Record<string, unknown>) => {
      if (path === "user") return { id: "u1" };
      if (path === "workspaces") {
        return [
          {
            id: "src-ws",
            name: "Main",
            cakeOrganizationId: "67d471fb56aa9668b7bfa295",
          },
        ];
      }
      if (path.includes("/projects") || path.includes("/tags")) return [];
      if (path.includes("/time-entries")) {
        const page = Number(params?.page ?? 1);
        if (page > 1) return [];
        if (path.includes("new-backup-ws") || path.includes("dry-run")) return [];
        return [
          {
            id: "te1",
            description: "x",
            timeInterval: {
              start: "2026-01-01T09:00:00Z",
              end: "2026-01-01T10:00:00Z",
            },
          },
        ];
      }
      return [];
    });
    const post = vi.fn(async (path: string, body?: Record<string, unknown>) => {
      if (path === "workspaces") {
        return { id: "new-backup-ws", name: body?.name };
      }
      return { id: "te-new" };
    });

    const result = await backupTimeEntries(mockClient({ get, post }), {
      destination_workspace_name: "Clockify Backup",
      source_workspace_id: "src-ws",
    });

    expect(post).toHaveBeenCalledWith("workspaces", {
      name: "Clockify Backup",
      organizationId: "67d471fb56aa9668b7bfa295",
    });
    expect(result.destination_workspace_id).toBe("new-backup-ws");
    expect(result.destination_workspace_created).toBe(true);
    expect(result.copied).toBe(1);
  });

  it("rejects workspace creation when cakeOrganizationId is unavailable", async () => {
    const get = vi.fn(async (path: string) => {
      if (path === "workspaces") return [{ id: "src-ws", name: "Main" }];
      if (path === "workspaces/src-ws") return { id: "src-ws", name: "Main" };
      return [];
    });

    await expect(
      backupTimeEntries(mockClient({ get, post: vi.fn() }), {
        destination_workspace_name: "Clockify Backup",
        source_workspace_id: "src-ws",
      }),
    ).rejects.toThrow(/organizationId|cakeOrganizationId/);
  });

  it("reuses an existing workspace when destination_workspace_name already exists", async () => {
    const get = vi.fn(async (path: string, params?: Record<string, unknown>) => {
      if (path === "user") return { id: "u1" };
      if (path === "workspaces") {
        return [
          { id: "src-ws", name: "Main" },
          { id: "existing-backup", name: "Clockify Backup" },
        ];
      }
      if (path.includes("/projects") || path.includes("/tags")) return [];
      if (path.includes("/time-entries")) {
        const page = Number(params?.page ?? 1);
        return page > 1
          ? []
          : path.includes("existing-backup")
            ? []
            : [
                {
                  id: "te1",
                  timeInterval: {
                    start: "2026-01-01T09:00:00Z",
                    end: "2026-01-01T10:00:00Z",
                  },
                },
              ];
      }
      return [];
    });
    const post = vi.fn(async () => ({ id: "te-new" }));

    const result = await backupTimeEntries(mockClient({ get, post }), {
      destination_workspace_name: "Clockify Backup",
      source_workspace_id: "src-ws",
    });

    expect(post).not.toHaveBeenCalledWith("workspaces", expect.anything());
    expect(result.destination_workspace_id).toBe("existing-backup");
    expect(result.destination_workspace_created).toBe(false);
  });

  it("copies completed entries into the destination workspace with remapped projects", async () => {
    const get = vi.fn(async (path: string, params?: Record<string, unknown>) => {
      if (path === "user") return { id: "u1", name: "Ada" };
      if (path === "workspaces/src-ws/projects") {
        return [{ id: "p-src", name: "Alpha" }];
      }
      if (path === "workspaces/dst-ws/projects") {
        return [{ id: "p-dst", name: "Alpha" }];
      }
      if (path === "workspaces/src-ws/tags") return [];
      if (path === "workspaces/dst-ws/tags") return [];
      if (path === "workspaces/src-ws/user/u1/time-entries") {
        const page = Number(params?.page ?? 1);
        if (page > 1) return [];
        return [
          {
            id: "te1",
            description: "coding",
            projectId: "p-src",
            timeInterval: {
              start: "2026-01-01T09:00:00Z",
              end: "2026-01-01T10:00:00Z",
            },
            billable: true,
          },
          {
            id: "te-running",
            description: "running",
            timeInterval: { start: "2026-01-02T09:00:00Z", end: null },
          },
        ];
      }
      if (path === "workspaces/dst-ws/user/u1/time-entries") return [];
      return [];
    });
    const post = vi.fn(async () => ({ id: "te-new" }));
    const client = mockClient({ get, post });

    const result = await backupTimeEntries(client, {
      destination_workspace_id: "dst-ws",
      source_workspace_id: "src-ws",
    });

    expect(result).toMatchObject({
      source_workspace_id: "src-ws",
      destination_workspace_id: "dst-ws",
      destination_workspace_created: false,
      user_id: "u1",
      scanned: 2,
      copied: 1,
      skipped_running: 1,
      skipped_duplicate: 0,
      dry_run: false,
    });
    expect(post).toHaveBeenCalledWith("workspaces/dst-ws/time-entries", {
      start: "2026-01-01T09:00:00Z",
      end: "2026-01-01T10:00:00Z",
      description: "coding\n[clk-backup:te1]",
      projectId: "p-dst",
      billable: true,
    });
  });

  it("skips entries already present by source marker on retry", async () => {
    const get = vi.fn(async (path: string, params?: Record<string, unknown>) => {
      if (path === "user") return { id: "u1" };
      if (path.includes("/projects") || path.includes("/tags")) return [];
      if (path === "workspaces/src-ws/user/u1/time-entries") {
        const page = Number(params?.page ?? 1);
        if (page > 1) return [];
        return [
          {
            id: "te1",
            description: "coding",
            timeInterval: {
              start: "2026-01-01T09:00:00Z",
              end: "2026-01-01T10:00:00Z",
            },
          },
        ];
      }
      if (path === "workspaces/dst-ws/user/u1/time-entries") {
        const page = Number(params?.page ?? 1);
        if (page > 1) return [];
        return [
          {
            id: "te-dst",
            description: "coding\n[clk-backup:te1]",
            timeInterval: {
              start: "2026-01-01T09:00:00Z",
              end: "2026-01-01T10:00:00Z",
            },
          },
        ];
      }
      return [];
    });
    const post = vi.fn();
    const result = await backupTimeEntries(mockClient({ get, post }), {
      destination_workspace_id: "dst-ws",
      source_workspace_id: "src-ws",
    });
    expect(result.copied).toBe(0);
    expect(result.skipped_duplicate).toBe(1);
    expect(post).not.toHaveBeenCalled();
  });

  it("skips legacy copies by content fingerprint when marker is missing", async () => {
    const get = vi.fn(async (path: string, params?: Record<string, unknown>) => {
      if (path === "user") return { id: "u1" };
      if (path === "workspaces/src-ws/projects") {
        return [{ id: "p-src", name: "Alpha" }];
      }
      if (path === "workspaces/dst-ws/projects") {
        return [{ id: "p-dst", name: "Alpha" }];
      }
      if (path.includes("/tags")) return [];
      if (path === "workspaces/src-ws/user/u1/time-entries") {
        const page = Number(params?.page ?? 1);
        if (page > 1) return [];
        return [
          {
            id: "te1",
            description: "coding",
            projectId: "p-src",
            timeInterval: {
              start: "2026-01-01T09:00:00.000Z",
              end: "2026-01-01T10:00:00.000Z",
            },
          },
        ];
      }
      if (path === "workspaces/dst-ws/user/u1/time-entries") {
        const page = Number(params?.page ?? 1);
        if (page > 1) return [];
        return [
          {
            id: "te-legacy",
            description: "coding",
            projectId: "p-dst",
            timeInterval: {
              start: "2026-01-01T09:00:00Z",
              end: "2026-01-01T10:00:00Z",
            },
          },
        ];
      }
      return [];
    });
    const post = vi.fn();
    const result = await backupTimeEntries(mockClient({ get, post }), {
      destination_workspace_id: "dst-ws",
      source_workspace_id: "src-ws",
    });
    expect(result.copied).toBe(0);
    expect(result.skipped_duplicate).toBe(1);
    expect(post).not.toHaveBeenCalled();
  });

  it("force=true re-copies even when a duplicate exists", async () => {
    const get = vi.fn(async (path: string, params?: Record<string, unknown>) => {
      if (path === "user") return { id: "u1" };
      if (path.includes("/projects") || path.includes("/tags")) return [];
      if (path === "workspaces/src-ws/user/u1/time-entries") {
        const page = Number(params?.page ?? 1);
        if (page > 1) return [];
        return [
          {
            id: "te1",
            description: "coding",
            timeInterval: {
              start: "2026-01-01T09:00:00Z",
              end: "2026-01-01T10:00:00Z",
            },
          },
        ];
      }
      return [];
    });
    const post = vi.fn(async () => ({ id: "te-new" }));
    const result = await backupTimeEntries(mockClient({ get, post }), {
      destination_workspace_id: "dst-ws",
      source_workspace_id: "src-ws",
      force: true,
    });
    expect(result.copied).toBe(1);
    expect(result.skipped_duplicate).toBe(0);
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("dry_run does not create entries", async () => {
    const get = vi.fn(async (path: string, params?: Record<string, unknown>) => {
      if (path === "user") return { id: "u1" };
      if (path.includes("/projects") || path.includes("/tags")) return [];
      if (path.includes("/time-entries")) {
        const page = Number(params?.page ?? 1);
        if (page > 1) return [];
        // Source path only — dest empty for first dry_run
        if (path.includes("/dst-ws/")) return [];
        return [
          {
            id: "te1",
            description: "x",
            timeInterval: {
              start: "2026-01-01T09:00:00Z",
              end: "2026-01-01T10:00:00Z",
            },
          },
        ];
      }
      return [];
    });
    const post = vi.fn();
    const result = await backupTimeEntries(mockClient({ get, post }), {
      destination_workspace_id: "dst-ws",
      dry_run: true,
    });
    expect(result.copied).toBe(1);
    expect(result.dry_run).toBe(true);
    expect(post).not.toHaveBeenCalled();
  });
});
