# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
WORKDIR /src
COPY . .
RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /wheels

FROM python:3.12-slim
# Ownership marker required by the MCP Registry for OCI packages — must match
# the "name" in server.json.
LABEL io.modelcontextprotocol.server.name="io.github.tracegazer/clockify-mcp" \
      org.opencontainers.image.source="https://github.com/tracegazer/clockify-mcp" \
      org.opencontainers.image.description="Full-coverage Clockify MCP server" \
      org.opencontainers.image.licenses="MIT"
RUN useradd --create-home --uid 1000 app
COPY --from=builder /wheels/*.whl /tmp/
# Install with the telemetry extra so CLOCKIFY_TELEMETRY works out of the box.
RUN WHEEL="$(ls /tmp/*.whl)" \
    && pip install --no-cache-dir "${WHEEL}[telemetry]" \
    && rm -rf /tmp/*.whl
USER app
# stdio MCP server: the console script runs the server's main().
ENTRYPOINT ["clockify-mcp"]
