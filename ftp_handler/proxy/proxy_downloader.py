"""HTTP-proxy FTP downloader — the client half, drop-in for the direct downloader.

For a PC that CANNOT reach the equipment FTP servers directly (firewalled) but
CAN reach the Flask proxy (``ftp_handler/proxy/flask_proxy.py``) on a firewall-free
host. Exposes the SAME public names as ``direct_downloader.fleet_downloader``, so a
call site swaps with one import line and nothing else changes. This downloader
satisfies the ``FleetTransport`` seam declared in ``fleet_downloader`` (both
``download`` and ``list_dirs``); a conformance test asserts both adapters keep
matching it::

    # direct FTP (no firewall in the way):
    from ftp_handler.direct_downloader import FtpFleetDownloader, HostSpec, ListDir
    # via the proxy (firewalled client):
    from ftp_handler.proxy import FtpFleetDownloader, HostSpec, ListDir

The dataclasses (HostSpec, ListDir, DownloadReport, FileResult, HostFailure,
HostListing, ListingReport) are re-exported from ``direct_downloader.fleet_downloader``, so
report.grouped(), report.failure_ratio, to_specs(), and your on_file handler
behave identically under either transport. Within one consistent import context
they are the *same class objects*; the transport itself is duck-typed (specs are
serialized structurally), so a call site that imports everything from one side —
all package (``ftp_handler.*``) or all copy-out (bare) — never has to care which.

Transport: specs are split into batches and POSTed to the proxy concurrently;
the proxy does the real FTP and returns base64'd bytes. ``on_file`` still runs
HERE on the client, so your parse/archive/index processing stays local.

Proxy location & auth are module constants (NOT constructor args), so the
constructor signature stays identical to the direct downloader — a shared call
site swaps the import line and passes nothing transport-specific. Edit these at
the top of this file for your deployment:
    PROXY_URL    e.g. "https://proxy.host:8080"   (default the SEM fileloader webapp)
    PROXY_TOKEN  bearer-token string the proxy enforces, or None for no auth

The proxy host reads the equipment FTP credentials from
``FTP_PROXY_FTP_USER`` / ``FTP_PROXY_FTP_PASSWORD``. They are never serialized
into the client's HTTP request body.

Run: pip install requests
"""

import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

# Reuse the SAME dataclasses so reports are interchangeable with direct mode.
try:
    from ..direct_downloader.fleet_downloader import (
        DownloadReport,
        FileResult,
        FileSize,
        HostFailure,
        HostListing,
        HostSpec,
        ListDir,
        ListingReport,
        OnFile,
        SizingReport,
        UploadFile,
        UploadReport,
        UploadResult,
        UploadSpec,
        group_files_by_host,
        image_sidecar_target,
        local_target,
        save_image_with_sidecar,
        save_to_dir,
        specs_from_hosts,
        upload_specs_from_hosts,
    )
except ImportError:  # copied beside fleet_downloader.py and imported bare
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fleet_downloader import (
        DownloadReport,
        FileResult,
        FileSize,
        HostFailure,
        HostListing,
        HostSpec,
        ListDir,
        ListingReport,
        OnFile,
        SizingReport,
        UploadFile,
        UploadReport,
        UploadResult,
        UploadSpec,
        group_files_by_host,
        image_sidecar_target,
        local_target,
        save_image_with_sidecar,
        save_to_dir,
        specs_from_hosts,
        upload_specs_from_hosts,
    )

__all__ = [
    "FtpFleetDownloader",
    "download_fleet",
    "list_fleet",
    "size_fleet",
    "upload_fleet",
    "HostSpec",
    "ListDir",
    "DownloadReport",
    "FileResult",
    "FileSize",
    "HostFailure",
    "HostListing",
    "ListingReport",
    "SizingReport",
    "UploadFile",
    "UploadSpec",
    "UploadResult",
    "UploadReport",
    "image_sidecar_target",
    "local_target",
    "save_image_with_sidecar",
    "save_to_dir",
    "specs_from_hosts",
    "group_files_by_host",
    "upload_specs_from_hosts",
]


# Proxy location & auth — edit these for your deployment. They live as module
# constants (NOT constructor args) so the client constructor stays identical to
# the direct downloader: a shared call site swaps the import line and passes
# nothing transport-specific. The firewalled client box reaches the proxy at
# PROXY_URL; set PROXY_TOKEN to the bearer-token string if the proxy enforces
# auth (leave None for the trusted single-user, no-auth case).
PROXY_URL = "http://skewnono-scheduler1-webapp.aipp01.skhynix.com"
PROXY_TOKEN = None


def _credentials_to_wire(spec: "HostSpec | UploadSpec") -> dict:
    """The per-host credential OVERRIDE, or nothing at all when it is unset.

    The shared fleet account still never crosses this hop — it lives in the
    proxy host's own environment (``FTP_PROXY_FTP_USER``). Only a spec that
    deliberately names a different account serializes one, so a fleet on one
    account produces byte-identical payloads to before this field existed.
    """
    override = {}
    if spec.user is not None:
        override["user"] = spec.user
    if spec.password is not None:
        override["password"] = spec.password
    return override


def _spec_to_wire(spec: HostSpec) -> dict:
    return {
        "host": spec.host,
        "files": list(spec.files),
        "listings": [
            {"remote_dir": ld.remote_dir, "pattern": ld.pattern}
            for ld in spec.listings
        ],
        **_credentials_to_wire(spec),
    }


def _upload_spec_to_wire(spec: UploadSpec) -> dict:
    # File bytes aren't JSON-native, so base64 them; the proxy decodes before the
    # STOR. The data travels client → proxy here (the reverse of download).
    return {
        "host": spec.host,
        "files": [
            {
                "remote_path": item.remote_path,
                "data_b64": base64.b64encode(item.data).decode("ascii"),
            }
            for item in spec.files
        ],
        **_credentials_to_wire(spec),
    }


class FtpFleetDownloader:
    """Same surface as direct_downloader.FtpFleetDownloader, over HTTP.

    The proxy *location* (``PROXY_URL``) and *auth* (``PROXY_TOKEN``) are module
    constants at the top of this file, NOT constructor args — they're deployment
    facts of the firewalled client box, edited once. Keeping them out of the
    signature is what makes the seam clean: the constructor takes exactly the
    same args as the direct downloader, so a shared call site swaps the import
    line and passes nothing transport-specific.

    The only extra args are HTTP tuning knobs, all defaulted, and only set in
    proxy-specific setup — never at the shared call site:
        request_batch  hosts per HTTP request (bounds proxy-side transient RAM:
                       Mode-A collect + base64 + jsonify ~= 3x a batch's raw
                       bytes). Default 5; sized for ~10MB files on the shared
                       8GiB/reload-on-rss=1500 proxy host. See ADR 0001.
        client_workers concurrent in-flight requests to the proxy. Default 4 to
                       match the proxy's processes=4 — one batch per worker, no
                       stacking in a single worker's address space.
        http_timeout   per-request read timeout; defaults generously to the
                       proxy's worst-case batch time
    """

    def __init__(
        self,
        *,
        user: str,
        password: str,
        port: int = 21,
        max_concurrency: int = 48,
        connect_timeout: float = 8.0,
        host_timeout: float = 45.0,
        passive: bool = True,
        request_batch: int = 5,
        client_workers: int = 4,
        http_timeout: float | None = None,
    ) -> None:
        self.user = user
        self.password = password
        self.port = port
        self.max_concurrency = max_concurrency
        self.connect_timeout = connect_timeout
        self.host_timeout = host_timeout
        self.passive = passive
        self.proxy_url = PROXY_URL.rstrip("/")
        self.token = PROXY_TOKEN
        self.request_batch = request_batch
        self.client_workers = client_workers
        # Worst case: the proxy works one batch of hosts roughly serially in the
        # tail, so allow host_timeout per host in the batch plus slack.
        self.http_timeout = http_timeout or (host_timeout * request_batch + 30.0)

    def download(
        self,
        specs: list[HostSpec],
        *,
        on_file: OnFile | None = None,
    ) -> DownloadReport:
        """Synchronous, same signature as the direct downloader.

        Splits specs into batches, POSTs them to the proxy concurrently, and
        merges the results into one DownloadReport. A whole-batch transport
        failure marks every host in that batch failed — per-host isolation one
        level up.
        """
        if not specs:
            return DownloadReport(files=[], failures=[])

        files: list[FileResult] = []
        failures: list[HostFailure] = []
        for batch_files, batch_failures in self._post_batches(
            specs, lambda b: self._post_batch(b, on_file)
        ):
            files.extend(batch_files)
            failures.extend(batch_failures)
        return DownloadReport(files=files, failures=failures)

    def list_dirs(self, specs: list[HostSpec]) -> ListingReport:
        """List each host's ``listings`` dirs through the proxy — no fetching.

        Same surface as the direct downloader's ``list_dirs``: the proxy runs the
        real listing pass and returns discovered paths (no file bytes), which are
        merged into one ListingReport. The same batching as ``download`` keeps
        each HTTP request under the proxy's harakiri budget; listings carry no
        bytes, so memory is never the constraint here.
        """
        if not specs:
            return ListingReport(listings=[], failures=[])

        listings: list[HostListing] = []
        failures: list[HostFailure] = []
        for batch_listings, batch_failures in self._post_batches(
            specs, self._post_list_batch
        ):
            listings.extend(batch_listings)
            failures.extend(batch_failures)
        return ListingReport(listings=listings, failures=failures)

    def size_dirs(self, specs: list[HostSpec]) -> SizingReport:
        """Measure the fleet's file sizes through the proxy — no fetching.

        Same surface as the direct downloader's ``size_dirs``: the proxy resolves
        each host's paths and SIZEs them, returning per-file byte counts (no file
        bytes), merged into one SizingReport. Like ``list_dirs`` it carries no
        bytes, so memory is never the constraint — the batching only keeps each
        HTTP request under the proxy's harakiri budget.
        """
        if not specs:
            return SizingReport(files=[], failures=[])

        files: list[FileSize] = []
        failures: list[HostFailure] = []
        for batch_files, batch_failures in self._post_batches(
            specs, self._post_size_batch
        ):
            files.extend(batch_files)
            failures.extend(batch_failures)
        return SizingReport(files=files, failures=failures)

    def upload(self, specs: list[UploadSpec]) -> UploadReport:
        """Push files to the fleet through the proxy — same surface as direct.

        Splits specs into batches, POSTs them (file bytes base64'd in the request
        body) to the proxy concurrently, and merges the per-file results. A
        whole-batch transport failure marks every host in that batch failed;
        per-file STOR failures come back from the proxy. The same ``request_batch``
        knob bounds inbound RAM on the proxy — see ADR 0001, applied to the
        request side here.
        """
        if not specs:
            return UploadReport(results=[], failures=[])

        results: list[UploadResult] = []
        failures: list[HostFailure] = []
        for batch_results, batch_failures in self._post_batches(
            specs, self._post_upload_batch
        ):
            results.extend(batch_results)
            failures.extend(batch_failures)
        return UploadReport(results=results, failures=failures)

    def _post_batches(self, specs, post):
        """Split specs into batches and run ``post`` over them concurrently.

        Shared transport loop for download and list_dirs: batch by
        ``request_batch``, fan out at ``client_workers``, yield each batch's
        ``(ok_items, failures)`` tuple. The caller merges them into its report.
        """
        batches = [
            specs[i : i + self.request_batch]
            for i in range(0, len(specs), self.request_batch)
        ]
        workers = max(1, min(len(batches), self.client_workers))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            yield from pool.map(post, batches)

    def _tuning(self) -> dict:
        return {
            "port": self.port,
            "max_concurrency": self.max_concurrency,
            "connect_timeout": self.connect_timeout,
            "host_timeout": self.host_timeout,
            "passive": self.passive,
        }

    def _payload(self, batch: list[HostSpec]) -> dict:
        return {**self._tuning(), "specs": [_spec_to_wire(s) for s in batch]}

    def _upload_payload(self, batch: list[UploadSpec]) -> dict:
        return {**self._tuning(), "specs": [_upload_spec_to_wire(s) for s in batch]}

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _post(self, path: str, payload: dict) -> dict:
        """POST ``payload`` to ``path`` and return the parsed JSON, or raise.

        Paths carry the ``_sknn_v3`` suffix to avoid collisions with routes
        already mounted on the host Flask app — must match flask_proxy.py.
        """
        resp = requests.post(
            f"{self.proxy_url}{path}",
            json=payload,
            headers=self._headers(),
            timeout=self.http_timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _post_batch(
        self,
        batch: list[HostSpec],
        on_file: OnFile | None,
    ) -> tuple[list[FileResult], list[HostFailure]]:
        try:
            data = self._post("/download_sknn_v3", self._payload(batch))
        except Exception as exc:  # noqa: BLE001 - whole-batch transport failure
            return [], [
                HostFailure(
                    host=s.host,
                    error=f"proxy request failed: {type(exc).__name__}: {exc}",
                )
                for s in batch
            ]

        files: list[FileResult] = []
        failures: list[HostFailure] = [
            HostFailure(
                host=item["host"],
                error=item["error"],
                remote_path=item.get("remote_path"),
            )
            for item in data.get("failures", [])
        ]
        for item in data.get("files", []):
            host = item["host"]
            remote_path = item["remote_path"]
            raw = base64.b64decode(item["data_b64"])
            if on_file is not None:
                # Same contract as direct mode: callback consumes the bytes,
                # the report keeps none; a callback raise fails that file only.
                try:
                    on_file(host, remote_path, raw)
                    files.append(FileResult(host=host, remote_path=remote_path, data=b""))
                except Exception as exc:  # noqa: BLE001
                    failures.append(
                        HostFailure(
                            host=host,
                            error=f"{type(exc).__name__}: {exc}",
                            remote_path=remote_path,
                        )
                    )
            else:
                files.append(FileResult(host=host, remote_path=remote_path, data=raw))
        return files, failures

    def _post_list_batch(
        self,
        batch: list[HostSpec],
    ) -> tuple[list[HostListing], list[HostFailure]]:
        try:
            data = self._post("/list_dirs_sknn_v3", self._payload(batch))
        except Exception as exc:  # noqa: BLE001 - whole-batch transport failure
            return [], [
                HostFailure(
                    host=s.host,
                    error=f"proxy request failed: {type(exc).__name__}: {exc}",
                )
                for s in batch
            ]

        listings = [
            HostListing(host=item["host"], paths=item["paths"])
            for item in data.get("listings", [])
        ]
        failures = [
            HostFailure(
                host=item["host"],
                error=item["error"],
                remote_path=item.get("remote_path"),
            )
            for item in data.get("failures", [])
        ]
        return listings, failures

    def _post_size_batch(
        self,
        batch: list[HostSpec],
    ) -> tuple[list[FileSize], list[HostFailure]]:
        try:
            data = self._post("/size_dirs_sknn_v3", self._payload(batch))
        except Exception as exc:  # noqa: BLE001 - whole-batch transport failure
            return [], [
                HostFailure(
                    host=s.host,
                    error=f"proxy request failed: {type(exc).__name__}: {exc}",
                )
                for s in batch
            ]

        files = [
            FileSize(
                host=item["host"],
                remote_path=item["remote_path"],
                size=item["size"],
            )
            for item in data.get("files", [])
        ]
        failures = [
            HostFailure(
                host=item["host"],
                error=item["error"],
                remote_path=item.get("remote_path"),
            )
            for item in data.get("failures", [])
        ]
        return files, failures

    def _post_upload_batch(
        self,
        batch: list[UploadSpec],
    ) -> tuple[list[UploadResult], list[HostFailure]]:
        try:
            data = self._post("/upload_sknn_v3", self._upload_payload(batch))
        except Exception as exc:  # noqa: BLE001 - whole-batch transport failure
            return [], [
                HostFailure(
                    host=s.host,
                    error=f"proxy request failed: {type(exc).__name__}: {exc}",
                )
                for s in batch
            ]

        results = [
            UploadResult(host=item["host"], remote_path=item["remote_path"])
            for item in data.get("results", [])
        ]
        failures = [
            HostFailure(
                host=item["host"],
                error=item["error"],
                remote_path=item.get("remote_path"),
            )
            for item in data.get("failures", [])
        ]
        return results, failures


def download_fleet(
    specs: list[HostSpec],
    *,
    user: str,
    password: str,
    on_file: OnFile | None = None,
    **kwargs: object,
) -> DownloadReport:
    """One-call wrapper, mirroring direct_downloader.download_fleet."""
    downloader = FtpFleetDownloader(user=user, password=password, **kwargs)  # type: ignore[arg-type]
    return downloader.download(specs, on_file=on_file)


def list_fleet(
    specs: list[HostSpec],
    *,
    user: str,
    password: str,
    **kwargs: object,
) -> ListingReport:
    """One-call wrapper, mirroring direct_downloader.list_fleet."""
    downloader = FtpFleetDownloader(user=user, password=password, **kwargs)  # type: ignore[arg-type]
    return downloader.list_dirs(specs)


def size_fleet(
    specs: list[HostSpec],
    *,
    user: str,
    password: str,
    **kwargs: object,
) -> SizingReport:
    """One-call wrapper, mirroring direct_downloader.size_fleet."""
    downloader = FtpFleetDownloader(user=user, password=password, **kwargs)  # type: ignore[arg-type]
    return downloader.size_dirs(specs)


def upload_fleet(
    specs: list[UploadSpec],
    *,
    user: str,
    password: str,
    **kwargs: object,
) -> UploadReport:
    """One-call wrapper, mirroring direct_downloader.upload_fleet."""
    downloader = FtpFleetDownloader(user=user, password=password, **kwargs)  # type: ignore[arg-type]
    return downloader.upload(specs)
