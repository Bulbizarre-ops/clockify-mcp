"""Async HTTP client for the Clockify API (regular + reports hosts)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .config import Config
from .errors import ErrorCategory, classify_error
from .telemetry import Telemetry

MAX_ERROR_LEN = 1000
_REDACTED = "***REDACTED***"
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds


def _form_str(value: Any) -> str:
    """Render a multipart form value: bools as lowercase true/false, else str()."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class ClockifyAPIError(Exception):
    """Raised when the Clockify API returns a non-2xx response.

    category/hint are set by classify_error when the failure matches a known case
    (plan missing, feature/permission, auth). Both are None for generic errors.
    The display string appends ` [<category.value>] <hint>` only when hint is present;
    the original sanitized message is always a substring of str(exc).
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        body: Any = None,
        *,
        category: ErrorCategory | None = None,
        hint: str | None = None,
    ):
        display = f"Clockify API error {status_code}: {message}"
        if hint and category:
            display = f"{display} [{category.value}] {hint}"
        super().__init__(display)
        self.status_code = status_code
        self.body = body
        self.category = category
        self.hint = hint


class ClockifyClient:
    """Thin async wrapper over the Clockify REST API.

    Two hosts: the regular API (config.regular_base) and the Reports API
    (config.reports_base). Read methods are exposed now; write verbs exist for
    later phases but are only surfaced as tools when writes are enabled.
    """

    def __init__(
        self,
        config: Config,
        http_client: httpx.AsyncClient | None = None,
        telemetry: Telemetry | None = None,
    ):
        self._config = config
        self._telemetry = telemetry or Telemetry()
        self._client = http_client or httpx.AsyncClient(
            headers={"X-Api-Key": config.api_key},
            timeout=30.0,
        )
        self._secrets = [s for s in (config.api_key,) if s]
        self._current_user_id: str | None = None

    @property
    def writes_enabled(self) -> bool:
        return self._config.enable_writes

    @property
    def default_workspace_id(self) -> str | None:
        return self._config.default_workspace_id

    @property
    def time_tracking_enabled(self) -> bool:
        return self._config.access_mode in ("time-tracking", "full")

    async def current_user_id(self) -> str:
        """Return the authenticated user's id (cached after the first call)."""
        if self._current_user_id is None:
            user = await self.get("user")
            self._current_user_id = user["id"]
        return self._current_user_id

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", self._config.regular_base, path, params=params)

    async def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        """GET raw bytes (binary downloads such as expense receipt files)."""
        return await self._request(
            "GET", self._config.regular_base, path, params=params, raw=True
        )

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            "POST", self._config.regular_base, path, params=params, json=json
        )

    async def put(
        self, path: str, json: dict[str, Any] | list[Any] | None = None
    ) -> Any:
        return await self._request("PUT", self._config.regular_base, path, json=json)

    async def patch(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._request("PATCH", self._config.regular_base, path, json=json)

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("DELETE", self._config.regular_base, path, params=params)

    async def report(self, path: str, json: dict[str, Any] | None = None) -> Any:
        """POST to the Reports API host (reports return data via POST filters)."""
        return await self._request("POST", self._config.reports_base, path, json=json)

    async def report_bytes(self, path: str, json: dict[str, Any] | None = None) -> bytes:
        """POST to the Reports API host and return raw bytes (PDF/CSV/XLSX exports)."""
        return await self._request(
            "POST", self._config.reports_base, path, json=json, raw=True
        )

    async def report_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET from the Reports API host (e.g. shared-reports list / generate-by-id)."""
        return await self._request("GET", self._config.reports_base, path, params=params)

    async def report_put(self, path: str, json: dict[str, Any] | None = None) -> Any:
        """PUT to the Reports API host (e.g. update a shared report)."""
        return await self._request("PUT", self._config.reports_base, path, json=json)

    async def report_delete(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """DELETE on the Reports API host (e.g. delete a shared report)."""
        return await self._request("DELETE", self._config.reports_base, path, params=params)

    async def post_multipart(
        self,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        """POST multipart/form-data (e.g. an expense with an optional receipt file)."""
        return await self._request(
            "POST", self._config.regular_base, path, data=data, files=files
        )

    async def put_multipart(
        self,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        """PUT multipart/form-data (expense update with an optional receipt file)."""
        return await self._request(
            "PUT", self._config.regular_base, path, data=data, files=files
        )

    async def _request(
        self,
        method: str,
        base: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        url = f"{base}/{path.lstrip('/')}"
        multipart = (
            self._multipart_parts(data, files)
            if data is not None or files is not None
            else None
        )
        with self._telemetry.client_span(method, path, params or json or data) as span:
            response = await self._send_with_retry(
                method, url, params=self._clean(params), json=json, files=multipart
            )
            span.set_status_code(response.status_code)
            if raw:
                result = self._handle_bytes(response)
                span.set_result({"bytes": len(result)})
                return result
            result = self._handle(response)
            span.set_result(result)
            return result

    async def _send_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any],
        json: dict[str, Any] | None,
        files: list[tuple[str, Any]] | None = None,
    ) -> httpx.Response:
        """Send, retrying 429 with light exponential backoff (honors Retry-After).

        Up to _MAX_RETRIES retries AFTER the initial attempt (so a persistently
        rate-limited request makes 1 + _MAX_RETRIES total calls before the final
        429 is returned to the caller).
        """
        attempt = 0
        while True:
            response = await self._client.request(
                method, url, params=params or None, json=json, files=files
            )
            if response.status_code != 429 or attempt >= _MAX_RETRIES:
                return response
            delay = self._retry_delay(response, attempt)
            await asyncio.sleep(delay)
            attempt += 1

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return _BACKOFF_BASE * (2**attempt)

    @staticmethod
    def _clean(values: dict[str, Any] | None) -> dict[str, Any]:
        """Drop None values from query params."""
        return {k: v for k, v in (values or {}).items() if v is not None}

    @staticmethod
    def _multipart_parts(
        data: dict[str, Any] | None, files: dict[str, Any] | None
    ) -> list[tuple[str, Any]]:
        """Build an httpx multipart 'files' list from scalar fields + file parts.

        Scalar fields become ``(name, (None, str_value))`` parts so the request is
        multipart/form-data even with no file attached. List/tuple values expand
        into repeated parts (e.g. ``changeFields``). Booleans are rendered as the
        lowercase ``true``/``false`` the API expects. Real files pass through as
        ``(name, (filename, content, content_type))``. None values are dropped.

        Callers must supply at least one non-None field or a file; httpx omits the
        multipart framing for a fully empty parts list. Clockify's expense
        endpoints always have required fields, so this holds in practice.
        """
        parts: list[tuple[str, Any]] = []
        for key, value in (data or {}).items():
            if value is None:
                continue
            items = value if isinstance(value, (list, tuple)) else [value]
            for item in items:
                parts.append((key, (None, _form_str(item))))
        for key, file_part in (files or {}).items():
            parts.append((key, file_part))
        return parts

    def _handle(self, response: httpx.Response) -> Any:
        if response.is_success:
            if not response.content:
                return None
            return response.json()
        self._raise_for_error(response)

    def _handle_bytes(self, response: httpx.Response) -> bytes:
        if response.is_success:
            return response.content
        self._raise_for_error(response)

    def _raise_for_error(self, response: httpx.Response) -> None:
        try:
            body = response.json()
            message = body.get("message") or body.get("error") or response.text
        except Exception:
            body = response.text
            message = response.text
        sanitized = self._sanitize(message)
        category, hint = classify_error(response.status_code, sanitized)
        raise ClockifyAPIError(
            response.status_code,
            sanitized,
            self._sanitize(body),
            category=category,
            hint=hint,
        )

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, str):
            for secret in self._secrets:
                value = value.replace(secret, _REDACTED)
            if len(value) > MAX_ERROR_LEN:
                value = value[:MAX_ERROR_LEN] + "...[truncated]"
            return value
        if isinstance(value, dict):
            return {k: self._sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize(v) for v in value]
        return value

    async def aclose(self) -> None:
        await self._client.aclose()
