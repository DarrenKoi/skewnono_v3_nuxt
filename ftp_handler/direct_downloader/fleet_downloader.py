"""In-memory concurrent FTP fleet downloader.

Pulls files from many equipment FTP servers at once and hands the raw bytes
back to the caller. Async fan-out is an implementation detail: callers use the
plain synchronous ``download()`` method (or the ``download_fleet()`` helper) and
never touch a coroutine, so this drops into a non-async script or an Airflow
``PythonOperator`` unchanged.

Why threads, not aioftp:
  Each host is one short-lived FTP session that is almost entirely socket I/O,
  and Python releases the GIL during socket I/O. So a ``ThreadPoolExecutor``
  over blocking ``ftplib`` fans out N hosts concurrently with zero extra
  packages — no aioftp to pip-install into an Airflow venv, no version drift
  between your laptop and the worker. There is no event loop: ``download`` and
  ``list_dirs`` are plain synchronous calls, safe to invoke from a script, an
  Airflow task, or a Flask request handler / scheduler thread — even one that
  already runs its own asyncio loop.

Two failure modes this is built to survive:
  - One unreachable / black-holed host. ``connect_timeout`` bounds every
    blocking socket op, ``host_timeout`` backstops a whole pathological host,
    and per-host errors are isolated (gather never aborts siblings). A dead
    host is reported in ``failures``; the rest still download.
  - Resource exhaustion under fan-out. ``max_concurrency`` caps simultaneous
    connections (and, because files are held in memory, peak RAM ~=
    concurrency x file size). Without this cap, ~200 simultaneous connections
    blow past the worker's open-file limit and downloads silently fail.

Memory:
  ``download(specs)`` collects every file's bytes into the returned report —
  peak RAM is the SUM of all files. For a large fleet, pass an ``on_file``
  callback instead: each file is handed to the callback the moment it lands and
  then dropped, so peak RAM stays bounded by concurrency x file size. The
  callback runs inside the per-host worker thread, so multiple callbacks run
  concurrently — use thread-safe clients or construct them inside the callback.
"""

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import contextmanager
from dataclasses import dataclass, field
from ftplib import FTP, all_errors
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Iterator, Protocol, runtime_checkable

# The shared NLST normalizer lives in core so both downloaders behave
# identically. Relative import in-package; bare fallback when copied out flat
# beside the proxy pair (the file then sits next to listing.py).
try:
    from ..core.listing import _normalize_listing
except ImportError:  # copied out flat, imported by bare name
    from listing import _normalize_listing

# Invoked once per successfully downloaded file: (host, remote_path, data).
OnFile = Callable[[str, str, bytes], None]

# Turn one downloaded file's raw bytes into the value to store: a live Python
# object for pickle, a pandas DataFrame for parquet. This is the processing
# seam — parse / reshape the bytes here before they're written to MinIO.
ToObject = Callable[[str, str, bytes], object]
# Build the MinIO object key from (host, remote_path).
KeyFn = Callable[[str, str], str]


@dataclass(slots=True)
class ListDir:
    """Discover files to fetch by listing a remote directory.

    ``remote_dir`` is listed (NLST); entries whose basename matches ``pattern``
    (an fnmatch glob, e.g. ``"*.dat"``) are fetched. ``pattern=None`` fetches
    every entry. Use this for the timestamped measurement files whose names you
    can't know ahead of time.
    """

    remote_dir: str
    pattern: str | None = None


@dataclass(slots=True)
class HostSpec:
    """One equipment host and everything to pull from it in a run.

    ``files``    fixed remote paths fetched directly (RETR), no listing — for
                 the append-only logs at known paths.
    ``listings`` directories listed then filtered, one RETR per match — for the
                 timestamped measurement files.

    Both run over a single FTP connection that is opened once, reused for the
    listing and every RETR, then closed.

    ``user``/``password`` override the downloader's credentials for this host
    alone; ``None`` (the default) means "use the downloader's". One fleet is not
    always one account -- a run spanning two vendors' tools spans two logins,
    and the credential is a property of the host, not of the run. Leave them
    unset when the fleet shares an account, which stays the common case and
    needs no change at any call site.
    """

    host: str
    files: list[str] = field(default_factory=list)
    listings: list[ListDir] = field(default_factory=list)
    user: str | None = None
    password: str | None = None


@dataclass(slots=True)
class FileResult:
    """A successfully downloaded file. ``data`` is empty when an ``on_file``
    callback consumed the bytes (streaming mode) — the entry then only records
    that the file succeeded."""

    host: str
    remote_path: str
    data: bytes


@dataclass(slots=True)
class UploadFile:
    """One file to push to a host: the remote destination path and its bytes.

    The mirror of a download's ``FileResult`` for the write direction — here the
    caller supplies ``data`` (a download returns it). ``remote_path`` is STOR'd
    verbatim and overwrites any existing file at that path.
    """

    remote_path: str
    data: bytes


@dataclass(slots=True)
class UploadSpec:
    """One equipment host and the files to push to it in a run.

    The upload counterpart to ``HostSpec``: ``files`` are uploaded over a single
    FTP connection that is opened once, reused for every STOR, then closed.
    There is no listing analogue — upload destinations are always explicit.

    ``user``/``password`` are the per-host override, same contract as
    ``HostSpec``'s. Kept symmetric on purpose: a fleet that needs two accounts
    to read needs the same two to write.
    """

    host: str
    files: list[UploadFile] = field(default_factory=list)
    user: str | None = None
    password: str | None = None


@dataclass(slots=True)
class UploadResult:
    """A successfully uploaded file. Unlike ``FileResult`` it carries no bytes —
    the caller already holds the source data; this only records that the STOR
    landed."""

    host: str
    remote_path: str


@dataclass(slots=True)
class HostFailure:
    """A failed download. ``remote_path`` is ``None`` when the failure happened
    before any specific file (connect / login / directory listing)."""

    host: str
    error: str
    remote_path: str | None = None


@dataclass(slots=True)
class DownloadReport:
    files: list[FileResult]
    failures: list[HostFailure]

    @property
    def ok(self) -> int:
        return len(self.files)

    @property
    def ng(self) -> int:
        return len(self.failures)

    @property
    def failure_ratio(self) -> float:
        """Fraction of attempted units that failed, for threshold-based
        alerting. 0.0 when nothing was attempted."""
        total = self.ok + self.ng
        return self.ng / total if total else 0.0

    def grouped(self) -> dict[str, dict[str, bytes]]:
        """Collected files as one nested dict: ``{host: {remote_path: data}}``.

        Convenience for the "process everything after it's all in memory"
        workflow — iterate this single structure, parse/transform each file's
        bytes, then ship to OpenSearch. Empty when ``download`` ran with an
        ``on_file`` callback (the bytes were streamed out, not retained)."""
        out: dict[str, dict[str, bytes]] = {}
        for f in self.files:
            out.setdefault(f.host, {})[f.remote_path] = f.data
        return out


@dataclass(slots=True)
class UploadReport:
    """Outcome of a fleet upload run, mirroring ``DownloadReport``'s shape so
    the same ``ok`` / ``ng`` / ``failure_ratio`` threshold-alerting code works
    unchanged for the write direction."""

    results: list[UploadResult]
    failures: list[HostFailure]

    @property
    def ok(self) -> int:
        return len(self.results)

    @property
    def ng(self) -> int:
        return len(self.failures)

    @property
    def failure_ratio(self) -> float:
        """Fraction of attempted units that failed, for threshold-based
        alerting. 0.0 when nothing was attempted."""
        total = self.ok + self.ng
        return self.ng / total if total else 0.0

    def grouped(self) -> dict[str, list[str]]:
        """Uploaded paths as ``{host: [remote_path, ...]}``."""
        out: dict[str, list[str]] = {}
        for r in self.results:
            out.setdefault(r.host, []).append(r.remote_path)
        return out


@dataclass(slots=True)
class HostListing:
    """The remote paths discovered on one host. ``paths`` may be empty if the
    host connected but its directories were empty or all listings failed (the
    failures are recorded separately on the report)."""

    host: str
    paths: list[str]


@dataclass(slots=True)
class ListingReport:
    """Result of listing the fleet's directories without fetching anything.

    This is the "look before you download" step for a large fleet: list the
    measurement dirs across all ~300 hosts, decide what's worth pulling, then
    feed the chosen paths back into ``download`` via ``to_specs()``.
    """

    listings: list[HostListing]
    failures: list[HostFailure]

    @property
    def ok(self) -> int:
        return len(self.listings)

    @property
    def ng(self) -> int:
        return len(self.failures)

    @property
    def total_paths(self) -> int:
        return sum(len(l.paths) for l in self.listings)

    def grouped(self) -> dict[str, list[str]]:
        """Discovered paths as ``{host: [remote_path, ...]}``."""
        return {l.host: l.paths for l in self.listings}

    def to_specs(self) -> list["HostSpec"]:
        """Turn discovered paths into download-ready ``HostSpec`` objects.

        Each host's paths become fixed ``files`` (no re-listing on download).
        Hosts that discovered nothing are dropped. This closes the loop:
        ``downloader.download(report.to_specs())``.
        """
        return [
            HostSpec(host=l.host, files=list(l.paths)) for l in self.listings if l.paths
        ]


@dataclass(slots=True)
class FileSize:
    """The size in bytes of one remote file, as reported by the server's ``SIZE``
    command — no bytes were transferred to learn it."""

    host: str
    remote_path: str
    size: int


@dataclass(slots=True)
class SizingReport:
    """Result of probing the fleet's file sizes without downloading anything.

    The RAM-budget counterpart to ``ListingReport``: where ``list_dirs`` answers
    "what files are out there", this answers "how many bytes would they cost in
    memory". ``total_bytes`` is the sum the collect-mode ``download`` would hold
    at once; divide a per-host or per-batch slice of it to decide how to chunk a
    large run. A file whose ``SIZE`` failed or was unsupported lands in
    ``failures`` (never silently counted as zero), so ``total_bytes`` only sums
    files that were actually measured.
    """

    files: list[FileSize]
    failures: list[HostFailure]

    @property
    def ok(self) -> int:
        return len(self.files)

    @property
    def ng(self) -> int:
        return len(self.failures)

    @property
    def failure_ratio(self) -> float:
        """Fraction of attempted units that failed, for threshold-based
        alerting. 0.0 when nothing was attempted."""
        total = self.ok + self.ng
        return self.ng / total if total else 0.0

    @property
    def total_bytes(self) -> int:
        """Sum of every measured file's size — the peak RAM a collect-mode
        ``download`` of this exact set would hold at once."""
        return sum(f.size for f in self.files)

    def by_host(self) -> dict[str, int]:
        """Measured bytes per host: ``{host: total_bytes}``. Use it to spot the
        heavy hosts and split a fleet run into RAM-bounded batches."""
        out: dict[str, int] = {}
        for f in self.files:
            out[f.host] = out.get(f.host, 0) + f.size
        return out

    def to_specs(self) -> list["HostSpec"]:
        """Turn measured paths into download-ready ``HostSpec`` objects.

        Mirrors ``ListingReport.to_specs`` — each host's measured paths become
        fixed ``files`` (no re-listing on download), so you download exactly the
        set you just sized: ``downloader.download(report.to_specs())``.
        """
        by_host: dict[str, list[str]] = {}
        for f in self.files:
            by_host.setdefault(f.host, []).append(f.remote_path)
        return [HostSpec(host=host, files=paths) for host, paths in by_host.items()]


@runtime_checkable
class FleetTransport(Protocol):
    """The interchange seam between the two FTP deployment paths.

    Two adapters satisfy it: the direct ``FtpFleetDownloader`` (this module,
    real FTP) and the HTTP-proxy ``FtpFleetDownloader`` (``proxy.proxy_downloader``,
    same surface over HTTP). A call site swaps one import line between them and
    nothing else changes — that swap is the whole point of the seam.

    All four fleet operations are on the seam: ``list_dirs`` (the
    look-before-you-download listing pass), ``size_dirs`` (the
    estimate-RAM-before-you-pull sizing pass), ``download``, and ``upload`` (the
    write direction). The conformance test guards that both adapters keep
    matching every method, so neither path drifts.
    """

    def download(
        self, specs: list[HostSpec], *, on_file: OnFile | None = None
    ) -> DownloadReport: ...

    def list_dirs(self, specs: list[HostSpec]) -> ListingReport: ...

    def size_dirs(self, specs: list[HostSpec]) -> SizingReport: ...

    def upload(self, specs: list[UploadSpec]) -> UploadReport: ...


class _FileGate:
    """A one-way gate around one host's ``on_file`` callback.

    ``shutdown(wait=False)`` cannot kill a worker thread, so a host abandoned at
    ``host_timeout`` keeps running — and, in streaming mode, keeps calling back
    into caller state that ``download`` has already reported as failed. A caller
    that reasonably assumes "download returned, so my callback is done" then
    races its own results: mutating the dict it is iterating, or counting the
    same file twice.

    So each host gets a gate. ``download`` closes it when that host is abandoned
    and closes every gate before returning. ``close`` takes the same lock
    ``__call__`` holds, so it cannot return while a callback is mid-flight:
    **once ``download`` returns, no ``on_file`` is running and none will start.**

    That lock is deliberate and it has a cost: ``close`` waits out a callback
    that is already running, so a slow sink (a stalled MinIO PUT) delays the
    abandonment by up to one callback. The cheaper design — a bare flag, no lock
    — only promises that no callback *starts* after close, which is not the
    promise the caller needs: a callback already inside the flag check still
    lands in the middle of the caller's cleanup, which is the exact corruption
    this exists to prevent. Bound the wait with a timeout inside your sink if
    that matters; a partial guarantee here would be worse than none, because it
    reads like a guarantee.

    Collect mode (``on_file=None``) needs no gate — an abandoned worker there
    fills a ``files`` list that is discarded, touching nothing the caller holds.
    """

    __slots__ = ("_on_file", "_lock", "_closed")

    def __init__(self, on_file: OnFile) -> None:
        self._on_file = on_file
        self._lock = threading.Lock()
        self._closed = False

    @property
    def closed(self) -> bool:
        # Read without the lock: the worker loop uses this only to stop early,
        # and the gate itself is what makes the guarantee. Racing it costs at
        # most one extra file fetched, never an escaped callback.
        return self._closed

    def __call__(self, host: str, remote_path: str, data: bytes) -> None:
        with self._lock:
            if self._closed:
                return
            self._on_file(host, remote_path, data)

    def close(self) -> None:
        with self._lock:
            self._closed = True


class FtpFleetDownloader:
    """Reusable, synchronous, concurrent FTP downloader for a host fleet.

    Construct once with shared credentials and tuning, then call ``download``
    (sync) as many times as you like::

        dl = FtpFleetDownloader(user="ftpuser", password="ftppass")
        report = dl.download([
            HostSpec("10.0.0.1", files=["/HITACHI/SYSFILE/LOG_RECIPE_EXE.log"]),
            HostSpec("10.0.0.2", listings=[ListDir("/MEAS", "*.dat")]),
        ])
        print(report.ok, report.ng)
        for f in report.files:
            handle(f.host, f.remote_path, f.data)
    """

    def __init__(
        self,
        *,
        user: str,
        password: str,
        port: int = 21,
        max_concurrency: int = 48,
        connect_timeout: float = 8.0,
        host_timeout: float = 60.0,
        passive: bool = True,
    ) -> None:
        # connect_timeout is the connection-wait knob: it bounds each blocking
        # socket op (connect, login, RETR). 8s means an offline/black-holed tool
        # is abandoned in 8s instead of hanging a slot — essential at hundreds
        # of hosts. host_timeout backstops a whole host (connect + listing + all
        # its files); it does NOT govern dead-host detection (connect_timeout
        # does), so keep it comfortably above connect_timeout x files-per-host.
        # It only fires for a host that connects then stalls mid-transfer.
        # passive=True is ftplib's default and the right choice behind NAT, but
        # is exposed because a worker on a different subnet than your laptop can
        # need the opposite — the classic second "works locally, not on the
        # server" gotcha after concurrency.
        self.user = user
        self.password = password
        self.port = port
        self.max_concurrency = max_concurrency
        self.connect_timeout = connect_timeout
        self.host_timeout = host_timeout
        self.passive = passive

    # ── public sync API ─────────────────────────────────────────────────────
    def download(
        self,
        specs: list[HostSpec],
        *,
        on_file: OnFile | None = None,
    ) -> DownloadReport:
        """Download every spec concurrently and return a report.

        Synchronous and event-loop-free — the fan-out runs on a plain thread
        pool, so this is safe to call from anywhere: a script, an Airflow task,
        a Flask request handler, or a scheduler thread, including one that
        already runs its own asyncio loop. Pass ``on_file`` to stream-process
        each file and keep RAM bounded; omit it to collect all bytes into the
        report.

        ``on_file`` never fires after this returns. A host abandoned at
        ``host_timeout`` leaves a thread running that no API can kill, so each
        host's callback goes through a ``_FileGate`` that is closed when that
        host is abandoned and, unconditionally, before returning — see
        ``_FileGate`` for why a caller cannot be left racing its own results.
        """
        gates = [_FileGate(on_file) for _ in specs] if on_file is not None else None
        try:
            files, failures = self._run_fleet(
                specs,
                lambda spec, idx: self._host_worker(
                    spec, gates[idx] if gates is not None else None
                ),
                on_abandon=(lambda idx: gates[idx].close()) if gates is not None else None,
            )
        finally:
            for gate in gates or ():
                gate.close()
        return DownloadReport(files=files, failures=failures)

    def list_dirs(self, specs: list[HostSpec]) -> ListingReport:
        """List each host's ``listings`` directories concurrently — no fetching.

        The "look before you download" pass for a large fleet: enumerate the
        measurement dirs across all hosts, inspect ``report.grouped()`` /
        ``report.total_paths`` to decide what's worth pulling, then download the
        survivors with ``downloader.download(report.to_specs())``. Only
        ``spec.listings`` is consulted; ``spec.files`` is ignored (you already
        know those paths — list to *discover* unknown ones).

        Same concurrency, timeout, per-host failure isolation, and
        event-loop-free safety as ``download``.
        """
        listings, failures = self._run_fleet(
            specs, lambda spec, _idx: self._list_worker(spec)
        )
        return ListingReport(listings=listings, failures=failures)

    def size_dirs(self, specs: list[HostSpec]) -> SizingReport:
        """Measure each spec's files concurrently via ``SIZE`` — no fetching.

        The "estimate RAM before you pull" pass: resolve every host's paths
        (fixed ``files`` plus whatever its ``listings`` discover, exactly as
        ``download`` would), then ask the server each file's size with the FTP
        ``SIZE`` command instead of RETR'ing the bytes. ``report.total_bytes`` is
        then the peak RAM a collect-mode ``download`` of the same set would hold;
        ``report.by_host()`` shows where the weight sits so you can chunk a large
        run. Feed the measured set straight into ``download`` with
        ``report.to_specs()``.

        Same concurrency, per-host ``host_timeout`` backstop, per-host AND
        per-file failure isolation, and event-loop-free safety as ``download``.
        A file whose ``SIZE`` fails or is unsupported is recorded in
        ``failures``, never counted as zero bytes.
        """
        sizes, failures = self._run_fleet(
            specs, lambda spec, _idx: self._size_worker(spec)
        )
        return SizingReport(files=sizes, failures=failures)

    def upload(self, specs: list[UploadSpec]) -> UploadReport:
        """Push every spec's files to its host concurrently and return a report.

        The write-direction counterpart to ``download``: each host's files are
        STOR'd over one reused connection, overwriting any file already at the
        destination path. Same concurrency cap, per-host ``host_timeout``
        backstop, per-host AND per-file failure isolation, and event-loop-free
        safety as ``download`` — they share the ``_run_fleet`` engine.

        Bytes live in memory here (``UploadSpec.files`` carries them), so peak
        RAM is the sum of all queued upload data; for a large push, send it in
        chunks of specs rather than one giant call.
        """
        results, failures = self._run_fleet(
            specs, lambda spec, _idx: self._upload_worker(spec)
        )
        return UploadReport(results=results, failures=failures)

    # ── concurrent orchestration (private) ──────────────────────────────────
    @contextmanager
    def _session(self, spec: "HostSpec | UploadSpec") -> Iterator[FTP]:
        """One connected, logged-in FTP session for ``spec.host``, closed on exit.

        Shared open/login/passive setup for both the download and listing
        workers, so a host is always reached the same way.

        Takes the whole spec rather than a bare host string because the
        credential now travels with the host: ``spec.user``/``spec.password``
        win when set, and fall back to the downloader's own pair otherwise.
        The fallback is what keeps every existing single-account call site
        working untouched.
        """
        with FTP(timeout=self.connect_timeout) as ftp:
            ftp.connect(host=spec.host, port=self.port, timeout=self.connect_timeout)
            ftp.login(
                user=spec.user or self.user,
                passwd=spec.password or self.password,
            )
            ftp.set_pasv(self.passive)
            yield ftp

    def _run_fleet(
        self,
        specs: list[HostSpec],
        worker: "Callable[[HostSpec, int], tuple[list, list[HostFailure]]]",
        *,
        on_abandon: "Callable[[int], None] | None" = None,
    ) -> tuple[list, list[HostFailure]]:
        """Fan ``worker`` out across ``specs`` on a thread pool and aggregate.

        The shared engine behind ``download`` and ``list_dirs``. A
        ``ThreadPoolExecutor`` sized to ``max_concurrency`` caps simultaneous
        connections; every host is backstopped by ``host_timeout``; a raise from
        one host never aborts its siblings (partial success is the normal case).
        ``worker`` is called as ``worker(spec, idx)``, runs blocking in a pool
        thread, and returns ``(ok_items, failures)``; what's in ``ok_items`` is
        the caller's business (``FileResult`` or ``HostListing``). ``idx`` is the
        spec's position, so a caller can key per-host state (``download`` keys
        its ``_FileGate``s by it) without matching on ``spec.host`` — several
        specs may name the SAME host to fan one host's files over n connections.

        ``on_abandon(idx)`` fires when that spec is given up on at
        ``host_timeout``. Its thread is still running and cannot be killed, so
        this is the caller's only chance to stop trusting it.

        ``host_timeout`` is measured from when each host's worker *starts*
        running, not from submit — so a host queued behind a full pool isn't
        charged for its wait, and a host that has started can't gain extra budget
        by finishing while we happen to be blocked on an earlier future.

        No asyncio event loop is involved, so this is safe even when called from
        inside an already-running loop (e.g. an async web worker).
        """
        # Pool sized to max_concurrency so at most that many connections are
        # open at once. shutdown(wait=False): a host that connects then stalls
        # mid-transfer can't be force-cancelled — we abandon its result after
        # host_timeout rather than block teardown, and connect_timeout bounds
        # each socket op so the abandoned thread drains on its own shortly after.
        pool = ThreadPoolExecutor(
            max_workers=self.max_concurrency, thread_name_prefix="ftp-fleet"
        )
        started: dict[int, float] = {}
        started_lock = threading.Lock()

        def _timed(idx: int, spec: HostSpec):
            # Stamp the start time before any blocking work so host_timeout is
            # measured from here, not from when the future was submitted.
            with started_lock:
                started[idx] = time.monotonic()
            return worker(spec, idx)

        ok: list = []
        failures: list[HostFailure] = []
        try:
            futures = [
                (pool.submit(_timed, idx, spec), idx, spec)
                for idx, spec in enumerate(specs)
            ]
            # Iterate in submission order so failures stay in spec order.
            for future, idx, spec in futures:
                # Wait for this host's worker to actually begin (it may be queued
                # behind a full pool), then bound it by what remains of its budget.
                while True:
                    with started_lock:
                        start = started.get(idx)
                    if start is not None or future.done():
                        break
                    time.sleep(0.01)
                remaining = (
                    None
                    if start is None
                    else max(0.0, self.host_timeout - (time.monotonic() - start))
                )
                try:
                    host_ok, host_failures = future.result(timeout=remaining)
                except FutureTimeoutError:
                    # The thread survives this; only the caller's trust in it
                    # ends here. Cut it off BEFORE recording the failure, so a
                    # host reported as failed can no longer emit successes.
                    if on_abandon is not None:
                        on_abandon(idx)
                    failures.append(
                        HostFailure(
                            host=spec.host,
                            error=f"TimeoutError: exceeded host_timeout={self.host_timeout}s",
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - one host never sinks the fleet
                    failures.append(
                        HostFailure(
                            host=spec.host, error=f"{type(exc).__name__}: {exc}"
                        )
                    )
                else:
                    ok.extend(host_ok)
                    failures.extend(host_failures)
        finally:
            pool.shutdown(wait=False)
        return ok, failures

    # ── blocking per-host work (runs in a thread) ───────────────────────────
    def _host_worker(
        self,
        spec: HostSpec,
        on_file: OnFile | None,
    ) -> tuple[list[FileResult], list[HostFailure]]:
        files: list[FileResult] = []
        failures: list[HostFailure] = []
        try:
            with self._session(spec) as ftp:
                for remote_path in self._resolve_paths(ftp, spec, failures):
                    # Abandoned at host_timeout: stop pulling. The gate already
                    # blocks the callback, but leaving the loop also hands the
                    # tool its FTP connection back instead of holding it for
                    # files whose bytes nobody will look at.
                    if getattr(on_file, "closed", False):
                        break
                    self._fetch_one(ftp, spec.host, remote_path, on_file, files, failures)
        except all_errors as exc:
            # connect / login / quit failed — no file got a chance.
            failures.append(
                HostFailure(host=spec.host, error=f"{type(exc).__name__}: {exc}")
            )
        return files, failures

    def _list_worker(
        self,
        spec: HostSpec,
    ) -> tuple[list[HostListing], list[HostFailure]]:
        # Discovery-only counterpart to _host_worker: connect once, enumerate
        # each listing dir, never RETR. A host that connects always yields a
        # HostListing (possibly empty); a listing that fails to enumerate is
        # recorded but doesn't sink the host's other listings.
        paths: list[str] = []
        failures: list[HostFailure] = []
        try:
            with self._session(spec) as ftp:
                for listing in spec.listings:
                    try:
                        names = ftp.nlst(listing.remote_dir)
                    except all_errors as exc:
                        failures.append(
                            HostFailure(
                                host=spec.host,
                                error=f"list {listing.remote_dir} failed: {type(exc).__name__}: {exc}",
                                remote_path=listing.remote_dir,
                            )
                        )
                        continue
                    paths.extend(
                        _normalize_listing(names, listing.remote_dir, listing.pattern)
                    )
        except all_errors as exc:
            # connect / login failed — host discovered nothing.
            failures.append(
                HostFailure(host=spec.host, error=f"{type(exc).__name__}: {exc}")
            )
            return [], failures
        return [HostListing(host=spec.host, paths=paths)], failures

    def _size_worker(
        self,
        spec: HostSpec,
    ) -> tuple[list[FileSize], list[HostFailure]]:
        # Sizing counterpart to _host_worker: connect once, resolve the same
        # paths download would, then SIZE each instead of RETR. A connect/login
        # failure sinks the whole host; a single SIZE failure is isolated to that
        # file. _resolve_paths records any listing-expansion failures into the
        # same `failures` list.
        sizes: list[FileSize] = []
        failures: list[HostFailure] = []
        try:
            with self._session(spec) as ftp:
                # SIZE is only reliable in binary mode: RFC 3659 lets a server
                # report a different (line-ending-adjusted) count for an
                # ASCII-mode SIZE than the bytes a binary RETR transfers, so we
                # switch to TYPE I first to size what download would actually pull.
                ftp.voidcmd("TYPE I")
                for remote_path in self._resolve_paths(ftp, spec, failures):
                    try:
                        size = ftp.size(remote_path)
                    except all_errors as exc:
                        failures.append(
                            HostFailure(
                                host=spec.host,
                                error=f"{type(exc).__name__}: {exc}",
                                remote_path=remote_path,
                            )
                        )
                        continue
                    if size is None:
                        # ftplib returns None when the server has no SIZE support.
                        failures.append(
                            HostFailure(
                                host=spec.host,
                                error="SIZE unsupported by server",
                                remote_path=remote_path,
                            )
                        )
                        continue
                    sizes.append(
                        FileSize(host=spec.host, remote_path=remote_path, size=size)
                    )
        except all_errors as exc:
            # connect / login failed — host measured nothing.
            failures.append(
                HostFailure(host=spec.host, error=f"{type(exc).__name__}: {exc}")
            )
        return sizes, failures

    def _upload_worker(
        self,
        spec: "UploadSpec",
    ) -> tuple[list[UploadResult], list[HostFailure]]:
        # Write-direction counterpart to _host_worker: connect once, STOR each
        # file. A connect/login failure sinks the whole host (no file got a
        # chance); a single STOR failure is isolated to that file and never
        # aborts the host's remaining uploads.
        results: list[UploadResult] = []
        failures: list[HostFailure] = []
        try:
            with self._session(spec) as ftp:
                for item in spec.files:
                    try:
                        ftp.storbinary(f"STOR {item.remote_path}", BytesIO(item.data))
                    except all_errors as exc:
                        failures.append(
                            HostFailure(
                                host=spec.host,
                                error=f"{type(exc).__name__}: {exc}",
                                remote_path=item.remote_path,
                            )
                        )
                    else:
                        results.append(
                            UploadResult(host=spec.host, remote_path=item.remote_path)
                        )
        except all_errors as exc:
            # connect / login failed — no file got a chance.
            failures.append(
                HostFailure(host=spec.host, error=f"{type(exc).__name__}: {exc}")
            )
        return results, failures

    def _resolve_paths(
        self,
        ftp: FTP,
        spec: HostSpec,
        failures: list[HostFailure],
    ) -> list[str]:
        # Fixed paths first, then expand each listing. A listing that fails to
        # enumerate is recorded but doesn't sink the fixed-path fetches.
        paths = list(spec.files)
        for listing in spec.listings:
            try:
                names = ftp.nlst(listing.remote_dir)
            except all_errors as exc:
                failures.append(
                    HostFailure(
                        host=spec.host,
                        error=f"list {listing.remote_dir} failed: {type(exc).__name__}: {exc}",
                        remote_path=listing.remote_dir,
                    )
                )
                continue
            paths.extend(_normalize_listing(names, listing.remote_dir, listing.pattern))
        return paths

    def _fetch_one(
        self,
        ftp: FTP,
        host: str,
        remote_path: str,
        on_file: OnFile | None,
        files: list[FileResult],
        failures: list[HostFailure],
    ) -> None:
        # Broad except: covers ftplib errors AND anything an on_file callback
        # raises (e.g. a MinIO/OpenSearch write), so a per-file failure is
        # isolated to that file and reported, never propagated.
        try:
            buf = BytesIO()
            ftp.retrbinary(f"RETR {remote_path}", buf.write)
            data = buf.getvalue()
            if on_file is not None:
                on_file(host, remote_path, data)
                # Drop the bytes once consumed — streaming mode keeps RAM flat.
                files.append(FileResult(host=host, remote_path=remote_path, data=b""))
            else:
                files.append(FileResult(host=host, remote_path=remote_path, data=data))
        except Exception as exc:  # noqa: BLE001 - intentional per-file isolation
            failures.append(
                HostFailure(
                    host=host,
                    error=f"{type(exc).__name__}: {exc}",
                    remote_path=remote_path,
                )
            )


def specs_from_hosts(
    hosts: list[str],
    *,
    files: list[str] | None = None,
    listings: list[ListDir] | None = None,
) -> list[HostSpec]:
    """Wrap a plain list of host IPs into ``HostSpec`` objects.

    The common case: every host shares the same fixed ``files`` and/or directory
    ``listings``. Each spec gets its own copy of the lists, so mutating one
    host's spec never bleeds into another's::

        specs = specs_from_hosts(ips, listings=[ListDir("/MEAS", "*.dat")])
        report = FtpFleetDownloader(user=u, password=p).list_dirs(specs)

    For per-host configuration that differs, build from JSON with
    ``collect.build_host_specs`` instead.
    """
    return [
        HostSpec(host=host, files=list(files or []), listings=list(listings or []))
        for host in hosts
    ]


def group_files_by_host(pairs: Iterable[tuple[str, str]]) -> list[HostSpec]:
    """Fold ``(host, remote_path)`` pairs into one ``HostSpec`` per host.

    The fan-in for the "I have a flat table of (IP, file-path) rows" case — a
    DataFrame, a CSV, a SQL result — where the same host recurs across many rows
    and each row names one fixed file to RETR. Rows are bucketed by host so each
    host opens a single reused FTP connection (not one per file); host order
    follows first appearance::

        # df_meas_hist has columns eqp_ip, class_name, idw_name, idp_name
        specs = group_files_by_host(
            (row.eqp_ip,
             f"/HITACHI/DEVICE/HD/{row.class_name}/data/{row.idw_name}/{row.idp_name}.idp")
            for row in df_meas_hist.itertuples(index=False)
        )
        report = FtpFleetDownloader(user="hitachi", password="hid").download(specs)

    Composing the remote path is the caller's one line — kept out of here because
    the layout differs per deployment. Accepts any iterable of pairs (not a
    DataFrame), so ``ftp_handler`` stays free of a pandas dependency. This is the
    different-files-per-host counterpart to ``specs_from_hosts`` (same files to
    every host).
    """
    by_host: dict[str, list[str]] = {}
    for host, remote_path in pairs:
        by_host.setdefault(host, []).append(remote_path)
    return [HostSpec(host=host, files=paths) for host, paths in by_host.items()]


def upload_specs_from_hosts(
    hosts: list[str],
    *,
    files: list[UploadFile],
) -> list[UploadSpec]:
    """Wrap a plain host list into ``UploadSpec`` objects sharing the same files.

    The common write case: push the SAME file(s) to every host (a recipe, a
    config drop). Each spec gets its own copy of the list so mutating one host's
    spec never bleeds into another's::

        specs = upload_specs_from_hosts(ips, files=[UploadFile("/INBOX/r.csv", data)])
        report = FtpFleetDownloader(user=u, password=p).upload(specs)
    """
    return [UploadSpec(host=host, files=list(files)) for host in hosts]


def upload_fleet(
    specs: list[UploadSpec],
    *,
    user: str,
    password: str,
    **kwargs: object,
) -> UploadReport:
    """One-call convenience wrapper around ``FtpFleetDownloader.upload``.

    ``upload_fleet(specs, user=..., password=...)`` pushes files across the
    fleet; extra keyword args (port, max_concurrency, connect_timeout,
    host_timeout, passive) are forwarded to the constructor.
    """
    downloader = FtpFleetDownloader(user=user, password=password, **kwargs)  # type: ignore[arg-type]
    return downloader.upload(specs)


def download_fleet(
    specs: list[HostSpec],
    *,
    user: str,
    password: str,
    on_file: OnFile | None = None,
    **kwargs: object,
) -> DownloadReport:
    """One-call convenience wrapper around ``FtpFleetDownloader``.

    For callers that just want a function: ``download_fleet(specs, user=...,
    password=...)``. Extra keyword args (port, max_concurrency, connect_timeout,
    host_timeout, passive) are forwarded to the constructor.
    """
    downloader = FtpFleetDownloader(user=user, password=password, **kwargs)  # type: ignore[arg-type]
    return downloader.download(specs, on_file=on_file)


def list_fleet(
    specs: list[HostSpec],
    *,
    user: str,
    password: str,
    **kwargs: object,
) -> ListingReport:
    """One-call convenience wrapper for the fleet-wide listing pass.

    ``list_fleet(specs, user=..., password=...)`` discovers paths across the
    fleet; extra keyword args (port, max_concurrency, connect_timeout,
    host_timeout, passive) are forwarded to the constructor.
    """
    downloader = FtpFleetDownloader(user=user, password=password, **kwargs)  # type: ignore[arg-type]
    return downloader.list_dirs(specs)


def size_fleet(
    specs: list[HostSpec],
    *,
    user: str,
    password: str,
    **kwargs: object,
) -> SizingReport:
    """One-call convenience wrapper for the fleet-wide sizing pass.

    ``size_fleet(specs, user=..., password=...)`` estimates the bytes each file
    would cost in memory across the fleet without downloading any; extra keyword
    args (port, max_concurrency, connect_timeout, host_timeout, passive) are
    forwarded to the constructor.
    """
    downloader = FtpFleetDownloader(user=user, password=password, **kwargs)  # type: ignore[arg-type]
    return downloader.size_dirs(specs)


# Characters illegal in a Windows path component (plus control chars). A Linux
# FTP server can produce filenames containing these; they'd crash a write on a
# Windows client, so each path component is sanitized before landing on disk.
_ILLEGAL_COMPONENT = re.compile(r'[<>:"|?*\x00-\x1f]')


def _safe_relative(remote_path: str) -> Path:
    """Map an FTP remote path to a safe RELATIVE local Path.

    Handles both POSIX and Windows-FTP separators, strips path-traversal and
    drive components, and sanitizes characters illegal on the local FS. The
    remote directory structure is otherwise preserved.
    """
    # A Windows-hosted FTP server may use backslashes; normalize to one form.
    normalized = remote_path.replace("\\", "/")
    parts: list[str] = []
    for raw in normalized.split("/"):
        if raw in ("", ".", ".."):
            continue  # drop leading slash, current- and parent-dir segments
        cleaned = _ILLEGAL_COMPONENT.sub("_", raw).rstrip(". ")  # Windows trims these
        if cleaned:
            parts.append(cleaned)
    return Path(*parts) if parts else Path("_unnamed")


def _keep_last_components(rel: Path, keep_last: int) -> Path:
    """Trim a relative path to its trailing ``keep_last`` components.

    Drops the leading (parent) components and keeps the tail — ``keep_last=1``
    reduces to the bare filename, ``keep_last=2`` keeps ``<parent>/<file>``.
    When ``keep_last`` meets or exceeds the path's depth the whole path is kept
    unchanged (nothing to drop). Used by ``save_to_dir`` to land files without
    mirroring the remote FTP parent directories.

        _keep_last_components(Path("IMAGES/20260615/sub/x.jpeg"), 2)  # -> sub/x.jpeg
    """
    parts = rel.parts
    if keep_last >= len(parts):
        return rel
    return Path(*parts[len(parts) - keep_last:])


def _strip_components(rel: Path, strip: int) -> Path:
    """Drop the leading ``strip`` path components, keeping the rest of the structure.

    tar's ``--strip-components``: removes the first N parent parts while
    preserving the remaining directory structure below them (the opposite end
    from ``_keep_last_components``, which keeps the tail). When ``strip`` meets
    or exceeds the depth only the filename remains — never an empty path.

        _strip_components(Path("IMAGES/20260615/sub/x.jpeg"), 2)  # -> sub/x.jpeg
    """
    parts = rel.parts
    if strip >= len(parts):
        return Path(parts[-1])
    return Path(*parts[strip:])


def local_target(
    dest_dir: str | Path,
    host: str,
    remote_path: str,
    *,
    keep_last: int | None = None,
    strip_components: int | None = None,
) -> Path:
    """Compute the exact local Path ``save_to_dir`` writes a file to.

    Pure and deterministic mirror of ``save_to_dir``'s mapping
    (``dest_dir/<host>/<remote path>``, with the same trimming and component
    sanitizing). Use it to recover local paths AFTER a download — the report
    carries ``host`` + ``remote_path`` but not the local path, so map over
    ``report.files`` with the same args you passed to ``save_to_dir``:

        report = dl.download(specs, on_file=save_to_dir(dest, strip_components=2))
        paths = [local_target(dest, f.host, f.remote_path, strip_components=2)
                 for f in report.files]

    ``strip_components`` drops the first N parent parts (front), ``keep_last``
    keeps the last N (back). When both are given, ``strip_components`` is applied
    first, then ``keep_last``.
    """
    rel = _safe_relative(remote_path)
    if strip_components is not None:
        rel = _strip_components(rel, strip_components)
    if keep_last is not None:
        rel = _keep_last_components(rel, keep_last)
    return Path(dest_dir) / _ILLEGAL_COMPONENT.sub("_", host) / rel


def save_to_dir(
    dest_dir: str | Path,
    *,
    keep_last: int | None = None,
    strip_components: int | None = None,
    then: OnFile | None = None,
) -> OnFile:
    """Build an ``on_file`` callback that writes each file to local disk.

    Lands files at ``dest_dir/<host>/<remote path>``, creating parent dirs.
    Works in both direct and proxy mode — the write happens wherever the
    callback runs (on the client PC in proxy mode). Because it runs per file,
    RAM stays bounded (streaming), unlike collecting then writing.

    Two ways to trim the remote path so you don't mirror the whole FTP tree
    (the ``<host>`` segment is always kept regardless):

      - ``keep_last`` keeps only the trailing N components (back): ``keep_last=1``
        flattens to just the filename, ``keep_last=2`` keeps ``<parent>/<file>``.
      - ``strip_components`` drops the first N parent parts (front), keeping the
        rest of the structure — like tar's ``--strip-components``. Better when
        the depth below the stripped prefix varies between files.

    ``None`` (default) for both preserves the full remote path. If both are
    given, ``strip_components`` is applied first, then ``keep_last``.

    ``then`` chains a second callback after the write (e.g. parse + index), so
    you can archive to disk AND process in one pass.

        dl.download(specs, on_file=save_to_dir(r"C:\\eqp_downloads"))
        dl.download(specs, on_file=save_to_dir(r"C:\\eqp_downloads", keep_last=2))
        dl.download(specs, on_file=save_to_dir(r"C:\\eqp_downloads", strip_components=2))
    """
    def on_file(host: str, remote_path: str, data: bytes) -> None:
        target = local_target(
            dest_dir,
            host,
            remote_path,
            keep_last=keep_last,
            strip_components=strip_components,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if then is not None:
            then(host, remote_path, data)

    return on_file


def image_sidecar_target(
    dest_dir: str | Path,
    remote_path: str,
    *,
    sidecar_name: str = "cond.txt",
) -> Path:
    """Local Path for the image + sidecar layout (image at root, sidecar in its folder).

    Equipment image folders pair each image with a sidecar file that lives in a
    subfolder named after the image (e.g. ``S09-01AP.jpeg`` alongside
    ``.S09-01AP.jpeg/cond.txt``). A uniform ``keep_last`` can't lay these out
    well — ``keep_last=1`` collapses every sidecar to the same ``cond.txt`` and
    they overwrite each other. This maps the two kinds ASYMMETRICALLY:

      - sidecar (basename == ``sidecar_name``) -> ``dest/<parent folder>/<name>``
        (keeps the per-image folder, so sidecars never collide)
      - anything else (the image)             -> ``dest/<name>`` (bare, at root)

        .../S09-01AP.jpeg            -> dest/S09-01AP.jpeg
        .../.S09-01AP.jpeg/cond.txt  -> dest/.S09-01AP.jpeg/cond.txt

    Pure mapping (no ``<host>`` segment, no I/O) — the counterpart to
    ``local_target`` for this layout, so you can recover paths from
    ``report.files`` the same way. Flat across hosts: if you fan out over
    multiple hosts whose image names overlap, prefix the dest per host.
    """
    p = PurePosixPath(remote_path)
    base = Path(dest_dir)
    if p.name == sidecar_name:
        return base / _safe_relative(f"{p.parent.name}/{p.name}")
    return base / _safe_relative(p.name)


def save_image_with_sidecar(
    dest_dir: str | Path,
    *,
    sidecar_name: str = "cond.txt",
    then: OnFile | None = None,
) -> OnFile:
    """Build an ``on_file`` that saves paired image + sidecar files in a flat layout.

    The image lands directly under ``dest_dir`` and its sidecar (a file named
    ``sidecar_name``, default ``cond.txt``) keeps the per-image subfolder it
    lived in on the server, so sidecars from different images don't collide.
    See ``image_sidecar_target`` for the exact mapping and why a uniform
    ``keep_last`` can't express it. ``then`` chains a second callback after the
    write, same as ``save_to_dir``.

        # spec carries both the image and its .../<sidecar folder>/cond.txt
        dl.download(specs, on_file=save_image_with_sidecar(r"C:\\eqp_images"))
    """
    def on_file(host: str, remote_path: str, data: bytes) -> None:
        target = image_sidecar_target(dest_dir, remote_path, sidecar_name=sidecar_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if then is not None:
            then(host, remote_path, data)

    return on_file


def _object_key(host: str, remote_path: str, suffix: str) -> str:
    """Default MinIO key for a downloaded file: ``<host>/<remote path><suffix>``.

    The remote path keeps its directory structure (slashes are just key
    separators in S3/MinIO); a leading slash is dropped and Windows-FTP
    backslashes are normalized so the key is stable across server types.
    """
    rel = remote_path.replace("\\", "/").lstrip("/")
    return f"{host}/{rel}{suffix}"


def put_pickle_to_minio(
    client: Any,
    transform: ToObject,
    *,
    key: KeyFn | None = None,
    then: OnFile | None = None,
) -> OnFile:
    """Build an ``on_file`` callback that pickles each file and puts it to MinIO.

    The MinIO counterpart to ``save_to_dir``: instead of writing to local disk,
    each downloaded file is run through ``transform`` (bytes → a live Python
    object) and uploaded via ``client.put_pickle`` — nothing touches disk, peak
    RAM stays bounded by ``max_concurrency`` (streaming). ``client`` is an
    injected ``minio_handler.MinioObject`` (passed in, never imported here, so
    ``ftp_handler`` stays free of a minio dependency). By default the object
    lands at ``<host>/<remote path>.pkl``; pass ``key`` to choose your own.

    Reach for this when ``transform`` yields a non-tabular value (nested dict,
    custom class, model object). For a ``pd.DataFrame`` prefer
    ``put_parquet_to_minio`` — parquet is portable and not a code-execution risk
    on read. The callback runs inside the per-host worker thread, so use a
    thread-safe client (minio-py's object client is); ``then`` chains a second
    callback after the upload (e.g. index to OpenSearch)::

        mc = MinioObject()
        dl.download(specs, on_file=put_pickle_to_minio(mc, parse))
    """
    key_for = key or (lambda host, remote_path: _object_key(host, remote_path, ".pkl"))

    def on_file(host: str, remote_path: str, data: bytes) -> None:
        client.put_pickle(key_for(host, remote_path), transform(host, remote_path, data))
        if then is not None:
            then(host, remote_path, data)

    return on_file


def put_parquet_to_minio(
    client: Any,
    transform: ToObject,
    *,
    key: KeyFn | None = None,
    then: OnFile | None = None,
) -> OnFile:
    """Build an ``on_file`` callback that writes each file to MinIO as parquet.

    Same shape as ``put_pickle_to_minio`` but ``transform`` must return a pandas
    ``DataFrame``, which is serialized to parquet (pyarrow) and uploaded via
    ``client.put_dataframe`` — nothing touches disk, RAM stays streaming-bounded.
    ``client`` is an injected ``minio_handler.MinioObject``. By default the
    object lands at ``<host>/<remote path>.parquet``; pass ``key`` to override.

    Prefer this over pickle for tabular equipment data: parquet is compressed,
    columnar, and readable by anything (Spark, DuckDB, pandas) without trusting
    the producer. The callback runs in the per-host worker thread; ``then``
    chains a follow-up callback after the upload::

        mc = MinioObject()
        dl.download(specs, on_file=put_parquet_to_minio(mc, parse_to_frame))
    """
    key_for = key or (
        lambda host, remote_path: _object_key(host, remote_path, ".parquet")
    )

    def on_file(host: str, remote_path: str, data: bytes) -> None:
        client.put_dataframe(
            key_for(host, remote_path), transform(host, remote_path, data)
        )
        if then is not None:
            then(host, remote_path, data)

    return on_file


def put_bytes_to_minio(
    client: Any,
    *,
    key: KeyFn | None = None,
    then: OnFile | None = None,
) -> OnFile:
    """Build an ``on_file`` callback that puts each file's RAW bytes to MinIO.

    The simplest MinIO sink: the downloaded bytes are uploaded unchanged via
    ``client.put`` — no serialization, no transform. Use this to archive files
    exactly as they came off the FTP server (logs, .dat, anything). Nothing
    touches disk and peak RAM stays bounded by ``max_concurrency`` (streaming),
    same as ``put_pickle_to_minio`` / ``put_parquet_to_minio``. ``client`` is an
    injected ``minio_handler.MinioObject`` (passed in, never imported here, so
    ``ftp_handler`` stays free of a minio dependency).

    By default the object lands at ``<host>/<remote path>`` (the remote
    directory structure preserved as the key, no suffix); pass ``key`` to choose
    your own scheme. ``then`` chains a second callback after the upload (e.g.
    parse + index to OpenSearch), so you archive AND process in one pass::

        mc = MinioObject(bucket="eqp-logs")
        dl.download(specs, on_file=put_bytes_to_minio(mc))

        # custom key + index in the same streaming pass
        dl.download(specs, on_file=put_bytes_to_minio(
            mc,
            key=lambda host, rp: f"eqp/{host}/{day}/{PurePosixPath(rp).name}",
            then=lambda host, rp, data: index(parse(host, rp, data)),
        ))
    """
    key_for = key or (lambda host, remote_path: _object_key(host, remote_path, ""))

    def on_file(host: str, remote_path: str, data: bytes) -> None:
        client.put(key_for(host, remote_path), data)
        if then is not None:
            then(host, remote_path, data)

    return on_file
