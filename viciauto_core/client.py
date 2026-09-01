"""Low-level ViciDial HTTP client (API and admin.php)."""

import re

import requests
import urllib3

from .config import ADMIN_ENDPOINT, API_ENDPOINT
from .response import parse_response

ADD_ACTION_CODE = "21222222222"


class AuthError(Exception):
    pass


class ViciClient:
    def __init__(self, profile: dict):
        self.profile = profile

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    def make_session(self) -> requests.Session:
        session = requests.Session()
        if not self.profile.get("verify_ssl", True):
            session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return session

    # ------------------------------------------------------------------
    # URL builders
    # ------------------------------------------------------------------
    @property
    def base_url(self) -> str:
        return self.profile["base_url"].rstrip("/")

    @property
    def admin_url(self) -> str:
        endpoint = self.profile.get("login_endpoint", ADMIN_ENDPOINT).lstrip("/")
        return f"{self.base_url}/{endpoint}"

    @property
    def api_url(self) -> str:
        login_endpoint = self.profile.get("login_endpoint", ADMIN_ENDPOINT)
        dir_part = login_endpoint.rsplit("/", 1)[0] if "/" in login_endpoint else ""
        api_endpoint = self.profile.get("api_endpoint", API_ENDPOINT).lstrip("/")
        if dir_part:
            return f"{self.base_url}/{dir_part}/{api_endpoint}"
        return f"{self.base_url}/{api_endpoint}"

    # ------------------------------------------------------------------
    # API call
    # ------------------------------------------------------------------
    def api(self, session: requests.Session, function: str, **params) -> str:
        full = {
            "source": "ViciAuto",
            "function": function,
            "user": self.profile["admin_user"],
            "pass": self.profile["admin_pass"],
        }
        full.update(params)
        resp = session.get(self.api_url, params=full, timeout=20)
        return resp.text.strip()

    def validate_login(self) -> bool:
        session = self.make_session()
        try:
            text = self.api(session, "user_details", agent_user=self.profile["admin_user"])
        except requests.exceptions.RequestException:
            return False
        finally:
            session.close()
        resp = parse_response(text)
        return not resp.status == "error" and self.profile["admin_user"] in text

    # ------------------------------------------------------------------
    # admin.php helpers
    # ------------------------------------------------------------------
    def _admin_session(self) -> requests.Session:
        session = self.make_session()
        session.auth = (self.profile["admin_user"], self.profile["admin_pass"])
        return session

    def fetch_admin(self, params: dict) -> str:
        session = self._admin_session()
        try:
            resp = session.get(self.admin_url, params=params, timeout=20)
            return resp.text
        finally:
            session.close()

    def post_admin(self, data: dict) -> requests.Response:
        session = self._admin_session()
        resp = session.post(self.admin_url, data=data, timeout=20)
        session.close()
        return resp

    def list_phones(self) -> list:
        """Scrape the phone list page for (extension, server_ip) pairs."""
        html = self.fetch_admin({"ADD": "10000000000"})
        pairs = set(re.findall(r'extension=([0-9]+)&server_ip=([0-9.]+)', html))
        return sorted(pairs)

    def list_aliases(self) -> list:
        """Scrape the phone alias list page for alias_id values."""
        html = self.fetch_admin({"ADD": "12000000000"})
        ids = set(re.findall(r'alias_id=([^&"\']+)', html))
        return sorted(ids)

    def phone_ip_map(self) -> dict:
        """Return {extension: server_ip} for every phone on the server.

        Used to auto-resolve the server_ip of a target extension so operators
        don't have to type it. When an extension exists on multiple servers,
        the first (sorted) IP wins.
        """
        mapping = {}
        for ext, ip in self.list_phones():
            mapping.setdefault(ext, ip)
        return mapping
