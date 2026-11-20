"""Worker tests against a fake ViciDial client (no network)."""

from viciauto_core.operations import Operations


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    @property
    def ok(self):
        return 200 <= self.status_code < 400


class FakeClient:
    def __init__(self, response=None, api_text=""):
        self.profile = {"server_ip": "1.2.3.4"}
        self.response = response
        self.api_text = api_text
        self.payloads = []
        self.api_calls = []

    def post_admin(self, payload, session=None):
        self.payloads.append(payload)
        return self.response

    def api(self, session, function, **params):
        self.api_calls.append((function, params))
        return self.api_text


def _copy(client, source_ip="9.9.9.9"):
    ops = Operations(client)
    return ops.copy_phone(
        {"extension": "4100", "server_ip": "1.2.3.4"},
        "7001",
        source_ip,
        "confsecret",
    )


def test_copy_phone_success_and_source_ip_is_independent():
    client = FakeClient(FakeResponse("<html>phone copied</html>"))
    ok, msg, retryable = _copy(client, source_ip="9.9.9.9")

    assert (ok, msg, retryable) == (True, "Created", False)
    payload = client.payloads[0]
    assert payload["source_phone"] == "7001|9.9.9.9"
    assert payload["new_server_ip"] == "1.2.3.4"


def test_copy_phone_login_page_is_not_success():
    client = FakeClient(FakeResponse("<html>Please Login</html>"))
    ok, msg, retryable = _copy(client)
    assert ok is False
    assert msg == "Admin login rejected"
    assert retryable is False


def test_copy_phone_explicit_failure_body():
    client = FakeClient(FakeResponse("PHONE NOT COPIED - SOURCE PHONE DOES NOT EXIST"))
    ok, msg, retryable = _copy(client)
    assert ok is False
    assert msg == "Source phone not found"
    assert retryable is False


def test_copy_phone_server_error_is_retryable():
    client = FakeClient(FakeResponse("", status_code=503))
    ok, msg, retryable = _copy(client)
    assert ok is False
    assert msg == "HTTP 503"
    assert retryable is True


def test_delete_phone_friendly_error():
    client = FakeClient(api_text="ERROR: update_phone PHONE DOES NOT EXIST - 6666|4100")
    ok, msg, retryable = Operations(client).delete_phone({"extension": "4100", "server_ip": "1.2.3.4"})
    assert (ok, msg, retryable) == (False, "Phone not found", False)


def test_delete_alias_success():
    client = FakeClient(api_text="SUCCESS: update_phone_alias PHONE ALIAS DELETED - 6666|TEAM_A")
    ok, msg, retryable = Operations(client).delete_alias({"alias_id": "TEAM_A"})
    assert (ok, msg, retryable) == (True, "Deleted", False)


def test_delete_phone_without_server_ip_never_calls_the_client():
    """A missing server_ip must refuse rather than fall back to a hardcoded IP."""
    client = FakeClient()
    client.profile = {}
    result = Operations(client).delete_phone({"extension": "4100"})

    assert result == (False, "No server_ip for 4100", False)
    assert client.api_calls == []


def test_copy_phone_without_server_ip_never_posts():
    client = FakeClient(FakeResponse("<html>ok</html>"))
    client.profile = {}
    result = Operations(client).copy_phone({"extension": "4100"}, "7001", "9.9.9.9", "secret")

    assert result == (False, "No server_ip for 4100", False)
    assert client.payloads == []
