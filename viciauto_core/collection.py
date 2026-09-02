"""Input collection helpers for bulk operations (range, list, CSV)."""

from colorama import Fore, Style

from . import ui
from .config import SAMPLE_CSV_PATH
from .operations import (
    ACTION_DELETE_ALIAS,
    ACTION_DELETE_PHONE,
    ACTION_UPDATE_USER,
    Operations,
)


def collect_user_records(mode: str = None) -> list:
    mode = mode or ui.range_or_csv_menu()

    if mode == "C":
        return Operations.read_csv(
            ui.prompt_csv_path(SAMPLE_CSV_PATH),
            action=ACTION_UPDATE_USER,
        )

    start = ui.prompt_int("  First user ID: ", 5001)
    end = ui.prompt_int("  Last user ID:  ", 5015)
    if start > end:
        print(f"{Fore.RED}  First user ID must be lower than or equal to the last.{Style.RESET_ALL}")
        return []
    return [{"user_id": str(i), "phone_login": str(i), "phone_pass": str(i)}
            for i in range(start, end + 1)]


def collect_phone_items(mode: str = None) -> list:
    mode = mode or ui.range_or_csv_menu()
    if mode == "C":
        records = Operations.read_csv(
            ui.prompt_csv_path(SAMPLE_CSV_PATH),
            action=ACTION_DELETE_PHONE,
        )
        return [{"extension": r["extension"], "server_ip": r.get("server_ip", "")}
                for r in records if r.get("extension")]

    start = ui.prompt_int("  First extension: ", 4001)
    end = ui.prompt_int("  Last extension:  ", 4050)
    if start > end:
        print(f"{Fore.RED}  First extension must be lower than or equal to the last.{Style.RESET_ALL}")
        return []
    return [{"extension": str(i), "server_ip": ""}
            for i in range(start, end + 1)]


def collect_alias_items(mode: str = None) -> list:
    mode = mode or ui.list_or_csv_menu()
    if mode == "C":
        records = Operations.read_csv(
            ui.prompt_csv_path(SAMPLE_CSV_PATH),
            action=ACTION_DELETE_ALIAS,
        )
        return [{"alias_id": r["alias_id"]} for r in records if r.get("alias_id")]

    raw = input("  Comma-separated alias IDs: ").strip()
    if not raw:
        print(f"{Fore.YELLOW}  No aliases provided.{Style.RESET_ALL}")
        return []
    return [{"alias_id": x.strip()} for x in raw.split(",") if x.strip()]


def collect_both_delete():
    mode = ui.range_or_csv_menu()
    if mode == "C":
        records = Operations.read_csv(
            ui.prompt_csv_path(SAMPLE_CSV_PATH)
        )
        phones = [{"extension": r["extension"], "server_ip": r.get("server_ip", "")}
                  for r in records
                  if r.get("action", "").lower() == ACTION_DELETE_PHONE and r.get("extension")]
        aliases = [{"alias_id": r["alias_id"]}
                   for r in records
                   if r.get("action", "").lower() == ACTION_DELETE_ALIAS and r.get("alias_id")]
        return phones, aliases

    phones = collect_phone_items(mode="R")
    aliases = collect_alias_items(mode="L")
    return phones, aliases


def resolve_phone_server_ips(client, records: list) -> list:
    """Resolve each extension's server_ip from the server, dropping misses.

    Extensions absent from the phone list are skipped with a warning; a
    CSV-supplied server_ip is kept only as a fallback when the extension
    is not on the server.
    """
    try:
        ip_map = client.phone_ip_map()
    except Exception as e:
        ip_map = {}
        print(f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL} Could not list phones ({e}); relying on CSV/default IPs.")

    resolved = []
    for rec in records:
        ext = rec["extension"]
        if ext in ip_map:
            resolved.append({"extension": ext, "server_ip": ip_map[ext]})
        elif rec.get("server_ip"):
            resolved.append({"extension": ext, "server_ip": rec["server_ip"]})
        else:
            print(f"  {Fore.YELLOW}[SKIP]{Style.RESET_ALL} {ext} - not found on server")
    return resolved
