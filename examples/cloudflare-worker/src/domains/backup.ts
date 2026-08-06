import type { ClockifyClient } from "../clockify/client.js";
import { resolveWorkspaceId } from "./workspace.js";

type Dict = Record<string, unknown>;

/** Embedded in destination descriptions so retries can skip already-copied source entries. */
function sourceMarkerRe(): RegExp {
  return /\[clk-backup:([^\]]+)\]/g;
}

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

/** Normalize ISO timestamps so "…Z" and "….000Z" still match. */
function normalizeInstant(iso: string): string {
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? new Date(ms).toISOString() : iso;
}

function stripSourceMarker(description: string | undefined): string {
  if (!description) return "";
  return description.replace(sourceMarkerRe(), "").replace(/\n+$/g, "").trim();
}

function withSourceMarker(description: string | undefined, sourceId: string): string {
  const marker = `[clk-backup:${sourceId}]`;
  const base = stripSourceMarker(description);
  return base ? `${base}\n${marker}` : marker;
}

function extractSourceIds(description: string | undefined): string[] {
  if (!description) return [];
  const ids: string[] = [];
  const re = sourceMarkerRe();
  let match: RegExpExecArray | null;
  while ((match = re.exec(description)) !== null) {
    ids.push(match[1]);
  }
  return ids;
}

function contentFingerprint(
  start: string,
  end: string,
  description: string | undefined,
  projectId: string | undefined,
): string {
  return [
    normalizeInstant(start),
    normalizeInstant(end),
    stripSourceMarker(description),
    projectId ?? "",
  ].join("\0");
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
  const destByName = new Map<string, string>();
  if (!dryRun && !destWs.startsWith("dry-run:")) {
    const dest = await listAllPages(client, `workspaces/${destWs}/${kind}`);
    for (const item of dest) {
      const name = asString(item.name);
      const id = asString(item.id);
      if (name && id) destByName.set(name, id);
    }
  }

  const map = new Map<string, string>();
  for (const item of source) {
    const sourceId = asString(item.id);
    const name = asString(item.name);
    if (!sourceId || !name) continue;
    let destId = destByName.get(name);
    if (!destId) {
      if (dryRun || destWs.startsWith("dry-run:")) {
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
  destination_workspace_created: boolean;
  user_id: string;
  scanned: number;
  copied: number;
  skipped_running: number;
  skipped_missing_project: number;
  skipped_duplicate: number;
  errors: Array<{ time_entry_id?: string; error: string }>;
  dry_run: boolean;
  created_projects: number;
  created_tags: number;
};

function cakeOrganizationId(ws: Dict): string | undefined {
  // Clockify workspace payloads expose Cake org as cakeOrganizationId;
  // createWorkspace body field is organizationId.
  return asString(ws.cakeOrganizationId) ?? asString(ws.organizationId);
}

async function resolveOrganizationId(
  client: ClockifyClient,
  args: Dict,
  workspaces: Dict[],
): Promise<string | undefined> {
  const fromArgs = asString(args.organization_id);
  if (fromArgs) return fromArgs;

  const sourceId =
    asString(args.source_workspace_id) ?? client.defaultWorkspaceId;
  if (sourceId) {
    const fromList = workspaces.find((ws) => asString(ws.id) === sourceId);
    const listed = fromList ? cakeOrganizationId(fromList) : undefined;
    if (listed) return listed;
    try {
      const detail = (await client.get(`workspaces/${sourceId}`)) as Dict;
      const fromDetail = cakeOrganizationId(detail);
      if (fromDetail) return fromDetail;
    } catch {
      // fall through to any workspace in the list
    }
  }

  for (const ws of workspaces) {
    const org = cakeOrganizationId(ws);
    if (org) return org;
  }
  return undefined;
}

async function resolveDestinationWorkspace(
  client: ClockifyClient,
  args: Dict,
  dryRun: boolean,
): Promise<{ id: string; created: boolean }> {
  const destinationId = asString(args.destination_workspace_id);
  if (destinationId) {
    return { id: destinationId, created: false };
  }

  const name = asString(args.destination_workspace_name)?.trim();
  if (!name) {
    throw new Error(
      "Provide destination_workspace_id or destination_workspace_name (dedicated backup workspace).",
    );
  }
  if (name.length > 50) {
    throw new Error(
      "destination_workspace_name must be at most 50 characters (Clockify limit).",
    );
  }

  const workspaces = asArray(await client.get("workspaces"));
  const existing = workspaces.find(
    (ws) => asString(ws.name)?.toLowerCase() === name.toLowerCase(),
  );
  const existingId = existing ? asString(existing.id) : undefined;
  if (existingId) {
    return { id: existingId, created: false };
  }

  const organizationId = await resolveOrganizationId(client, args, workspaces);
  if (!organizationId) {
    throw new Error(
      "Clockify requires organizationId (cakeOrganizationId) to create a workspace. Pass organization_id, or create the backup workspace in the Clockify UI and pass destination_workspace_id.",
    );
  }

  if (dryRun) {
    return { id: `dry-run:workspace:${name}`, created: true };
  }

  // organizationId is required by Clockify (Cake); omitting it yields an ObjectId parse error.
  const created = (await client.post("workspaces", {
    name,
    organizationId,
  })) as Dict;
  const id = asString(created.id);
  if (!id) {
    throw new Error("Clockify did not return an id for the created workspace.");
  }
  return { id, created: true };
}

type DestIndex = {
  bySourceId: Set<string>;
  byFingerprint: Set<string>;
};

function indexDestinationEntries(entries: Dict[]): DestIndex {
  const bySourceId = new Set<string>();
  const byFingerprint = new Set<string>();
  for (const entry of entries) {
    const start = entryStart(entry);
    const end = entryEnd(entry);
    const description = asString(entry.description);
    for (const sourceId of extractSourceIds(description)) {
      bySourceId.add(sourceId);
    }
    if (start && end) {
      byFingerprint.add(
        contentFingerprint(start, end, description, asString(entry.projectId)),
      );
    }
  }
  return { bySourceId, byFingerprint };
}

/**
 * Copy completed time entries from a source workspace into a dedicated backup workspace.
 * Projects/tags are matched by name (created on the destination when missing).
 * Running timers (no end) are skipped. Requires access mode full.
 *
 * Idempotent by default: embeds `[clk-backup:<sourceId>]` in the destination
 * description and skips entries already present (by marker, or by start/end/
 * description/project fingerprint for legacy copies). Pass force=true to bypass.
 *
 * Destination: pass destination_workspace_id, or destination_workspace_name to
 * reuse/create a workspace by name (create requires Cake organizationId).
 */
export async function backupTimeEntries(
  client: ClockifyClient,
  args: Dict,
): Promise<BackupResult> {
  const dryRun = asBool(args.dry_run) === true;
  const force = asBool(args.force) === true;
  const destination = await resolveDestinationWorkspace(client, args, dryRun);
  const sourceWs = resolveWorkspaceId(client, args.source_workspace_id);
  if (sourceWs === destination.id) {
    throw new Error("source_workspace_id and destination_workspace_id must differ.");
  }

  let userId = asString(args.user_id);
  if (!userId) {
    const me = (await client.get("user")) as Dict;
    userId = asString(me.id);
    if (!userId) throw new Error("Could not resolve current user id.");
  }

  // Snapshot destination counts before ensure (for reporting creates).
  const syntheticDest = destination.id.startsWith("dry-run:");
  const destProjectsBefore =
    dryRun || syntheticDest
      ? 0
      : (await listAllPages(client, `workspaces/${destination.id}/projects`))
          .length;
  const destTagsBefore =
    dryRun || syntheticDest
      ? 0
      : (await listAllPages(client, `workspaces/${destination.id}/tags`)).length;

  const projectMap = await ensureNamedResources(
    client,
    sourceWs,
    destination.id,
    "projects",
    dryRun || syntheticDest,
  );
  const tagMap = await ensureNamedResources(
    client,
    sourceWs,
    destination.id,
    "tags",
    dryRun || syntheticDest,
  );

  const destProjectsAfter =
    dryRun || syntheticDest
      ? destProjectsBefore
      : (await listAllPages(client, `workspaces/${destination.id}/projects`))
          .length;
  const destTagsAfter =
    dryRun || syntheticDest
      ? destTagsBefore
      : (await listAllPages(client, `workspaces/${destination.id}/tags`)).length;

  const rangeParams = {
    start: asString(args.start),
    end: asString(args.end),
    hydrated: false as const,
  };

  const entries = await listAllPages(
    client,
    `workspaces/${sourceWs}/user/${userId}/time-entries`,
    rangeParams,
  );

  let destIndex: DestIndex = { bySourceId: new Set(), byFingerprint: new Set() };
  if (!force && !syntheticDest) {
    const destEntries = await listAllPages(
      client,
      `workspaces/${destination.id}/user/${userId}/time-entries`,
      rangeParams,
    );
    destIndex = indexDestinationEntries(destEntries);
  }

  const result: BackupResult = {
    source_workspace_id: sourceWs,
    destination_workspace_id: destination.id,
    destination_workspace_created: destination.created,
    user_id: userId,
    scanned: entries.length,
    copied: 0,
    skipped_running: 0,
    skipped_missing_project: 0,
    skipped_duplicate: 0,
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

    const sourceDescription = asString(entry.description);
    const fingerprint = contentFingerprint(
      start,
      end,
      sourceDescription,
      destProjectId,
    );
    if (
      !force &&
      ((sourceId && destIndex.bySourceId.has(sourceId)) ||
        destIndex.byFingerprint.has(fingerprint))
    ) {
      result.skipped_duplicate += 1;
      continue;
    }

    const sourceTagIds = Array.isArray(entry.tagIds)
      ? (entry.tagIds as unknown[]).filter((t): t is string => typeof t === "string")
      : [];
    const destTagIds = sourceTagIds
      .map((id) => tagMap.get(id))
      .filter((id): id is string => Boolean(id));

    const description = sourceId
      ? withSourceMarker(sourceDescription, sourceId)
      : sourceDescription;

    const body = {
      start,
      end,
      description,
      projectId: destProjectId,
      tagIds: destTagIds.length > 0 ? destTagIds : undefined,
      billable: typeof entry.billable === "boolean" ? entry.billable : undefined,
      type: asString(entry.type),
    };

    try {
      if (!dryRun) {
        await client.post(`workspaces/${destination.id}/time-entries`, body);
      }
      result.copied += 1;
      // Keep in-run index warm so the same source batch cannot duplicate itself.
      if (sourceId) destIndex.bySourceId.add(sourceId);
      destIndex.byFingerprint.add(fingerprint);
    } catch (error) {
      result.errors.push({
        time_entry_id: sourceId,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  return result;
}
