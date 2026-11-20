"""Response parsing tests."""

from viciauto_core.response import ResponseStatus, parse_copy_result, parse_response


def test_success_body():
    resp = parse_response("SUCCESS: update_user USER HAS BEEN UPDATED - 6666|4001|")
    assert resp.status == ResponseStatus.SUCCESS
    assert resp.ok
    assert resp.data.startswith("6666|4001|")


def test_error_body():
    resp = parse_response(
        "ERROR: update_user YOU MUST USE A VALID PHONE LOGIN, THIS IS AN OPTIONAL FIELD: |6666|4001|0|0"
    )
    assert resp.status == ResponseStatus.ERROR
    assert not resp.ok


def test_notice_body():
    resp = parse_response("NOTICE: update_phone USER DOES NOT HAVE PERMISSION TO DELETE PHONES - 6666|0")
    assert resp.status == ResponseStatus.NOTICE
    assert not resp.ok


def test_unknown_body():
    resp = parse_response("PHONE ADDED")
    assert resp.status == ResponseStatus.UNKNOWN
    assert not resp.ok


def test_empty_body():
    resp = parse_response("   ")
    assert resp.status == ResponseStatus.UNKNOWN
    assert not resp.ok


def test_copy_result_success():
    resp = parse_copy_result("<html>Phone copied</html>")
    assert resp.ok
    assert resp.reason == "Created"


def test_copy_result_login_page_is_not_success():
    resp = parse_copy_result("<html>Please Login</html>")
    assert not resp.ok
    assert resp.reason == "ADMIN LOGIN REJECTED"
    assert not resp.retryable


def test_copy_result_explicit_failure_reason():
    resp = parse_copy_result("PHONE NOT COPIED - SOURCE PHONE DOES NOT EXIST")
    assert not resp.ok
    assert resp.reason == "SOURCE PHONE DOES NOT EXIST"


def test_copy_result_empty_body_is_retryable():
    resp = parse_copy_result("   ")
    assert not resp.ok
    assert resp.reason == "Empty response"
    assert resp.retryable
