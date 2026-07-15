"""Single-server FTP client — one connection, reused for many operations.

The fleet downloader (``ftp_fleet_downloader.py``) is built for fanning out
across hundreds of hosts concurrently. This is its small sibling: one host, one
blocking connection, the four operations you reach for from a notebook or an
ad-hoc script — list a directory, download a file, upload a file, remove a file.

Use it as a context manager so the connection is opened once and always closed::

    from ftp_handler.ftp_client import FtpClient

    with FtpClient(host="10.0.0.1", user="ftpuser", password="ftppass") as ftp:
        names = ftp.list_dir("/MEAS", pattern="*.dat")   # discover
        data = ftp.download(names[0])                     # fetch one
        ftp.upload("/INBOX/report.csv", csv_bytes)        # push one
        ftp.remove("/MEAS/stale.dat")                     # delete one

Errors from the server (``ftplib.error_perm`` for a missing path, socket
timeouts for a dead host) propagate to the caller unchanged — there's no fleet
report to absorb them here, and a single-server caller wants the real exception.
"""

import fnmatch
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from ftplib import FTP
from io import BytesIO
from zoneinfo import ZoneInfo

# Shared NLST normalization lives in core.listing so single-server and fan-out
# listing behave identically.
from ftp_handler.core.listing import _normalize_listing

# Server-local time of equipment FTP servers. Project convention: ingested
# timestamps are KST, and these servers sit in that zone, so a naive LIST mtime
# is interpreted as Asia/Seoul unless the caller overrides.
_DEFAULT_TZ = ZoneInfo("Asia/Seoul")


@dataclass(slots=True)
class FileInfo:
    """One entry from a ``LIST`` listing, parsed into typed fields.

    ``modified`` is timezone-aware (server-local, KST by default) or ``None`` if
    the line's date couldn't be parsed. ``size`` is ``None`` for directories.
    ``raw`` keeps the original LIST line so an unrecognized server format can be
    diagnosed from the returned data.
    """

    name: str
    path: str
    is_dir: bool
    size: int | None
    modified: datetime | None
    raw: str


_MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        start=1,
    )
}

# Unix `ls -l` style: type+perms, link count, owner, group, size, then the date
# triple (month, day, time-or-year) and the name. `.*?` skips owner/group (which
# may be numeric UIDs) up to the size, which is anchored by the month name that
# follows it — only the size sits immediately before the month.
_UNIX_RE = re.compile(
    r"^([-dlbcps])[rwxsStT-]{9}[+@.]?\s+"
    r".*?\s+(\d+)\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(\d{1,2})\s+"
    r"(\d{1,2}:\d{2}|\d{4})\s+"
    r"(.+)$"
)

# MS-DOS / IIS style: `MM-DD-YY[YY]  HH:MM(AM|PM)  (<DIR>|size)  name`.
# This is the `%m-%d-%y %I:%M%p` family the equipment Windows servers emit.
_DOS_RE = re.compile(
    r"^(\d{2})-(\d{2})-(\d{2,4})\s+"
    r"(\d{1,2}):(\d{2})\s*([AaPp][Mm])\s+"
    r"(<DIR>|\d+)\s+"
    r"(.+)$"
)


def _unix_datetime(month_abbr: str, day: int, time_or_year: str, now: datetime) -> datetime:
    """Build the mtime for a Unix LIST entry, handling the year-less recent form.

    Recent files print ``HH:MM`` with no year — assume the current year, and if
    that lands in the future (allowing a day of clock skew) roll back one year.
    Old files print a 4-digit year and no time (midnight).
    """
    month = _MONTHS[month_abbr]
    if ":" in time_or_year:
        hour, minute = time_or_year.split(":")
        dt = datetime(now.year, month, day, int(hour), int(minute), tzinfo=now.tzinfo)
        if dt > now + timedelta(days=1):
            dt = dt.replace(year=now.year - 1)
        return dt
    return datetime(int(time_or_year), month, day, tzinfo=now.tzinfo)


def _parse_list_line(line: str, now: datetime) -> tuple[str, bool, int | None, datetime] | None:
    """Parse one raw LIST line into ``(name, is_dir, size, modified)``.

    Returns ``None`` for lines matching neither known format (e.g. the Unix
    ``total 8`` header or blanks). ``now`` anchors year inference and supplies
    the target timezone. Pure and side-effect-free — the connection-bound
    ``FtpClient.list_details`` wraps it.
    """
    m = _UNIX_RE.match(line)
    if m:
        type_char, size_s, mon, day, time_or_year, name = m.groups()
        is_dir = type_char == "d"
        if type_char == "l" and " -> " in name:
            name = name.split(" -> ", 1)[0]  # drop the symlink target
        modified = _unix_datetime(mon, int(day), time_or_year, now)
        return name, is_dir, None if is_dir else int(size_s), modified

    m = _DOS_RE.match(line)
    if m:
        mm, dd, yy, hh, minute, ampm, size_s, name = m.groups()
        year = int(yy)
        if year < 100:
            year += 2000
        hour = int(hh) % 12
        if ampm.upper() == "PM":
            hour += 12
        modified = datetime(year, int(mm), int(dd), hour, int(minute), tzinfo=now.tzinfo)
        is_dir = size_s == "<DIR>"
        return name, is_dir, None if is_dir else int(size_s), modified

    return None


@dataclass(slots=True)
class DirEntries:
    """Split listing of one directory: subfolders and files as separate lists
    of full remote paths. ``pattern`` (when given to ``list_entries``) filters
    ``files`` only — you almost always want every subfolder but only the files
    matching a glob."""

    dirs: list[str]
    files: list[str]


class FtpClient:
    """One equipment FTP server, one connection reused across operations.

    Open with the context manager; the connection is established on ``__enter__``
    (connect → login → set passive mode) and closed on ``__exit__``. All four
    operations run over that single connection.
    """

    def __init__(
        self,
        *,
        host: str,
        user: str,
        password: str,
        port: int = 21,
        timeout: float = 8.0,
        passive: bool = True,
    ) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.timeout = timeout
        self.passive = passive
        self._ftp: FTP | None = None

    def __enter__(self) -> "FtpClient":
        ftp = FTP(timeout=self.timeout)
        ftp.connect(host=self.host, port=self.port, timeout=self.timeout)
        ftp.login(user=self.user, passwd=self.password)
        ftp.set_pasv(self.passive)
        self._ftp = ftp
        return self

    def __exit__(self, *exc: object) -> None:
        if self._ftp is not None:
            # close() never raises; quit() can if the connection already dropped.
            self._ftp.close()
            self._ftp = None

    def list_dir(self, remote_dir: str, pattern: str | None = None) -> list[str]:
        """List ``remote_dir`` (NLST), returning normalized paths.

        Pass ``pattern`` (e.g. ``"*.dat"``) to keep only matching basenames.
        """
        return _normalize_listing(self._ftp.nlst(remote_dir), remote_dir, pattern)

    def list_entries(self, remote_dir: str, pattern: str | None = None) -> DirEntries:
        """List ``remote_dir`` splitting subfolders from files (MLSD).

        Unlike ``list_dir`` (NLST, no type info), this uses MLSD so each entry's
        type is known — returns a ``DirEntries(dirs, files)`` of full paths.
        ``pattern`` filters ``files`` only. The ``.``/``..`` pseudo-entries are
        dropped.

        Requires server MLSD support (RFC 3659); an old equipment FTP daemon
        that lacks it raises ``error_perm`` — fall back to ``list_dir`` there.
        """
        dirs: list[str] = []
        files: list[str] = []
        for name, facts in self._ftp.mlsd(remote_dir):
            full = f"{remote_dir.rstrip('/')}/{name}"
            entry_type = facts.get("type")
            if entry_type == "dir":
                dirs.append(full)
            elif entry_type == "file":
                if pattern is None or fnmatch.fnmatch(name, pattern):
                    files.append(full)
            # cdir / pdir (the . and .. self/parent entries) and any unknown
            # type are skipped — neither a real subfolder nor a file.
        return DirEntries(dirs=dirs, files=files)

    def list_details(
        self,
        remote_dir: str,
        pattern: str | None = None,
        *,
        tz: ZoneInfo = _DEFAULT_TZ,
    ) -> list[FileInfo]:
        """List ``remote_dir`` with sizes and modified times (LIST).

        The broadly-compatible fallback for servers without MLSD: parses the
        server's ``LIST`` output (Unix ``ls -l`` and MS-DOS/IIS formats) into
        ``FileInfo`` entries with typed ``size`` and a timezone-aware
        ``modified``. ``tz`` is the server's local zone used to interpret the
        wall-clock times (KST by default).

        ``pattern`` filters files only (subfolders are always returned, like
        ``list_entries``). The ``.``/``..`` entries are dropped, and lines in an
        unrecognized format are skipped — inspect ``FileInfo.raw`` on the
        results, or capture raw lines yourself via ``self._ftp.retrlines``, if a
        server's format isn't covered.
        """
        lines: list[str] = []
        self._ftp.retrlines(f"LIST {remote_dir}", lines.append)
        now = datetime.now(tz)
        out: list[FileInfo] = []
        for line in lines:
            try:
                parsed = _parse_list_line(line, now)
            except ValueError:
                parsed = None  # malformed date (e.g. impossible day) — skip
            if parsed is None:
                continue
            name, is_dir, size, modified = parsed
            if name in (".", ".."):
                continue
            if not is_dir and pattern is not None and not fnmatch.fnmatch(name, pattern):
                continue
            full = f"{remote_dir.rstrip('/')}/{name}"
            out.append(
                FileInfo(
                    name=name,
                    path=full,
                    is_dir=is_dir,
                    size=size,
                    modified=modified,
                    raw=line,
                )
            )
        return out

    def download(self, remote_path: str) -> bytes:
        """Fetch ``remote_path`` (RETR) and return its bytes."""
        buf = BytesIO()
        self._ftp.retrbinary(f"RETR {remote_path}", buf.write)
        return buf.getvalue()

    def upload(self, remote_path: str, data: bytes) -> None:
        """Store ``data`` at ``remote_path`` (STOR), overwriting if it exists."""
        self._ftp.storbinary(f"STOR {remote_path}", BytesIO(data))

    def remove(self, remote_path: str) -> None:
        """Delete ``remote_path`` (DELE)."""
        self._ftp.delete(remote_path)
