"""Console UI helpers (prompts, banners, summaries)."""

import secrets
import string
import sys

from colorama import Fore, Style

import tqdm


def generate_conf_secret(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def read_key() -> str:
    """Read a single character without requiring Enter (cross-platform)."""
    try:
        import msvcrt
    except ImportError:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    ch = msvcrt.getch()
    try:
        return ch.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        return ""


MENU_WIDTH = 72


def choose_key(valid_keys, prompt: str = "Select: ", default=None) -> str:
    """Prompt for a single keypress and return it only when valid."""
    valid = {str(k).upper() for k in valid_keys}
    if default is not None:
        default = str(default).upper()
    while True:
        print(prompt, end="", flush=True)
        key = read_key()
        if key in ("\r", "\n"):
            if default is not None:
                print(default)
                return default
            continue
        key = key.upper()
        if key in valid:
            print(key)
            return key


def menu(title, options, *, width=MENU_WIDTH, prompt="Choice", default=None, subtitle=None, style="bracket") -> str:
    """Render a bordered menu and return the selected key (upper-cased).

    `options` is a list of (key, label) tuples. `style` is "bracket" or "dot".
    """
    border = "─" * width
    print()
    print(f"{Fore.CYAN}{Style.BRIGHT}{border}")
    print(f"  {title}")
    if subtitle:
        print(subtitle)
    print(f"{border}{Style.RESET_ALL}")
    for key, label in options:
        if style == "dot":
            print(f"  {Fore.GREEN}{key}.{Style.RESET_ALL} {label}")
        else:
            print(f"  [{Fore.GREEN}{key}{Style.RESET_ALL}] {label}")
    print(f"{Fore.CYAN}{border}{Style.RESET_ALL}")
    return choose_key([k for k, _ in options], f"  {prompt}: ", default=default)


def range_or_csv_menu() -> str:
    """Ask the operator to pick Range or CSV input; returns 'R' or 'C'."""
    return menu("Input Source", [("R", "Range"), ("C", "CSV")], prompt="Source", default="R")


def list_or_csv_menu() -> str:
    """Ask the operator to pick manual list or CSV input; returns 'L' or 'C'."""
    return menu("Input Source", [("L", "Manual list"), ("C", "CSV")], prompt="Source", default="L")


def prompt_int(prompt: str, default: int) -> int:
    while True:
        raw = input(prompt).strip()
        if not raw:
            return default
        if raw.lstrip("-").isdigit():
            return int(raw)
        print(f"{Fore.RED}  Must be a numeric value.{Style.RESET_ALL}")


def confirm() -> bool:
    while True:
        resp = input(f"  Proceed? ({Fore.GREEN}Y{Style.RESET_ALL}/{Fore.RED}n{Style.RESET_ALL}): ").strip().lower()
        if resp in ("", "y", "yes"):
            return True
        if resp in ("n", "no"):
            print(f"{Fore.YELLOW}  Aborted.{Style.RESET_ALL}")
            return False


def confirm_destructive() -> bool:
    print(f"{Fore.RED}{Style.BRIGHT}  This action permanently deletes data and cannot be undone.{Style.RESET_ALL}")
    while True:
        resp = input(f"  Type {Fore.RED}DELETE{Style.RESET_ALL} to continue, or {Fore.GREEN}n{Style.RESET_ALL} to cancel: ").strip()
        if resp == "DELETE":
            return True
        if resp.lower() in ("n", "no", "cancel", ""):
            print(f"{Fore.YELLOW}  Cancelled.{Style.RESET_ALL}")
            return False
        print(f"{Fore.RED}  Type exactly 'DELETE' to continue, or 'n' to cancel.{Style.RESET_ALL}")


def print_banner(title: str, profile: dict, count: int, source: str, dry_run: bool = False) -> None:
    print()
    print(f"{Fore.CYAN}{Style.BRIGHT}{'─' * MENU_WIDTH}")
    print(f"  {title}")
    print(f"  Profile  : {profile['_name']}  ->  {profile['base_url']}")
    print(f"  User     : {profile['admin_user']}")
    print(f"  Count    : {count}  ({source})")
    if dry_run:
        print(f"  Mode     : {Fore.YELLOW}{Style.BRIGHT}DRY-RUN{Style.RESET_ALL}")
    print(f"{'─' * MENU_WIDTH}{Style.RESET_ALL}")
    print()


def print_task_summary(ok_count: int, failed: list, total: int, action: str = "Successful") -> None:
    failed_count = len(failed)
    print()
    border = "─" * MENU_WIDTH
    print(f"{Fore.CYAN}{Style.BRIGHT}{border}")
    print(f"  Processed : {total}")
    print(f"  {Fore.GREEN}{action:<10}: {ok_count}{Style.RESET_ALL}")
    print(f"  {Fore.RED}Failed    : {failed_count}{Style.RESET_ALL}")
    if failed:
        fail_ids = ", ".join(f"{uid} ({err})" for uid, err in failed)
        print(f"  Failures  : {fail_ids}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{border}{Style.RESET_ALL}")
    print()


def item_label(item) -> str:
    if isinstance(item, dict):
        return str(item.get("user_id") or item.get("extension") or item.get("alias_id") or item)
    return str(item)


def run_bulk(items, worker, *, title, profile, unit, destructive=False,
             delay_ms=200, max_retries=2, dry_run=False):
    """Run a worker over items with retries and a progress bar.

    `worker(item) -> (bool, str)`.
    """
    print_banner(title, profile, len(items), f"{len(items)} {unit}s", dry_run=dry_run)
    if not (confirm_destructive() if destructive else confirm()):
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

            label = item_label(item)
            if final_success:
                ok_count += 1
            else:
                failed.append((label, last_error))
                tqdm.tqdm.write(f"  {Fore.RED}[FAIL]{Style.RESET_ALL} {label} - {last_error}")

            pbar.update(1)

    print_task_summary(ok_count, failed, len(items))
