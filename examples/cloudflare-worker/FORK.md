# Fork → PR guide

Goal: contribute this Worker as `examples/cloudflare-worker/` to [tracegazer/clockify-mcp](https://github.com/tracegazer/clockify-mcp) without changing the Python runtime.

## From this fork

If you are already inside a fork of `tracegazer/clockify-mcp` and this directory exists:

```bash
cd examples/cloudflare-worker
npm ci && npm test && npm run typecheck
cd ../..
git checkout -b cursor/cloudflare-worker-example
git add examples/cloudflare-worker README.md
git commit -m "$(cat <<'EOF'
feat: add Cloudflare Worker HTTP MCP example (wave 1, BYO API key)

EOF
)"
git push -u origin HEAD
gh pr create --repo tracegazer/clockify-mcp \
  --title "feat: Cloudflare Worker HTTP MCP example" \
  --body "$(cat <<'EOF'
## Summary
- Adds \`examples/cloudflare-worker\`: Streamable HTTP MCP on Cloudflare Workers
- Bring-your-own Clockify API key per request
- Tool names + access modes aligned with the Python server
- Wave 1 core coverage (32 tools) + Vitest TDD suite
- README link to the example

## Test plan
- [ ] \`cd examples/cloudflare-worker && npm ci && npm test\`
- [ ] \`npm run typecheck\`
- [ ] \`wrangler dev\` + MCP Inspector against \`/mcp\` with a real API key
- [ ] Confirm 401 without API key; read-only tools in default mode
EOF
)"
```

## Sync helper

If you maintain a standalone copy of the Worker and need to copy it into a fresh upstream fork:

```bash
./examples/cloudflare-worker/scripts/sync-into-tracegazer-fork.sh /path/to/clockify-mcp-fork
```

## Upstream conventions

Follow root [CONTRIBUTING.md](../../CONTRIBUTING.md): Conventional Commits, tests first, no documented tools without implementation.
