# ViciAuto

Menu-driven TUI for automating ViciDial bulk tasks.

## Bulk Operations menu
  1. Copy Phones
  2. Phone Credentials Configuration
  3. Delete Phones & Aliases
  4. Delete All Phones & Aliases
  5. Switch Profile
  D. Toggle dry-run (runtime-only)
  0. Back

## Profile menu
  - Select a saved profile
  - A. Add a new profile
  - E. Edit a profile
  - R. Remove a profile
  - 0. Back

## Input
Every operation accepts a range (start/end) or a single unified CSV. The CSV
has an `action` column plus the union of all per-task columns; each operation
processes only rows matching its action.

```
action,user_id,user_password,phone_extension,server_ip,phone_pass,full_name,alias_id
```

Actions: `copy_phone`, `update_user`, `delete_phone`, `delete_alias`.

- `phone_extension` doubles as `extension` (copy/delete phone) and `phone_login`
  (update_user); `extension` and `phone_login` are also accepted directly.
- Range mode (copy/update/delete phone) sets `phone_login`/`phone_pass` to the ID.
- CSV mode for `update_user` also honors `user_password` and `full_name` (or `name`).
- Delete-phone rows resolve `server_ip` automatically from the server; copy-phone
  rows resolve it from the source phone.
