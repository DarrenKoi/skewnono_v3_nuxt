"""Shapes the tool-files routes return, identical across providers."""

from typing import Literal, NotRequired, TypedDict


class Entry(TypedDict):
    name: str
    # Opaque key: hand it back verbatim to list or download. It is the server's
    # own path string, so a filename whose bytes are not valid UTF-8 (read as
    # latin-1, see SKEWNONO_TOOL_FTP_ENCODING) still round-trips.
    path: str
    is_dir: bool
    size: int | None
    # Server-local wall time from LIST, ISO 8601, or None when unparseable.
    # LIST omits the year for recent files and the time for old ones, so this
    # is an estimate, not a timestamp of record.
    modified: str | None


class Crumb(TypedDict):
    name: str
    path: str


class Listing(TypedDict):
    root: str
    # The login directory (PWD): where a listing opens and writes are confined.
    home: str
    path: str
    parent: str | None
    crumbs: list[Crumb]
    entries: list[Entry]
    # The download cap, so the page can disable a button it knows will 413.
    max_bytes: int


Verdict = Literal[
    "granted",
    "pending",
    "rejected",
    "none",
    "untrusted_identity",
    "directory_unavailable",
    "store_unavailable",
]


class Request(TypedDict):
    """One person's access request, stored under their normalised empno."""

    # uuid4 hex, new on every (re)request: the token approve/reject compare,
    # because requested_at has one-second grain and can repeat.
    request_id: str
    reason: str
    # The team the directory gave at request time. Display, and which pending
    # requests a team approval clears; never evidence of current membership.
    dept_nm: str | None
    requested_at: str
    status: Literal["pending", "rejected"]


class RequestRow(Request):
    empno: str
    # Current name from the directory, None when it cannot say.
    emp_nm: str | None


class Access(TypedDict):
    verdict: Verdict
    can_write: bool
    # Present only for "pending" and "rejected": the caller's own request.
    request: NotRequired[Request]


class Grant(TypedDict):
    granted_at: str
    granted_by: str


class GrantRow(Grant):
    kind: Literal["team", "emp"]
    value: str
    # emp rows only: the grantee's current team, when the directory knows it,
    # so the admin page can say a team grant would keep them in after revoke.
    dept_nm: str | None


class Team(TypedDict):
    dept_nm: str
    members: int


class Teams(TypedDict):
    teams: list[Team]
    # False when some directory rows could not be read, so a 0 is not proof.
    complete: bool
