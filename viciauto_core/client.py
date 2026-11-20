"""Low-level ViciDial HTTP client (API and admin.php)."""

import re

import requests
import urllib3
from colorama import Fore, Style

from .config import ADMIN_ENDPOINT, API_ENDPOINT
from .response import ResponseStatus, parse_response

TIMEOUT = (10, 30)

# admin.php action codes.
ADMIN_COPY_PHONE = "21222222222"
ADMIN_LIST_PHONES = "10000000000"
ADMIN_LIST_ALIASES = "12000000000"

# Upper bound on paginated list scraping, so a server that echoes page 1
# forever cannot spin us in a loop.
MAX_LIST_PAGES = 50


def _mentions_user(text: str, user: str) -> bool:
    """True when `text` names `user` as a whole token and is not an error body."""
    if parse_response(text).status == ResponseStatus.ERROR:
        return False
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(user)}(?![A-Za-z0-9_-])"
    return re.search(pattern, text) is not None


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
            print(
                f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL} TLS verification disabled for "
                f"{self.base_url} (verify_ssl is off)."
            )
        return session

    def admin_session(self) -> requests.Session:
        """An admin.php session with basic auth; reuse it across a bulk run."""
        session = self.make_session()
        session.auth = (self.profile["admin_user"], self.profile["admin_pass"])
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
        resp = session.get(self.api_url, params=full, timeout=TIMEOUT)
        if resp.status_code >= 500:
            raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
        return resp.text.strip()

    def validate_login(self) -> bool:
        session = self.make_session()
        try:
            text = self.api(session, "user_details", agent_user=self.profile["admin_user"])
        except requests.exceptions.RequestException:
            return False
        finally:
            session.close()
        return _mentions_user(text, self.profile["admin_user"])

    # ------------------------------------------------------------------
    # admin.php helpers
    # ------------------------------------------------------------------
    def fetch_admin(self, params: dict, session: requests.Session = None) -> str:
        if session is not None:
            resp = session.get(self.admin_url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.text

        session = self.admin_session()
        try:
            resp = session.get(self.admin_url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.text
        finally:
            session.close()

    def post_admin(self, data: dict, session: requests.Session = None) -> requests.Response:
        if session is not None:
            return session.post(self.admin_url, data=data, timeout=TIMEOUT)

        session = self.admin_session()
        try:
            return session.post(self.admin_url, data=data, timeout=TIMEOUT)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # List scraping
    # ------------------------------------------------------------------
    def _scrape(self, params: dict, pattern: str, session: requests.Session = None) -> set:
        """Walk admin.php list pages until a page adds nothing new."""
        found = set()
        for page in range(1, MAX_LIST_PAGES + 1):
            html = self.fetch_admin({**params, "page": str(page)}, session=session)
            page_items = set(re.findall(pattern, html))
            if not page_items - found:
                break
            found |= page_items
        return found

    def list_phones(self, session: requests.Session = None) -> list:
        """Scrape the phone list pages for (extension, server_ip) pairs."""
        pairs = self._scrape(
            {"ADD": ADMIN_LIST_PHONES},
            r"extension=([0-9]+)&server_ip=([0-9.]+)",
            session=session,
        )
        return sorted(pairs)

    def list_aliases(self, session: requests.Session = None) -> list:
        """Scrape the phone alias list pages for alias_id values."""
        ids = self._scrape({"ADD": ADMIN_LIST_ALIASES}, r"alias_id=([^&\"']+)", session=session)
        return sorted(ids)

    def phone_ip_map(self, session: requests.Session = None) -> dict:
        """Return {extension: [server_ip, ...]} for every phone on the server.

        A single extension may be registered on more than one Asterisk server;
        every IP is kept so a destructive operation can target all of them
        instead of silently deleting just the first.
        """
        mapping = {}
        for ext, ip in self.list_phones(session=session):
            mapping.setdefault(ext, []).append(ip)
        return {ext: sorted(ips) for ext, ips in mapping.items()}
