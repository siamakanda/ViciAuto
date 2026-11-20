"""Centralized ViciDial response parsing.

ViciDial returns HTTP 200 for both success and error responses, so the HTTP
status cannot be trusted — the body text must be inspected. Every worker should
route its response text through one of these parsers instead of doing its own
substring matching.
"""

import re

# An HTML login/permission page carries no failure marker, so it must never be
# mistaken for success.
LOGIN_MARKERS = (
    "PLEASE LOGIN",
    "INVALID USERNAME",
    "INVALID PASSWORD",
    "PERMISSION DENIED",
    "NO PERMISSION",
)


class ResponseStatus:
    SUCCESS = "success"
    ERROR = "error"
    NOTICE = "notice"
    UNKNOWN = "unknown"


class ParsedResponse:
    def __init__(self, status: str, reason: str = "", data: str = "", retryable: bool = False):
        self.status = status
        self.reason = reason
        self.data = data
        self.retryable = retryable

    @property
    def ok(self) -> bool:
        return self.status == ResponseStatus.SUCCESS


def parse_response(text: str) -> ParsedResponse:
    """Parse a ViciDial API/admin response body into status + reason + data.

    ViciDial bodies are typically a single line shaped like:

        STATUS: <reason> - <user>|<data>
        SUCCESS: update_user USER HAS BEEN UPDATED - 6666|4001|
        ERROR:   update_user YOU MUST USE A VALID PHONE LOGIN ...

    The leading token (before the first colon) is the status, and the text after
    it up to an optional " - " is the human-readable reason.
    """
    if text is None:
        return ParsedResponse(ResponseStatus.UNKNOWN)

    line = text.strip()
    if not line:
        return ParsedResponse(ResponseStatus.UNKNOWN)

    if ":" not in line:
        return ParsedResponse(ResponseStatus.UNKNOWN, reason=line[:200])

    status_token, _, rest = line.partition(":")
    status = status_token.strip().upper()

    reason = rest.strip()
    data = ""
    if " - " in reason:
        reason, _, data = reason.partition(" - ")
    elif " -" in reason:
        reason, _, data = reason.partition(" -")
    elif "- " in reason:
        reason, _, data = reason.partition("- ")

    reason = reason.strip()
    data = data.strip()

    if status in ("SUCCESS", "OK"):
        return ParsedResponse(ResponseStatus.SUCCESS, reason, data)
    if status == "ERROR":
        return ParsedResponse(ResponseStatus.ERROR, reason, data)
    if status == "NOTICE":
        return ParsedResponse(ResponseStatus.NOTICE, reason, data)

    return ParsedResponse(ResponseStatus.UNKNOWN, reason=line[:200])


def parse_copy_result(text: str) -> ParsedResponse:
    """Parse an `admin.php` copy-phone page.

    The copy flow returns HTML rather than a `STATUS:` line, so success is
    detected positively: the body must lack the `PHONE NOT COPIED` marker *and*
    lack any login/permission page marker. The absence of a failure string alone
    is not sufficient evidence of success.
    """
    if not text or not text.strip():
        return ParsedResponse(ResponseStatus.UNKNOWN, reason="Empty response", retryable=True)

    upper = text.upper()

    if "PHONE NOT COPIED" in upper:
        match = re.search(r"PHONE NOT COPIED\s*[-:]\s*([^<\n]+)", upper)
        reason = match.group(1).strip() if match else "Copy failed"
        return ParsedResponse(ResponseStatus.ERROR, reason=reason)

    if any(marker in upper for marker in LOGIN_MARKERS):
        return ParsedResponse(ResponseStatus.ERROR, reason="ADMIN LOGIN REJECTED")

    return ParsedResponse(ResponseStatus.SUCCESS, reason="Created")
