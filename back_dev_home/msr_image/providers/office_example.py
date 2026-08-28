# TEMPLATE — copy to office.py at the office, then verify against a real tool.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 msr_image adapter: tool FTP -> Flask relay. Pure-FTP, no OpenSearch.

The frontend sends eqp_ip/class_name/msr/name; routes validate the IP and pass a
locator here. This module assembles the /HITACHI path, lists the dir, and fetches
image + cond over ftp_handler's FtpFleetDownloader (vendored, instantiated only).

Transport is platform-selected at import time. The office local PC (Windows)
cannot open FTP connections to tools directly — every call must go through the
HTTP proxy on a firewall-free host. The cloud deploy (Linux) downloads directly.
Both classes expose the same surface and share the same dataclasses, so only
the import line differs.
"""

from collections.abc import Callable
from pathlib import PurePosixPath
from platform import system

if system() == "Windows":
    # Office local PC: direct FTP egress to tools is blocked; route through the
    # HTTP proxy (location/auth are PROXY_URL/PROXY_TOKEN module constants in
    # ftp_handler/proxy/proxy_downloader.py — edit once per deployment).
    from ftp_handler.proxy import FtpFleetDownloader, HostSpec, ListDir
else:
    # Cloud (Phase 3) and any host with direct reach to the tools.
    from ftp_handler.direct_downloader import FtpFleetDownloader, HostSpec, ListDir

from back_dev_home.msr_image.config import ImageConfig, ftp_account_lookup, load_config
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator
from back_dev_home.msr_image.errors import ImageNotFound, SourceUnavailable
from back_dev_home.msr_image.paths import cond_path, image_dir, image_path

OnFile = Callable[[str, FetchedImage | None, str | None], None]

# Office-confirmed 2026-07-24: tools serve JPEG previews alongside TIFF
# originals, and the minio_pkl's mp_image_name columns reference BOTH — a
# jpeg-only filter makes the TIFFs invisible (13/39 "missing" in the first
# office smoke run).
_IMAGE_EXTS = (".jpeg", ".jpg", ".tif", ".tiff")


def _content_type(name: str) -> str:
    return "image/tiff" if name.lower().endswith((".tif", ".tiff")) else "image/jpeg"


def _test_config() -> ImageConfig:
    # Convenience for the tracked-template tests; real calls load env config.
    return load_config({})


# Per-image budget used to size a download job's host_timeout. Two RETRs per
# image (the image itself and its cond sidecar).
#
# office 확인 2026-08-10 (scripts.measure_msr_image_ftp against a real tool):
# 0.20 s per image inside download_all at the configured concurrency, x2
# headroom. The previous 5.0 was reasoned from "multi-MB TIFFs" and ran 12x
# generous -- the images are small and the link is fast, so nearly the whole
# cost of a cold fetch is the LOGIN, not the transfer (94 ms of 133 ms).
#
# Being generous was never wrong output, only slow failure: this is a backstop,
# so an oversized one merely holds a genuinely stalled connection for minutes
# before giving up. Detecting a dead tool is ftp_timeout's job and was never
# affected by this number.
_SECONDS_PER_IMAGE = 0.4

# Default ceiling on that scaling for the PROXY transport only. The proxy host's
# uWSGI kills a request at harakiri=75s (ftp_handler/proxy/wsgi.ini), and one
# request carries a BATCH of up to request_batch specs -- so a budget above
# harakiri does not buy a longer download, it gets every spec in the batch
# killed at once. Staying under it means a job too big for the proxy degrades
# to ordinary per-host failures, which the frontend already retries per image.
# Raise this together with harakiri (both are office-side), never alone.
#
# What the cap actually costs, now that _SECONDS_PER_IMAGE is measured: at
# 0.4 s/image this ceiling is reached at ~150 images on one connection, where
# the old 5.0 hit it at 12. The cap stopped being the binding constraint on
# real jobs the moment the per-image number became real.
_PROXY_HOST_TIMEOUT_CAP = 60.0
_VIA_PROXY = system() == "Windows"


def _host_timeout(cfg: ImageConfig, images_per_connection: int = 1) -> float:
    """How long one connection may run before the fleet gives up on it.

    Leaving this at the library default was a live bug, not a tuning nit. The
    default is 60s (45s through the proxy) no matter how much work the
    connection was handed, so a warm job big enough to need longer was abandoned
    MID-TRANSFER -- and an abandoned worker keeps running, so its ``on_file``
    went on writing into the job registry and into the pairing state that
    ``download_all`` flushes once ``download()`` has returned. ftp_handler now
    gates the callback shut on abandonment, which stops the corruption; scaling
    the budget here is what stops the abandonment.

    ``ftp_host_timeout`` is the floor -- it covers a single fetch or a listing.
    Past that the budget grows with the files actually queued on the connection.
    Growing it does not weaken dead-tool detection: ``ftp_timeout`` bounds every
    socket op, so an offline tool still fails in seconds either way.

    The growth is capped, because the proxy transport has a hard ceiling its
    uWSGI enforces (see ``_PROXY_HOST_TIMEOUT_CAP``). ``ftp_host_timeout_max``
    overrides the cap on either transport; 0 means uncapped.
    """
    budget = max(cfg.ftp_host_timeout, _SECONDS_PER_IMAGE * max(1, images_per_connection))
    cap = cfg.ftp_host_timeout_max or (_PROXY_HOST_TIMEOUT_CAP if _VIA_PROXY else 0.0)
    # The floor wins over the cap: a cap below it would mean the operator asked
    # for two contradictory things, and shrinking a single fetch's budget is not
    # what a proxy-batch ceiling is for.
    return max(cfg.ftp_host_timeout, min(budget, cap)) if cap else budget


def _downloader(cfg: ImageConfig, images_per_connection: int = 1) -> FtpFleetDownloader:
    return FtpFleetDownloader(
        user=cfg.ftp_user,
        password=cfg.ftp_password,
        port=cfg.ftp_port,
        connect_timeout=cfg.ftp_timeout,
        host_timeout=_host_timeout(cfg, images_per_connection),
    )


def list_images(eqp_ip, class_name, msr, _config: ImageConfig | None = None) -> list[str]:
    cfg = _config or load_config()
    directory = image_dir(class_name, msr)
    account = ftp_account_lookup(cfg)
    report = _downloader(cfg).list_dirs(
        [HostSpec(eqp_ip, listings=[ListDir(directory)], **account(eqp_ip))]
    )
    if report.failures:  # dead host, auth, or the one listing dir failed
        raise SourceUnavailable(f"tool listing failed: {report.failures[0].error}")
    # Listing paths are FULL remote paths (ftp_handler normalizes NLST output
    # to paths RETR accepts). The contract here is BASENAMES — the frontend
    # sends the basename back as `name`, and fetch_image rebuilds the full
    # path via image_path(). So basename them here.
    #
    # The dot check is NOT tidiness (office 확인 2026-08-10). Each image's cond
    # sidecar lives in a hidden DIRECTORY named after it — `foo.jpeg`'s cond is
    # `.foo.jpeg/cond.txt` (see cond_path in ../paths.py). That directory ends
    # in `.jpeg` too, so an extension filter alone hands it back as an image,
    # and the first RETR against it gets a 550 the adapter reports as
    # ImageNotFound. Every image in a real folder has one, so this doubled the
    # listing and made every other entry unfetchable.
    return [
        PurePosixPath(p).name
        for listing in report.listings
        for p in listing.paths
        if p.lower().endswith(_IMAGE_EXTS) and not PurePosixPath(p).name.startswith(".")
    ]


def _image_error(report, img: str) -> str:
    # Prefer the per-file failure; fall back to the host-level one
    # (connect/login failures carry remote_path=None).
    for f in report.failures:
        if f.remote_path == img:
            return f.error
    for f in report.failures:
        if f.remote_path is None:
            return f.error
    return "unknown"


def fetch_image(locator: ImageLocator, _config: ImageConfig | None = None) -> FetchedImage:
    cfg = _config or load_config()
    img = image_path(locator.class_name, locator.msr, locator.name)
    report = _downloader(cfg).download(
        [
            HostSpec(
                locator.eqp_ip,
                files=[img, cond_path(img)],
                **ftp_account_lookup(cfg)(locator.eqp_ip),
            )
        ]
    )
    data = {f.remote_path: f.data for f in report.files}
    if img not in data:
        err = _image_error(report, img)
        # ftp_handler formats per-file failures as "<ExcName>: <msg>", so a 550
        # from the tool surfaces as "error_perm: ..." -> the file is not there.
        if err.startswith("error_perm"):
            raise ImageNotFound(f"image not found: {locator.name}")
        raise SourceUnavailable(f"tool fetch failed: {err}")
    cond_bytes = data.get(cond_path(img))
    cond = cond_bytes.decode("utf-8", errors="replace") if cond_bytes is not None else None
    return FetchedImage(data[img], _content_type(locator.name), cond)


def download_all(eqp_ip, class_name, msr, names, on_file: OnFile, concurrency=6, _config=None) -> None:
    """One fleet call fans the files out over n connections to the one tool:
    ftp_handler runs each HostSpec on its own connection, so n same-host specs
    replace the old bounded ThreadPool of FtpClient logins. Progress is
    reported per image via on_file; the caller (the job worker) writes to
    cache and counts."""
    cfg = _config or load_config()
    n = max(1, min(concurrency, cfg.ftp_concurrency))
    chunks = [c for c in (names[i::n] for i in range(n)) if c]
    # The busiest connection is what the per-host budget has to cover.
    per_connection = max((len(c) for c in chunks), default=1)

    account = ftp_account_lookup(cfg)(eqp_ip)
    specs: list[HostSpec] = []
    name_of_image: dict[str, str] = {}
    image_of_cond: dict[str, str] = {}
    chunk_of: dict[str, int] = {}
    for idx, chunk in enumerate(chunks):
        files: list[str] = []
        for name in chunk:
            img = image_path(class_name, msr, name)
            files += [img, cond_path(img)]
            name_of_image[img] = name
            image_of_cond[cond_path(img)] = img
            chunk_of[img] = chunk_of[cond_path(img)] = idx
        # One resolver for the whole run: every chunk is the same tool, and the
        # lookup behind it reads the sem_list roster (see ftp_account_lookup).
        specs.append(HostSpec(eqp_ip, files=files, **account))

    # Streamed pairing keeps RAM flat and progress live. Each chunk is one
    # connection fetching [img1, cond1, img2, cond2, ...] in order, so an image
    # is emitted the moment its cond arrives — or, when the cond RETR failed
    # and thus never calls back, the moment the NEXT image on the same
    # connection proves the cond phase is over. Leftovers flush after the call.
    pending: dict[int, tuple[str, bytes]] = {}  # chunk idx -> (image path, bytes)
    done: set[str] = set()  # image paths already reported to on_file

    def emit(img: str, data: bytes, cond_bytes: bytes | None) -> None:
        done.add(img)
        cond = cond_bytes.decode("utf-8", errors="replace") if cond_bytes is not None else None
        name = name_of_image[img]
        on_file(name, FetchedImage(data, _content_type(name), cond), None)

    def stream(_host: str, remote_path: str, data: bytes) -> None:
        idx = chunk_of[remote_path]
        prev = pending.pop(idx, None)
        if remote_path in name_of_image:  # an image arrived
            if prev is not None:
                emit(prev[0], prev[1], None)  # its cond never called back
            pending[idx] = (remote_path, data)
        elif prev is not None:  # a cond arrived
            if prev[0] == image_of_cond[remote_path]:
                emit(prev[0], prev[1], data)
            else:  # cond of a failed image; keep waiting for prev's own cond
                pending[idx] = prev

    report = _downloader(cfg, per_connection).download(specs, on_file=stream)

    for img, data in pending.values():  # last image per chunk, cond missing
        emit(img, data, None)
    errors = {f.remote_path: f.error for f in report.failures if f.remote_path}
    host_error = next((f.error for f in report.failures if f.remote_path is None), None)
    for name in names:
        img = image_path(class_name, msr, name)
        if img in done:
            continue
        err = errors.get(img)
        on_file(name, None, err or f"connection failed: {host_error or 'unknown'}")


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.msr_image.providers.office
    # Cross-checks the FTP listing against the minio_pkl ground truth: the
    # pickle's df_result_data carries "mp_image_name NN" columns naming every
    # image the run produced, while list_images() reports what the tool's FTP
    # dir actually serves. The request path stays pure FTP — OpenSearch/MinIO
    # are imported HERE only, to find a real (msr, class, eqp_ip) to probe.
    from minio_handler import MinioObject

    from back_dev_home.ebeam._office_meas_hist import ALL_INDICES, search, text

    body = {
        "query": {"bool": {"filter": [
            {"exists": {"field": "minio_pkl"}},
            {"exists": {"field": "eqp_ip"}},
        ]}},
        "sort": [{"timestamp": "desc"}],
        "size": 1,
    }
    hits = search(ALL_INDICES).search_raw(body).get("hits", {}).get("hits", [])
    if not hits:
        raise SystemExit("no meas_hist doc with minio_pkl + eqp_ip — check ingestion")
    src = hits[0].get("_source", {})
    probe_msr = text(src.get("msr"))
    probe_class = text(src.get("class_name"))
    probe_ip = text(src.get("eqp_ip"))
    print(f"probe msr: {probe_msr!r}  class: {probe_class!r}  eqp_ip: {probe_ip!r}")
    print(f"ftp dir  : {image_dir(probe_class, probe_msr)!r}")

    payload = MinioObject().get_pickle(text(src.get("minio_pkl")).lstrip("/"))
    df = payload.get("df_result_data")
    records = df.to_dict(orient="records") if hasattr(df, "to_dict") else list(df or [])
    expected = {
        str(v).strip()
        for rec in records
        for col, v in rec.items()
        if str(col).lower().startswith("mp_image_name")
        and v is not None and str(v).strip() not in ("", "None", "nan")
    }
    listed = set(list_images(probe_ip, probe_class, probe_msr))
    print(f"pickle names: {len(expected)}   ftp names: {len(listed)}")

    # Tolerate case differences; a pickle name may also omit the extension,
    # so fall back to matching the listed file's stem.
    by_name = {n.lower(): n for n in listed}
    by_stem = {PurePosixPath(n).name.lower().rsplit(".", 1)[0]: n for n in sorted(listed)}
    matched = {by_name.get(e.lower()) or by_stem.get(e.lower()) for e in expected}
    matched.discard(None)
    missing = sorted(e for e in expected if e.lower() not in by_name and e.lower() not in by_stem)
    extra = sorted(listed - matched)
    print(f"matched: {len(matched)}")
    if missing:
        print(f"MISSING on tool ({len(missing)}): {missing[:10]}{' …' if len(missing) > 10 else ''}")
    if extra:
        print(f"extra on tool, not in pickle (usually fine): {len(extra)}")

    probe_name = min(matched, default=None) or min(listed, default=None)
    if probe_name is None:
        raise SystemExit("tool dir has no images to fetch")
    fetched = fetch_image(ImageLocator(probe_ip, probe_class, probe_msr, probe_name))
    print(f"fetch_image({probe_name!r}): {len(fetched.data)} bytes, cond={'yes' if fetched.cond else 'none'}")
    print("smoke:", "OK" if not missing else f"CHECK — {len(missing)} pickle names not on tool FTP")
