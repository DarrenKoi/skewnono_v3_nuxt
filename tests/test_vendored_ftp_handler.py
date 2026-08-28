"""Characterization tests for the vendored ``ftp_handler`` package.

``ftp_handler`` is the other office swap surface for the image feature:
``msr_image``'s office adapter drives ``FtpFleetDownloader`` (direct on Linux,
HTTP-proxy on the firewalled Windows client) to pull images and their
``cond.txt`` sidecars off the tool FTP servers. It shipped with no
package-local tests.

These pin **current** behaviour, not a redesign. Two things dominate:

* **Path assembly.** Remote paths are composed from NLST output, and local /
  MinIO targets are derived from those remote paths. A separator off-by-one
  or a lost path component only fails against a real server, hours away from
  the code that caused it.
* **Failure isolation.** The whole point of the fleet downloader is that one
  dead tool out of ~300 does not sink the run. Every level of that isolation
  (host, listing, file, and the caller's ``on_file`` sink) is pinned here.

``ftp_handler/`` is a **vendored copy** of an upstream ``flask_modules``
package; nothing here edits it. Company FTP is unreachable from home, so
``ftplib.FTP`` is replaced by an in-memory fake and ``requests`` by a fake
transport — no socket is opened by any test in this file.
"""

import base64
import datetime as dt
import ftplib
import inspect
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ftp_handler.core.client import _parse_list_line
from ftp_handler.core.listing import _normalize_listing
from ftp_handler.direct_downloader import collect
from ftp_handler.direct_downloader import fleet_downloader as direct
from ftp_handler.proxy import proxy_downloader as proxy
from ftp_handler.web_app import jobs as web_jobs


_REPO_ROOT = Path(__file__).resolve().parents[1]


# ── NLST normalization (shared by both downloaders) ──────────────────────────


def test_bare_basenames_are_joined_onto_the_listed_directory():
    """Servers that answer NLST with basenames need the directory put back, or
    the RETR that follows addresses the login directory instead."""
    assert _normalize_listing(["a.dat", "b.dat"], "/MEAS") == ["/MEAS/a.dat", "/MEAS/b.dat"]


def test_absolute_names_are_kept_verbatim():
    """Other servers answer with full paths; re-joining would double the
    directory. The leading ``/`` is the discriminator."""
    assert _normalize_listing(["/MEAS/a.dat"], "/MEAS") == ["/MEAS/a.dat"]


def test_a_trailing_slash_on_the_directory_never_doubles_the_separator():
    assert _normalize_listing(["a.dat"], "/MEAS/") == ["/MEAS/a.dat"]


def test_a_relative_multi_segment_name_keeps_its_subfolder():
    """``sub/d.dat`` is re-anchored on the listed directory WITH its subfolder
    intact. Until the 2026-08-09 upstream sync only the basename survived, so a
    recursive NLST silently produced ``/MEAS/d.dat`` — a path that either 550s
    or, worse, resolves to a different file that happens to share the name."""
    assert _normalize_listing(["sub/d.dat"], "/MEAS") == ["/MEAS/sub/d.dat"]


def test_a_relative_name_already_qualified_by_the_listed_dir_is_not_doubled():
    """Some servers answer NLST with the full path minus its leading slash.
    Re-anchoring that blindly would yield ``/MEAS/MEAS/d.dat``, so the
    normalizer detects the case where the name already carries the root."""
    assert _normalize_listing(["MEAS/d.dat"], "/MEAS") == ["/MEAS/d.dat"]


def test_the_glob_matches_the_basename_not_the_whole_path():
    assert _normalize_listing(["/MEAS/a.dat", "/MEAS/b.txt"], "/MEAS", "*.dat") == [
        "/MEAS/a.dat"
    ]


def test_a_none_pattern_keeps_every_entry():
    names = ["a.dat", "b.txt", "no_extension"]
    assert len(_normalize_listing(names, "/MEAS", None)) == 3


# ── LIST line parsing (the MLSD-less fallback) ───────────────────────────────


# ``now`` anchors year inference and supplies the target timezone. Frozen so
# the year-rollback assertion below does not drift with the calendar.
_NOW = dt.datetime(2026, 7, 26, 12, 0, tzinfo=ZoneInfo("Asia/Seoul"))


def test_unix_list_line_parses_name_size_and_mtime():
    parsed = _parse_list_line(
        "-rw-r--r--   1 root root      1234 Jul 24 09:15 shot01.jpeg", _NOW
    )
    name, is_dir, size, modified = parsed
    assert (name, is_dir, size) == ("shot01.jpeg", False, 1234)
    assert modified == dt.datetime(2026, 7, 24, 9, 15, tzinfo=_NOW.tzinfo)


def test_a_unix_directory_reports_no_size():
    """Directory sizes are meaningless (the 4096 is the dirent block), so the
    parser deliberately drops them rather than reporting a fake byte count."""
    name, is_dir, size, _ = _parse_list_line(
        "drwxr-xr-x   2 root root      4096 Jan 05  2025 archive", _NOW
    )
    assert (name, is_dir, size) == ("archive", True, None)


def test_a_year_less_timestamp_in_the_future_rolls_back_one_year():
    """Unix LIST prints ``HH:MM`` with no year for recent files. A December
    entry seen in July belongs to LAST year; assuming the current one would
    date it six months in the future and break any recency filter."""
    _, _, _, modified = _parse_list_line(
        "-rw-r--r--   1 root root      1234 Dec 31 23:59 newyear.dat", _NOW
    )
    assert modified.year == 2025


def test_a_symlink_entry_drops_its_target():
    """``link -> target.dat`` must yield ``link``; keeping the arrow would
    produce a remote path no RETR can resolve."""
    name, is_dir, _, _ = _parse_list_line(
        "lrwxrwxrwx   1 root root        11 Dec 31 23:59 link -> target.dat", _NOW
    )
    assert (name, is_dir) == ("link", False)


def test_dos_list_line_converts_twelve_hour_time():
    """The equipment Windows servers emit ``MM-DD-YY HH:MMAM/PM``; 01:05PM is
    13:05 and a naive ``%H`` read would put it at 01:05."""
    name, is_dir, size, modified = _parse_list_line(
        "07-24-2026  01:05PM       <DIR>          IMAGES", _NOW
    )
    assert (name, is_dir, size) == ("IMAGES", True, None)
    assert modified.hour == 13


def test_a_two_digit_dos_year_is_read_as_twenty_first_century():
    _, _, _, modified = _parse_list_line(
        "07-24-26  09:15AM              1234 shot01.jpeg", _NOW
    )
    assert modified.year == 2026


def test_an_unrecognized_line_is_skipped_not_raised():
    """The Unix ``total 8`` header and blank lines are normal output."""
    assert _parse_list_line("total 8", _NOW) is None
    assert _parse_list_line("", _NOW) is None


def test_an_impossible_calendar_date_raises_for_the_caller_to_absorb():
    """``_parse_list_line`` lets the ``ValueError`` out; ``list_details``
    catches it and skips the line. Pinned so the split of responsibility stays
    where the caller expects it."""
    with pytest.raises(ValueError):
        _parse_list_line("-rw-r--r--   1 r r  1 Feb 30 09:15 bad.dat", _NOW)


# ── local path mapping ───────────────────────────────────────────────────────


def test_safe_relative_drops_traversal_and_root_segments():
    """The remote server names the path; a ``..`` in it must never let a
    download escape ``dest_dir``. Segments are dropped, not resolved."""
    assert str(direct._safe_relative("/A/B/../C/x.txt")) == "A/B/C/x.txt"


def test_safe_relative_normalizes_windows_separators_and_drive_letters():
    """A Windows-hosted equipment FTP server emits backslashes; the ``:`` in a
    drive letter is illegal in a path component on the download client."""
    assert str(direct._safe_relative("C:\\data\\x.txt")) == "C_/data/x.txt"


def test_safe_relative_sanitizes_characters_illegal_on_windows():
    assert str(direct._safe_relative("/a/b?c/x*.txt")) == "a/b_c/x_.txt"


def test_safe_relative_trims_trailing_dots_and_spaces_windows_would_eat():
    """Windows silently strips them on create, so a later lookup by the
    untrimmed name would miss the file that was actually written."""
    assert str(direct._safe_relative("/a/trail. /x.txt")) == "a/trail/x.txt"


def test_a_path_with_no_usable_segments_becomes_a_placeholder():
    """Never an empty path — that would resolve to ``dest_dir`` itself and the
    write would fail with a confusing IsADirectoryError."""
    assert str(direct._safe_relative("/")) == "_unnamed"


def test_keep_last_takes_the_tail_and_strip_components_takes_the_front():
    rel = Path("IMAGES/20260615/sub/x.jpeg")
    assert str(direct._keep_last_components(rel, 2)) == "sub/x.jpeg"
    assert str(direct._strip_components(rel, 2)) == "sub/x.jpeg"


def test_over_trimming_never_produces_an_empty_path():
    """``keep_last`` beyond the depth keeps everything; ``strip`` beyond the
    depth leaves the bare filename. Neither may return ``Path('')``."""
    rel = Path("a/b.jpeg")
    assert direct._keep_last_components(rel, 9) == rel
    assert str(direct._strip_components(rel, 9)) == "b.jpeg"


def test_local_target_always_keeps_the_host_segment():
    """Image names collide across tools, so the ``<host>`` directory is the
    only thing separating two tools' ``S09-01AP.jpeg``."""
    assert str(direct.local_target("/dest", "10.0.0.1", "/MEAS/2026/x.dat")) == (
        "/dest/10.0.0.1/MEAS/2026/x.dat"
    )


def test_local_target_applies_strip_components_before_keep_last():
    """Order matters and is documented: strip from the front, then keep the
    tail of what remains."""
    target = direct.local_target(
        "/dest", "10.0.0.1", "/A/B/C/x.dat", strip_components=1, keep_last=2
    )
    assert str(target) == "/dest/10.0.0.1/C/x.dat"


def test_image_sidecar_target_flattens_the_image_but_not_its_sidecar():
    """Every image's sidecar is named ``cond.txt``, so flattening both would
    have each image's sidecar overwrite the last. The image lands at the root
    and the sidecar keeps its per-image folder."""
    assert str(direct.image_sidecar_target("/d", "/IMAGES/20260615/S09-01AP.jpeg")) == (
        "/d/S09-01AP.jpeg"
    )
    assert str(
        direct.image_sidecar_target("/d", "/IMAGES/20260615/.S09-01AP.jpeg/cond.txt")
    ) == "/d/.S09-01AP.jpeg/cond.txt"


def test_save_to_dir_writes_where_local_target_predicts(tmp_path):
    """``local_target`` is advertised as the pure mirror of ``save_to_dir`` —
    callers use it to recover local paths after a download, so the two must
    not drift."""
    sink = direct.save_to_dir(tmp_path, keep_last=1)
    sink("10.0.0.1", "/MEAS/2026/x.dat", b"payload")
    expected = direct.local_target(tmp_path, "10.0.0.1", "/MEAS/2026/x.dat", keep_last=1)
    assert expected.read_bytes() == b"payload"


def test_save_to_dir_chains_the_then_callback_after_the_write(tmp_path):
    seen = []
    sink = direct.save_to_dir(tmp_path, then=lambda h, p, d: seen.append((h, p, len(d))))
    sink("10.0.0.1", "/MEAS/x.dat", b"1234")
    assert seen == [("10.0.0.1", "/MEAS/x.dat", 4)]


def test_save_image_with_sidecar_keeps_two_images_sidecars_apart(tmp_path):
    sink = direct.save_image_with_sidecar(tmp_path)
    sink("h", "/IMG/.a.jpeg/cond.txt", b"mag=1")
    sink("h", "/IMG/.b.jpeg/cond.txt", b"mag=2")
    assert (tmp_path / ".a.jpeg" / "cond.txt").read_bytes() == b"mag=1"
    assert (tmp_path / ".b.jpeg" / "cond.txt").read_bytes() == b"mag=2"


# ── MinIO object key assembly ────────────────────────────────────────────────


class FakeMinioClient:
    """Records what the ``put_*_to_minio`` sinks would upload."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    def put(self, key, data):
        self.calls.append(("put", key, data))

    def put_pickle(self, key, obj):
        self.calls.append(("put_pickle", key, obj))

    def put_dataframe(self, key, frame):
        self.calls.append(("put_dataframe", key, frame))


def test_object_key_preserves_the_remote_directory_structure():
    """Slashes are just key separators in S3, so the remote layout survives
    into the key and stays browsable."""
    assert direct._object_key("10.0.0.1", "/MEAS/2026/x.dat", "") == (
        "10.0.0.1/MEAS/2026/x.dat"
    )


def test_object_key_normalizes_backslashes_so_windows_hosts_key_the_same():
    """Otherwise the same logical file would live at two different keys
    depending on which OS the tool's FTP daemon runs."""
    assert direct._object_key("10.0.0.1", "\\MEAS\\sub\\x.dat", ".pkl") == (
        "10.0.0.1/MEAS/sub/x.dat.pkl"
    )


def test_the_three_minio_sinks_use_their_documented_default_suffixes():
    client = FakeMinioClient()
    direct.put_bytes_to_minio(client)("h", "/a/x.dat", b"raw")
    direct.put_pickle_to_minio(client, lambda h, p, d: {"v": 1})("h", "/a/x.dat", b"raw")
    direct.put_parquet_to_minio(client, lambda h, p, d: "frame")("h", "/a/x.dat", b"raw")
    assert [key for _, key, _ in client.calls] == [
        "h/a/x.dat",
        "h/a/x.dat.pkl",
        "h/a/x.dat.parquet",
    ]


def test_a_custom_key_function_replaces_the_default_scheme_entirely():
    client = FakeMinioClient()
    sink = direct.put_bytes_to_minio(client, key=lambda host, path: f"eqp/{host}/fixed")
    sink("h", "/a/x.dat", b"raw")
    assert client.calls[0][1] == "eqp/h/fixed"


def test_the_transform_output_not_the_raw_bytes_is_what_gets_stored():
    """``put_pickle_to_minio`` is the processing seam: the callback receives
    the raw bytes and what it RETURNS is uploaded."""
    client = FakeMinioClient()
    direct.put_pickle_to_minio(client, lambda h, p, data: {"len": len(data)})(
        "h", "/a/x.dat", b"1234"
    )
    assert client.calls[0][2] == {"len": 4}


# ── spec construction ────────────────────────────────────────────────────────


def test_specs_from_hosts_gives_every_host_its_own_list_copies():
    """Shared list objects would make mutating one host's spec silently edit
    the whole fleet's."""
    listings = [direct.ListDir("/MEAS", "*.dat")]
    specs = direct.specs_from_hosts(["a", "b"], files=["/log"], listings=listings)
    specs[0].files.append("/extra")
    assert specs[1].files == ["/log"]
    assert specs[0].listings is not specs[1].listings


def test_group_files_by_host_folds_rows_into_one_connection_per_host():
    """The flat ``(ip, path)`` table case: bucketing by host is what keeps a
    300-row frame from opening 300 FTP connections."""
    specs = direct.group_files_by_host(
        [("a", "/1"), ("b", "/2"), ("a", "/3")]
    )
    assert [(s.host, s.files) for s in specs] == [("a", ["/1", "/3"]), ("b", ["/2"])]


def test_group_files_by_host_preserves_first_appearance_order():
    specs = direct.group_files_by_host([("z", "/1"), ("a", "/2")])
    assert [s.host for s in specs] == ["z", "a"]


def test_build_host_specs_reads_the_orchestrator_json_shape():
    """The ``listings`` entries are dicts with an optional ``pattern``; a
    missing one means "fetch everything in that directory"."""
    specs = collect.build_host_specs(
        [
            {"host": "10.0.0.1", "files": ["/log"],
             "listings": [{"remote_dir": "/MEAS", "pattern": "*.dat"}]},
            {"host": "10.0.0.2", "listings": [{"remote_dir": "/IMG"}]},
        ]
    )
    assert specs[0].listings[0] == direct.ListDir("/MEAS", "*.dat")
    assert specs[1].listings[0].pattern is None
    assert specs[1].files == []


def test_upload_specs_from_hosts_copies_the_file_list_per_host():
    files = [direct.UploadFile("/INBOX/r.csv", b"x")]
    specs = direct.upload_specs_from_hosts(["a", "b"], files=files)
    assert specs[0].files is not specs[1].files
    assert specs[0].files[0].data == b"x"


# ── report aggregation ───────────────────────────────────────────────────────


def test_failure_ratio_is_zero_for_an_empty_run_not_a_division_error():
    """Threshold alerting calls this unconditionally; an empty fleet must not
    raise inside the alerting path."""
    assert direct.DownloadReport(files=[], failures=[]).failure_ratio == 0.0
    assert direct.UploadReport(results=[], failures=[]).failure_ratio == 0.0


def test_failure_ratio_counts_failures_against_all_attempted_units():
    report = direct.DownloadReport(
        files=[direct.FileResult("h", "/a", b"1")],
        failures=[direct.HostFailure("h", "e"), direct.HostFailure("h", "e")],
    )
    assert (report.ok, report.ng, report.failure_ratio) == (1, 2, pytest.approx(2 / 3))


def test_grouped_nests_files_by_host_then_remote_path():
    report = direct.DownloadReport(
        files=[direct.FileResult("h1", "/a", b"1"), direct.FileResult("h2", "/b", b"2")],
        failures=[],
    )
    assert report.grouped() == {"h1": {"/a": b"1"}, "h2": {"/b": b"2"}}


def test_listing_report_to_specs_drops_hosts_that_discovered_nothing():
    """Otherwise the follow-up download would re-open a connection to a host
    with no work to do."""
    report = direct.ListingReport(
        listings=[direct.HostListing("h1", ["/a"]), direct.HostListing("h2", [])],
        failures=[],
    )
    assert [s.host for s in report.to_specs()] == ["h1"]
    assert report.total_paths == 1


def test_listing_report_to_specs_yields_fixed_files_so_no_relisting_happens():
    report = direct.ListingReport(listings=[direct.HostListing("h1", ["/a", "/b"])], failures=[])
    spec = report.to_specs()[0]
    assert (spec.files, spec.listings) == (["/a", "/b"], [])


def test_sizing_report_sums_only_measured_files():
    """A file whose SIZE failed lands in ``failures`` and is never counted as
    zero — the RAM estimate would otherwise understate the run."""
    report = direct.SizingReport(
        files=[direct.FileSize("h1", "/a", 10), direct.FileSize("h1", "/b", 5),
               direct.FileSize("h2", "/c", 7)],
        failures=[direct.HostFailure("h2", "SIZE unsupported by server", "/d")],
    )
    assert report.total_bytes == 22
    assert report.by_host() == {"h1": 15, "h2": 7}


# ── fleet download: failure isolation, driven by a fake FTP ──────────────────


class FakeFTP:
    """In-memory ``ftplib.FTP`` stand-in — no socket, no sleep.

    Behaviour is keyed off well-known names so one fake covers every isolation
    level: host ``"dead"`` refuses to connect, ``/BAD`` refuses to list,
    ``*.txt`` refuses to RETR, ``nosize`` has no SIZE, and a STOR path
    containing ``fail`` refuses to store. It raises real ``ftplib`` errors so
    the ``all_errors`` matching in the source is genuinely exercised.
    """

    def __init__(self, timeout=None):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def connect(self, host=None, port=None, timeout=None):
        if host == "dead":
            raise ftplib.error_temp("421 no route to host")

    def login(self, user=None, passwd=None):
        pass

    def set_pasv(self, passive):
        pass

    def voidcmd(self, command):
        pass

    def nlst(self, remote_dir):
        if remote_dir == "/BAD":
            raise ftplib.error_perm("550 no such directory")
        return ["a.dat", "b.txt"]

    def retrbinary(self, command, callback):
        path = command.split(" ", 1)[1]
        if path.endswith(".txt"):
            raise ftplib.error_perm("550 missing")
        callback(b"data:" + path.encode())

    def size(self, remote_path):
        return None if remote_path.endswith("nosize") else 42

    def storbinary(self, command, stream):
        if "fail" in command:
            raise ftplib.error_perm("553 permission denied")


@pytest.fixture
def fleet(monkeypatch) -> direct.FtpFleetDownloader:
    """A downloader whose transport is the in-memory fake.

    ``host_timeout`` is left generous: the fake returns instantly, so a test
    that takes measurable time means a real socket got opened.
    """
    monkeypatch.setattr(direct, "FTP", FakeFTP)
    return direct.FtpFleetDownloader(user="u", password="p", host_timeout=30.0)


def test_a_dead_host_is_reported_without_a_remote_path(fleet):
    """``remote_path=None`` is the marker for "failed before any file" —
    connect/login/listing. ``msr_image``'s office adapter reads exactly this
    to decide ``SourceUnavailable`` rather than ``ImageNotFound``."""
    report = fleet.download([direct.HostSpec("dead", files=["/x/a.dat"])])
    assert report.files == []
    assert report.failures[0].remote_path is None
    assert report.failures[0].error.startswith("error_temp:")


def test_a_dead_host_never_sinks_its_siblings(fleet):
    report = fleet.download(
        [direct.HostSpec("dead", files=["/x/a.dat"]),
         direct.HostSpec("10.0.0.1", files=["/x/a.dat"])]
    )
    assert [f.host for f in report.files] == ["10.0.0.1"]
    assert [f.host for f in report.failures] == ["dead"]


def test_one_missing_file_is_isolated_from_the_rest_of_its_host(fleet):
    """Per-file isolation with the remote path attached, so the caller can
    tell WHICH file went missing."""
    report = fleet.download([direct.HostSpec("10.0.0.1", files=["/x/a.dat", "/x/b.txt"])])
    assert [f.remote_path for f in report.files] == ["/x/a.dat"]
    assert report.failures[0].remote_path == "/x/b.txt"


def test_a_failed_listing_does_not_cancel_the_hosts_fixed_files(fleet):
    """Listings are discovery; the fixed paths are already known. Losing one
    must not lose the other."""
    report = fleet.download(
        [direct.HostSpec("10.0.0.1", files=["/x/a.dat"],
                         listings=[direct.ListDir("/BAD")])]
    )
    assert [f.remote_path for f in report.files] == ["/x/a.dat"]
    assert report.failures[0].error.startswith("list /BAD failed:")
    assert report.failures[0].remote_path == "/BAD"


def test_failure_strings_are_always_exception_name_colon_message(fleet):
    """Downstream code (and ``msr_image``'s fakes) parse this shape; it is a
    de facto contract across every worker in the package."""
    report = fleet.download([direct.HostSpec("10.0.0.1", files=["/x/b.txt"])])
    assert report.failures[0].error == "error_perm: 550 missing"


def test_streaming_mode_drops_the_bytes_from_the_report(fleet):
    """``on_file`` consumed them; keeping a second copy is what blows the RAM
    budget the callback exists to protect."""
    seen = []
    report = fleet.download(
        [direct.HostSpec("10.0.0.1", files=["/x/a.dat"])],
        on_file=lambda host, path, data: seen.append((host, path, data)),
    )
    assert seen == [("10.0.0.1", "/x/a.dat", b"data:/x/a.dat")]
    assert report.files[0].data == b""
    assert report.ok == 1


def test_a_raising_on_file_sink_fails_only_that_file(fleet):
    """The callback does real work (MinIO put, OpenSearch index). A raise is
    caught by the same per-file guard as an FTP error, so a flaky sink degrades
    the run instead of aborting it — and the file is NOT counted as ok."""
    def explode(host, path, data):
        raise RuntimeError("sink down")

    report = fleet.download(
        [direct.HostSpec("10.0.0.1", files=["/x/a.dat"])], on_file=explode
    )
    assert report.ok == 0
    assert report.failures[0].error == "RuntimeError: sink down"
    assert report.failures[0].remote_path == "/x/a.dat"


def test_on_file_cannot_fire_after_download_returns(monkeypatch):
    """The property ``msr_image``'s office adapter depends on.

    ``host_timeout`` abandons a host's FUTURE, but nothing can kill its thread —
    ``shutdown(wait=False)`` just stops waiting. ``download_all`` then flushes
    its leftover image/cond pairing state and finishes the job the moment
    ``download()`` returns, so a straggling callback would mutate the dict being
    iterated (``RuntimeError: dictionary changed size during iteration``, which
    marks the whole warm job errored) or double-count a file into the registry
    (``done > total``). The downloader gates each host's callback shut on
    abandonment, and every gate before returning.
    """
    import threading

    monkeypatch.setattr(direct, "FTP", FakeFTP)
    released = threading.Event()
    seen: list[str] = []
    original = direct.FtpFleetDownloader._fetch_one

    def stall_on_first(self, ftp, host, remote_path, on_file, files, failures):
        if remote_path.endswith("a.dat"):
            released.wait(2.0)
        return original(self, ftp, host, remote_path, on_file, files, failures)

    monkeypatch.setattr(direct.FtpFleetDownloader, "_fetch_one", stall_on_first)
    fleet = direct.FtpFleetDownloader(user="u", password="p", host_timeout=0.05)
    try:
        report = fleet.download(
            [direct.HostSpec("10.0.0.1", files=["/x/a.dat", "/x/c.dat", "/x/d.dat"])],
            on_file=lambda h, p, d: seen.append(p),
        )
        assert report.ng == 1 and seen == []
        released.set()
        time.sleep(0.3)  # the abandoned thread runs on; it must stay silent
    finally:
        released.set()
    assert seen == [], "a callback escaped after download() returned"


def test_list_dirs_consults_listings_only_and_ignores_fixed_files(fleet):
    """You list to DISCOVER unknown paths; the fixed ones are already known,
    so echoing them back would double-count them on the follow-up download."""
    report = fleet.list_dirs(
        [direct.HostSpec("10.0.0.2", files=["/known"],
                         listings=[direct.ListDir("/MEAS", "*.dat")])]
    )
    assert report.grouped() == {"10.0.0.2": ["/MEAS/a.dat"]}


def test_a_connect_failure_yields_no_listing_entry_at_all(fleet):
    """A host that connected but found nothing still gets an (empty) listing;
    a host that never connected gets none. The two cases must stay
    distinguishable."""
    report = fleet.list_dirs([direct.HostSpec("dead", listings=[direct.ListDir("/MEAS")])])
    assert report.listings == []
    assert report.ng == 1


def test_size_dirs_records_unsupported_size_rather_than_counting_zero(fleet):
    report = fleet.size_dirs(
        [direct.HostSpec("10.0.0.1", files=["/x/a.dat", "/x/nosize"])]
    )
    assert report.total_bytes == 42
    assert report.failures[0].error == "SIZE unsupported by server"
    assert report.failures[0].remote_path == "/x/nosize"


def test_upload_isolates_a_rejected_stor_from_the_hosts_other_files(fleet):
    report = fleet.upload(
        [direct.UploadSpec("10.0.0.1", files=[
            direct.UploadFile("/in/ok.csv", b"x"),
            direct.UploadFile("/in/fail.csv", b"y"),
        ])]
    )
    assert report.grouped() == {"10.0.0.1": ["/in/ok.csv"]}
    assert report.failures[0].remote_path == "/in/fail.csv"


def test_failures_stay_in_submission_order_despite_the_thread_pool(fleet):
    """Futures are collected in submit order, not completion order, so a
    report is reproducible enough to diff between runs."""
    report = fleet.download(
        [direct.HostSpec("dead", files=["/a"]),
         direct.HostSpec("10.0.0.1", files=["/x/b.txt"]),
         direct.HostSpec("dead", files=["/c"])]
    )
    assert [f.host for f in report.failures] == ["dead", "10.0.0.1", "dead"]


class OneFileFleet:
    """Minimal ``FtpFleetDownloader`` stand-in: hands exactly one file to the
    caller's ``on_file`` and reports nothing, so ``collect_fleet``'s callback
    is exercised without any FTP."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def download(self, specs, *, on_file=None):
        on_file("h", "/x/a.dat", b"raw")
        return direct.DownloadReport(files=[], failures=[])


def test_collect_fleet_stamps_the_archive_key_onto_every_parsed_document(monkeypatch):
    """The archive→parse→index order is the invariant: nothing is indexed
    whose raw source was not stored first, and each doc carries the storage
    key that produced it."""
    order: list[str] = []

    monkeypatch.setattr(collect, "FtpFleetDownloader", OneFileFleet)
    indexed: list[list[dict]] = []
    collect.collect_fleet(
        [direct.HostSpec("h", files=["/x/a.dat"])],
        user="u",
        password="p",
        archive=lambda h, p, d: order.append("archive") or "minio/key",
        parse=lambda h, p, d: order.append("parse") or [{"a": 1}, {"a": 2}],
        index=lambda docs: order.append("index") or indexed.append(docs),
    )
    assert order == ["archive", "parse", "index"]
    assert all(doc["minio_key"] == "minio/key" for doc in indexed[0])


def test_collect_fleet_skips_the_index_call_when_parse_yields_nothing(monkeypatch):
    """An empty bulk request is a wasted round trip, and some clients treat it
    as an error."""
    monkeypatch.setattr(collect, "FtpFleetDownloader", OneFileFleet)
    calls = []
    collect.collect_fleet(
        [direct.HostSpec("h", files=["/x/a.dat"])],
        user="u", password="p",
        archive=lambda h, p, d: "k",
        parse=lambda h, p, d: [],
        index=lambda docs: calls.append(docs),
    )
    assert calls == []


# ── the proxy transport (firewalled client) ──────────────────────────────────


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class FakeRequests:
    """Stand-in for the ``requests`` module: records POSTs, never opens a
    socket. ``boom`` makes every call raise, modelling an unreachable proxy."""

    def __init__(self, payload: dict | None = None, *, boom: bool = False) -> None:
        self.payload = payload or {}
        self.boom = boom
        self.posts: list[dict] = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if self.boom:
            raise ConnectionError("proxy unreachable")
        return FakeResponse(self.payload)


@pytest.mark.parametrize("method", ["download", "list_dirs", "size_dirs", "upload"])
def test_both_transports_expose_an_identical_method_signature(method):
    """The whole seam is "swap one import line". A signature drift between the
    direct and proxy downloaders would break exactly the call sites that were
    supposed to be transport-agnostic — ``msr_image``'s office adapter picks
    its transport at import time and passes the same arguments either way."""
    assert inspect.signature(getattr(direct.FtpFleetDownloader, method)) == (
        inspect.signature(getattr(proxy.FtpFleetDownloader, method))
    )


def test_both_transports_satisfy_the_fleet_transport_protocol():
    assert isinstance(direct.FtpFleetDownloader(user="u", password="p"), direct.FleetTransport)
    assert isinstance(proxy.FtpFleetDownloader(user="u", password="p"), direct.FleetTransport)


def test_the_proxy_reuses_the_direct_report_dataclasses():
    """Same class objects, so ``report.grouped()`` / ``failure_ratio`` /
    ``to_specs()`` behave identically under either transport."""
    assert proxy.DownloadReport is direct.DownloadReport
    assert proxy.HostSpec is direct.HostSpec


def test_a_spec_serializes_to_the_wire_without_losing_a_none_pattern():
    """``pattern`` must survive as an explicit ``None`` — dropping the key
    would make the proxy apply no filter, which happens to be the same
    behaviour but stops being so the moment the server-side default changes."""
    wire = proxy._spec_to_wire(
        direct.HostSpec("h", files=["/a"], listings=[direct.ListDir("/M", None)])
    )
    assert wire == {"host": "h", "files": ["/a"],
                    "listings": [{"remote_dir": "/M", "pattern": None}]}


def test_the_constructors_account_travels_to_the_proxy():
    """The client's ``user``/``password`` must reach the proxy, or it logs in
    as its own ``FTP_PROXY_FTP_USER`` and the caller's account is silently
    ignored — the direct transport uses ``spec.user or self.user``, and the two
    transports have to reach the same tool as the same account. A per-host
    override still wins over the constructor's."""
    client = proxy.FtpFleetDownloader(user="hitachi", password="hid")
    specs = client._payload([direct.HostSpec("h1"), direct.HostSpec("h2", user="amat", password="ad")])["specs"]
    assert (specs[0]["user"], specs[0]["password"]) == ("hitachi", "hid")
    assert (specs[1]["user"], specs[1]["password"]) == ("amat", "ad")

    uploads = client._upload_payload([direct.UploadSpec("h1")])["specs"]
    assert (uploads[0]["user"], uploads[0]["password"]) == ("hitachi", "hid")


def test_upload_bytes_travel_base64_encoded_because_json_has_no_byte_type():
    wire = proxy._upload_spec_to_wire(
        direct.UploadSpec("h", files=[direct.UploadFile("/a", b"\x00\xff")])
    )
    assert base64.b64decode(wire["files"][0]["data_b64"]) == b"\x00\xff"


def test_specs_are_split_into_request_batch_sized_posts(monkeypatch):
    """``request_batch`` bounds the proxy's transient RAM (collect + base64 +
    jsonify is roughly 3x a batch's raw bytes), so the batching is a memory
    guard, not a nicety.

    Batch SIZES are asserted as a multiset, not a sequence: the batches are
    POSTed concurrently across ``client_workers`` threads, so the order they
    reach the transport is genuinely nondeterministic. Every host must still
    appear exactly once.
    """
    fake = FakeRequests({"files": [], "failures": []})
    monkeypatch.setattr(proxy, "requests", fake)
    client = proxy.FtpFleetDownloader(user="u", password="p", request_batch=2)
    client.download([direct.HostSpec(f"h{i}") for i in range(5)])
    assert sorted(len(post["json"]["specs"]) for post in fake.posts) == [1, 2, 2]
    posted_hosts = [
        spec["host"] for post in fake.posts for spec in post["json"]["specs"]
    ]
    assert sorted(posted_hosts) == [f"h{i}" for i in range(5)]


def test_a_whole_batch_transport_failure_fails_every_host_in_that_batch(monkeypatch):
    """The proxy is all-or-nothing per request, so per-host isolation moves up
    one level: an unreachable proxy must still produce one ``HostFailure`` per
    host rather than a bare exception."""
    monkeypatch.setattr(proxy, "requests", FakeRequests(boom=True))
    client = proxy.FtpFleetDownloader(user="u", password="p", request_batch=5)
    report = client.download([direct.HostSpec("h1"), direct.HostSpec("h2")])
    assert report.ok == 0
    assert [f.host for f in report.failures] == ["h1", "h2"]
    assert all(f.error.startswith("proxy request failed: ConnectionError:")
               for f in report.failures)
    assert all(f.remote_path is None for f in report.failures)


def test_the_proxy_decodes_file_bytes_and_preserves_host_failures(monkeypatch):
    monkeypatch.setattr(proxy, "requests", FakeRequests({
        "files": [{"host": "h1", "remote_path": "/a",
                   "data_b64": base64.b64encode(b"AB").decode()}],
        "failures": [{"host": "h1", "error": "error_perm: 550", "remote_path": "/b"}],
    }))
    report = proxy.FtpFleetDownloader(user="u", password="p").download([direct.HostSpec("h1")])
    assert report.files[0].data == b"AB"
    assert report.failures[0].remote_path == "/b"


def test_the_on_file_contract_is_identical_under_the_proxy(monkeypatch):
    """Bytes are consumed by the callback and dropped from the report, and a
    raising callback fails only that file — same as direct mode."""
    monkeypatch.setattr(proxy, "requests", FakeRequests({
        "files": [{"host": "h1", "remote_path": "/a",
                   "data_b64": base64.b64encode(b"AB").decode()}],
        "failures": [],
    }))
    client = proxy.FtpFleetDownloader(user="u", password="p")

    seen = []
    report = client.download([direct.HostSpec("h1")], on_file=lambda h, p, d: seen.append(d))
    assert seen == [b"AB"] and report.files[0].data == b""

    def explode(host, path, data):
        raise RuntimeError("sink down")

    report = client.download([direct.HostSpec("h1")], on_file=explode)
    assert report.ok == 0
    assert report.failures[0].error == "RuntimeError: sink down"


def test_an_empty_spec_list_short_circuits_before_any_http_call(monkeypatch):
    fake = FakeRequests()
    monkeypatch.setattr(proxy, "requests", fake)
    client = proxy.FtpFleetDownloader(user="u", password="p")
    assert client.download([]).ok == 0
    assert client.list_dirs([]).ok == 0
    assert client.size_dirs([]).ok == 0
    assert client.upload([]).ok == 0
    assert fake.posts == []


def test_the_bearer_header_appears_only_when_a_token_is_configured(monkeypatch):
    """``PROXY_TOKEN`` is a module constant (a deployment fact of the
    firewalled client box), deliberately not a constructor argument — that is
    what keeps the constructor identical to the direct downloader's."""
    monkeypatch.setattr(proxy, "PROXY_TOKEN", None)
    assert proxy.FtpFleetDownloader(user="u", password="p")._headers() == {}
    monkeypatch.setattr(proxy, "PROXY_TOKEN", "sekret")
    assert proxy.FtpFleetDownloader(user="u", password="p")._headers() == {
        "Authorization": "Bearer sekret"
    }


def test_the_default_http_timeout_covers_a_whole_batch_worked_serially():
    """The proxy can end up working one batch's hosts serially in the tail, so
    the client budget is ``host_timeout * request_batch`` plus slack. A tighter
    default would time out a healthy slow run."""
    client = proxy.FtpFleetDownloader(user="u", password="p", host_timeout=45.0, request_batch=5)
    assert client.http_timeout == 45.0 * 5 + 30.0


def test_the_fleet_account_reaches_the_request_body(monkeypatch):
    """The constructor's account IS serialized — reversed 2026-08-28.

    It was not, between 2026-08-09 and 2026-08-28: the account lived only in the
    proxy host's ``FTP_PROXY_FTP_USER`` / ``FTP_PROXY_FTP_PASSWORD``, to keep it
    out of plaintext bodies on the http-only cloud. That bought little and cost
    correctness. Little, because FTP itself sends USER/PASS in the clear to the
    same tools on the same network one hop later. Cost, because the proxy then
    ignored whatever account the caller constructed the client with — invisible
    while every tool family shared one login, wrong the moment one did not, and
    wrong as a WRONG-ACCOUNT LOGIN rather than an error. The direct transport
    has always used ``spec.user or self.user``; the two now agree.

    The proxy env survives as the default for a request that names no account.
    """
    fake = FakeRequests({"files": [], "failures": []})
    monkeypatch.setattr(proxy, "requests", fake)
    proxy.FtpFleetDownloader(user="hitachi", password="hid").download([direct.HostSpec("h")])
    entry = fake.posts[0]["json"]["specs"][0]
    assert entry["user"] == "hitachi"
    assert entry["password"] == "hid"
    # Still per-spec, never a top-level field: the proxy logs in per host.
    body = fake.posts[0]["json"]
    assert "user" not in body and "password" not in body


def test_a_per_host_credential_override_does_reach_the_body(monkeypatch):
    """A spec's OWN credentials ARE serialized — that is what they are for.

    Added upstream 2026-08-10: one fleet is not one account, so a HostSpec may
    name the account for its host and only that host. Necessary once a run
    spans two vendors' tools, since the proxy's single environment pair cannot
    express two logins.
    """
    fake = FakeRequests({"files": [], "failures": []})
    monkeypatch.setattr(proxy, "requests", fake)
    proxy.FtpFleetDownloader(user="hitachi", password="hid").download(
        [direct.HostSpec("h", user="amat", password="other")]
    )
    entry = fake.posts[0]["json"]["specs"][0]
    assert entry["user"] == "amat"
    assert entry["password"] == "other"


def test_a_per_host_override_beats_the_fleet_account_only_for_that_host(monkeypatch):
    """Two accounts in one batch: the override host gets its own, the sibling
    keeps the constructor's. This is the case the whole fallback exists for —
    a run spanning two vendors' tools, which the proxy's single environment
    pair cannot express."""
    fake = FakeRequests({"files": [], "failures": []})
    monkeypatch.setattr(proxy, "requests", fake)
    proxy.FtpFleetDownloader(user="hitachi", password="hid").download(
        [direct.HostSpec("shared"), direct.HostSpec("other", user="amat", password="x")]
    )
    by_host = {e["host"]: e for e in fake.posts[0]["json"]["specs"]}
    assert by_host["shared"]["user"] == "hitachi"
    assert by_host["other"]["user"] == "amat"


@pytest.mark.parametrize(
    "method,path",
    [("download", "/download_sknn_v3"), ("list_dirs", "/list_dirs_sknn_v3"),
     ("size_dirs", "/size_dirs_sknn_v3"), ("upload", "/upload_sknn_v3")],
)
def test_each_operation_posts_to_its_suffixed_route(monkeypatch, method, path):
    """The ``_sknn_v3`` suffix avoids colliding with routes already mounted on
    the host Flask app, and must match ``ftp_handler/proxy/flask_proxy.py``."""
    fake = FakeRequests({})
    monkeypatch.setattr(proxy, "requests", fake)
    client = proxy.FtpFleetDownloader(user="u", password="p")
    spec = direct.UploadSpec("h") if method == "upload" else direct.HostSpec("h")
    getattr(client, method)([spec])
    assert fake.posts[0]["url"].endswith(path)


# ── background jobs ──────────────────────────────────────────────────────────


@pytest.fixture
def jobs_registry():
    """A ``BackgroundJobs`` whose pool is always shut down.

    Without the teardown each test would leak a live worker thread into the
    rest of the session — harmless individually, a slow drift across a
    thousand-test run.
    """
    registry = web_jobs.BackgroundJobs()
    try:
        yield registry
    finally:
        registry.shutdown()


def _await_job(jobs: web_jobs.BackgroundJobs, job_id: str) -> web_jobs.Job:
    """Poll until the job leaves ``running``.

    The submitted work is in-process and returns in microseconds, so this
    normally exits on the first read. The loop is bounded (2s worst case) so a
    regression fails the test instead of hanging the suite — no wall-clock
    behaviour is being asserted here, only that the worker ran.
    """
    for _ in range(400):
        job = jobs.get(job_id)
        if job.status != "running":
            return job
        time.sleep(0.005)
    pytest.fail("background job never finished")


def test_a_completed_job_carries_its_return_value(jobs_registry):
    job = _await_job(jobs_registry, jobs_registry.submit(lambda: "payload"))
    assert (job.status, job.result, job.error) == ("done", "payload", None)
    assert job.finished_at is not None


def test_a_raising_job_becomes_error_state_not_an_unhandled_exception(jobs_registry):
    """The pool thread has nobody to propagate to; the failure has to become
    job state or it is lost entirely."""
    def boom():
        raise RuntimeError("nope")

    job = _await_job(jobs_registry, jobs_registry.submit(boom))
    assert (job.status, job.result) == ("error", None)
    assert job.error == "RuntimeError: nope"


def test_get_returns_a_snapshot_so_a_poller_never_sees_a_half_written_job(jobs_registry):
    job_id = jobs_registry.submit(lambda: "x")
    _await_job(jobs_registry, job_id)
    first, second = jobs_registry.get(job_id), jobs_registry.get(job_id)
    assert first is not second and first == second


def test_an_unknown_job_id_is_none_so_the_route_can_answer_404(jobs_registry):
    assert jobs_registry.get("does-not-exist") is None


def test_summarize_never_ships_file_bytes_in_a_status_payload():
    """A collect-mode report holds the whole fleet in memory; serializing it
    into a JSON status response would be catastrophic. Only counts and failure
    metadata come out."""
    report = direct.DownloadReport(
        files=[direct.FileResult("h", "/a", b"secret-bytes")],
        failures=[direct.HostFailure("h", "error_perm: 550", "/b")],
    )
    summary = web_jobs.summarize(report)
    assert summary == {
        "ok": 1,
        "ng": 1,
        "failure_ratio": 0.5,
        "failures": [{"host": "h", "error": "error_perm: 550", "remote_path": "/b"}],
    }
    assert b"secret-bytes" not in repr(summary).encode()


def test_summarize_adds_total_paths_only_for_a_listing_report():
    summary = web_jobs.summarize(
        direct.ListingReport(listings=[direct.HostListing("h", ["/a", "/b"])], failures=[])
    )
    assert summary["total_paths"] == 2


def test_summarize_declines_anything_that_is_not_a_fleet_report():
    """Duck-typed on ``failures``; a custom result must be serialized by its
    own owner rather than silently half-rendered here."""
    assert web_jobs.summarize("a string") is None
    assert web_jobs.summarize(None) is None


def test_job_to_dict_reports_a_non_report_result_as_null(jobs_registry):
    """Consequence of the rule above: a job whose work returned something
    ``summarize`` does not understand still reports ``status: done`` but a
    ``result`` of ``None``. Pinned because it reads like a bug and is the
    documented trade-off."""
    job = _await_job(jobs_registry, jobs_registry.submit(lambda: {"custom": 1}))
    payload = web_jobs.job_to_dict(job)
    assert payload["status"] == "done" and payload["result"] is None
    assert payload["job_id"] == job.id


def test_finished_jobs_are_evicted_once_the_registry_outgrows_keep_last():
    """A long-lived server would otherwise accumulate every completed job
    forever. Eviction is oldest-finished-first and never touches a running
    job.

    Constructed inline rather than via the fixture because ``keep_last`` is
    the very thing under test.
    """
    jobs = web_jobs.BackgroundJobs(keep_last=3)
    try:
        ids = [jobs.submit(lambda: "x") for _ in range(3)]
        for job_id in ids:
            _await_job(jobs, job_id)
        newest = jobs.submit(lambda: "x")
        _await_job(jobs, newest)
        assert jobs.get(ids[0]) is None
        assert jobs.get(newest) is not None
    finally:
        jobs.shutdown()


# ── import-time side effects ─────────────────────────────────────────────────


def test_the_direct_downloader_imports_without_requests_or_flask():
    """Import-time side effects, pinned deliberately.

    No package in ``ftp_handler`` constructs a client at import — but the
    *dependencies* an import drags in are load-bearing: a collector worker
    that has neither ``requests`` nor ``flask`` must still be able to use
    ``core`` and ``direct_downloader``, which is what the package docstring
    promises. The proxy client is the deliberate exception (next test).

    Run in a subprocess because this module imports the proxy at the top, so
    ``sys.modules`` is already populated in-process.
    """
    probe = (
        "import sys; import ftp_handler.direct_downloader; "
        "print(any(m in sys.modules for m in ('requests', 'flask')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=_REPO_ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "False"


def test_the_proxy_client_eagerly_imports_requests_but_never_flask():
    """``ftp_handler.proxy`` re-exports only the CLIENT half, so importing it
    needs ``requests`` (a hard dependency of the firewalled box) but must not
    drag in ``flask`` — the server half lives behind an explicit
    ``ftp_handler.proxy.flask_proxy`` import for exactly that reason."""
    probe = (
        "import sys; import ftp_handler.proxy; "
        "print('requests' in sys.modules, 'flask' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=_REPO_ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "True False"
