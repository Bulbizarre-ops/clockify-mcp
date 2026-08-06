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
  it("requires destination_workspace_id", async () => {
    await expect(
      backupTimeEntries(mockClient(), {}),
    ).rejects.toThrow(/destination_workspace_id/);
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
      user_id: "u1",
      scanned: 2,
      copied: 1,
      skipped_running: 1,
      dry_run: false,
    });
    expect(post).toHaveBeenCalledWith("workspaces/dst-ws/time-entries", {
      start: "2026-01-01T09:00:00Z",
      end: "2026-01-01T10:00:00Z",
      description: "coding",
      projectId: "p-dst",
      billable: true,
    });
  });

  it("dry_run does not create entries", async () => {
    const get = vi.fn(async (path: string, params?: Record<string, unknown>) => {
      if (path === "user") return { id: "u1" };
      if (path.includes("/projects") || path.includes("/tags")) return [];
      if (path.includes("/time-entries")) {
        const page = Number(params?.page ?? 1);
        if (page > 1) return [];
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
