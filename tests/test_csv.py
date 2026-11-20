"""Unified CSV parsing tests."""

from viciauto_core.operations import Operations


def _write(tmp_path, text):
    path = tmp_path / "input.csv"
    path.write_text(text)
    return str(path)


def test_phone_extension_wins_over_blank_extension(tmp_path):
    path = _write(
        tmp_path,
        "action,phone_extension,extension,server_ip\ndelete_phone,4100,,1.2.3.4\n",
    )
    rows = Operations.read_csv(path, action="delete_phone")
    assert len(rows) == 1
    assert rows[0]["extension"] == "4100"
    assert rows[0]["phone_login"] == "4100"


def test_action_filter(tmp_path):
    path = _write(
        tmp_path,
        "action,user_id,alias_id\nupdate_user,5001,\ndelete_alias,,TEAM_A\n",
    )
    rows = Operations.read_csv(path, action="delete_alias")
    assert [r["alias_id"] for r in rows] == ["TEAM_A"]


def test_missing_required_field_is_skipped(tmp_path, capsys):
    path = _write(
        tmp_path,
        "action,user_id,phone_extension\nupdate_user,,4100\n",
    )
    rows = Operations.read_csv(path, action="update_user")
    assert rows == []
    assert "row 2" in capsys.readouterr().out


def test_full_name_aliases(tmp_path):
    path = _write(
        tmp_path,
        "action,user_id,name,agent_name\nupdate_user,5001,Bob,\nupdate_user,5002,,Alice\n",
    )
    rows = Operations.read_csv(path, action="update_user")
    assert [r["full_name"] for r in rows] == ["Bob", "Alice"]


def test_missing_file(tmp_path, capsys):
    rows = Operations.read_csv(str(tmp_path / "nope.csv"))
    assert rows == []
    assert "CSV not found" in capsys.readouterr().out
