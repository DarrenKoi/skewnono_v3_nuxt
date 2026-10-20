"""Shapes the tool-files routes return, identical across providers."""

from typing import Literal, TypedDict


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
    # A trusted identity outside the allowed teams.
    "none",
    "untrusted_identity",
    "directory_unavailable",
]


class Access(TypedDict):
    verdict: Verdict
    can_write: bool
    # access.ALLOWED_TEAMS, so the refusal page names who does get in.
    teams: list[str]
