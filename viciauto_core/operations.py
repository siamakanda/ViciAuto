"""Bulk operation workers and CSV parsing."""

import csv
import os

import requests
from colorama import Fore, Style

from .client import ADMIN_COPY_PHONE
from .response import parse_copy_result, parse_response

ACTION_COPY_PHONE = "copy_phone"
ACTION_UPDATE_USER = "update_user"
ACTION_DELETE_PHONE = "delete_phone"
ACTION_DELETE_ALIAS = "delete_alias"

ACTION_FIELDS = {
    ACTION_COPY_PHONE: ("extension",),
    ACTION_UPDATE_USER: ("user_id",),
    ACTION_DELETE_PHONE: ("extension",),
    ACTION_DELETE_ALIAS: ("alias_id",),
}


def _failure(exc: Exception) -> tuple:
    return False, f"{type(exc).__name__}: {exc}".replace("\n", " ")[:60], True


class Operations:
    def __init__(self, client):
        self.client = client
        self.profile = client.profile
        self.session = None
        self.admin_session = None

    def set_session(self, session) -> None:
        self.session = session

    def set_admin_session(self, session) -> None:
        self.admin_session = session

    @staticmethod
    def _friendly_error(reason: str, mapping: dict) -> str:
        """Map a ViciDial reason to a friendly message, falling back to the raw reason."""
        upper = reason.upper()
        for needle, friendly in mapping.items():
            if needle in upper:
                return friendly
        return reason[:60] if reason else "Unknown error"

    def _admin_post(self, payload: dict) -> requests.Response:
        if self.admin_session is None:
            return self.client.post_admin(payload)
        return self.client.post_admin(payload, self.admin_session)

    # ------------------------------------------------------------------
    # User operations
    # ------------------------------------------------------------------
    def update_user_phone(self, record: dict) -> tuple:
        params = {"agent_user": record["user_id"]}
        if record.get("phone_login"):
            params["phone_login"] = record["phone_login"]
        if record.get("phone_pass"):
            params["phone_pass"] = record["phone_pass"]
        if record.get("user_password"):
            params["user_password"] = record["user_password"]
        if record.get("full_name"):
            params["full_name"] = record["full_name"]

        try:
            text = self.client.api(self.session, "update_user", **params)
        except requests.RequestException as exc:
            return _failure(exc)

        resp = parse_response(text)
        if resp.ok:
            return True, "Updated", False
        return (
            False,
            self._friendly_error(
                resp.reason,
                {
                    "USER DOES NOT EXIST": "User does not exist",
                    "VALID PHONE LOGIN": "Phone login must be an existing phone or alias",
                },
            ),
            False,
        )

    # ------------------------------------------------------------------
    # Phone operations
    # ------------------------------------------------------------------
    def copy_phone(self, record: dict, copy_phone: str, source_ip: str, conf_secret: str) -> tuple:
        ext = record["extension"]
        server_ip = record.get("server_ip") or self.profile.get("server_ip")
        if not server_ip:
            return False, f"No server_ip for {ext}", False

        payload = {
            "ADD": ADMIN_COPY_PHONE,
            "DB": "0",
            "new_extension": ext,
            "new_dialplan_number": ext,
            "new_voicemail_id": ext,
            "new_outbound_cid": ext,
            "new_server_ip": server_ip,
            "new_login": ext,
            "new_pass": ext,
            "new_conf_secret": conf_secret,
            "new_fullname": f"Extension {ext}",
            "source_phone": f"{copy_phone}|{source_ip}",
            "SUBMIT": "SUBMIT",
        }

        try:
            http_resp = self._admin_post(payload)
        except requests.RequestException as exc:
            return _failure(exc)

        if not http_resp.ok:
            return False, f"HTTP {http_resp.status_code}", http_resp.status_code >= 500

        result = parse_copy_result(http_resp.text or "")
        if result.ok:
            return True, "Created", False
        return (
            False,
            self._friendly_error(
                result.reason,
                {
                    "SOURCE PHONE DOES NOT EXIST": "Source phone not found",
                    "ALREADY EXISTS": "Already exists",
                    "DUPLICATE": "Already exists",
                    "ADMIN LOGIN REJECTED": "Admin login rejected",
                    "EMPTY RESPONSE": "Empty response",
                },
            ),
            result.retryable,
        )

    def delete_phone(self, record: dict) -> tuple:
        extension = record["extension"]
        server_ip = record.get("server_ip") or self.profile.get("server_ip")
        if not server_ip:
            return False, f"No server_ip for {extension}", False
        try:
            text = self.client.api(
                self.session,
                "update_phone",
                extension=extension,
                server_ip=server_ip,
                delete_phone="Y",
            )
        except requests.RequestException as exc:
            return _failure(exc)

        resp = parse_response(text)
        if resp.ok:
            return True, "Deleted", False
        return (
            False,
            self._friendly_error(
                resp.reason,
                {
                    "PHONE DOES NOT EXIST": "Phone not found",
                    "PERMISSION TO DELETE PHONES": "No permission to delete phones",
                },
            ),
            False,
        )

    def delete_alias(self, record: dict) -> tuple:
        try:
            text = self.client.api(
                self.session,
                "update_phone_alias",
                alias_id=record["alias_id"],
                delete_alias="Y",
            )
        except requests.RequestException as exc:
            return _failure(exc)

        resp = parse_response(text)
        if resp.ok:
            return True, "Deleted", False
        return (
            False,
            self._friendly_error(
                resp.reason,
                {
                    "PHONE ALIAS DOES NOT EXIST": "Alias not found",
                },
            ),
            False,
        )

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------
    @staticmethod
    def read_csv(path: str, action: str = None) -> list:
        """Read the unified CSV and return rows, optionally filtered by `action`.

        The unified CSV has an `action` column plus the union of all per-task
        columns (user_id, user_password, phone_extension, server_ip, phone_pass,
        full_name, alias_id). `phone_extension` doubles as both `extension`
        (copy/delete phone) and `phone_login` (update_user); `extension` and
        `phone_login` are also accepted directly. `name`/`agent_name` are
        aliases for `full_name`. Rows missing a field required by their action
        are reported and skipped instead of crashing the run.
        """
        if not os.path.exists(path):
            print(f"{Fore.RED}Error: CSV not found: {path}{Style.RESET_ALL}")
            return []

        records = []
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                print(f"{Fore.RED}Error: CSV has no header.{Style.RESET_ALL}")
                return []

            for row in reader:
                rec = {k.strip(): (v or "").strip() for k, v in row.items() if k}
                row_action = rec.get("action", "").lower()
                if action and row_action != action:
                    continue

                ext = rec.get("phone_extension") or rec.get("extension")
                if ext:
                    rec["extension"] = ext
                    rec["phone_login"] = rec.get("phone_login") or ext
                if not rec.get("full_name"):
                    rec["full_name"] = rec.get("name") or rec.get("agent_name") or ""

                required = ACTION_FIELDS.get(action or row_action, ())
                missing = [field for field in required if not rec.get(field)]
                if missing:
                    print(
                        f"{Fore.YELLOW}  row {reader.line_num}: missing "
                        f"{', '.join(missing)} - skipped{Style.RESET_ALL}"
                    )
                    continue

                records.append(rec)

        if not records:
            print(f"{Fore.RED}Error: no rows found.{Style.RESET_ALL}")
            return []
        return records
