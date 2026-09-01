"""Configuration and profile management."""

import json
import os
import sys

from colorama import Fore, Style

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "servers.json")
SAMPLE_CSV_PATH = os.path.join(SCRIPT_DIR, "sample.csv")

DEFAULT_SERVER_IP = "***REMOVED***"
API_ENDPOINT = "non_agent_api.php"
ADMIN_ENDPOINT = "vicidial/admin.php"

DEFAULTS = {
    "request_delay_ms": 200,
    "max_retries": 2,
    "dry_run": False,
    "server_ip": DEFAULT_SERVER_IP,
}


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
            with open(self.path, "w") as f:
                json.dump(_default_config(), f, indent=2)
            return _default_config()
        with open(self.path, "r") as f:
            return json.load(f)

    def save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    @property
    def profiles(self) -> dict:
        return self.data.get("profiles", {})

    def defaults(self, key: str, fallback=None):
        return self.data.get("defaults", {}).get(key, fallback)

    def get_profile(self, name: str) -> dict:
        if name not in self.profiles:
            print(f"{Fore.RED}Error: Profile '{name}' not found.")
            print(f"{Fore.YELLOW}Available: {', '.join(self.profiles) or '(none)'}")
            sys.exit(1)

        profile = dict(self.profiles[name])
        profile["_name"] = name
        profile.setdefault("login_endpoint", ADMIN_ENDPOINT)
        profile.setdefault("api_endpoint", API_ENDPOINT)
        profile.setdefault("verify_ssl", False)
        profile.setdefault("server_ip", self.defaults("server_ip", DEFAULT_SERVER_IP))

        # Env-var overrides take precedence over stored values, so secrets can
        # live outside the repo. Never write these back to servers.json.
        profile["base_url"] = os.environ.get("VICIAUTO_BASE_URL", profile["base_url"])
        profile["admin_user"] = os.environ.get("VICIAUTO_ADMIN_USER", profile["admin_user"])
        profile["admin_pass"] = os.environ.get("VICIAUTO_ADMIN_PASS", profile["admin_pass"])
        return profile

    def add_profile(self, name: str, profile: dict) -> None:
        self.data.setdefault("profiles", {})[name] = {
            k: v for k, v in profile.items() if not k.startswith("_")
        }
        self.save()

    def list_profiles(self) -> None:
        if not self.profiles:
            print(f"{Fore.YELLOW}No saved profiles.")
            return
        print(f"\n{Fore.CYAN}{Style.BRIGHT}Saved profiles:{Style.RESET_ALL}")
        print("-" * 65)
        for i, (name, p) in enumerate(self.profiles.items(), 1):
            verify = "SSL-verify" if p.get("verify_ssl", True) else "no-verify"
            print(f"  [{Fore.GREEN}{i}{Style.RESET_ALL}] {Fore.WHITE}{name:<15}{Style.RESET_ALL} "
                  f"-> {p.get('base_url', '?')}  (user: {p.get('admin_user', '?')})  [{verify}]")
        print("-" * 65)
