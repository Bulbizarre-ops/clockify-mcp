#!/usr/bin/env bash
# Copy this Worker example into a clone/fork of tracegazer/clockify-mcp.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST_ROOT="${1:-}"

if [[ -z "$DEST_ROOT" ]]; then
  echo "Usage: $0 /path/to/clockify-mcp-fork" >&2
  exit 1
fi

DEST="$DEST_ROOT/examples/cloudflare-worker"
mkdir -p "$DEST"
rsync -a --delete \
  --exclude node_modules \
  --exclude .wrangler \
  --exclude dist \
  --exclude coverage \
  --exclude .dev.vars \
  "$SRC/" "$DEST/"

echo "Synced Worker example → $DEST"
echo "Next: cd $DEST && npm ci && npm test"
