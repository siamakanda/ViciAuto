"""Console UI helpers (prompts, banners, summaries)."""

import os
import secrets
import string
import sys

from colorama import Fore, Style


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


def menu(title, options, *, width=MENU_WIDTH, prompt="Choice", default=None, subtitle=None, style="bracket", actions=None) -> str:
    """Render a bordered menu and return the selected key (upper-cased).

    `options` is a list of (key, label) tuples rendered vertically. `actions`,
    if given, is a list of (key, label) tuples rendered on a single horizontal
    row below a separator border. `style` is "bracket" or "dot".
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
    if actions:
        print(f"{Fore.CYAN}{border}{Style.RESET_ALL}")
        parts = [f"[{Fore.GREEN}{key}{Style.RESET_ALL}] {label}" for key, label in actions]
        print("  " + "    ".join(parts))
    print(f"{Fore.CYAN}{border}{Style.RESET_ALL}")
    valid_keys = [k for k, _ in options] + [k for k, _ in (actions or [])]
    return choose_key(valid_keys, f"  {prompt}: ", default=default)


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


def prompt_csv_path(default_path: str) -> str:
    """Prompt for a CSV path, showing a friendly basename as the default."""
    return input(f"  CSV path [{os.path.basename(default_path)}]: ").strip() or default_path


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
