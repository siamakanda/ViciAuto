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
| `viciauto_core/runner.py` | Bulk execution loop: retries, progress bar, summary |
| `viciauto_core/operations.py` | Per-item workers (`copy_phone`, `delete_phone`, `delete_alias`, `update_user_phone`) + CSV parser + action constants |
| `viciauto_core/client.py` | Low-level HTTP: sessions, URL builders, API GETs, `admin.php` GET/POST, list scraping |
| `viciauto_core/config.py` | Config load/save, profile CRUD, env-var overrides |
| `viciauto_core/response.py` | Centralized ViciDial response parsing |
| `viciauto_core/ui.py` | Rendering/prompts only: menus, key reading, banners, confirmations |

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

- `ui.py` has **no side effects** (pure rendering/prompts).
- `runner.py` only iterates and calls a `worker(item) -> (bool, str)`.
- `collection.py` only turns user input into item records.
- `operations.py` only turns one record into one API call + parsed result.
- `app.py` wires them together and owns program state (`_dry_run`).

## Request flow for a bulk operation

1. `app.py` picks a profile, shows the bulk menu, and delegates to a flow
   method (e.g. `_create_phones`).
2. `collection.py` gathers target records (range prompt or CSV).
3. `app.py` creates a `ViciClient` + `Operations` and defines a `worker`.
4. `app.py._run` opens a shared `requests.Session` and calls
   `runner.run_bulk(...)`.
5. `runner.run_bulk` prints a banner, asks for confirmation, then loops over
   items with retries and a `tqdm` progress bar, calling the worker.
6. The worker (`operations.py`) issues the HTTP call and interprets the
   response via `response.parse_response`.

Sessions are closed in a `finally`, so Ctrl+C and other exceptions never leak
connections.

## Two ViciDial entry points

- `non_agent_api.php` — plain GET endpoints used for updates/deletes
  (`update_user`, `update_phone`, `update_phone_alias`, `user_details`).
- `admin.php` — form POST/GET used for copying phones (`ADD=21222222222`) and
  for scraping the phone/alias list pages.

> `non_agent_api.php` returns HTTP 200 for both success and error, so status
> codes are ignored in favour of body parsing (`response.py`).

## Key design decisions

- **Centralized response parsing** (`response.py`) — every worker routes its
  body through `parse_response` rather than doing ad-hoc substring checks.
- **Modular, no new dependencies** — menu-driven over Rich/Textual; only
  `requests`, `colorama`, `tqdm`.
- **Unified CSV** with an `action` column; one file drives every operation
  (see `contexts.md`).
- **server_ip auto-detection** — delete/copy resolve the server IP from the
  server itself (`client.phone_ip_map()`) so operators never type it.
- **Safety** — destructive actions require an explicit `DELETE` confirmation;
  dry-run is a runtime toggle.

## Configuration & secrets

Profiles live in `servers.json` (git-ignored). Secrets can be overridden via
environment variables (`VICIAUTO_BASE_URL`, `VICIAUTO_ADMIN_USER`,
`VICIAUTO_ADMIN_PASS`) without being written back to disk.

## Dependencies

See `requirements.txt`: `requests`, `colorama`, `tqdm`.
