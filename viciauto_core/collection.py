"""Input collection helpers for bulk operations (range, list, CSV)."""

from colorama import Fore, Style

from . import ui
from .config import DEFAULTS, SAMPLE_CSV_PATH
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

    start = ui.prompt_int("  First user ID: ", DEFAULTS["range_start_user"])
    end = ui.prompt_int("  Last user ID:  ", DEFAULTS["range_end_user"])
    if start > end:
        print(f"{Fore.RED}  First user ID must be lower than or equal to the last.{Style.RESET_ALL}")
        return []
    return [{"user_id": str(i), "phone_login": str(i), "phone_pass": str(i)} for i in range(start, end + 1)]


def collect_phone_items(mode: str = None, action: str = ACTION_DELETE_PHONE) -> list:
    mode = mode or ui.range_or_csv_menu()
    if mode == "C":
        records = Operations.read_csv(
            ui.prompt_csv_path(SAMPLE_CSV_PATH),
            action=action,
        )
        return [
            {"extension": r["extension"], "server_ip": r.get("server_ip", "")}
            for r in records
            if r.get("extension")
        ]

    start = ui.prompt_int("  First extension: ", DEFAULTS["range_start_phone"])
    end = ui.prompt_int("  Last extension:  ", DEFAULTS["range_end_phone"])
    if start > end:
        print(f"{Fore.RED}  First extension must be lower than or equal to the last.{Style.RESET_ALL}")
        return []
    return [{"extension": str(i), "server_ip": ""} for i in range(start, end + 1)]


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
        records = Operations.read_csv(ui.prompt_csv_path(SAMPLE_CSV_PATH))
        phones = [
            {"extension": r["extension"], "server_ip": r.get("server_ip", "")}
            for r in records
            if r.get("action", "").lower() == ACTION_DELETE_PHONE and r.get("extension")
        ]
        aliases = [
            {"alias_id": r["alias_id"]}
            for r in records
            if r.get("action", "").lower() == ACTION_DELETE_ALIAS and r.get("alias_id")
        ]
        return phones, aliases

    phones = collect_phone_items(mode="R")
    aliases = collect_alias_items(mode="L")
    return phones, aliases


def resolve_phone_server_ips(client, records: list, session=None) -> list:
    """Resolve each extension's server_ip from the server, dropping misses.

    An extension registered on several Asterisk servers is expanded into one
    record per IP, so a delete targets every copy instead of silently removing
    one and reporting success. Extensions absent from the phone list are skipped
    with a warning unless the record carried its own server_ip.
    """
    try:
        ip_map = client.phone_ip_map(session=session)
    except Exception as e:
        ip_map = {}
        print(f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL} Could not list phones ({e}); relying on supplied IPs.")

    resolved = []
    for rec in records:
        ext = rec["extension"]
        ips = ip_map.get(ext)
        if ips:
            if len(ips) > 1:
                print(
                    f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL} {ext} exists on "
                    f"{len(ips)} servers: {', '.join(ips)}"
                )
            resolved.extend({"extension": ext, "server_ip": ip} for ip in ips)
        elif rec.get("server_ip"):
            resolved.append({"extension": ext, "server_ip": rec["server_ip"]})
        else:
            print(f"  {Fore.YELLOW}[SKIP]{Style.RESET_ALL} {ext} - not found on server")
    return resolved
