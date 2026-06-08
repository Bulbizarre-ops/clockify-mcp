# Security Policy

## Supported versions

Only the latest released version of `clockify-mcp` receives security fixes.

| Version | Supported |
| ------- | --------- |
| latest  | ✅        |
| older   | ❌        |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report privately via GitHub's [private vulnerability reporting](https://github.com/tracegazer/clockify-mcp/security/advisories/new)
(Security → Report a vulnerability). You should receive an acknowledgement within a
few days. If a fix is warranted, it will be released and credited (unless you prefer
to remain anonymous).

## Handling of credentials

`clockify-mcp` authenticates to Clockify with a single API key (`X-Api-Key`).

- The key is read from `CLOCKIFY_API_KEY` (env) or a local `config.toml` and is never
  written back to disk.
- The API key is redacted from error messages and from all OpenTelemetry spans, metrics,
  and logs before export.
- Treat your Clockify API key like a password: scope it to the minimum access you need
  and run the server in read-only mode (`CLOCKIFY_ACCESS_MODE=read`, the default) unless
  you explicitly require write tools.
