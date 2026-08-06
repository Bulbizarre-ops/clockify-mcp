import type { ClockifyClient } from "../clockify/client.js";
import { resolveWorkspaceId } from "./workspace.js";

type Dict = Record<string, unknown>;

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function asBool(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function asArray(value: unknown): Dict[] {
  return Array.isArray(value) ? (value as Dict[]) : [];
}

function entryStart(entry: Dict): string | undefined {
  const interval = entry.timeInterval as Dict | undefined;
  return asString(interval?.start) ?? asString(entry.start);
}

function entryEnd(entry: Dict): string | undefined {
  const interval = entry.timeInterval as Dict | undefined;
  const end = interval?.end ?? entry.end;
  return typeof end === "string" && end.length > 0 ? end : undefined;
}

async function listAllPages(
  client: ClockifyClient,
  path: string,
  baseParams: Record<string, string | number | boolean | undefined | null> = {},
): Promise<Dict[]> {
  const out: Dict[] = [];
  let page = 1;
  const pageSize = 50;
  for (;;) {
    const batch = asArray(
      await client.get(path, { ...baseParams, page, "page-size": pageSize }),
    );
    out.push(...batch);
    if (batch.length < pageSize) break;
    page += 1;
    if (page > 200) break; // safety cap
  }
  return out;
}

async function ensureNamedResources(
  client: ClockifyClient,
  sourceWs: string,
  destWs: string,
  kind: "projects" | "tags",
  dryRun: boolean,
): Promise<Map<string, string>> {
  const source = await listAllPages(client, `workspaces/${sourceWs}/${kind}`);
  const dest = await listAllPages(client, `workspaces/${destWs}/${kind}`);
  const destByName = new Map<string, string>();
  for (const item of dest) {
    const name = asString(item.name);
    const id = asString(item.id);
    if (name && id) destByName.set(name, id);
  }

  const map = new Map<string, string>();
  for (const item of source) {
    const sourceId = asString(item.id);
    const name = asString(item.name);
    if (!sourceId || !name) continue;
    let destId = destByName.get(name);
    if (!destId) {
      if (dryRun) {
        destId = `dry-run:${kind}:${name}`;
        destByName.set(name, destId);
      } else {
        const created = (await client.post(`workspaces/${destWs}/${kind}`, {
          name,
        })) as Dict;
        destId = asString(created.id);
        if (destId) destByName.set(name, destId);
      }
    }
    if (destId) map.set(sourceId, destId);
  }
  return map;
}

export type BackupResult = {
  source_workspace_id: string;
  destination_workspace_id: string;
  user_id: string;
  scanned: number;
  copied: number;
  skipped_running: number;
  skipped_missing_project: number;
  errors: Array<{ time_entry_id?: string; error: string }>;
  dry_run: boolean;
  created_projects: number;
  created_tags: number;
};

/**
 * Copy completed time entries from a source workspace into a dedicated backup workspace.
 * Projects/tags are matched by name (created on the destination when missing).
 * Running timers (no end) are skipped. Requires access mode full.
 */
export async function backupTimeEntries(
  client: ClockifyClient,
  args: Dict,
): Promise<BackupResult> {
  const destinationWs = asString(args.destination_workspace_id);
  if (!destinationWs) {
    throw new Error(
      "destination_workspace_id is required (dedicated backup workspace).",
    );
  }
  const sourceWs = resolveWorkspaceId(client, args.source_workspace_id);
  if (sourceWs === destinationWs) {
    throw new Error("source_workspace_id and destination_workspace_id must differ.");
  }

  const dryRun = asBool(args.dry_run) === true;
  let userId = asString(args.user_id);
  if (!userId) {
    const me = (await client.get("user")) as Dict;
    userId = asString(me.id);
    if (!userId) throw new Error("Could not resolve current user id.");
  }

  // Snapshot destination counts before ensure (for reporting creates).
  const destProjectsBefore = (
    await listAllPages(client, `workspaces/${destinationWs}/projects`)
  ).length;
  const destTagsBefore = (
    await listAllPages(client, `workspaces/${destinationWs}/tags`)
  ).length;

  const projectMap = await ensureNamedResources(
    client,
    sourceWs,
    destinationWs,
    "projects",
    dryRun,
  );
  const tagMap = await ensureNamedResources(
    client,
    sourceWs,
    destinationWs,
    "tags",
    dryRun,
  );

  const destProjectsAfter = dryRun
    ? destProjectsBefore
    : (await listAllPages(client, `workspaces/${destinationWs}/projects`)).length;
  const destTagsAfter = dryRun
    ? destTagsBefore
    : (await listAllPages(client, `workspaces/${destinationWs}/tags`)).length;

  const entries = await listAllPages(
    client,
    `workspaces/${sourceWs}/user/${userId}/time-entries`,
    {
      start: asString(args.start),
      end: asString(args.end),
      hydrated: false,
    },
  );

  const result: BackupResult = {
    source_workspace_id: sourceWs,
    destination_workspace_id: destinationWs,
    user_id: userId,
    scanned: entries.length,
    copied: 0,
    skipped_running: 0,
    skipped_missing_project: 0,
    errors: [],
    dry_run: dryRun,
    created_projects: Math.max(0, destProjectsAfter - destProjectsBefore),
    created_tags: Math.max(0, destTagsAfter - destTagsBefore),
  };

  for (const entry of entries) {
    const start = entryStart(entry);
    const end = entryEnd(entry);
    const sourceId = asString(entry.id);
    if (!start) {
      result.errors.push({
        time_entry_id: sourceId,
        error: "missing start",
      });
      continue;
    }
    if (!end) {
      result.skipped_running += 1;
      continue;
    }

    const sourceProjectId = asString(entry.projectId);
    let destProjectId: string | undefined;
    if (sourceProjectId) {
      destProjectId = projectMap.get(sourceProjectId);
      if (!destProjectId) {
        result.skipped_missing_project += 1;
        continue;
      }
    }

    const sourceTagIds = Array.isArray(entry.tagIds)
      ? (entry.tagIds as unknown[]).filter((t): t is string => typeof t === "string")
      : [];
    const destTagIds = sourceTagIds
      .map((id) => tagMap.get(id))
      .filter((id): id is string => Boolean(id));

    const body = {
      start,
      end,
      description: asString(entry.description),
      projectId: destProjectId,
      tagIds: destTagIds.length > 0 ? destTagIds : undefined,
      billable: typeof entry.billable === "boolean" ? entry.billable : undefined,
      type: asString(entry.type),
    };

    try {
      if (!dryRun) {
        await client.post(`workspaces/${destinationWs}/time-entries`, body);
      }
      result.copied += 1;
    } catch (error) {
      result.errors.push({
        time_entry_id: sourceId,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  return result;
}
