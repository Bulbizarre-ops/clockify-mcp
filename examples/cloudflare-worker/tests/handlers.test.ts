import { describe, expect, it, vi } from "vitest";
import { createHandlers } from "../src/domains/handlers.js";
import type { ClockifyClient } from "../src/clockify/client.js";

function mockClient(overrides: Partial<ClockifyClient> = {}): ClockifyClient {
  return {
    defaultWorkspaceId: undefined,
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    report: vi.fn(),
    ...overrides,
  } as unknown as ClockifyClient;
}

describe("createHandlers workspace resolution", () => {
  it("requires workspace_id or default workspace for scoped tools", async () => {
    const client = mockClient();
    const handlers = createHandlers(client);
    await expect(handlers.get_workspace({})).rejects.toThrow(/workspace_id/);
  });

  it("uses X-Clockify-Workspace-Id default when tool omits workspace_id", async () => {
    const get = vi.fn(async () => ({ id: "ws1" }));
    const client = mockClient({ defaultWorkspaceId: "ws1", get });
    const handlers = createHandlers(client);
    await handlers.get_workspace({});
    expect(get).toHaveBeenCalledWith("workspaces/ws1");
  });
});

describe("createHandlers wave-1 API mapping", () => {
  it("get_current_user hits GET user", async () => {
    const get = vi.fn(async () => ({ id: "u1" }));
    const handlers = createHandlers(mockClient({ get }));
    await expect(handlers.get_current_user({})).resolves.toEqual({ id: "u1" });
    expect(get).toHaveBeenCalledWith("user");
  });

  it("create_time_entry posts to workspaces/{ws}/time-entries", async () => {
    const post = vi.fn(async () => ({ id: "te1" }));
    const handlers = createHandlers(
      mockClient({ defaultWorkspaceId: "ws", post }),
    );
    await handlers.create_time_entry({
      start: "2026-01-01T09:00:00Z",
      description: "coding",
    });
    expect(post).toHaveBeenCalledWith("workspaces/ws/time-entries", {
      start: "2026-01-01T09:00:00Z",
      description: "coding",
    });
  });

  it("stop_running_timer patches user time-entries", async () => {
    const patch = vi.fn(async () => ({ id: "te1", end: "x" }));
    const handlers = createHandlers(
      mockClient({ defaultWorkspaceId: "ws", patch }),
    );
    await handlers.stop_running_timer({
      user_id: "u1",
      end: "2026-01-01T17:00:00Z",
    });
    expect(patch).toHaveBeenCalledWith("workspaces/ws/user/u1/time-entries", {
      end: "2026-01-01T17:00:00Z",
    });
  });

  it("generate_summary_report posts to the reports host path", async () => {
    const report = vi.fn(async () => ({ totals: [] }));
    const handlers = createHandlers(
      mockClient({ defaultWorkspaceId: "ws", report }),
    );
    await handlers.generate_summary_report({
      date_range_start: "2026-01-01T00:00:00Z",
      date_range_end: "2026-01-31T23:59:59Z",
      groups: ["PROJECT"],
    });
    expect(report).toHaveBeenCalledWith(
      "workspaces/ws/reports/summary",
      expect.objectContaining({
        dateRangeStart: "2026-01-01T00:00:00Z",
        dateRangeEnd: "2026-01-31T23:59:59Z",
        summaryFilter: { groups: ["PROJECT"] },
      }),
    );
  });

  it("list_tasks requires project_id", async () => {
    const get = vi.fn(async () => []);
    const handlers = createHandlers(
      mockClient({ defaultWorkspaceId: "ws", get }),
    );
    await handlers.list_tasks({ project_id: "p1" });
    expect(get).toHaveBeenCalledWith(
      "workspaces/ws/projects/p1/tasks",
      expect.any(Object),
    );
  });
});
