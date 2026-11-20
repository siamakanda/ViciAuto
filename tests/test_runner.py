"""Bulk runner tests (no network, no prompts)."""

from viciauto_core.runner import run_bulk

PROFILE = {
    "_name": "test",
    "base_url": "https://example.invalid",
    "admin_user": "6666",
    "admin_pass": "secret",
}


def _run(items, worker, **overrides):
    options = dict(
        title="Test",
        profile=PROFILE,
        unit="item",
        delay_ms=0,
        max_retries=2,
        batch_warn=0,
        ask=False,
    )
    options.update(overrides)
    return run_bulk(items, worker, **options)


def test_exception_becomes_failure_and_run_continues():
    def worker(item):
        if item == 2:
            raise RuntimeError("boom")
        return True, "ok"

    result = _run([1, 2, 3], worker)
    assert result["ok"] == 2
    assert [label for label, _ in result["failed"]] == ["2"]
    assert "boom" in result["failed"][0][1]


def test_permanent_failure_is_not_retried():
    attempts = []

    def worker(item):
        attempts.append(item)
        return False, "User does not exist", False

    result = _run([1], worker)
    assert attempts == [1]
    assert len(result["failed"]) == 1


def test_transient_failure_is_retried_until_success():
    attempts = []

    def worker(item):
        attempts.append(item)
        if len(attempts) < 3:
            return False, "Read timed out", True
        return True, "ok", False

    result = _run([1], worker)
    assert attempts == [1, 1, 1]
    assert result["ok"] == 1
    assert result["failed"] == []


def test_dry_run_never_calls_worker():
    def worker(item):
        raise AssertionError("worker must not be called in dry-run")

    result = _run([1, 2, 3], worker, dry_run=True)
    assert result["ok"] == 3
    assert result["failed"] == []


def test_large_batch_requires_extra_confirmation(monkeypatch):
    from viciauto_core import ui

    monkeypatch.setattr(ui, "confirm_large_batch", lambda count, threshold: False)

    def worker(item):
        raise AssertionError("worker must not run when batch is declined")

    result = _run([1, 2, 3], worker, batch_warn=2, ask=True)
    assert result == {"ok": 0, "failed": []}
