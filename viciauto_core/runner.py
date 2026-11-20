"""Bulk execution loop: throttling, retries, progress bar, and summary."""

import sys
import time

import tqdm
from colorama import Fore, Style

from . import audit, ui
from .config import AUDIT_PATH

# Failures containing these hints are worth retrying; anything else (a
# missing user, a validation error) is permanent and would just add load.
TRANSIENT_HINTS = (
    "TIMEOUT",
    "TIMED OUT",
    "CONNECTION",
    "TEMPORARY",
    "HTTP 5",
    "TOO MANY REQUESTS",
)


def _brief(message) -> str:
    return str(message).replace("\n", " ")[:60]


def is_transient(message: str) -> bool:
    upper = str(message or "").upper()
    return any(hint in upper for hint in TRANSIENT_HINTS)


def _unpack(result) -> tuple:
    """Accept (ok, msg) or (ok, msg, retryable) from a worker."""
    if isinstance(result, tuple) and len(result) >= 3:
        return bool(result[0]), result[1], bool(result[2])
    success, message = result
    return bool(success), message, is_transient(message)


def run_bulk(
    items,
    worker,
    *,
    title,
    profile,
    unit,
    destructive=False,
    delay_ms=200,
    max_retries=2,
    dry_run=False,
    batch_warn=500,
    ask=True,
) -> dict:
    """Run a worker over items with throttling, retries, and a progress bar.

    `worker(item) -> (bool, str)` or `(bool, str, retryable)`.

    Returns {"ok": int, "failed": [(label, error), ...]}.
    """
    ui.print_banner(title, profile, len(items), f"{len(items)} {unit}s", dry_run=dry_run)

    if ask and batch_warn and len(items) > batch_warn:
        if not ui.confirm_large_batch(len(items), batch_warn):
            return {"ok": 0, "failed": []}
    if ask and not (ui.confirm_destructive() if destructive else ui.confirm()):
        return {"ok": 0, "failed": []}

    # Record the start of a destructive run, not just its summary, so a crash
    # mid-run still leaves evidence that the operation was started.
    if destructive:
        audit.record(
            {
                "event": "start",
                "operation": title,
                "profile": profile.get("_name"),
                "base_url": profile.get("base_url"),
                "dry_run": dry_run,
                "items": len(items),
            },
            AUDIT_PATH,
        )

    ok_count = 0
    failed = []

    with tqdm.tqdm(total=len(items), desc=title, unit=unit, file=sys.stdout) as pbar:
        for index, item in enumerate(items):
            last_error = None
            final_success = False

            for attempt in range(1, max_retries + 2):
                if dry_run:
                    success, msg, retryable = True, "DRY-RUN", False
                else:
                    try:
                        success, msg, retryable = _unpack(worker(item))
                    except Exception as exc:
                        success, msg, retryable = False, _brief(f"{type(exc).__name__}: {exc}"), True

                if success:
                    final_success = True
                    break

                last_error = msg
                if attempt > max_retries:
                    break
                if not retryable:
                    break

                tqdm.tqdm.write(f"    {Fore.YELLOW}[RETRY] {attempt}/{max_retries} - {msg}{Style.RESET_ALL}")
                time.sleep(min(delay_ms * attempt, 2000) / 1000.0)

            label = ui.item_label(item)
            if final_success:
                ok_count += 1
            else:
                failed.append((label, _brief(last_error)))
                tqdm.tqdm.write(f"  {Fore.RED}[FAIL]{Style.RESET_ALL} {label} - {_brief(last_error)}")

            pbar.update(1)

            if not dry_run and index < len(items) - 1 and delay_ms:
                time.sleep(delay_ms / 1000.0)

    ui.print_task_summary(ok_count, failed, len(items))
    audit.record(
        {
            "event": "summary",
            "operation": title,
            "profile": profile.get("_name"),
            "base_url": profile.get("base_url"),
            "dry_run": dry_run,
            "items": len(items),
            "ok": ok_count,
            "failed": len(failed),
            "failures": [{"item": label, "error": error} for label, error in failed],
        },
        AUDIT_PATH,
    )
    return {"ok": ok_count, "failed": failed}
