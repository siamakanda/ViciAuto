"""HTTP client behaviour: 5xx must surface as retryable, list scraping reuses a session."""

import pytest
import requests

from viciauto_core.client import MAX_LIST_PAGES, ViciClient

PROFILE = {
    "base_url": "https://example.invalid",
    "admin_user": "6666",
    "admin_pass": "p",
    "verify_ssl": True,
}


class FakeResponse:
    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.get_calls = 0

    def get(self, url, params=None, timeout=None):
        self.get_calls += 1
        return self.response


def test_api_raises_on_5xx_so_the_runner_can_retry():
    session = FakeSession(FakeResponse("<html>boom</html>", status_code=503))

    with pytest.raises(requests.HTTPError):
        ViciClient(PROFILE).api(session, "update_phone", extension="4001")


def test_api_returns_body_on_success():
    session = FakeSession(FakeResponse("SUCCESS: update_phone PHONE UPDATED - 6666|4001"))

    text = ViciClient(PROFILE).api(session, "update_phone", extension="4001")

    assert text.startswith("SUCCESS")


def test_scrape_reuses_the_supplied_session(monkeypatch):
    client = ViciClient(PROFILE)

    class FakeAdminSession:
        def __init__(self):
            self.pages = 0

        def get(self, url, params=None, timeout=None):
            self.pages += 1
            page = int(params["page"])
            if page == 1:
                return FakeResponse("extension=4001&server_ip=1.1.1.1")
            return FakeResponse("nothing new here")

    session = FakeAdminSession()
    phones = client.list_phones(session=session)

    assert phones == [("4001", "1.1.1.1")]
    assert session.pages == 2


def test_scrape_stops_at_the_page_cap(monkeypatch):
    client = ViciClient(PROFILE)
    pages = {"n": 0}

    def always_new(params, session=None):
        pages["n"] += 1
        return f"extension=400{pages['n']}&server_ip=1.1.1.1"

    monkeypatch.setattr(client, "fetch_admin", always_new)
    client.list_phones()

    assert pages["n"] == MAX_LIST_PAGES
