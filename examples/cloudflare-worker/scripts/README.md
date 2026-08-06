# Local tools (not MCP)

Standalone CLI utilities that talk **directly** to the Clockify REST API.
They do **not** go through the MCP Worker, Claude connectors, or OAuth.

| Tool | Script | Purpose |
|------|--------|---------|
| **Time-entry workspace backup** | [`backup_time_entries.py`](./backup_time_entries.py) | Copy completed time entries from one workspace to another |

---

## Time-entry workspace backup

Python 3 stdlib only (`urllib` / `json` / `argparse`) — no `pip install`.

Same behaviour as the Worker tool `backup_time_entries` (full mode), but runnable from a laptop:

- Destination by `--destination-id` or `--destination-name` (create with Cake `organizationId`)
- Remap projects / tags **by name** (create on destination if missing)
- Skip running timers (no end time)
- Idempotent: embeds `[clk-backup:<sourceId>]` in destination descriptions; skips duplicates on re-run
- `--dry-run` to preview without writes

### Auth

```bash
export CLOCKIFY_API_KEY=...          # required
export CLOCKIFY_REGION=global        # optional: global|euc1|use2|euw2|apse2
export CLOCKIFY_DEFAULT_WORKSPACE_ID=...  # optional default source
```

Or pass `--api-key` / `--region` / `--source-id` on the CLI.

### Example — migrate “Deprecated …” → new workspace

```bash
cd examples/cloudflare-worker

# Preview
python3 scripts/backup_time_entries.py \
  --source-id <DEPRECATED_WORKSPACE_ID> \
  --destination-id <NEW_WORKSPACE_ID> \
  --dry-run

# Real copy
python3 scripts/backup_time_entries.py \
  --source-id <DEPRECATED_WORKSPACE_ID> \
  --destination-id <NEW_WORKSPACE_ID>
```

Create destination by name (if it does not exist yet):

```bash
python3 scripts/backup_time_entries.py \
  --source-id <SOURCE_ID> \
  --destination-name "Gounid Backup" \
  --dry-run
```

### Useful flags

| Flag | Meaning |
|------|---------|
| `--start` / `--end` | ISO-8601 bounds on source entries |
| `--user-id` | Copy another user’s entries (default: authenticated user) |
| `--organization-id` | Cake org id when creating a workspace by name |
| `--force` | Do not skip duplicates |
| `--json` | Print full JSON summary |

Exit code `0` on success; `1` if non–dry-run finished with API errors on some entries.

### Relation to MCP

| | Local script | MCP `backup_time_entries` |
|--|--------------|---------------------------|
| Runtime | Your machine + Python 3 | Cloudflare Worker / Claude |
| Auth | `CLOCKIFY_API_KEY` env | OAuth grant or Bearer on `/mcp` |
| Best for | Bulk migrations, long runs, ops | Ad-hoc from a chat client |

Prefer this script for large backups (1000+ entries): progress logs every 50 entries, no MCP session limits.
