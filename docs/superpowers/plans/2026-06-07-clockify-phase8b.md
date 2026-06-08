# Phase 8b — attendance/expense reports, shared-reports CRUD, fetch_all

Date: 2026-06-07. Surface verified against the official Clockify OpenAPI 3.0.1
(`https://docs.clockify.me/openapi.json`, cached `/tmp/clockify_openapi.json`).
All report + shared-report endpoints live on the **reports host**
(`https://reports.api.clockify.me/v1`, regional `/report/v1`), NOT the regular host.

## Scope decisions (user-confirmed 2026-06-07)

- **fetch_all**: helper `fetch_all_pages()` in `pagination.py` + opt-in `fetch_all: bool`
  param on the high-volume list tools only: time_entries, projects, clients, tasks,
  tags, users.
- **attendance/expense reports**: JSON `generate_*` read tools AND extend `export_report`
  (8a) to accept `report_type` `attendance` / `expenses` (file export).
- **shared_reports**: new domain — read (list/get) + write (create/update/delete).

## Tasks

1. **client.py** — add reports-host verbs: `report_get(path, params)`, `report_put(path, json)`,
   `report_delete(path, params)` (mirror the regular-host get/put/delete, base=`reports_base`).
2. **pagination.py** — `fetch_all_pages(fetch_page, *, page_size=50, max_pages=...)`: call
   `fetch_page(page, page_size)` until an empty or short (< page_size) page; concatenate.
   (Clockify list endpoints return plain lists; `client.get` does not surface headers, so
   we detect the last page by a short/empty batch rather than the `Last-Page` header.)
3. **reports.py**:
   - `generate_attendance_report(date_range_start, date_range_end, page, page_size, ...)`
     → `POST workspaces/{ws}/reports/attendance` (body: dateRangeStart/End + attendanceFilter{page,pageSize}).
   - `generate_expense_report(date_range_start, date_range_end, page, page_size, ...)`
     → `POST workspaces/{ws}/reports/expenses/detailed` (body: dateRangeStart/End + page/pageSize).
   - extend `export_report`: accept `report_type` in detailed|summary|weekly|attendance|expenses.
     attendance → `reports/attendance` (attendanceFilter{}); expenses → `reports/expenses/detailed`.
4. **shared_reports.py** (new domain):
   - read: `list_shared_reports(page, page_size, shared_reports_filter)` →
     `GET workspaces/{ws}/shared-reports`; `get_shared_report(shared_report_id, ...)` →
     `GET shared-reports/{id}` (NOT workspace-scoped; optional date-range/export/page query).
   - write (full): `create_shared_report(name, type, ...)` → POST; `update_shared_report`
     (name required; isPublic/fixedDate/visibility ONLY — no filter/type) → PUT;
     `delete_shared_report` → DELETE (204).
   - register in server.py (read always; writes via `_register_writes` when writes_enabled).
5. **fetch_all wiring** — add `fetch_all: bool = False` to the 6 list fns + their registered
   tools; when True, loop via `fetch_all_pages` (closure builds per-page params), else single page.
6. **tests** — test_pagination (fetch_all_pages), test_reports (attendance/expense/export),
   test_shared_reports (CRUD, respx), fetch_all param on a representative list domain.
7. **docs** — README tool table + CLAUDE.md domain notes; live-smoke additions.

## Verified facts (do not re-derive)

- attendance required body: dateRangeStart, dateRangeEnd, attendanceFilter. sortColumn enum
  USER/DATE/START/END/BREAK/WORK/CAPACITY/OVERTIME/TIME_OFF. exportType JSON/PDF/CSV/XLSX/ZIP.
- expense detailed required: dateRangeStart, dateRangeEnd. response typed {expenses[], totals{}}.
  pagination is top-level page/pageSize (camelCase, NOT hyphenated).
- shared-report `type` enum includes DETAILED/WEEKLY/SUMMARY/EXPENSE_DETAILED/ATTENDANCE/...
  create filter requires nested filter.dateRangeStart/End. update accepts name(req)/isPublic/
  fixedDate/visibleToUsers/visibleToUserGroups ONLY. delete → 204. generate-by-id is
  `GET /v1/shared-reports/{id}` (no workspace), still ApiKey-authenticated.
- All shared-report + report endpoints on the reports host.
</content>
</invoke>
