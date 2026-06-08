# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-06-08

### Fixed
- Corrected the advertised tool count to **112 distinct tools** (was 117). The 117
  figure counted `@mcp.tool` decorators; `time_entries` re-registers 5 time-entry
  write tools for the `time-tracking` access tier (mutually exclusive with `full`),
  so 5 were duplicate registrations. 112 = 48 read + 64 write, matching the README
  domain tables.
- Unified the one-line description across pyproject / server.json / MCPB manifest.
- README write-tools header now leads with `CLOCKIFY_ACCESS_MODE=full` instead of
  the legacy `CLOCKIFY_ENABLE_WRITES=true`.

## [0.3.0] - 2026-06-08

### Added
- `py.typed` marker so downstream consumers get type information.
- CI jobs for packaging (`uv build` + import smoke) and dependency auditing (`pip-audit`).
- Release workflow: on `v*` tag, builds and publishes to PyPI via Trusted
  Publishing (OIDC) and creates a GitHub release with artifacts.
- Release workflow also publishes the manifest to the official MCP Registry
  (GitHub OIDC, no token), stamping `server.json` with the tag version so the
  registry never lags the released package.
- Multi-arch Docker image (`linux/amd64`, `linux/arm64`) published to
  `ghcr.io/tracegazer/clockify-mcp` on every release, and exposed as an `oci`
  package in `server.json` so container users are discoverable via the registry.
- Release workflow publishes the `.mcpb` bundle to Smithery on each tag
  (gated on a `SMITHERY_API_KEY` secret; skipped with a warning if unset).
- The `.mcpb` bundle is built once in CI and attached as an asset to every
  GitHub Release (same artifact used for Smithery), enabling one-click install
  into Claude Desktop. Documented prominently near the top of the README.
- Dependabot configuration for Python deps and GitHub Actions.
- `SECURITY.md`, `CONTRIBUTING.md`, issue/PR templates.

### Changed
- `__version__` is now derived from package metadata instead of a hardcoded string,
  removing version drift between `__init__.py` and `pyproject.toml`.
- Expanded Ruff lint rule set (`I`, `UP`, `B`, `SIM`, `RUF`) and applied fixes.
- Package maturity bumped from Alpha to Beta.

## [0.2.2] - 2026-06-08

### Added
- MCP registry metadata (official registry / Glama / Smithery).

## [0.2.1] - 2026-06-08

### Fixed
- Shared-report create filter handling.

## [0.2.0] - 2026-06-08

### Added
- Phase 8b: attendance and expense reports, shared reports, and `fetch_all`
  pagination across high-volume list tools.

## [0.1.0] - 2026-06-08

### Added
- Initial release: read tools across core Clockify domains, opt-in write tools
  gated by `CLOCKIFY_ACCESS_MODE`, and optional OpenTelemetry observability.

[Unreleased]: https://github.com/tracegazer/clockify-mcp/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/tracegazer/clockify-mcp/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/tracegazer/clockify-mcp/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/tracegazer/clockify-mcp/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/tracegazer/clockify-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/tracegazer/clockify-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tracegazer/clockify-mcp/releases/tag/v0.1.0
