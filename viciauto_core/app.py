"""Application orchestration: login flow, profile selection, bulk menu."""

import sys

from colorama import Fore, Style

from . import ui
from .client import ViciClient
from .collection import (
    collect_alias_items,
    collect_both_delete,
    collect_phone_items,
    collect_user_records,
    resolve_phone_server_ips,
)
from .config import (
    ADMIN_ENDPOINT,
    API_ENDPOINT,
    Config,
    ConfigError,
)
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
        try:
            profile = self._select_profile(allow_new=True)
        except ConfigError as exc:
            print(f"{Fore.RED}  {exc}{Style.RESET_ALL}")
            sys.exit(1)
        if profile:
            self._bulk_menu(profile)

    # ------------------------------------------------------------------
    # Profile selection & login
    # ------------------------------------------------------------------
    def _profile_options(self) -> list:
        return [
            (str(i + 1), f"{name}  ->  {p.get('base_url', '?')}  (admin: {p.get('admin_user', '?')})")
            for i, (name, p) in enumerate(self.config.profiles.items())
        ]

    def _select_profile(self, allow_new: bool = True) -> dict:
        while True:
            choices = list(self.config.profiles.items())

            if not choices and not allow_new:
                print(f"{Fore.RED}No profiles configured.{Style.RESET_ALL}")
                sys.exit(1)

            actions = []
            if allow_new:
                actions.append(("A", "Add a new profile"))
            if choices:
                actions.append(("E", "Edit a profile"))
                actions.append(("R", "Remove a profile"))
            actions.append(("B", "Back"))

            raw = ui.menu("Saved Profiles", self._profile_options(), prompt="Option", actions=actions)
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

        raw = ui.menu("Edit Profile", self._profile_options(), prompt="Profile")
        name = choices[int(raw) - 1][0]
        profile = self.config.get_profile(name)

        base_url = input(f"  Server URL [{profile['base_url']}]: ").strip()
        admin_user = input(f"  Admin user [{profile['admin_user']}]: ").strip()
        admin_pass = input("  Admin password (Enter to keep): ").strip()
        verify_ssl = (
            input(f"  Verify SSL? (y/n) [{'yes' if profile.get('verify_ssl', False) else 'no'}]: ")
            .strip()
            .lower()
        )
        login_endpoint = input(f"  Admin endpoint [{profile['login_endpoint']}]: ").strip()
        api_endpoint = input(f"  API endpoint [{profile['api_endpoint']}]: ").strip()
        server_ip = input(f"  Default server IP [{profile['server_ip']}]: ").strip()

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
        if login_endpoint:
            fields["login_endpoint"] = login_endpoint
        if api_endpoint:
            fields["api_endpoint"] = api_endpoint
        if server_ip:
            fields["server_ip"] = server_ip

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

        raw = ui.menu("Remove Profile", self._profile_options(), prompt="Profile")
        name = choices[int(raw) - 1][0]
        print(f"  Remove profile '{name}'?")
        if not ui.confirm():
            return
        self.config.remove_profile(name)
        print(f"{Fore.GREEN}  Removed profile '{name}'.{Style.RESET_ALL}")

    def _prompt_required(self, label: str) -> str:
        while True:
            value = input(label).strip()
            if value:
                return value
            print(f"{Fore.RED}  This field is required.{Style.RESET_ALL}")

    def _login_flow(self) -> dict:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'─' * ui.MENU_WIDTH}")
        print("  Add Profile")
        print(f"{'─' * ui.MENU_WIDTH}{Style.RESET_ALL}")

        while True:
            domain = self._prompt_required("  Server URL (e.g. https://dm3.callengine.org): ")
            if not domain.startswith(("http://", "https://")):
                domain = "https://" + domain
            user = self._prompt_required("  Admin user: ")
            password = self._prompt_required("  Admin password: ")
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
            if client.validate_login():
                break

            print(
                f"{Fore.RED}  Login failed — invalid credentials or "
                f"insufficient API permissions.{Style.RESET_ALL}"
            )
            if input("  Try again? (Y/n): ").strip().lower() in ("n", "no"):
                sys.exit(1)

        print(f"{Fore.GREEN}  Connected successfully.{Style.RESET_ALL}")

        save = (
            input(
                f"  Save this connection as a profile? "
                f"({Fore.GREEN}Y{Style.RESET_ALL}/{Fore.RED}n{Style.RESET_ALL}): "
            )
            .strip()
            .lower()
        )
        if save in ("", "y", "yes"):
            while True:
                name = input("  Profile name: ").strip()
                if not name:
                    print(f"{Fore.RED}  A name is required.{Style.RESET_ALL}")
                    continue
                if name in self.config.profiles:
                    overwrite = (
                        input(f"  Profile '{name}' already exists. Overwrite? (y/N): ").strip().lower()
                    )
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
    def _run(self, profile, title, items, ops, worker, unit, destructive=False, ask=True):
        session = ops.client.make_session()
        admin_session = ops.client.admin_session()
        ops.set_session(session)
        ops.set_admin_session(admin_session)
        try:
            run_bulk(
                items,
                worker,
                title=title,
                profile=profile,
                unit=unit,
                destructive=destructive,
                delay_ms=self.config.defaults("request_delay_ms", 200),
                max_retries=self.config.defaults("max_retries", 2),
                dry_run=self._dry_run,
                batch_warn=self.config.defaults("max_batch_warn", 500),
                ask=ask,
            )
        finally:
            admin_session.close()
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

        session = client.admin_session()
        try:
            ip_map = client.phone_ip_map(session=session)
        except Exception as e:
            ip_map = {}
            print(f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL} Could not list phones ({e}).")
        finally:
            session.close()

        if not ip_map:
            print(f"  {Fore.YELLOW}No phones found on server to copy from.{Style.RESET_ALL}")
            return

        sample = sorted(ip_map, key=int, reverse=True)[:3]
        default_phone = sample[0]
        print(
            f"  {Fore.CYAN}Available phones (showing {len(sample)} of {len(ip_map)}):{Style.RESET_ALL}  "
            + "  ".join(sample)
        )

        records = collect_phone_items(action=ACTION_COPY_PHONE)
        if not records:
            return

        copy_phone = input(f"  Copy settings from phone [{default_phone}]: ").strip() or default_phone
        conf_secret = ui.generate_conf_secret()
        conf_secret = (
            input(f"  Conference secret (press Enter to use generated) [{conf_secret}]: ").strip()
            or conf_secret
        )

        source_ips = ip_map.get(copy_phone)
        if not source_ips:
            print(
                f"  {Fore.RED}[ERROR]{Style.RESET_ALL} Source phone {copy_phone} is not on the server. "
                f"Refusing to guess a server IP."
            )
            return
        source_ip = source_ips[0]
        if len(source_ips) > 1:
            print(
                f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL} Source phone {copy_phone} exists on "
                f"{len(source_ips)} servers; using {source_ip}."
            )

        for rec in records:
            if not rec.get("server_ip"):
                rec["server_ip"] = source_ip

        ops = Operations(client)

        def worker(rec):
            return ops.copy_phone(rec, copy_phone, source_ip, conf_secret)

        if self._dry_run:
            print(
                f"  {Fore.YELLOW}[DRY-RUN]{Style.RESET_ALL} Would copy phone {copy_phone} ({source_ip}) "
                f"into {len(records)} extension(s)."
            )

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

        client = ViciClient(profile)
        ops = Operations(client)

        if phones:
            phones = resolve_phone_server_ips(client, phones)
            if not phones:
                print(f"{Fore.YELLOW}  No target phones found on the server.{Style.RESET_ALL}")
            else:
                self._run(profile, "Delete Phones", phones, ops, ops.delete_phone, "phone", destructive=True)

        if aliases:
            self._run(
                profile, "Delete Phone Aliases", aliases, ops, ops.delete_alias, "alias", destructive=True
            )

    # ------------------------------------------------------------------
    # Option 4 — Delete all phones & aliases
    # ------------------------------------------------------------------
    def _delete_all(self, profile: dict) -> None:
        client = ViciClient(profile)
        session = client.admin_session()
        try:
            phones = client.list_phones(session=session)
            aliases = client.list_aliases(session=session)
        except Exception as e:
            print(f"{Fore.RED}  Could not list server contents: {e}{Style.RESET_ALL}")
            return
        finally:
            session.close()

        phone_items = [{"extension": e, "server_ip": ip} for e, ip in phones]
        alias_items = [{"alias_id": a} for a in aliases]

        print(f"\n  Found {len(phone_items)} phones and {len(alias_items)} aliases on the server.\n")
        if self._dry_run:
            print(
                f"  {Fore.YELLOW}{Style.BRIGHT}[DRY-RUN] Would delete {len(phone_items)} phones "
                f"and {len(alias_items)} aliases on the server.{Style.RESET_ALL}\n"
            )
            return

        print(
            f"{Fore.RED}{Style.BRIGHT}  This permanently deletes every phone "
            f"and alias on the server.{Style.RESET_ALL}"
        )
        if not ui.confirm_destructive():
            return

        ops = Operations(client)
        if phone_items:
            self._run(profile, "Delete All Phones", phone_items, ops, ops.delete_phone, "phone", ask=False)
        if alias_items:
            self._run(profile, "Delete All Aliases", alias_items, ops, ops.delete_alias, "alias", ask=False)
