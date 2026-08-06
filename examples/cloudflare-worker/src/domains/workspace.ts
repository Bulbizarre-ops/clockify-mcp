import type { ClockifyClient } from "../clockify/client.js";

export function resolveWorkspaceId(
  client: ClockifyClient,
  workspaceId: unknown,
): string {
  const explicit =
    typeof workspaceId === "string" && workspaceId.length > 0
      ? workspaceId
      : undefined;
  const resolved = explicit ?? client.defaultWorkspaceId;
  if (!resolved) {
    throw new Error(
      "No workspace_id given and no default configured. Call list_workspaces to find one, or send X-Clockify-Workspace-Id.",
    );
  }
  return resolved;
}
