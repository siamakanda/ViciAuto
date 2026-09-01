"""Centralized ViciDial response parsing.

ViciDial returns HTTP 200 for both success and error responses, so the HTTP
status cannot be trusted — the body text must be inspected. Every worker should
route its response text through `parse_response` instead of doing its own
substring matching.
"""


class ResponseStatus:
    SUCCESS = "success"
    ERROR = "error"
    NOTICE = "notice"
    UNKNOWN = "unknown"


class ParsedResponse:
    def __init__(self, status: str, reason: str = "", data: str = ""):
        self.status = status
        self.reason = reason
        self.data = data

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
