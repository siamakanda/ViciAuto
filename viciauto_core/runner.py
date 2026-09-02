"""Bulk execution loop: retries, progress bar, and summary."""

import sys

from colorama import Fore, Style
import tqdm

from . import ui


def run_bulk(items, worker, *, title, profile, unit, destructive=False,
             delay_ms=200, max_retries=2, dry_run=False):
    """Run a worker over items with retries and a progress bar.

    `worker(item) -> (bool, str)`.
    """
    ui.print_banner(title, profile, len(items), f"{len(items)} {unit}s", dry_run=dry_run)
    if not (ui.confirm_destructive() if destructive else ui.confirm()):
        return

    ok_count = 0
    failed = []

    with tqdm.tqdm(total=len(items), desc=title, unit=unit, file=sys.stdout) as pbar:
        for item in items:
            last_error = None
            final_success = False

            for attempt in range(1, max_retries + 2):
                if dry_run:
                    success, msg = True, "DRY-RUN"
                else:
                    success, msg = worker(item)
                if success:
                    final_success = True
                    break
                last_error = msg
                if attempt <= max_retries:
                    tqdm.tqdm.write(f"    {Fore.YELLOW}[RETRY] {attempt}/{max_retries} - {msg}{Style.RESET_ALL}")

            label = ui.item_label(item)
            if final_success:
                ok_count += 1
            else:
                failed.append((label, last_error))
                tqdm.tqdm.write(f"  {Fore.RED}[FAIL]{Style.RESET_ALL} {label} - {last_error}")

            pbar.update(1)

    ui.print_task_summary(ok_count, failed, len(items))
