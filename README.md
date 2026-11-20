# ViciAuto

Menu-driven terminal tool for bulk changes on ViciDial call-center servers:
copy phones from a template, set phone credentials for users, delete phones
and aliases, or wipe the whole phone list — from a range, a list, or one CSV.

Python 3.9+, three runtime dependencies (`requests`, `colorama`, `tqdm`).

## Quick start (Windows)

```
install.bat      # creates venv\ and installs requirements.txt
run.bat          # launches the TUI
```

`run.bat` passes any arguments through, so `run.bat --list-profiles` works too.

## Profiles

A profile is a named server connection: base URL, admin user/password,
endpoints, and an SSL-verify flag. They live in `servers.json` at the project
root (git-ignored). The first launch has none — choose **A. Add a new profile**,
enter the URL and admin credentials, and the connection is verified before it
is saved.

Environment variables override stored values without touching the file:

```
set VICIAUTO_BASE_URL=https://dm3.callengine.org
set VICIAUTO_ADMIN_USER=6666
set VICIAUTO_ADMIN_PASS=your-password
```

`run.bat --list-profiles` prints the saved profiles.

## Operations

| Menu | What it does |
| --- | --- |
| 1. Copy Phones | Clone an existing phone into a range/CSV of extensions, with a generated conference secret per phone. |
| 2. Phone Credentials Configuration | Set `phone_login`, `phone_pass`, `user_password`, `full_name` per user. |
| 3. Delete Phones & Aliases | Delete phones only, aliases only, or both. |
| 4. Delete All Phones & Aliases | List everything on the server, then delete after an explicit `DELETE` confirmation. |
| D. Toggle dry-run | Simulate a run without sending requests. |

Every bulk run shows a progress bar, throttles requests
(`request_delay_ms`, default 200 ms), retries only transient failures, and ends
with an ok/failed summary. A single failing item never aborts the run.

## CSV input

One file drives every operation; each row's `action` selects what happens to
it. `templates/bulk_actions.csv` is the committed reference shape (real `*.csv`
files are git-ignored, because they contain user credentials):

```
action,user_id,user_password,phone_extension,server_ip,phone_pass,full_name,alias_id
copy_phone,,,,4001,,, 
delete_phone,,,,4002,,,
update_user,5001,secret,5001,,secret,Bob,
delete_alias,,,,,,,SALES_TEAM
```

- `phone_extension` doubles as `extension` and `phone_login`.
- `server_ip` is optional; it is resolved from the server when blank.
- Rows missing a field required by their action are skipped with a `row N`
  warning.
- Empty cells mean "leave unchanged / not applicable".

## Tests

```
venv\Scripts\python -m pip install -r requirements-dev.txt
venv\Scripts\python -m pytest -q
```

The suite covers response parsing, CSV normalization, retry/exception
behaviour, worker error mapping, login validation, and config recovery. It
never touches the network.

## Project layout

```
viciauto.py            entry point
viciauto_core/         app, audit, client, collection, config, operations, response, runner, ui
docs/                  architecture and domain notes
templates/             committed CSV reference shape (bulk_actions.csv)
tests/                 pytest suite
learning_resources/    superseded scripts kept for reference
install.bat, run.bat   Windows setup and launcher
```

See `docs/architecture.md` for the module map and `docs/contexts.md` for the
ViciDial domain vocabulary.
