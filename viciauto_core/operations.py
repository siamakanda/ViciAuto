"""Bulk operation workers and CSV parsing."""

import csv
import os
import re

from colorama import Fore, Style

from .client import ADD_ACTION_CODE
from .config import DEFAULT_SERVER_IP
from .response import parse_response

ACTION_COPY_PHONE = "copy_phone"
ACTION_UPDATE_USER = "update_user"
ACTION_DELETE_PHONE = "delete_phone"
ACTION_DELETE_ALIAS = "delete_alias"


class Operations:
    def __init__(self, client):
        self.client = client
        self.profile = client.profile
        self.session = None

    def set_session(self, session) -> None:
        self.session = session

    @staticmethod
    def _friendly_error(reason: str, mapping: dict) -> str:
        """Map a ViciDial reason to a friendly message, falling back to the raw reason."""
        upper = reason.upper()
        for needle, friendly in mapping.items():
            if needle in upper:
                return friendly
        return reason[:60] if reason else "Unknown error"

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

        text = self.client.api(self.session, "update_user", **params)
        resp = parse_response(text)
        if resp.ok:
            return True, "Updated"
        return False, self._friendly_error(resp.reason, {
            "USER DOES NOT EXIST": "User does not exist",
            "VALID PHONE LOGIN": "Phone login must be an existing phone or alias",
        })

    # ------------------------------------------------------------------
    # Phone operations
    # ------------------------------------------------------------------
    def copy_phone(self, record: dict, copy_phone: str, conf_secret: str) -> tuple:
        ext = record["extension"]
        server_ip = record.get("server_ip") or self.profile.get("server_ip", DEFAULT_SERVER_IP)

        payload = {
            "ADD": ADD_ACTION_CODE,
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
            "source_phone": f"{copy_phone}|{server_ip}",
            "SUBMIT": "SUBMIT",
        }

        try:
            http_resp = self.client.post_admin(payload)
        except Exception as e:
            return False, str(e)[:60]

        if not http_resp.ok:
            return False, f"HTTP {http_resp.status_code}"

        # admin.php reports the copy outcome in the page body, not via a
        # STATUS: line. Success leaves "PHONE NOT COPIED" absent; failure
        # includes "PHONE NOT COPIED - <reason>".
        text = http_resp.text.upper()
        if "PHONE NOT COPIED" in text:
            match = re.search(r"PHONE NOT COPIED\s*[-:]\s*([^<\n]+)", text)
            reason = match.group(1).strip() if match else "Copy failed"
            return False, self._friendly_error(reason, {
                "SOURCE PHONE DOES NOT EXIST": "Source phone not found",
                "ALREADY EXISTS": "Already exists",
                "DUPLICATE": "Already exists",
            })
        return True, "Created"

    def delete_phone(self, record: dict) -> tuple:
        extension = record["extension"]
        server_ip = record.get("server_ip") or self.profile.get("server_ip", DEFAULT_SERVER_IP)
        text = self.client.api(
            self.session, "update_phone",
            extension=extension,
            server_ip=server_ip,
            delete_phone="Y",
        )
        resp = parse_response(text)
        if resp.ok:
            return True, "Deleted"
        return False, self._friendly_error(resp.reason, {
            "PHONE DOES NOT EXIST": "Phone not found",
            "PERMISSION TO DELETE PHONES": "No permission to delete phones",
        })

    def delete_alias(self, record: dict) -> tuple:
        text = self.client.api(
            self.session, "update_phone_alias",
            alias_id=record["alias_id"],
            delete_alias="Y",
        )
        resp = parse_response(text)
        if resp.ok:
            return True, "Deleted"
        return False, self._friendly_error(resp.reason, {
            "PHONE ALIAS DOES NOT EXIST": "Alias not found",
        })

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
        aliases for `full_name`.
        """
        if not os.path.exists(path):
            print(f"{Fore.RED}Error: CSV not found: {path}{Style.RESET_ALL}")
            return []

        records = []
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                print(f"{Fore.RED}Error: CSV has no header.{Style.RESET_ALL}")
                return []

            for row in reader:
                rec = {k.strip(): (v or "").strip() for k, v in row.items() if k}
                if action and rec.get("action", "").lower() != action:
                    continue
                if rec.get("phone_extension"):
                    rec.setdefault("extension", rec["phone_extension"])
                    rec.setdefault("phone_login", rec["phone_extension"])
                if not rec.get("full_name"):
                    for alias in ("name", "agent_name"):
                        if rec.get(alias):
                            rec["full_name"] = rec[alias]
                            break
                records.append(rec)

        if not records:
            print(f"{Fore.RED}Error: no rows found.{Style.RESET_ALL}")
            return []
        return records
