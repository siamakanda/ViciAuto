"""Append-only audit trail for bulk runs.

Every run — destructive or not, dry-run or real — leaves a JSON-lines record so
that an irreversible change can always be traced back to a who/when/what. Never
logs credentials.
"""

import json
import time


def record(event: dict, path: str) -> None:
    """Append one JSON line to the audit log, creating it if needed."""
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **event}
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
