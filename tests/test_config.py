"""Config persistence and recovery tests."""

import json

import pytest

from viciauto_core.config import Config, ConfigError


def _config(tmp_path):
    return Config(str(tmp_path / "servers.json"))


def test_missing_config_is_created(tmp_path):
    cfg = _config(tmp_path)
    assert cfg.profiles == {}
    assert (tmp_path / "servers.json").exists()


def test_corrupt_config_is_backed_up_and_replaced(tmp_path, capsys):
    path = tmp_path / "servers.json"
    path.write_text("{ this is not json")

    cfg = Config(str(path))

    assert cfg.profiles == {}
    assert json.loads(path.read_text())["profiles"] == {}
    assert list(tmp_path.glob("servers.json.corrupt-*"))
    assert "unreadable" in capsys.readouterr().out


def test_save_is_atomic_and_roundtrips(tmp_path):
    cfg = _config(tmp_path)
    cfg.add_profile("dm3", {"base_url": "https://dm3.example", "admin_user": "6666", "admin_pass": "p"})

    stored = json.loads((tmp_path / "servers.json").read_text())
    assert stored["profiles"]["dm3"]["base_url"] == "https://dm3.example"
    assert not (tmp_path / "servers.json.tmp").exists()


def test_get_profile_applies_defaults_and_env(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    cfg.add_profile("dm3", {"base_url": "https://dm3.example", "admin_user": "6666", "admin_pass": "p"})

    monkeypatch.setenv("VICIAUTO_ADMIN_PASS", "from-env")
    profile = cfg.get_profile("dm3")

    assert profile["_name"] == "dm3"
    assert profile["verify_ssl"] is True
    assert profile["api_endpoint"] == "non_agent_api.php"
    assert profile["admin_pass"] == "from-env"


def test_get_profile_missing_name(tmp_path):
    cfg = _config(tmp_path)
    with pytest.raises(ConfigError):
        cfg.get_profile("nope")


def test_env_only_password_satisfies_required_fields(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    cfg.add_profile("dm3", {"base_url": "https://dm3.example", "admin_user": "6666"})
    monkeypatch.setenv("VICIAUTO_ADMIN_PASS", "from-env")

    profile = cfg.get_profile("dm3")
    assert profile["admin_pass"] == "from-env"


def test_get_profile_rejects_incomplete_profile(tmp_path):
    cfg = _config(tmp_path)
    cfg.data["profiles"]["broken"] = {"base_url": "https://broken.example"}
    with pytest.raises(ConfigError):
        cfg.get_profile("broken")
