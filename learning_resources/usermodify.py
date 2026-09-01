#!/usr/bin/env python3
"""
Bulk User Phone Modifier for VICIdial / Asterisk-based PBX systems.

Supports two modes:
  Range mode  - sets phone_login, phone_pass, user_password to the user ID
  CSV mode    - reads custom values per user from a CSV file

Profiles (server credentials, endpoints, defaults) are stored in servers.json.
"""

import argparse
import csv
import json
import os
import sys
import time
from typing import Optional

import colorama
from colorama import Fore, Style
import requests
import tqdm
import urllib3

colorama.init(autoreset=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "servers.json")
SAMPLE_CSV_PATH = os.path.join(SCRIPT_DIR, "sample.csv")


class AuthError(Exception):
    pass


class UserRecord:
    __slots__ = ("user_id", "phone_login", "phone_pass", "user_password")

    def __init__(self, user_id: str, phone_login: str = "", phone_pass: str = "", user_password: str = ""):
        self.user_id = user_id.strip()
        self.phone_login = str(phone_login).strip() if phone_login and str(phone_login).strip() else self.user_id
        self.phone_pass = str(phone_pass).strip() if phone_pass and str(phone_pass).strip() else self.user_id
        self.user_password = str(user_password).strip() if user_password and str(user_password).strip() else self.user_id


class UserModifier:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if not os.path.exists(CONFIG_PATH):
            print(f"{Fore.YELLOW}Config file not found at: {CONFIG_PATH}")
            print(f"{Fore.YELLOW}A template will be created. Edit it and re-run.")
            template = {
                "profiles": {
                    "example": {
                        "base_url": "https://your-server.com",
                        "admin_user": "6666",
                        "admin_pass": "your-password",
                        "verify_ssl": True,
                        "login_endpoint": "vicidial/admin.php",
                        "api_endpoint": "non_agent_api.php"
                    }
                },
                "defaults": {
                    "request_delay_ms": 200,
                    "max_retries": 2,
                    "dry_run": False
                }
            }
            with open(CONFIG_PATH, "w") as f:
                json.dump(template, f, indent=2)
            sys.exit(1)

        with open(CONFIG_PATH, "r") as f:
            return json.load(f)

    def list_profiles(self) -> None:
        profiles = self.config.get("profiles", {})
        if not profiles:
            print(f"{Fore.YELLOW}No profiles configured in servers.json.")
            return
        print(f"\n{Fore.CYAN}{Style.BRIGHT}Available profiles:{Style.RESET_ALL}")
        print("-" * 65)
        for i, (name, p) in enumerate(profiles.items(), 1):
            verify = "SSL-verify" if p.get("verify_ssl", True) else "no-verify"
            print(f"  [{Fore.GREEN}{i}{Style.RESET_ALL}] {Fore.WHITE}{name:<15}{Style.RESET_ALL} "
                  f"-> {p.get('base_url', '?')}  (admin: {p.get('admin_user', '?')})  [{verify}]")
        print("-" * 65)

    def _get_profile(self, name: str) -> dict:
        profiles = self.config.get("profiles", {})
        if name not in profiles:
            print(f"{Fore.RED}Error: Profile '{name}' not found in servers.json.")
            print(f"{Fore.YELLOW}Available: {', '.join(profiles.keys())}")
            sys.exit(1)
        return profiles[name]

    def _get_default(self, key: str, fallback=None):
        return self.config.get("defaults", {}).get(key, fallback)

    def authenticate(self, profile: dict) -> tuple:
        session = requests.Session()

        if not profile.get("verify_ssl", True):
            session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        base_url = profile["base_url"].rstrip("/")
        api_endpoint = profile.get("api_endpoint", "non_agent_api.php")
        admin_user = profile["admin_user"]
        admin_pass = profile["admin_pass"]

        url = f"{base_url}/{api_endpoint}"
        params = {
            "source": "admin",
            "function": "update_user",
            "user": admin_user,
            "pass": admin_pass,
            "agent_user": "99999999"
        }

        try:
            resp = session.get(url, params=params, timeout=15)
            if resp.ok and "login" not in resp.text.lower() and resp.status_code != 302:
                return session, None
        except Exception:
            pass

        login_endpoint = profile.get("login_endpoint", "vicidial/admin.php")
        login_url = f"{base_url}/{login_endpoint}"
        login_data = {
            "user": admin_user,
            "pass": admin_pass,
            "SUBMIT": "LOGIN"
        }

        try:
            resp = session.post(login_url, data=login_data, timeout=15, allow_redirects=True)
            cookies = session.cookies.get_dict()
            if cookies:
                return session, cookies
        except Exception as e:
            raise AuthError(f"Login request failed: {e}")

        raise AuthError(
            "Authentication failed: direct query-param auth returned an error "
            "and login-flow did not produce a session cookie."
        )

    def update_user(self, record: UserRecord, session, profile: dict, dry_run: bool = False) -> tuple:
        base_url = profile["base_url"].rstrip("/")
        api_endpoint = profile.get("api_endpoint", "non_agent_api.php")
        url = f"{base_url}/{api_endpoint}"

        params = {
            "source": "admin",
            "function": "update_user",
            "user": profile["admin_user"],
            "pass": profile["admin_pass"],
            "agent_user": record.user_id,
            "user_password": record.user_password,
            "phone_login": record.phone_login,
            "phone_pass": record.phone_pass
        }

        if dry_run:
            return True, "DRY-RUN"

        try:
            resp = session.get(url, params=params, timeout=15)
            if resp.ok and "error" not in resp.text.lower():
                return True, "Updated"
            else:
                return False, f"HTTP {resp.status_code} - {resp.reason}"
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection refused / unreachable"
        except Exception as e:
            return False, str(e)[:60]

    def read_csv(self, path: str) -> list:
        if not os.path.exists(path):
            print(f"{Fore.RED}Error: CSV file not found: {path}")
            sys.exit(1)

        records = []
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                print(f"{Fore.RED}Error: CSV file is empty or has no header row.")
                sys.exit(1)

            required = "user_id"
            if required not in (c.strip() if c else "" for c in reader.fieldnames):
                print(f"{Fore.RED}Error: CSV must have a 'user_id' column.")
                print(f"{Fore.YELLOW}Found columns: {', '.join(reader.fieldnames)}")
                sys.exit(1)

            for row_num, row in enumerate(reader, start=2):
                uid = row.get("user_id", "").strip()
                if not uid:
                    print(f"{Fore.YELLOW}Warning: Skipping row {row_num} - empty user_id.")
                    continue

                record = UserRecord(
                    user_id=uid,
                    phone_login=row.get("phone_login", ""),
                    phone_pass=row.get("phone_pass", ""),
                    user_password=row.get("user_password", "")
                )
                records.append(record)

        if not records:
            print(f"{Fore.RED}Error: No valid rows found in CSV.")
            sys.exit(1)

        return records

    def process(self, users: list, profile: dict, delay_ms: int, max_retries: int, dry_run: bool = False) -> dict:
        total = len(users)
        ok_count = 0
        failed = []

        try:
            session, cookies = self.authenticate(profile)
            auth_method = "cookie-based" if cookies else "query-param"
            print(f"{Fore.CYAN}  Auth method : {auth_method}")
        except AuthError as e:
            print(f"{Fore.RED}  Auth error  : {e}")
            sys.exit(1)

        bar_fmt = (
            "{l_bar}{bar}| {n_fmt}/{total_fmt}  "
            f"{Fore.GREEN}[OK]{{postfix[ok]}}{Style.RESET_ALL}  "
            f"{Fore.RED}[FAIL]{{postfix[fail]}}{Style.RESET_ALL}"
        )

        postfix_data = {"ok": 0, "fail": 0}

        desc_text = "DRY-RUN" if dry_run else "Processing"
        with tqdm.tqdm(total=total, desc=desc_text, unit="user", bar_format=bar_fmt,
                       postfix=postfix_data, file=sys.stdout) as pbar:

            for user in users:
                last_error = None
                final_success = False

                for attempt in range(1, max_retries + 2):
                    success, msg = self.update_user(user, session, profile, dry_run=dry_run)
                    if success:
                        final_success = True
                        break
                    last_error = msg

                    if attempt <= max_retries:
                        tqdm.tqdm.write(f"    {Fore.YELLOW}[RETRY] Retry {attempt}/{max_retries} for {user.user_id}{Style.RESET_ALL}")
                        time.sleep(0.3)

                if final_success:
                    tqdm.tqdm.write(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} {user.user_id} - {msg}")
                    ok_count += 1
                    pbar.postfix["ok"] = ok_count
                else:
                    tqdm.tqdm.write(f"  {Fore.RED}[FAIL]{Style.RESET_ALL} {user.user_id} - {last_error}")
                    failed.append((user.user_id, last_error))
                    pbar.postfix["fail"] = len(failed)

                pbar.update(1)
                time.sleep(delay_ms / 1000.0)

        session.close()
        return {"ok": ok_count, "failed": failed, "total": total}

    def print_summary(self, results: dict, profile: dict, duration: float) -> None:
        ok_count = results["ok"]
        failed = results["failed"]
        total = results["total"]
        failed_count = len(failed)

        print()
        width = 60
        border = "=" * width
        print(f"{Fore.CYAN}{Style.BRIGHT}{border}")
        print(f"  Profile   : {profile.get('_name', '?')} ({profile['base_url']})")
        print(f"  Admin     : {profile['admin_user']}")
        print(f"  Total     : {total} users")
        print(f"  Duration  : {duration:.1f}s")
        print(f"  {Fore.WHITE}{'_' * (width - 2)}{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}Updated{' ' * 4}: {ok_count}{Style.RESET_ALL}")
        print(f"  {Fore.RED}Failed{' ' * 6}: {failed_count}{Style.RESET_ALL}")
        if failed:
            fail_ids = ", ".join(f"{uid} ({err})" for uid, err in failed)
            print(f"  Failed IDs : {fail_ids}")
        print(f"{Fore.CYAN}{Style.BRIGHT}{border}{Style.RESET_ALL}")
        print()

        if failed_count > 0:
            sys.exit(1)

    def run_range(self, start: int, end: int, profile_name: str, **overrides) -> None:
        profile = self._get_profile(profile_name)
        profile["_name"] = profile_name

        delay_ms = overrides.get("delay_ms", self._get_default("request_delay_ms", 200))
        max_retries = overrides.get("retries", self._get_default("max_retries", 2))
        dry_run = overrides.get("dry_run", self._get_default("dry_run", False))

        users = [UserRecord(user_id=str(i)) for i in range(start, end + 1)]

        self._print_banner(profile_name, profile, len(users), f"{start} -> {end} (range)")

        if not self._confirm():
            return

        results = self._run_with_timing(users, profile, delay_ms, max_retries, dry_run)
        self.print_summary(results, profile, results["_duration"])

    def run_csv(self, csv_path: str, profile_name: str, **overrides) -> None:
        profile = self._get_profile(profile_name)
        profile["_name"] = profile_name

        delay_ms = overrides.get("delay_ms", self._get_default("request_delay_ms", 200))
        max_retries = overrides.get("retries", self._get_default("max_retries", 2))
        dry_run = overrides.get("dry_run", self._get_default("dry_run", False))

        users = self.read_csv(csv_path)

        self._print_banner(profile_name, profile, len(users), f"{os.path.basename(csv_path)} (CSV)")

        if not self._confirm():
            return

        results = self._run_with_timing(users, profile, delay_ms, max_retries, dry_run)
        self.print_summary(results, profile, results["_duration"])

    def _run_with_timing(self, users, profile, delay_ms, max_retries, dry_run):
        start_time = time.time()
        results = self.process(users, profile, delay_ms, max_retries, dry_run)
        results["_duration"] = time.time() - start_time
        return results

    def _print_banner(self, name: str, profile: dict, count: int, source: str) -> None:
        print()
        print(f"{Fore.CYAN}{Style.BRIGHT}{'─' * 60}")
        print(f"  Bulk User Phone Modifier")
        print(f"  Profile  : {name}  ->  {profile['base_url']}")
        print(f"  Admin    : {profile['admin_user']}")
        print(f"  Users    : {count}  ({source})")
        print(f"{'─' * 60}{Style.RESET_ALL}")
        print()

    @staticmethod
    def _confirm() -> bool:
        while True:
            resp = input(f"  Proceed? ({Fore.GREEN}Y{Style.RESET_ALL}/{Fore.RED}n{Style.RESET_ALL}): ").strip().lower()
            if resp in ("", "y", "yes"):
                return True
            if resp in ("n", "no"):
                print(f"{Fore.YELLOW}  Aborted.{Style.RESET_ALL}")
                return False

    def interactive(self) -> None:
        profiles = self.config.get("profiles", {})
        if not profiles:
            print(f"{Fore.RED}No profiles configured in servers.json. Exiting.")
            sys.exit(1)

        print(f"\n{Fore.CYAN}{Style.BRIGHT}Available profiles:{Style.RESET_ALL}")
        print("-" * 65)
        profile_list = list(profiles.items())
        for i, (name, p) in enumerate(profile_list, 1):
            verify = "SSL-verify" if p.get("verify_ssl", True) else "no-verify"
            print(f"  [{Fore.GREEN}{i}{Style.RESET_ALL}] {Fore.WHITE}{name:<15}{Style.RESET_ALL} "
                  f"-> {p.get('base_url', '?')}  (admin: {p.get('admin_user', '?')})  [{verify}]")
        print("-" * 65)

        while True:
            choice = input(f"\n  Select profile [1-{len(profile_list)}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(profile_list):
                profile_name = profile_list[int(choice) - 1][0]
                break
            print(f"{Fore.RED}  Invalid selection. Choose 1-{len(profile_list)}.{Style.RESET_ALL}")

        profile = profiles[profile_name]
        profile["_name"] = profile_name

        mode = input(f"\n  Mode: ({Fore.GREEN}R{Style.RESET_ALL})ange or ({Fore.GREEN}C{Style.RESET_ALL})SV? [R]: ").strip().lower()

        if mode in ("c", "csv"):
            csv_path = input(f"  CSV file path [{SAMPLE_CSV_PATH}]: ").strip()
            if not csv_path:
                csv_path = SAMPLE_CSV_PATH
            users = self.read_csv(csv_path)
            source = f"{os.path.basename(csv_path)} (CSV)"
        else:
            while True:
                start_raw = input("  Start user ID: ").strip()
                if not start_raw or not start_raw.lstrip("-").isdigit():
                    print(f"{Fore.RED}  Must be a numeric value.{Style.RESET_ALL}")
                    continue
                start = int(start_raw)
                if start <= 0:
                    print(f"{Fore.RED}  Must be a positive number.{Style.RESET_ALL}")
                    continue
                break

            while True:
                end_raw = input("  End user ID:   ").strip()
                if not end_raw or not end_raw.lstrip("-").isdigit():
                    print(f"{Fore.RED}  Must be a numeric value.{Style.RESET_ALL}")
                    continue
                end = int(end_raw)
                if end <= 0:
                    print(f"{Fore.RED}  Must be a positive number.{Style.RESET_ALL}")
                    continue
                break

            if start > end:
                print(f"{Fore.RED}  Error: Start ({start}) is larger than End ({end}).{Style.RESET_ALL}")
                sys.exit(1)

            users = [UserRecord(user_id=str(i)) for i in range(start, end + 1)]
            source = f"{start} -> {end} (range)"

        pass_override = input(f"\n  Admin password [{profile.get('admin_pass', '')[:4]}****]: ").strip()
        if pass_override:
            profile["admin_pass"] = pass_override

        dry_run_input = input(f"  Dry run? (y/N): ").strip().lower()
        dry_run = dry_run_input in ("y", "yes")

        self._print_banner(profile_name, profile, len(users), source)

        if not self._confirm():
            return

        delay_ms = self._get_default("request_delay_ms", 200)
        max_retries = self._get_default("max_retries", 2)

        results = self._run_with_timing(users, profile, delay_ms, max_retries, dry_run)
        self.print_summary(results, profile, results["_duration"])


def main():
    parser = argparse.ArgumentParser(
        description="Bulk update phone login/pass/user_pass for VICIdial users."
    )
    parser.add_argument("--profile", "-p", help="Server profile name from servers.json")
    parser.add_argument("--start", type=int, help="Start of user ID range")
    parser.add_argument("--end", type=int, help="End of user ID range")
    parser.add_argument("--csv", help="Path to CSV file with per-user values")
    parser.add_argument("--pass", dest="admin_pass", help="Override admin password")
    parser.add_argument("--delay", type=int, help="Request delay in ms (overrides config)")
    parser.add_argument("--retries", type=int, help="Max retries per user (overrides config)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without sending requests")
    parser.add_argument("--log", help="Write detailed log to file")
    parser.add_argument("--list-profiles", action="store_true", help="Show configured profiles and exit")

    args = parser.parse_args()
    modifier = UserModifier()

    if args.list_profiles:
        modifier.list_profiles()
        return

    if not args.profile and not args.start and not args.csv:
        modifier.interactive()
        return

    if not args.profile:
        print(f"{Fore.RED}Error: --profile is required when using CLI arguments.{Style.RESET_ALL}")
        sys.exit(1)

    overrides = {}
    if args.delay is not None:
        overrides["delay_ms"] = args.delay
    if args.retries is not None:
        overrides["retries"] = args.retries
    if args.dry_run:
        overrides["dry_run"] = True

    profile_cfg = modifier._get_profile(args.profile)
    if args.admin_pass:
        profile_cfg["admin_pass"] = args.admin_pass

    if args.csv:
        modifier.run_csv(args.csv, args.profile, **overrides)
    elif args.start is not None and args.end is not None:
        if args.start <= 0 or args.end <= 0:
            print(f"{Fore.RED}Error: Range values must be positive.{Style.RESET_ALL}")
            sys.exit(1)
        if args.start > args.end:
            print(f"{Fore.RED}Error: Start range cannot be larger than End range.{Style.RESET_ALL}")
            sys.exit(1)
        modifier.run_range(args.start, args.end, args.profile, **overrides)
    else:
        print(f"{Fore.RED}Error: Provide --start/--end for range mode or --csv for CSV mode.{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    main()
