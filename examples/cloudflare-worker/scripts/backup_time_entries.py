#!/usr/bin/env python3
"""Local tool: backup Clockify time entries (NOT MCP).

Standalone CLI — talks to the Clockify REST API directly from your machine.
Same semantics as the Worker MCP tool `backup_time_entries`, without going
through Cloudflare, OAuth, or a chat client.

Docs: scripts/README.md

Mirrors examples/cloudflare-worker backup_time_entries:
  - destination by id or name (create with Cake organizationId)
  - remap projects/tags by name (create if missing)
  - skip running timers
  - idempotent via [clk-backup:<sourceId>] markers (+ fingerprint fallback)
  - dry-run support

Usage:
  export CLOCKIFY_API_KEY=...
  # optional: CLOCKIFY_REGION=global|euc1|use2|euw2|apse2

  # Preview
  python3 backup_time_entries.py \\
    --destination-name "Clockify Backup" \\
    --dry-run

  # Real copy
  python3 backup_time_entries.py \\
    --destination-name "Clockify Backup"

  # Existing destination workspace
  python3 backup_time_entries.py --destination-id <ws_id>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

SOURCE_MARKER_RE = re.compile(r"\[clk-backup:([^\]]+)\]")
PAGE_SIZE = 50
PAGE_CAP = 500


class ClockifyError(RuntimeError):
    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(f"Clockify API error {status}: {message}")
        self.status = status
        self.body = body


def resolve_base(region: str) -> str:
    region = (region or "global").strip().lower()
    if region == "global":
        return "https://api.clockify.me/api/v1"
    return f"https://{region}.clockify.me/api/v1"


class Client:
    def __init__(self, api_key: str, base: str, timeout: float = 60.0):
        self.api_key = api_key
        self.base = base.rstrip("/")
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base}/{path.lstrip('/')}"
        if params:
            qs = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            if qs:
                url = f"{url}?{qs}"

        data = None
        headers = {
            "X-Api-Key": self.api_key,
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                if resp.status == 204 or not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw
            message = raw[:1000] if isinstance(parsed, str) else json.dumps(parsed)[:1000]
            raise ClockifyError(exc.code, message or exc.reason, parsed) from exc

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, body=body)


def list_all_pages(
    client: Client,
    path: str,
    base_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while page <= PAGE_CAP:
        params = dict(base_params or {})
        params.update({"page": page, "page-size": PAGE_SIZE})
        batch = client.get(path, params=params)
        if not isinstance(batch, list):
            batch = []
        out.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return out


def entry_start(entry: dict[str, Any]) -> str | None:
    interval = entry.get("timeInterval")
    if isinstance(interval, dict) and isinstance(interval.get("start"), str):
        return interval["start"] or None
    start = entry.get("start")
    return start if isinstance(start, str) and start else None


def entry_end(entry: dict[str, Any]) -> str | None:
    interval = entry.get("timeInterval")
    if isinstance(interval, dict):
        end = interval.get("end")
        if isinstance(end, str) and end:
            return end
    end = entry.get("end")
    return end if isinstance(end, str) and end else None


def normalize_instant(iso: str) -> str:
    try:
        # Accept Z / offset; normalize to UTC ISO with ms.
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return iso


def strip_source_marker(description: str | None) -> str:
    if not description:
        return ""
    return SOURCE_MARKER_RE.sub("", description).rstrip("\n").strip()


def with_source_marker(description: str | None, source_id: str) -> str:
    marker = f"[clk-backup:{source_id}]"
    base = strip_source_marker(description)
    return f"{base}\n{marker}" if base else marker


def extract_source_ids(description: str | None) -> list[str]:
    if not description:
        return []
    return SOURCE_MARKER_RE.findall(description)


def content_fingerprint(
    start: str,
    end: str,
    description: str | None,
    project_id: str | None,
) -> str:
    return "\0".join(
        [
            normalize_instant(start),
            normalize_instant(end),
            strip_source_marker(description),
            project_id or "",
        ]
    )


def cake_organization_id(ws: dict[str, Any]) -> str | None:
    for key in ("cakeOrganizationId", "organizationId"):
        value = ws.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def resolve_organization_id(
    client: Client,
    workspaces: list[dict[str, Any]],
    *,
    source_id: str | None,
    organization_id: str | None,
) -> str | None:
    if organization_id:
        return organization_id
    if source_id:
        for ws in workspaces:
            if ws.get("id") == source_id:
                org = cake_organization_id(ws)
                if org:
                    return org
        try:
            detail = client.get(f"workspaces/{source_id}")
            if isinstance(detail, dict):
                org = cake_organization_id(detail)
                if org:
                    return org
        except ClockifyError:
            pass
    for ws in workspaces:
        org = cake_organization_id(ws)
        if org:
            return org
    return None


def resolve_destination(
    client: Client,
    *,
    destination_id: str | None,
    destination_name: str | None,
    source_id: str | None,
    organization_id: str | None,
    dry_run: bool,
) -> tuple[str, bool]:
    if destination_id:
        return destination_id, False

    name = (destination_name or "").strip()
    if not name:
        raise SystemExit("Provide --destination-id or --destination-name.")
    if len(name) > 50:
        raise SystemExit("destination name must be ≤ 50 characters (Clockify limit).")

    raw_workspaces = client.get("workspaces")
    workspaces = (
        [w for w in raw_workspaces if isinstance(w, dict)]
        if isinstance(raw_workspaces, list)
        else []
    )

    for ws in workspaces:
        ws_name = ws.get("name")
        if isinstance(ws_name, str) and ws_name.lower() == name.lower():
            ws_id = ws.get("id")
            if isinstance(ws_id, str) and ws_id:
                return ws_id, False

    org = resolve_organization_id(
        client,
        workspaces,
        source_id=source_id,
        organization_id=organization_id,
    )
    if not org:
        raise SystemExit(
            "Clockify requires organizationId (cakeOrganizationId) to create a "
            "workspace. Pass --organization-id, or create the workspace in the UI "
            "and use --destination-id."
        )

    if dry_run:
        return f"dry-run:workspace:{name}", True

    created = client.post("workspaces", {"name": name, "organizationId": org})
    if not isinstance(created, dict) or not isinstance(created.get("id"), str):
        raise SystemExit("Clockify did not return an id for the created workspace.")
    return created["id"], True


def ensure_named_resources(
    client: Client,
    source_ws: str,
    dest_ws: str,
    kind: str,
    dry_run: bool,
) -> dict[str, str]:
    source = list_all_pages(client, f"workspaces/{source_ws}/{kind}")
    dest_by_name: dict[str, str] = {}
    synthetic = dry_run or dest_ws.startswith("dry-run:")
    if not synthetic:
        for item in list_all_pages(client, f"workspaces/{dest_ws}/{kind}"):
            name = item.get("name")
            item_id = item.get("id")
            if isinstance(name, str) and isinstance(item_id, str):
                dest_by_name[name] = item_id

    mapping: dict[str, str] = {}
    for item in source:
        source_id = item.get("id")
        name = item.get("name")
        if not isinstance(source_id, str) or not isinstance(name, str):
            continue
        dest_id = dest_by_name.get(name)
        if not dest_id:
            if synthetic:
                dest_id = f"dry-run:{kind}:{name}"
                dest_by_name[name] = dest_id
            else:
                created = client.post(f"workspaces/{dest_ws}/{kind}", {"name": name})
                if isinstance(created, dict) and isinstance(created.get("id"), str):
                    dest_id = created["id"]
                    dest_by_name[name] = dest_id
        if dest_id:
            mapping[source_id] = dest_id
    return mapping


def index_destination_entries(
    entries: list[dict[str, Any]],
) -> tuple[set[str], set[str]]:
    by_source: set[str] = set()
    by_fp: set[str] = set()
    for entry in entries:
        start = entry_start(entry)
        end = entry_end(entry)
        description = entry.get("description")
        desc = description if isinstance(description, str) else None
        by_source.update(extract_source_ids(desc))
        if start and end:
            project_id = entry.get("projectId")
            by_fp.add(
                content_fingerprint(
                    start,
                    end,
                    desc,
                    project_id if isinstance(project_id, str) else None,
                )
            )
    return by_source, by_fp


def backup(args: argparse.Namespace) -> dict[str, Any]:
    api_key = args.api_key or os.environ.get("CLOCKIFY_API_KEY")
    if not api_key:
        raise SystemExit("Set CLOCKIFY_API_KEY or pass --api-key.")

    region = args.region or os.environ.get("CLOCKIFY_REGION") or "global"
    client = Client(api_key, resolve_base(region))

    me = client.get("user")
    if not isinstance(me, dict) or not isinstance(me.get("id"), str):
        raise SystemExit("Could not resolve authenticated user.")
    user_id = args.user_id or me["id"]

    source_ws = args.source_id or os.environ.get("CLOCKIFY_DEFAULT_WORKSPACE_ID")
    if not source_ws:
        workspaces = client.get("workspaces")
        if isinstance(workspaces, list) and workspaces:
            first = workspaces[0]
            if isinstance(first, dict) and isinstance(first.get("id"), str):
                source_ws = first["id"]
                print(f"Using first workspace as source: {first.get('name')} ({source_ws})")
    if not source_ws:
        raise SystemExit("Provide --source-id or CLOCKIFY_DEFAULT_WORKSPACE_ID.")

    dest_id, dest_created = resolve_destination(
        client,
        destination_id=args.destination_id,
        destination_name=args.destination_name,
        source_id=source_ws,
        organization_id=args.organization_id,
        dry_run=args.dry_run,
    )
    if source_ws == dest_id:
        raise SystemExit("source and destination workspace must differ.")

    synthetic = dest_id.startswith("dry-run:")
    print(
        f"{'[dry-run] ' if args.dry_run else ''}"
        f"source={source_ws} → dest={dest_id}"
        f"{' (created)' if dest_created else ''}"
    )

    project_map = ensure_named_resources(
        client, source_ws, dest_id, "projects", args.dry_run or synthetic
    )
    tag_map = ensure_named_resources(
        client, source_ws, dest_id, "tags", args.dry_run or synthetic
    )
    print(f"projects mapped: {len(project_map)}, tags mapped: {len(tag_map)}")

    range_params: dict[str, Any] = {"hydrated": "false"}
    if args.start:
        range_params["start"] = args.start
    if args.end:
        range_params["end"] = args.end

    entries = list_all_pages(
        client,
        f"workspaces/{source_ws}/user/{user_id}/time-entries",
        range_params,
    )
    print(f"scanned source entries: {len(entries)}")

    by_source: set[str] = set()
    by_fp: set[str] = set()
    if not args.force and not synthetic:
        dest_entries = list_all_pages(
            client,
            f"workspaces/{dest_id}/user/{user_id}/time-entries",
            range_params,
        )
        by_source, by_fp = index_destination_entries(dest_entries)
        print(
            f"destination index: {len(by_source)} markers, "
            f"{len(by_fp)} fingerprints"
        )

    result: dict[str, Any] = {
        "source_workspace_id": source_ws,
        "destination_workspace_id": dest_id,
        "destination_workspace_created": dest_created,
        "user_id": user_id,
        "scanned": len(entries),
        "copied": 0,
        "skipped_running": 0,
        "skipped_missing_project": 0,
        "skipped_duplicate": 0,
        "errors": [],
        "dry_run": args.dry_run,
    }

    t0 = time.time()
    for i, entry in enumerate(entries, start=1):
        start = entry_start(entry)
        end = entry_end(entry)
        source_id = entry.get("id") if isinstance(entry.get("id"), str) else None

        if not start:
            result["errors"].append(
                {"time_entry_id": source_id, "error": "missing start"}
            )
            continue
        if not end:
            result["skipped_running"] += 1
            continue

        source_project = entry.get("projectId")
        dest_project: str | None = None
        if isinstance(source_project, str) and source_project:
            dest_project = project_map.get(source_project)
            if not dest_project:
                result["skipped_missing_project"] += 1
                continue

        description = entry.get("description")
        desc = description if isinstance(description, str) else None
        fingerprint = content_fingerprint(start, end, desc, dest_project)
        if not args.force and (
            (source_id and source_id in by_source) or fingerprint in by_fp
        ):
            result["skipped_duplicate"] += 1
            continue

        tag_ids_raw = entry.get("tagIds")
        dest_tags: list[str] = []
        if isinstance(tag_ids_raw, list):
            for tid in tag_ids_raw:
                if isinstance(tid, str) and tid in tag_map:
                    dest_tags.append(tag_map[tid])

        body: dict[str, Any] = {
            "start": start,
            "end": end,
            "description": with_source_marker(desc, source_id) if source_id else desc,
        }
        if dest_project:
            body["projectId"] = dest_project
        if dest_tags:
            body["tagIds"] = dest_tags
        if isinstance(entry.get("billable"), bool):
            body["billable"] = entry["billable"]
        if isinstance(entry.get("type"), str) and entry["type"]:
            body["type"] = entry["type"]

        try:
            if not args.dry_run:
                client.post(f"workspaces/{dest_id}/time-entries", body)
            result["copied"] += 1
            if source_id:
                by_source.add(source_id)
            by_fp.add(fingerprint)
        except ClockifyError as exc:
            result["errors"].append(
                {"time_entry_id": source_id, "error": str(exc)}
            )

        if i % 50 == 0 or i == len(entries):
            elapsed = time.time() - t0
            print(
                f"  progress {i}/{len(entries)} "
                f"copied={result['copied']} "
                f"dup={result['skipped_duplicate']} "
                f"err={len(result['errors'])} "
                f"({elapsed:.1f}s)",
                flush=True,
            )

    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Local Clockify time-entry backup (no MCP).",
    )
    p.add_argument("--api-key", help="Clockify API key (else CLOCKIFY_API_KEY).")
    p.add_argument(
        "--region",
        default=None,
        help="global|euc1|use2|euw2|apse2 (else CLOCKIFY_REGION, default global).",
    )
    p.add_argument("--source-id", help="Source workspace id.")
    dest = p.add_mutually_exclusive_group(required=True)
    dest.add_argument("--destination-id", help="Existing destination workspace id.")
    dest.add_argument(
        "--destination-name",
        help="Destination workspace name (reuse or create).",
    )
    p.add_argument(
        "--organization-id",
        help="Cake organizationId when creating a workspace.",
    )
    p.add_argument("--user-id", help="User whose entries to copy (default: me).")
    p.add_argument("--start", help="ISO-8601 lower bound on time entries.")
    p.add_argument("--end", help="ISO-8601 upper bound on time entries.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report without creating workspace/projects/entries.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Do not skip duplicates (markers / fingerprints).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON summary at the end.",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = backup(args)
    except ClockifyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130

    print()
    print(
        f"done: scanned={result['scanned']} copied={result['copied']} "
        f"running={result['skipped_running']} "
        f"missing_project={result['skipped_missing_project']} "
        f"duplicate={result['skipped_duplicate']} "
        f"errors={len(result['errors'])} "
        f"dry_run={result['dry_run']}"
    )
    if result["errors"]:
        print("first errors:", file=sys.stderr)
        for err in result["errors"][:10]:
            print(f"  {err}", file=sys.stderr)
    if args.json:
        print(json.dumps(result, indent=2))
    return 1 if result["errors"] and not args.dry_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
