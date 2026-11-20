"""Login validation and UI prompt tests."""

from viciauto_core.client import ViciClient, _mentions_user


class FakeSession:
    def close(self):
        pass


def _client(monkeypatch, body):
    client = ViciClient(
        {
            "base_url": "https://example.invalid",
            "admin_user": "6666",
            "admin_pass": "p",
        }
    )
    monkeypatch.setattr(client, "make_session", lambda: FakeSession())
    monkeypatch.setattr(client, "api", lambda session, function, **params: body)
    return client


def test_validate_login_accepts_exact_user_token(monkeypatch):
    body = "SUCCESS: user_details USER FOUND - 6666|6666|ACTIVE"
    assert _client(monkeypatch, body).validate_login() is True


def test_validate_login_rejects_substring_match(monkeypatch):
    body = "SUCCESS: user_details USER FOUND - 66660|66660|ACTIVE"
    assert _client(monkeypatch, body).validate_login() is False


def test_validate_login_rejects_error_body(monkeypatch):
    body = "ERROR: user_details USER DOES NOT EXIST - 6666"
    assert _client(monkeypatch, body).validate_login() is False


def test_mentions_user_respects_token_boundaries():
    assert _mentions_user("SUCCESS: x - 6666|6666|", "6666")
    assert not _mentions_user("SUCCESS: x - 66660|66660|", "6666")
    assert _mentions_user("SUCCESS: x - |QA1-METRO|", "QA1-METRO")


def test_choose_line_retries_invalid_input(monkeypatch, capsys):
    from viciauto_core.ui import choose_line

    answers = iter(["99", "10"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert choose_line(["1", "2", "10"], "Pick: ") == "10"
    assert "Invalid selection" in capsys.readouterr().out


def test_menu_uses_line_input_when_an_option_needs_two_digits(monkeypatch):
    from viciauto_core.ui import menu

    monkeypatch.setattr("builtins.input", lambda _: "10")
    options = [(str(i), f"profile {i}") for i in range(1, 11)]

    assert menu("Profiles", options, prompt="Profile") == "10"
