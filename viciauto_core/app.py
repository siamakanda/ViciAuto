"""Application orchestration: login flow, profile selection, bulk menu."""

import sys
import time

from colorama import Fore, Style
import tqdm

from . import ui
from .client import ViciClient
from .config import ADMIN_ENDPOINT, API_ENDPOINT, Config, DEFAULT_SERVER_IP, SAMPLE_CSV_PATH
from .operations import Operations


class ViciAutoApp:
    def __init__(self):
        self.config = Config()

    # ------------------------------------------------------------------
    # Top level
    # ------------------------------------------------------------------
    def run(self) -> None:
        profile = self._select_profile(allow_new=True)
        if profile:
            self._bulk_menu(profile)

    # ------------------------------------------------------------------
    # Profile selection & login
    # ------------------------------------------------------------------
    def _select_profile(self, allow_new: bool = True) -> dict:
        self.config.list_profiles()
        choices = list(self.config.profiles.items())

        if allow_new:
            print(f"  [{Fore.GREEN}N{Style.RESET_ALL}] New login / add profile")

        if not choices and not allow_new:
            print(f"{Fore.RED}No profiles configured.{Style.RESET_ALL}")
            sys.exit(1)

        while True:
            prompt = f"  Select profile [1-{len(choices)}]" + (" or N" if allow_new else "") + ": "
            raw = input(prompt).strip()
            if allow_new and raw.lower() in ("n", "new"):
                return self._login_flow()
            if raw.isdigit() and 1 <= int(raw) <= len(choices):
                return self.config.get_profile(choices[int(raw) - 1][0])
            print(f"{Fore.RED}  Invalid selection.{Style.RESET_ALL}")

    def _login_flow(self) -> dict:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'─' * 60}")
        print(f"  ViciDial Login")
        print(f"{'─' * 60}{Style.RESET_ALL}")

        domain = input("  Domain (e.g. https://dm3.callengine.org): ").strip()
        if not domain:
            print(f"{Fore.RED}  Domain is required.{Style.RESET_ALL}")
            return self._login_flow()
        if not domain.startswith(("http://", "https://")):
            domain = "https://" + domain

        user = input("  User: ").strip()
        if not user:
            print(f"{Fore.RED}  User is required.{Style.RESET_ALL}")
            return self._login_flow()

        password = input("  Password: ").strip()
        if not password:
            print(f"{Fore.RED}  Password is required.{Style.RESET_ALL}")
            return self._login_flow()

        verify_ssl = input("  Verify SSL? (Y/n): ").strip().lower() not in ("n", "no")

        profile = {
            "base_url": domain.rstrip("/"),
            "admin_user": user,
            "admin_pass": password,
            "verify_ssl": verify_ssl,
            "login_endpoint": ADMIN_ENDPOINT,
            "api_endpoint": API_ENDPOINT,
        }

        print(f"{Fore.CYAN}  Validating credentials...{Style.RESET_ALL}")
        client = ViciClient(profile)
        if not client.validate_login():
            print(f"{Fore.RED}  Login failed: invalid credentials or insufficient API permissions.{Style.RESET_ALL}")
            retry = input("  Try again? (Y/n): ").strip().lower()
            if retry not in ("n", "no"):
                return self._login_flow()
            sys.exit(1)

        print(f"{Fore.GREEN}  Login successful.{Style.RESET_ALL}")

        save = input(f"  Save this login as a profile? ({Fore.GREEN}Y{Style.RESET_ALL}/{Fore.RED}n{Style.RESET_ALL}): ").strip().lower()
        if save in ("", "y", "yes"):
            while True:
                name = input("  Profile name: ").strip()
                if not name:
                    print(f"{Fore.RED}  Name required.{Style.RESET_ALL}")
                    continue
                if name in self.config.profiles:
                    overwrite = input(f"  Profile '{name}' exists. Overwrite? (y/N): ").strip().lower()
                    if overwrite not in ("y", "yes"):
                        continue
                break
            profile["_name"] = name
            self.config.add_profile(name, profile)
            print(f"{Fore.GREEN}  Saved profile '{name}'.{Style.RESET_ALL}")
            return profile

        profile["_name"] = "(session)"
        return profile

    # ------------------------------------------------------------------
    # Bulk menu
    # ------------------------------------------------------------------
    def _bulk_menu(self, profile: dict) -> None:
        while True:
            print()
            print(f"{Fore.CYAN}{Style.BRIGHT}{'═' * 60}")
            print(f"  Bulk Operations — {profile['_name']} ({profile['base_url']})")
            print(f"{'═' * 60}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}1{Style.RESET_ALL}. Update User Phones & Pass   (range / CSV)")
            print(f"  {Fore.WHITE}2{Style.RESET_ALL}. Bulk Phone Creation / Copy   (range / CSV)")
            print(f"  {Fore.WHITE}3{Style.RESET_ALL}. Bulk Phone Delete & Alias Delete (range / CSV)")
            print(f"  {Fore.WHITE}4{Style.RESET_ALL}. Delete All Phones & Phone Alias List")
            print(f"  {Fore.WHITE}5{Style.RESET_ALL}. Switch profile")
            print(f"  {Fore.WHITE}0{Style.RESET_ALL}. Back")
            print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")

            choice = input("  Select option: ").strip()

            if choice == "0":
                return
            elif choice == "1":
                self._update_user_phones(profile)
            elif choice == "2":
                self._create_phones(profile)
            elif choice == "3":
                self._delete_phones_and_aliases(profile)
            elif choice == "4":
                self._delete_all(profile)
            elif choice == "5":
                new_profile = self._select_profile(allow_new=True)
                if new_profile:
                    profile = new_profile
            else:
                print(f"{Fore.RED}  Invalid option.{Style.RESET_ALL}")

    # ------------------------------------------------------------------
    # Bulk runner
    # ------------------------------------------------------------------
    def _run(self, profile, title, items, ops, worker, unit, destructive=False):
        session = ops.client.make_session()
        ops.set_session(session)
        try:
            ui.run_bulk(
                items, worker, title=title, profile=profile, unit=unit,
                destructive=destructive,
                delay_ms=self.config.defaults("request_delay_ms", 200),
                max_retries=self.config.defaults("max_retries", 2),
                dry_run=self.config.defaults("dry_run", False),
            )
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Option 1 — Update user phones & pass
    # ------------------------------------------------------------------
    def _update_user_phones(self, profile: dict) -> None:
        records = self._collect_user_records()
        if not records:
            return
        client = ViciClient(profile)
        ops = Operations(client)
        self._run(profile, "Update User Phones", records, ops, ops.update_user_phone, "user")

    # ------------------------------------------------------------------
    # Option 2 — Bulk phone creation / copy
    # ------------------------------------------------------------------
    def _create_phones(self, profile: dict) -> None:
        default_server_ip = profile.get("server_ip", DEFAULT_SERVER_IP)

        mode = input("  Mode: (R)ange or (C)SV? [R]: ").strip().lower()
        if mode in ("c", "csv"):
            records = Operations.read_csv(
                input(f"  CSV path [{SAMPLE_CSV_PATH}]: ").strip() or SAMPLE_CSV_PATH
            )
            for r in records:
                r.setdefault("extension", r.get("phone_login") or r.get("user_id"))
        else:
            server_ip = input(f"  Server IP [{default_server_ip}]: ").strip() or default_server_ip
            start = ui.prompt_int("  Start extension: ", 4001)
            end = ui.prompt_int("  End extension:   ", 4050)
            if start > end:
                print(f"{Fore.RED}  Start cannot exceed End.{Style.RESET_ALL}")
                return
            records = [{"extension": str(i), "server_ip": server_ip}
                       for i in range(start, end + 1)]

        if not records:
            return

        copy_phone = input("  Copy settings from phone [7001]: ").strip() or "7001"
        conf_secret = ui.generate_conf_secret()
        conf_secret = input(f"  Conference secret [{conf_secret}]: ").strip() or conf_secret

        client = ViciClient(profile)
        ops = Operations(client)

        def worker(rec):
            return ops.copy_phone(rec, copy_phone, conf_secret)

        self._run(profile, "Create/Copy Phones", records, ops, worker, "phone")

    # ------------------------------------------------------------------
    # Option 3 — Bulk phone delete & alias delete
    # ------------------------------------------------------------------
    def _delete_phones_and_aliases(self, profile: dict) -> None:
        print(f"\n  Delete target:")
        print(f"    [{Fore.GREEN}1{Style.RESET_ALL}] Phones only")
        print(f"    [{Fore.GREEN}2{Style.RESET_ALL}] Phone aliases only")
        print(f"    [{Fore.GREEN}3{Style.RESET_ALL}] Both")
        target = input("  Choose [1]: ").strip() or "1"

        default_server_ip = profile.get("server_ip", DEFAULT_SERVER_IP)
        server_ip = default_server_ip
        if target in ("1", "3"):
            server_ip = input(f"  Server IP [{default_server_ip}]: ").strip() or default_server_ip

        if target in ("1", "3"):
            phones = self._collect_phone_items(server_ip)
            if phones:
                client = ViciClient(profile)
                ops = Operations(client)
                self._run(profile, "Delete Phones", phones, ops, ops.delete_phone, "phone", destructive=True)

        if target in ("2", "3"):
            aliases = self._collect_alias_items()
            if aliases:
                client = ViciClient(profile)
                ops = Operations(client)
                self._run(profile, "Delete Phone Aliases", aliases, ops, ops.delete_alias, "alias", destructive=True)

    # ------------------------------------------------------------------
    # Option 4 — Delete all phones & aliases
    # ------------------------------------------------------------------
    def _delete_all(self, profile: dict) -> None:
        print(f"{Fore.RED}{Style.BRIGHT}  This will DELETE every phone and phone alias on the server.{Style.RESET_ALL}")
        if not ui.confirm_destructive():
            return

        client = ViciClient(profile)
        ops = Operations(client)
        session = client.make_session()
        ops.set_session(session)

        try:
            phones = client.list_phones()
            aliases = client.list_aliases()
            print(f"\n  Found {len(phones)} phones and {len(aliases)} aliases.\n")

            delay_ms = self.config.defaults("request_delay_ms", 200)

            ok_phones = 0
            failed_phones = []
            phone_items = [{"extension": e, "server_ip": ip} for e, ip in phones]
            for rec in tqdm.tqdm(phone_items, desc="Deleting phones", unit="phone", file=sys.stdout):
                ok, msg = ops.delete_phone(rec)
                if ok:
                    ok_phones += 1
                else:
                    failed_phones.append((rec["extension"], msg))
                    tqdm.tqdm.write(f"  {Fore.RED}[FAIL]{Style.RESET_ALL} {rec['extension']} - {msg}")
                time.sleep(delay_ms / 1000.0)

            ok_aliases = 0
            failed_aliases = []
            alias_items = [{"alias_id": a} for a in aliases]
            for rec in tqdm.tqdm(alias_items, desc="Deleting aliases", unit="alias", file=sys.stdout):
                ok, msg = ops.delete_alias(rec)
                if ok:
                    ok_aliases += 1
                else:
                    failed_aliases.append((rec["alias_id"], msg))
                    tqdm.tqdm.write(f"  {Fore.RED}[FAIL]{Style.RESET_ALL} {rec['alias_id']} - {msg}")
                time.sleep(delay_ms / 1000.0)
        finally:
            session.close()

        print()
        border = "=" * 60
        print(f"{Fore.CYAN}{Style.BRIGHT}{border}")
        print(f"  Phones deleted : {ok_phones}/{len(phone_items)}")
        print(f"  Aliases deleted: {ok_aliases}/{len(alias_items)}")
        if failed_phones:
            print(f"  Failed phones  : {', '.join(x[0] for x in failed_phones)}")
        if failed_aliases:
            print(f"  Failed aliases : {', '.join(x[0] for x in failed_aliases)}")
        print(f"{Fore.CYAN}{Style.BRIGHT}{border}{Style.RESET_ALL}")
        print()

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------
    def _collect_user_records(self) -> list:
        print(f"\n  Update user phones — input source:")
        print(f"    [{Fore.GREEN}1{Style.RESET_ALL}] Range")
        print(f"    [{Fore.GREEN}2{Style.RESET_ALL}] CSV")
        mode = input("  Choose [1]: ").strip() or "1"

        if mode == "2":
            return Operations.read_csv(
                input(f"  CSV path [{SAMPLE_CSV_PATH}]: ").strip() or SAMPLE_CSV_PATH
            )

        start = ui.prompt_int("  Start user ID: ", 5001)
        end = ui.prompt_int("  End user ID:   ", 5015)
        if start > end:
            print(f"{Fore.RED}  Start cannot exceed End.{Style.RESET_ALL}")
            return []
        return [{"user_id": str(i), "phone_login": str(i), "phone_pass": str(i)}
                for i in range(start, end + 1)]

    def _collect_phone_items(self, server_ip: str) -> list:
        mode = input("  Mode: (R)ange or (C)SV? [R]: ").strip().lower()
        if mode in ("c", "csv"):
            records = Operations.read_csv(
                input(f"  CSV path [{SAMPLE_CSV_PATH}]: ").strip() or SAMPLE_CSV_PATH
            )
            for r in records:
                r.setdefault("extension", r.get("phone_login") or r.get("user_id"))
            return [{"extension": r["extension"], "server_ip": server_ip}
                    for r in records if r.get("extension")]

        start = ui.prompt_int("  Start extension: ", 4001)
        end = ui.prompt_int("  End extension:   ", 4050)
        if start > end:
            print(f"{Fore.RED}  Start cannot exceed End.{Style.RESET_ALL}")
            return []
        return [{"extension": str(i), "server_ip": server_ip}
                for i in range(start, end + 1)]

    def _collect_alias_items(self) -> list:
        mode = input("  Alias input: (L)ist or (C)SV? [L]: ").strip().lower()
        if mode in ("c", "csv"):
            records = Operations.read_csv(
                input(f"  CSV path [{SAMPLE_CSV_PATH}]: ").strip() or SAMPLE_CSV_PATH
            )
            return [{"alias_id": r["alias_id"]} for r in records if r.get("alias_id")]

        raw = input("  Comma-separated alias_id values: ").strip()
        if not raw:
            print(f"{Fore.YELLOW}  No aliases provided.{Style.RESET_ALL}")
            return []
        return [{"alias_id": x.strip()} for x in raw.split(",") if x.strip()]
