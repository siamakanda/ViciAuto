# ViciAuto — Contexts & Concepts

This document describes the domain the app operates in and the vocabulary it
uses. "Context" here means a distinct area of responsibility: dialer profiles,
phones, aliases, and users.

## What the app does

ViciAuto automates bulk changes on a ViciDial call-center server:

- **Copy Phones** — clone an existing phone into a range/CSV of new extensions.
- **Phone Credentials Configuration** — set a user's `phone_login`,
  `phone_pass`, `user_password`, and `full_name` in bulk.
- **Delete Phones & Aliases** — remove phones and/or phone aliases.
- **Delete All Phones & Aliases** — wipe every phone and alias on the server.

## Core concepts

| Concept | Meaning |
| --- | --- |
| **Profile (dialer)** | A named connection to one ViciDial server: base URL, admin user/pass, endpoints, SSL flag. Stored in `servers.json`. |
| **Phone / extension** | A SIP phone record. Keyed by the pair `(extension, server_ip)`. |
| **server_ip** | The IP of the Asterisk server a phone is registered on. An extension number alone is not unique across a cluster. |
| **Phone alias** | A named alias for a group of phones (`alias_id`, e.g. `SALES_TEAM`). |
| **User / agent** | A ViciDial user, identified by `user_id` (also `agent_user`). Has `phone_login`, `phone_pass`, `user_password`, `full_name`. |
| **Conference secret** | A per-phone random secret generated when copying phones. |
| **Action code** | A ViciDial `ADD` parameter selecting an `admin.php` operation. |

## ViciDial endpoints

- **`non_agent_api.php`** — GET API for `update_user`, `update_phone`,
  `update_phone_alias`, `user_details`. Always returns HTTP 200; the body text
  (`SUCCESS:` / `ERROR:` / `NOTICE:`) carries the real result.
- **`admin.php`** — HTML form endpoints. Used for:
  - copying phones (`ADD=21222222222`),
  - listing phones (`ADD=10000000000`),
  - listing aliases (`ADD=12000000000`).

List pages are walked page by page until a page adds no new records (capped at
50 pages). The copy flow returns an HTML page; success is detected by the
**absence** of `PHONE NOT COPIED` **and** the absence of login/permission page
markers (`PLEASE LOGIN`, `INVALID USERNAME`, `PERMISSION DENIED`, …). Failures
include `PHONE NOT COPIED - <reason>`.

## Operations (contexts)

### Copy Phones
Source settings are cloned from an existing phone. The available phones are
fetched and shown **first** — before the input-source prompt — as the highest
three extensions plus a total count, so they appear in both Range and CSV
modes. The source-phone prompt defaults to the highest visible phone; if the
server has no phones the operation stops with a notice (no fallback). Each new
phone gets a generated `conf_secret`. The source phone's `server_ip` is
resolved independently from the destination's `server_ip`, so a CSV row may
target a different Asterisk server than the phone it copies from. A dry-run
prints the source phone, its IP, and the planned count before the loop.

### Phone Credentials Configuration
- **Range mode** — sets `phone_login`/`phone_pass` = user ID (no password).
- **CSV mode** — also honors `user_password` and `full_name`.

### Delete Phones & Aliases
Target selection: phones only / aliases only / both. Phone `server_ip` is
auto-resolved from the server; missing extensions are skipped with a warning,
and an extension registered on several Asterisk servers is deleted from **all**
of them. If no `server_ip` can be resolved the item is refused — there is no
hardcoded fallback server.

### Delete All
Scrapes every phone and alias from the server, prints the counts **before**
asking for an explicit `DELETE` confirmation, then runs both deletions through
the shared bulk runner (retries, throttling, per-item summary). In dry-run it
prints the counts and exits without prompting.

## Input methods

Every bulk operation accepts one of:

- **Range** — a numeric start/end (`First extension:` / `Last extension:`),
  defaulting to the values in `config.DEFAULTS`.
- **List** — comma-separated values (aliases only).
- **CSV** — a single unified file with an `action` column.

## Unified CSV

One file drives all operations. Each row's `action` selects the operation; each
operation filters rows by its own action. The committed reference shape is
`templates/bulk_actions.csv`; `*.csv` elsewhere is git-ignored.

```
action,user_id,user_password,phone_extension,server_ip,phone_pass,full_name,alias_id
```

- Actions: `copy_phone`, `update_user`, `delete_phone`, `delete_alias`.
- `phone_extension` doubles as `extension` (copy/delete phone) and
  `phone_login` (update user). `extension` / `phone_login` are also accepted.
- `name` / `agent_name` are aliases for `full_name`.
- Empty CSV cells mean "leave unchanged / not applicable".
- A row missing a field required by its action is skipped with a
  `row N: missing <field>` warning; the run continues.

## Safety model

- Destructive operations require typing `DELETE` (or `n` to cancel).
- Non-destructive operations require a `Proceed? (Y/n)` confirmation.
- Runs larger than `max_batch_warn` (default 500) require an additional
  confirmation showing the item count.
- **Dry-run** is a runtime toggle (key `D`) that simulates the run without
  sending requests.
- Every run is appended to `audit.log` (JSON lines) with its profile, item
  count, and ok/failed summary; destructive runs are recorded before they start
  as well as when they finish.
- `Ctrl+C` triggers a graceful shutdown (session closed, no traceback), and is
  handled even while a single-key menu prompt is waiting for input.
