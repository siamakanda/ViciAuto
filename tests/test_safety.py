"""Safety behaviour: duplicate extensions, encoding, and the audit trail."""

import json

from viciauto_core import audit
from viciauto_core.collection import resolve_phone_server_ips
from viciauto_core.operations import Operations


class FakeClient:
    def __init__(self, ip_map):
        self.ip_map = ip_map

    def phone_ip_map(self, session=None):
        return self.ip_map


def test_duplicate_extension_is_expanded_per_server():
    """An extension on two Asterisk servers must yield two delete targets."""
    client = FakeClient({"4001": ["1.1.1.1", "2.2.2.2"]})

    resolved = resolve_phone_server_ips(client, [{"extension": "4001", "server_ip": ""}])

    assert resolved == [
        {"extension": "4001", "server_ip": "1.1.1.1"},
        {"extension": "4001", "server_ip": "2.2.2.2"},
    ]


def test_missing_extension_without_supplied_ip_is_skipped():
    client = FakeClient({})

    resolved = resolve_phone_server_ips(client, [{"extension": "9999", "server_ip": ""}])

    assert resolved == []


def test_supplied_ip_is_kept_when_extension_is_unknown():
    client = FakeClient({})

    resolved = resolve_phone_server_ips(client, [{"extension": "9999", "server_ip": "3.3.3.3"}])

    assert resolved == [{"extension": "9999", "server_ip": "3.3.3.3"}]


def test_read_csv_handles_non_ascii_names_and_a_bom(tmp_path):
    path = tmp_path / "input.csv"
    path.write_bytes("\ufeffaction,user_id,full_name\nupdate_user,5001,Müller\n".encode("utf-8"))

    rows = Operations.read_csv(str(path), action="update_user")

    assert rows[0]["full_name"] == "Müller"
    assert rows[0]["user_id"] == "5001"


def test_audit_records_are_appended_as_json_lines(tmp_path):
    log = tmp_path / "audit.log"

    audit.record({"event": "start", "operation": "Delete All"}, str(log))
    audit.record({"event": "summary", "ok": 3, "failed": 1}, str(log))

    lines = log.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines]

    assert [e["event"] for e in entries] == ["start", "summary"]
    assert entries[1]["ok"] == 3
    assert all("ts" in e for e in entries)


def test_audit_failure_does_not_raise(tmp_path):
    audit.record({"event": "start"}, str(tmp_path / "no" / "such" / "dir" / "audit.log"))
