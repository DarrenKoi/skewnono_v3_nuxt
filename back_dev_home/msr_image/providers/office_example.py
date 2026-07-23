# TEMPLATE — copy to office.py at the office, then verify against a real tool.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 msr_image adapter: tool FTP -> Flask relay. Pure-FTP, no OpenSearch.

The frontend sends eqp_ip/class_name/msr/name; routes validate the IP and pass a
locator here. This module assembles the /HITACHI path, lists the dir, and fetches
image + cond over ftp_handler's FtpClient (vendored, instantiated only).
"""

import ftplib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath

from ftp_handler.core.client import FtpClient

from back_dev_home.msr_image.config import ImageConfig, load_config
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator
from back_dev_home.msr_image.errors import ImageNotFound, SourceUnavailable
from back_dev_home.msr_image.paths import cond_path, image_dir, image_path

OnFile = Callable[[str, FetchedImage | None, str | None], None]


def _test_config() -> ImageConfig:
    # Convenience for the tracked-template tests; real calls load env config.
    return load_config({})


def _client(eqp_ip: str, cfg: ImageConfig) -> FtpClient:
    return FtpClient(
        host=eqp_ip,
        user=cfg.ftp_user,
        password=cfg.ftp_password,
        port=cfg.ftp_port,
        timeout=cfg.ftp_timeout,
    )


def list_images(eqp_ip, class_name, msr, _config: ImageConfig | None = None) -> list[str]:
    cfg = _config or load_config()
    directory = image_dir(class_name, msr)
    try:
        with _client(eqp_ip, cfg) as ftp:
            entries = ftp.list_dir(directory)
    except Exception as exc:  # dead host, auth, timeout
        raise SourceUnavailable(f"tool listing failed: {type(exc).__name__}") from exc
    # FtpClient.list_dir returns FULL remote paths (ftp_handler normalizes NLST
    # output to paths RETR accepts). The contract here is BASENAMES — the
    # frontend sends the basename back as `name`, and fetch_image rebuilds the
    # full path via image_path(). So basename them here.
    return [
        PurePosixPath(e).name
        for e in entries
        if e.lower().endswith((".jpeg", ".jpg"))
    ]


def _fetch(ftp: FtpClient, class_name, msr, name) -> FetchedImage:
    img_path = image_path(class_name, msr, name)
    try:
        data = ftp.download(img_path)
    except ftplib.error_perm as exc:
        raise ImageNotFound(f"image not found: {name}") from exc
    except Exception as exc:
        raise SourceUnavailable(f"tool fetch failed: {type(exc).__name__}") from exc
    cond = None
    try:
        cond_bytes = ftp.download(cond_path(img_path))
        cond = cond_bytes.decode("utf-8", errors="replace")
    except Exception:
        cond = None  # cond is best-effort; image already present
    return FetchedImage(data, "image/jpeg", cond)


def fetch_image(locator: ImageLocator, _config: ImageConfig | None = None) -> FetchedImage:
    cfg = _config or load_config()
    try:
        with _client(locator.eqp_ip, cfg) as ftp:
            return _fetch(ftp, locator.class_name, locator.msr, locator.name)
    except (ImageNotFound, SourceUnavailable):
        raise
    except Exception as exc:
        raise SourceUnavailable(f"tool fetch failed: {type(exc).__name__}") from exc


def download_all(eqp_ip, class_name, msr, names, on_file: OnFile, concurrency=6, _config=None) -> None:
    """Bounded pool of FtpClient connections to the one tool. Each worker owns
    one login and pulls a slice of the files. Progress is reported per file via
    on_file; the caller (the job worker) writes to cache and counts."""
    cfg = _config or load_config()
    n = max(1, min(concurrency, cfg.ftp_concurrency))

    def worker(chunk: list[str]) -> None:
        try:
            with _client(eqp_ip, cfg) as ftp:
                for name in chunk:
                    try:
                        on_file(name, _fetch(ftp, class_name, msr, name), None)
                    except Exception as exc:
                        on_file(name, None, f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            for name in chunk:
                on_file(name, None, f"connection failed: {type(exc).__name__}")

    chunks: list[list[str]] = [names[i::n] for i in range(n)]
    chunks = [c for c in chunks if c]
    with ThreadPoolExecutor(max_workers=len(chunks) or 1) as pool:
        list(pool.map(worker, chunks))
