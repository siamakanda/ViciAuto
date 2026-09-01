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
action,extension,server_ip,user_id,phone_login,phone_pass,user_password,full_name,alias_id
```

Actions: `copy_phone`, `update_user`, `delete_phone`, `delete_alias`.

- Range mode (copy/update/delete phone) sets `phone_login`/`phone_pass` to the ID.
- CSV mode for `update_user` also honors `user_password` and `full_name` (or `name`).
