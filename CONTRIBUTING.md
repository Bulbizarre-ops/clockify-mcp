# Contributing

Thanks for your interest in improving `clockify-mcp`.

## Development setup

This project uses [uv](https://docs.astral.sh/uv/). Do not activate the venv manually.

```bash
uv sync --extra dev
```

## Workflow

- **Tests first.** Add a test for every new tool or behavior change in `tests/`.
- **Run the suite:**
  ```bash
  uv run pytest -q          # expect: passing + live-smoke tests skipped
  ```
  Live-smoke tests run only when `CLOCKIFY_LIVE_TEST` is set (they hit the real API).
- **Lint must be clean:**
  ```bash
  uv run ruff check src/ tests/
  ```
- **Build must succeed:**
  ```bash
  uv build
  ```

## Conventions

- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
  `chore:`, `docs:`, `test:`, `refactor:`.
- Code in English; comments/docs in English or Spanish are both fine.
- Each domain lives in `src/clockify_mcp/domains/*.py` and registers its tools via
  `register(mcp, client)`. Write tools register only when `client.writes_enabled`
  (or `client.time_tracking_enabled`) — see existing domains for the pattern.
- Never document or register a tool that does not exist. Keep the README accurate to
  the implemented state.
- Never construct or guess Clockify IDs; they are opaque strings.

## Releasing

When cutting a release, bump the version in **all** of these and keep them in sync:

1. `pyproject.toml` → `version`
2. `server.json` → both `version` fields
3. `CHANGELOG.md` → move `Unreleased` entries under the new version

`src/clockify_mcp/__init__.py` derives `__version__` from package metadata, so it does
not need editing. `bundle/manifest.json` is stamped automatically by
`scripts/build-mcpb.sh`.

Then tag and publish:

```bash
git tag vX.Y.Z && git push --tags
```
