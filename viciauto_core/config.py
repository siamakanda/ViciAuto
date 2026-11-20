"""Configuration and profile management."""

import json
import os
import time

from colorama import Fore, Style

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "servers.json")
SAMPLE_CSV_PATH = os.path.join(SCRIPT_DIR, "templates", "bulk_actions.csv")
AUDIT_PATH = os.path.join(SCRIPT_DIR, "audit.log")

API_ENDPOINT = "non_agent_api.php"
ADMIN_ENDPOINT = "vicidial/admin.php"

DEFAULTS = {
    "request_delay_ms": 200,
    "max_retries": 2,
    "dry_run": False,
    "max_batch_warn": 500,
    "server_ip": "",
    "range_start_phone": 4001,
    "range_end_phone": 4050,
    "range_start_user": 5001,
    "range_end_user": 5015,
}

PROFILE_REQUIRED = ("base_url", "admin_user", "admin_pass")


class ConfigError(Exception):
    """Raised when a profile is missing or malformed."""


def _default_config() -> dict:
    return {
        "profiles": {},
        "defaults": dict(DEFAULTS),
    }


class Config:
    def __init__(self, path: str = CONFIG_PATH):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            data = _default_config()
            self._write(data)
            return data

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("top-level value is not an object")
        except (json.JSONDecodeError, OSError, ValueError) as e:
            return self._recover(e)

        data.setdefault("profiles", {})
        data.setdefault("defaults", dict(DEFAULTS))
        return data

    def _recover(self, error: Exception) -> dict:
        backup = f"{self.path}.corrupt-{int(time.time())}"
        try:
            os.replace(self.path, backup)
        except OSError:
            backup = "(could not be backed up)"
        print(f"{Fore.YELLOW}Warning: config unreadable ({error}).{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Previous file: {backup}. Starting with defaults.{Style.RESET_ALL}")
        data = _default_config()
        self._write(data)
        return data

    def _write(self, data: dict) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)

    def save(self) -> None:
        self._write(self.data)

    @property
    def profiles(self) -> dict:
        return self.data.get("profiles", {})

    def defaults(self, key: str, fallback=None):
        return self.data.get("defaults", {}).get(key, fallback)

    def get_profile(self, name: str) -> dict:
        if name not in self.profiles:
            available = ", ".join(self.profiles) or "(none)"
            raise ConfigError(f"Profile '{name}' not found. Available: {available}")

        stored = self.profiles[name]

        profile = dict(stored)
        profile["_name"] = name
        profile.setdefault("login_endpoint", ADMIN_ENDPOINT)
        profile.setdefault("api_endpoint", API_ENDPOINT)
        profile.setdefault("verify_ssl", True)
        profile.setdefault("server_ip", self.defaults("server_ip", ""))

        # Env-var overrides take precedence over stored values, so secrets can
        # live outside the repo. Never write these back to servers.json.
        profile["base_url"] = os.environ.get("VICIAUTO_BASE_URL") or stored.get("base_url", "")
        profile["admin_user"] = os.environ.get("VICIAUTO_ADMIN_USER") or stored.get("admin_user", "")
        profile["admin_pass"] = os.environ.get("VICIAUTO_ADMIN_PASS") or stored.get("admin_pass", "")

        missing = [key for key in PROFILE_REQUIRED if not profile.get(key)]
        if missing:
            raise ConfigError(f"Profile '{name}' is missing: {', '.join(missing)}")
        return profile

    def add_profile(self, name: str, profile: dict) -> None:
        self.data.setdefault("profiles", {})[name] = {
            k: v for k, v in profile.items() if not k.startswith("_")
        }
        self.save()

    def remove_profile(self, name: str) -> None:
        self.data.setdefault("profiles", {}).pop(name, None)
        self.save()

    def update_profile(self, name: str, **fields) -> None:
        profiles = self.data.setdefault("profiles", {})
        if name not in profiles:
            return
        profiles[name].update({k: v for k, v in fields.items() if v is not None})
        self.save()

    def list_profiles(self) -> None:
        if not self.profiles:
            print(f"{Fore.YELLOW}No saved profiles.")
            return
        print(f"\n{Fore.CYAN}{Style.BRIGHT}Saved profiles:{Style.RESET_ALL}")
        print("-" * 65)
        for i, (name, p) in enumerate(self.profiles.items(), 1):
            verify = "SSL-verify" if p.get("verify_ssl", True) else "no-verify"
            print(
                f"  {Fore.GREEN}{i}.{Style.RESET_ALL} {Fore.WHITE}{name:<15}{Style.RESET_ALL} "
                f"-> {p.get('base_url', '?')}  (admin: {p.get('admin_user', '?')})  [{verify}]"
            )
        print("-" * 65)
