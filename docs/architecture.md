# ViciAuto — Architecture

A menu-driven TUI (Python 3, no framework) for automating bulk tasks against
ViciDial. It has a thin entry point plus a single package of small,
single-responsibility modules.

## Module layout

| Module | Responsibility |
| --- | --- |
| `viciauto.py` | Entry point: CLI args, colorama init, top-level `KeyboardInterrupt` handler |
| `viciauto_core/app.py` | Orchestration: profile selection/login, menus, operation flows |
| `viciauto_core/collection.py` | Input collection: range / list / CSV parsing into item records |
| `viciauto_core/runner.py` | Bulk execution: throttling, retry classification, progress bar, summary |
| `viciauto_core/operations.py` | Per-item workers (`copy_phone`, `delete_phone`, `delete_alias`, `update_user_phone`) + unified CSV parser + action constants |
| `viciauto_core/client.py` | Low-level HTTP: sessions, URL builders, API GETs, `admin.php` GET/POST, paginated list scraping |
| `viciauto_core/config.py` | Config load/save (atomic, self-recovering), profile CRUD, env-var overrides |
| `viciauto_core/response.py` | Centralized ViciDial response parsing (`parse_response`, `parse_copy_result`) |
| `viciauto_core/audit.py` | Append-only JSON-lines audit trail for bulk runs (`audit.log`) |
| `viciauto_core/ui.py` | Presentation only: menus, key reading, banners, confirmations (holds no state) |

## Dependency direction

```
viciauto.py
   └── app.py ──┬── collection.py ──┬── ui.py
                │                   └── operations.py
                ├── runner.py ──────┼── ui.py
                ├── operations.py ──┼── client.py
                │                   └── response.py
                ├── client.py ──────┼── config.py
                │                   └── response.py
                └── config.py
```

Rules kept in practice:

- `ui.py` renders and prompts; it keeps no state and performs no HTTP.
- `runner.py` owns iteration, throttling, retries, and the summary.
- `collection.py` only turns user input into item records.
- `operations.py` only turns one record into one API call + parsed result.
- `app.py` wires them together and owns program state (`_dry_run`).

## Request flow for a bulk operation

1. `app.py` picks a profile, shows the bulk menu, and delegates to a flow
   method (e.g. `_create_phones`).
2. `collection.py` gathers target records (range prompt or CSV) and validates
   required fields per action, skipping bad rows with a `row N` warning.
3. `app.py` creates a `ViciClient` + `Operations` and defines a `worker`.
4. `app.py._run` opens **one** shared API session and **one** authenticated
   admin session, hands them to `Operations`, and calls `runner.run_bulk(...)`.
5. `runner.run_bulk` prints a banner, applies the large-batch guard, asks for
   confirmation, then loops over items with delay, retries, and a `tqdm`
   progress bar. Worker exceptions are converted into item failures instead of
   aborting the run.
6. The worker issues the HTTP call and returns
   `(success, message, retryable)`; only transient failures are retried.

Sessions are closed in `finally`, so Ctrl+C and other exceptions never leak
connections.

## Two ViciDial entry points

- `non_agent_api.php` — plain GET endpoints used for updates/deletes
  (`update_user`, `update_phone`, `update_phone_alias`, `user_details`).
- `admin.php` — form POST/GET used for copying phones (`ADD=21222222222`) and
  for scraping the phone/alias list pages. List scraping walks pages until a
  page adds no new records, capped at 50 pages, reusing **one** admin session
  for every page.

> `non_agent_api.php` returns HTTP 200 for both success and error, so status
> codes are ignored in favour of body parsing (`response.py`). The one exception
> is 5xx, which `client.api` raises as `HTTPError` so the runner can retry it.

## Key design decisions

- **Centralized response parsing** (`response.py`) — every worker routes its
  body through `parse_response` or `parse_copy_result` rather than doing ad-hoc
  substring checks.
- **Positive failure detection for copy** (`parse_copy_result`) — a copy is only
  reported successful when the body lacks `PHONE NOT COPIED` *and* lacks
  login/permission page markers. Absence of a failure string alone is not
  treated as success.
- **One run never dies on one item** — `run_bulk` catches worker exceptions,
  records the failure, and continues.
- **Retry only what can succeed later** — workers classify failures as
  transient (timeouts, connection errors, HTTP 5xx) or permanent (validation
  errors, missing records).
- **Throttling is real** — `request_delay_ms` is applied between items and as
  a growing backoff between retries.
- **Modular, no new runtime dependencies** — only `requests`, `colorama`,
  `tqdm`; tests use `pytest` from `requirements-dev.txt`.
- **Unified CSV** with an `action` column; one file drives every operation
  (see `contexts.md`). The committed reference shape lives in
  `templates/bulk_actions.csv`; `*.csv` is git-ignored so real user data can
  never be committed.
- **server_ip auto-detection** — delete/copy resolve the server IP from the
  server itself (`client.phone_ip_map()`) so operators never type it. The
  source phone's IP is resolved independently of the destination's IP.
- **No server_ip, no request** — there is no hardcoded fallback IP. A record
  that cannot be resolved is refused with an explicit error, never sent to a
  guessed server.
- **Every duplicate is targeted** — `phone_ip_map()` returns
  `{extension: [ip, ...]}`. An extension registered on several Asterisk
  servers is expanded into one record per IP so a delete removes all copies.
- **Safety** — destructive actions require an explicit `DELETE` confirmation;
  runs above `max_batch_warn` items require a second confirmation; dry-run is
  a runtime toggle. Delete All lists what exists *before* asking for
  confirmation.
- **Audit trail** (`audit.py`) — every bulk run appends JSON lines to
  `audit.log` (git-ignored): timestamp, operation, profile, base_url, dry-run
  flag, item count, and the ok/failed summary. Destructive runs are recorded
  at start as well as at completion, so a crash still leaves evidence.

## Configuration & secrets

Profiles live in `servers.json` (git-ignored, along with `servers.json.*` so a
`.corrupt-*` backup is never committed). Writes are atomic (temp file +
`os.replace`); an unreadable file is renamed to `servers.json.corrupt-<timestamp>`
and replaced with defaults instead of crashing. Secrets can be overridden via
environment variables (`VICIAUTO_BASE_URL`, `VICIAUTO_ADMIN_USER`,
`VICIAUTO_ADMIN_PASS`) without being written back to disk.

`*.csv` is git-ignored: bulk-input files contain real user credentials. The
committed reference shape is `templates/bulk_actions.csv`, which is synthetic
and explicitly un-ignored.

TLS verification is **on** by default (`verify_ssl` defaults to `True`). A
profile that disables it prints a warning whenever a session is created.

## Audit log

Every `run_bulk` call appends to `audit.log` (git-ignored, JSON lines):

```
{"ts": "2026-11-20T14:02:11", "event": "start", "operation": "Delete All Phones", ...}
{"ts": "2026-11-20T14:02:19", "event": "summary", "ok": 41, "failed": 2, "failures": [...]}
```

Destructive operations log at start as well as completion, so an interrupted
run still leaves a record. Credentials are never written to the log.

## Testing

```
venv\Scripts\python -m pip install -r requirements-dev.txt
venv\Scripts\python -m pytest -q
```

Tests cover response parsing, CSV normalization, retry/exception behaviour,
worker error mapping, login validation, and config recovery. No test touches
the network.
