"""Application orchestration: login flow, profile selection, bulk menu."""

import sys
import time

from colorama import Fore, Style
import tqdm

from . import ui
from .client import ViciClient
from .collection import (
    collect_alias_items,
    collect_both_delete,
    collect_phone_items,
    collect_user_records,
    resolve_phone_server_ips,
)
from .config import ADMIN_ENDPOINT, API_ENDPOINT, Config, DEFAULT_SERVER_IP, SAMPLE_CSV_PATH
from .operations import ACTION_COPY_PHONE, Operations
from .runner import run_bulk


class ViciAutoApp:
    def __init__(self):
        self.config = Config()
        self._dry_run = self.config.defaults("dry_run", False)

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
        while True:
            choices = list(self.config.profiles.items())

            if not choices and not allow_new:
                print(f"{Fore.RED}No profiles configured.{Style.RESET_ALL}")
                sys.exit(1)

            options = [(str(i + 1), f"{name}  ->  {p.get('base_url', '?')}  (admin: {p.get('admin_user', '?')})")
                       for i, (name, p) in enumerate(choices)]
            actions = []
            if allow_new:
                actions.append(("A", "Add a new profile"))
            if choices:
                actions.append(("E", "Edit a profile"))
                actions.append(("R", "Remove a profile"))
            actions.append(("B", "Back"))

            raw = ui.menu("Saved Profiles", options, prompt="Option", style="dot", actions=actions)
            if raw == "A":
                return self._login_flow()
            if raw == "E":
                self._edit_profile()
                continue
            if raw == "R":
                self._remove_profile()
                continue
            if raw == "B":
                return None
            return self.config.get_profile(choices[int(raw) - 1][0])

    def _edit_profile(self) -> None:
        choices = list(self.config.profiles.items())
        if not choices:
            print(f"{Fore.YELLOW}  No profiles to edit.{Style.RESET_ALL}")
            return
        options = [(str(i + 1), f"{name}  ->  {p.get('base_url', '?')}  (admin: {p.get('admin_user', '?')})")
                   for i, (name, p) in enumerate(choices)]
        raw = ui.menu("Edit Profile", options, prompt="Profile", style="dot")
        name = choices[int(raw) - 1][0]
        profile = self.config.get_profile(name)

        base_url = input(f"  Server URL [{profile['base_url']}]: ").strip()
        admin_user = input(f"  Admin user [{profile['admin_user']}]: ").strip()
        admin_pass = input("  Admin password (Enter to keep): ").strip()
        verify_ssl = input(f"  Verify SSL? (y/n, Enter to keep [{ 'yes' if profile.get('verify_ssl', False) else 'no' }]): ").strip().lower()

        fields = {}
        if base_url:
            if not base_url.startswith(("http://", "https://")):
                base_url = "https://" + base_url
            fields["base_url"] = base_url.rstrip("/")
        if admin_user:
            fields["admin_user"] = admin_user
        if admin_pass:
            fields["admin_pass"] = admin_pass
        if verify_ssl in ("y", "yes"):
            fields["verify_ssl"] = True
        elif verify_ssl in ("n", "no"):
            fields["verify_ssl"] = False

        if not fields:
            print(f"{Fore.YELLOW}  Nothing changed.{Style.RESET_ALL}")
            return

        candidate = dict(profile)
        candidate.update(fields)

        print(f"{Fore.CYAN}  Verifying connection...{Style.RESET_ALL}")
        client = ViciClient(candidate)
        if not client.validate_login():
            print(f"{Fore.RED}  Login failed — changes not saved.{Style.RESET_ALL}")
            return

        self.config.update_profile(name, **fields)
        print(f"{Fore.GREEN}  Updated profile '{name}'.{Style.RESET_ALL}")

    def _remove_profile(self) -> None:
        choices = list(self.config.profiles.items())
        if not choices:
            print(f"{Fore.YELLOW}  No profiles to remove.{Style.RESET_ALL}")
            return
        options = [(str(i + 1), f"{name}  ->  {p.get('base_url', '?')}  (admin: {p.get('admin_user', '?')})")
                   for i, (name, p) in enumerate(choices)]
        raw = ui.menu("Remove Profile", options, prompt="Profile", style="dot")
        name = choices[int(raw) - 1][0]
        print(f"  Remove profile '{name}'?")
        if not ui.confirm():
            return
        self.config.remove_profile(name)
        print(f"{Fore.GREEN}  Removed profile '{name}'.{Style.RESET_ALL}")

    def _login_flow(self) -> dict:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'─' * ui.MENU_WIDTH}")
        print(f"  Add Profile")
        print(f"{'─' * ui.MENU_WIDTH}{Style.RESET_ALL}")

        domain = input("  Server URL (e.g. https://dm3.callengine.org): ").strip()
        if not domain:
            print(f"{Fore.RED}  Server URL is required.{Style.RESET_ALL}")
            return self._login_flow()
        if not domain.startswith(("http://", "https://")):
            domain = "https://" + domain

        user = input("  Admin user: ").strip()
        if not user:
            print(f"{Fore.RED}  Admin user is required.{Style.RESET_ALL}")
            return self._login_flow()

        password = input("  Admin password: ").strip()
        if not password:
            print(f"{Fore.RED}  Admin password is required.{Style.RESET_ALL}")
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

        print(f"{Fore.CYAN}  Verifying connection...{Style.RESET_ALL}")
        client = ViciClient(profile)
        if not client.validate_login():
            print(f"{Fore.RED}  Login failed — invalid credentials or insufficient API permissions.{Style.RESET_ALL}")
            retry = input("  Try again? (Y/n): ").strip().lower()
            if retry not in ("n", "no"):
                return self._login_flow()
            sys.exit(1)

        print(f"{Fore.GREEN}  Connected successfully.{Style.RESET_ALL}")

        save = input(f"  Save this connection as a profile? ({Fore.GREEN}Y{Style.RESET_ALL}/{Fore.RED}n{Style.RESET_ALL}): ").strip().lower()
        if save in ("", "y", "yes"):
            while True:
                name = input("  Profile name: ").strip()
                if not name:
                    print(f"{Fore.RED}  A name is required.{Style.RESET_ALL}")
                    continue
                if name in self.config.profiles:
                    overwrite = input(f"  Profile '{name}' already exists. Overwrite? (y/N): ").strip().lower()
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
            subtitle = f"  {profile['_name']}  ->  {profile['base_url']}"
            if self._dry_run:
                subtitle += f"  {Fore.YELLOW}{Style.BRIGHT}[DRY-RUN]{Style.RESET_ALL}"

            choice = ui.menu(
                "Bulk Operations",
                [
                    ("1", "Copy Phones"),
                    ("2", "Phone Credentials Configuration"),
                    ("3", "Delete Phones & Aliases"),
                    ("4", "Delete All Phones & Aliases"),
                    ("5", "Switch Profile"),
                    ("D", f"Toggle dry-run  ({'ON' if self._dry_run else 'OFF'})"),
                    ("B", "Back"),
                ],
                prompt="Option",
                subtitle=subtitle,
                style="dot",
            )

            if choice == "B":
                return
            elif choice == "D":
                self._dry_run = not self._dry_run
            elif choice == "1":
                self._create_phones(profile)
            elif choice == "2":
                self._update_user_phones(profile)
            elif choice == "3":
                self._delete_phones_and_aliases(profile)
            elif choice == "4":
                self._delete_all(profile)
            elif choice == "5":
                new_profile = self._select_profile(allow_new=True)
                if new_profile:
                    profile = new_profile

    # ------------------------------------------------------------------
    # Bulk runner
    # ------------------------------------------------------------------
    def _run(self, profile, title, items, ops, worker, unit, destructive=False):
        session = ops.client.make_session()
        ops.set_session(session)
        try:
            run_bulk(
                items, worker, title=title, profile=profile, unit=unit,
                destructive=destructive,
                delay_ms=self.config.defaults("request_delay_ms", 200),
                max_retries=self.config.defaults("max_retries", 2),
                dry_run=self._dry_run,
            )
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Option 2 — Phone credentials configuration
    # ------------------------------------------------------------------
    def _update_user_phones(self, profile: dict) -> None:
        records = collect_user_records()
        if not records:
            return
        client = ViciClient(profile)
        ops = Operations(client)
        self._run(profile, "Phone Credentials Configuration", records, ops, ops.update_user_phone, "user")

    # ------------------------------------------------------------------
    # Option 1 — Copy phones
    # ------------------------------------------------------------------
    def _create_phones(self, profile: dict) -> None:
        client = ViciClient(profile)

        try:
            ip_map = client.phone_ip_map()
        except Exception as e:
            ip_map = {}
            print(f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL} Could not list phones ({e}).")

        if not ip_map:
            print(f"  {Fore.YELLOW}No phones found on server to copy from.{Style.RESET_ALL}")
            return

        sample = sorted(ip_map, key=int, reverse=True)[:3]
        default_phone = sample[0]
        print(f"  {Fore.CYAN}Available phones (showing {len(sample)} of {len(ip_map)}):{Style.RESET_ALL}  " + "  ".join(sample))

        mode = ui.range_or_csv_menu()
        if mode == "C":
            records = Operations.read_csv(
                ui.prompt_csv_path(SAMPLE_CSV_PATH),
                action=ACTION_COPY_PHONE,
            )
            records = [r for r in records if r.get("extension")]
        else:
            start = ui.prompt_int("  First extension: ", 4001)
            end = ui.prompt_int("  Last extension:  ", 4050)
            if start > end:
                print(f"{Fore.RED}  First extension must be lower than or equal to the last.{Style.RESET_ALL}")
                return
            records = [{"extension": str(i), "server_ip": ""}
                       for i in range(start, end + 1)]

        if not records:
            return

        copy_phone = input(f"  Copy settings from phone [{default_phone}]: ").strip() or default_phone
        conf_secret = ui.generate_conf_secret()
        conf_secret = input(f"  Conference secret (press Enter to use generated) [{conf_secret}]: ").strip() or conf_secret

        source_ip = ip_map.get(copy_phone)
        if not source_ip:
            source_ip = profile.get("server_ip", DEFAULT_SERVER_IP)
            print(f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL} Source phone {copy_phone} not found on server; using {source_ip}.")

        for rec in records:
            if not rec.get("server_ip"):
                rec["server_ip"] = source_ip

        ops = Operations(client)

        def worker(rec):
            return ops.copy_phone(rec, copy_phone, conf_secret)

        self._run(profile, "Copy Phones", records, ops, worker, "phone")

    # ------------------------------------------------------------------
    # Option 3 — Bulk phone delete & alias delete
    # ------------------------------------------------------------------
    def _delete_phones_and_aliases(self, profile: dict) -> None:
        target = ui.menu(
            "Delete Target",
            [
                ("1", "Phones only"),
                ("2", "Aliases only"),
                ("3", "Both phones and aliases"),
            ],
            prompt="Target",
            default="1",
        )

        phones = []
        aliases = []

        if target == "3":
            phones, aliases = collect_both_delete()
        elif target == "1":
            phones = collect_phone_items()
        else:
            aliases = collect_alias_items()

        if phones:
            client = ViciClient(profile)
            phones = resolve_phone_server_ips(client, phones)
            if not phones:
                print(f"{Fore.YELLOW}  No target phones found on the server.{Style.RESET_ALL}")
            else:
                ops = Operations(client)
                self._run(profile, "Delete Phones", phones, ops, ops.delete_phone, "phone", destructive=True)

        if aliases:
            client = ViciClient(profile)
            ops = Operations(client)
            self._run(profile, "Delete Phone Aliases", aliases, ops, ops.delete_alias, "alias", destructive=True)

    # ------------------------------------------------------------------
    # Option 4 — Delete all phones & aliases
    # ------------------------------------------------------------------
    def _delete_all(self, profile: dict) -> None:
        print(f"{Fore.RED}{Style.BRIGHT}  This permanently deletes every phone and alias on the server.{Style.RESET_ALL}")
        if not ui.confirm_destructive():
            return

        client = ViciClient(profile)
        ops = Operations(client)
        session = client.make_session()
        ops.set_session(session)

        try:
            phones = client.list_phones()
            aliases = client.list_aliases()

            if self._dry_run:
                print(f"\n  {Fore.YELLOW}{Style.BRIGHT}[DRY-RUN] Would delete {len(phones)} phones and {len(aliases)} aliases on the server.{Style.RESET_ALL}\n")
                return

            print(f"\n  Found {len(phones)} phones and {len(aliases)} aliases on the server.\n")

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
        border = "─" * ui.MENU_WIDTH
        print(f"{Fore.CYAN}{Style.BRIGHT}{border}")
        print(f"  Phones deleted : {ok_phones}/{len(phone_items)}")
        print(f"  Aliases deleted: {ok_aliases}/{len(alias_items)}")
        if failed_phones:
            print(f"  Failed phones  : {', '.join(x[0] for x in failed_phones)}")
        if failed_aliases:
            print(f"  Failed aliases : {', '.join(x[0] for x in failed_aliases)}")
        print(f"{Fore.CYAN}{Style.BRIGHT}{border}{Style.RESET_ALL}")
        print()
