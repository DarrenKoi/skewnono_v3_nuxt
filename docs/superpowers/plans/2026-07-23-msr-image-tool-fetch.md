# MSR Image Tool-FTP Fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve MSR SEM micrographs by relaying them from the measuring tool's FTP server through Flask, with a shared MinIO cache at the office and an offline SVG mock at home, plus a fast bounded-parallel "download all" job.

**Architecture:** A new feature slice `back_dev_home/msr_image/` with a `data.py` seam that picks `mock` (SVG, offline) or `office` (`ftp_handler` FTP fetch) via `get_data_provider("msr_image")`. Phase-agnostic machinery — an `ImageCache` interface (disk at home, shared MinIO at the office), an async download-all job, and a nightly purge scheduler — is identical in both phases; only the byte source swaps. The frontend sends semantic fields (`eqp_ip`, `class_name`, `msr`, `name`); the backend assembles the FTP path and validates the IP.

**Tech Stack:** Flask blueprints, `ftp_handler` (vendored `FtpClient`), `minio_handler` (vendored `MinioObject`), APScheduler, Python 3.14 stdlib (`concurrent.futures`, `ipaddress`, `pathlib.PurePosixPath`, `urllib.parse`), Nuxt 4 + composables.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-23-msr-image-tool-fetch-design.md` — this plan implements it.
- Vendored `ftp_handler/` and `minio_handler/` MUST NOT be modified. Instantiate/​call them only. (If a change is ever unavoidable, mirror it in `flask_modules` too — out of scope here.)
- Provider seam only: `routes.py`/`contracts.py`/`cache.py`/`jobs.py` know nothing about phase. Office knowledge lives only in `providers/office.py`.
- `office.py` is gitignored; the tracked skeleton is `providers/office_example.py`. Create/edit the skeleton; `cp office_example.py office.py` happens at the office.
- No mock fallback on office source failure. Surface errors as JSON: 400 `invalid_tool_ip`, 500 `office_configuration_error`, 503 `office_source_unavailable`, 404 missing.
- Home boot path must NOT import `ftp_handler` or `minio_handler` — office provider imports them lazily.
- Data format: dict/TypedDict responses; images are raw bytes with `image/jpeg` (office) or `image/svg+xml` (mock).
- FTP path template: `/HITACHI/DEVICE/HD/{class_name}/images/{msr}`; image `{dir}/{name}`; cond `{dir}/.{name}/cond.txt`.
- FTP creds default `hitachi`/`hid` (non-confidential); env `SKEWNONO_TOOL_FTP_USER`/`_PASSWORD`/`_PORT`.
- Bounded pool: `SKEWNONO_TOOL_FTP_CONCURRENCY` (default 6). Cache TTL: `IMAGE_CACHE_TTL_HOURS` (default 72).
- Markdown edits: run `npm run lint:md`; tables use `MD060` compact style.
- Python tests run with `.venv/bin/pytest`. Frontend type/lint via existing `npm` scripts.

## File Structure

New feature `back_dev_home/msr_image/`:

| File | Responsibility |
| --- | --- |
| `__init__.py` | Re-export `bp` |
| `contracts.py` | `ImageLocator`, `FetchedImage`, `ImageListResponse`, `DownloadJobStatus`, `DownloadFailure` |
| `errors.py` | `MsrImageError` hierarchy → HTTP status mapping |
| `paths.py` | Pure FTP path assembly + `validate_tool_ip` |
| `cache.py` | `ImageCache` protocol + `DiskImageCache` + `MinioImageCache` + `make_cache()` |
| `data.py` | Provider seam: `list_images`, `fetch_image`, `download_all`, `make_cache` dispatch |
| `providers/__init__.py` | No provider imports (home boot protection) |
| `providers/mock.py` | SVG bytes + synthetic listing + synthetic cond |
| `providers/office_example.py` | `ftp_handler` list/fetch/bounded-pool download + IP guard (tracked skeleton) |
| `jobs.py` | `JobRegistry` (memory/Redis) + async download-all runner |
| `scheduler.py` | APScheduler nightly cache purge |
| `routes.py` | Blueprint: 4 endpoints |
| `MIGRATION.md` | Office adapter obligations + Verify commands |
| `tests/…` | Unit tests per component |

Modified:

- `back_dev_home/__init__.py` — register `msr_image` bp, move rate-limit exemption, start purge scheduler.
- `back_dev_home/msr_file/{routes.py,data.py,providers/*}` — remove image endpoint/functions.
- `front-dev-home/app/composables/useMsrFileApi.ts` — drop `msrImageUrl`.
- `back_dev_home/meas_hist/{contracts.py,providers/mock.py,providers/office_example.py}` — add `eqp_ip`.
- `back_dev_home/requirements.txt` — add `apscheduler>=3.10`.
- `.gitignore` — `var/`, `back_dev_home/msr_image/providers/office.py`.
- New `front-dev-home/app/composables/useMsrImageApi.ts` + component edits (Task 16).

---

## Task 1: Contracts, errors, and pure path assembly

**Files:**
- Create: `back_dev_home/msr_image/__init__.py`
- Create: `back_dev_home/msr_image/contracts.py`
- Create: `back_dev_home/msr_image/errors.py`
- Create: `back_dev_home/msr_image/paths.py`
- Create: `back_dev_home/msr_image/providers/__init__.py`
- Test: `back_dev_home/msr_image/tests/__init__.py`, `back_dev_home/msr_image/tests/test_paths.py`

**Interfaces:**
- Produces:
  - `ImageLocator(eqp_ip: str, class_name: str, msr: str, name: str)` — `NamedTuple`.
  - `FetchedImage(data: bytes, content_type: str, cond: str | None)` — `NamedTuple`.
  - `ImageListResponse`, `DownloadFailure`, `DownloadJobStatus` — `TypedDict`.
  - `MsrImageError`, `InvalidToolIp`, `ConfigError`, `SourceUnavailable`, `ImageNotFound` with `.status`/`.code`.
  - `image_dir(class_name, msr) -> str`, `image_path(class_name, msr, name) -> str`, `cond_path(image_path: str) -> str`, `validate_tool_ip(ip, allowed_subnets=None) -> str`.

- [ ] **Step 1: Write the failing test**

`back_dev_home/msr_image/tests/test_paths.py`:

```python
import pytest

from back_dev_home.msr_image.errors import InvalidToolIp
from back_dev_home.msr_image.paths import (
    cond_path,
    image_dir,
    image_path,
    validate_tool_ip,
)


def test_image_dir_uses_hitachi_template():
    assert image_dir("ADI", "MSR_123") == "/HITACHI/DEVICE/HD/ADI/images/MSR_123"


def test_image_path_joins_name():
    assert (
        image_path("ADI", "MSR_123", "shot01.jpeg")
        == "/HITACHI/DEVICE/HD/ADI/images/MSR_123/shot01.jpeg"
    )


def test_cond_path_is_hidden_sidecar_dir():
    p = image_path("ADI", "MSR_123", "shot01.jpeg")
    assert cond_path(p) == "/HITACHI/DEVICE/HD/ADI/images/MSR_123/.shot01.jpeg/cond.txt"


def test_validate_tool_ip_accepts_ipv4():
    assert validate_tool_ip("10.0.0.1") == "10.0.0.1"


def test_validate_tool_ip_rejects_garbage():
    with pytest.raises(InvalidToolIp):
        validate_tool_ip("not-an-ip")


def test_validate_tool_ip_rejects_outside_subnet():
    with pytest.raises(InvalidToolIp):
        validate_tool_ip("192.168.1.5", allowed_subnets=["10.0.0.0/8"])


def test_validate_tool_ip_accepts_inside_subnet():
    assert validate_tool_ip("10.1.2.3", allowed_subnets=["10.0.0.0/8"]) == "10.1.2.3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: back_dev_home.msr_image.errors`.

- [ ] **Step 3: Write the implementation**

`back_dev_home/msr_image/__init__.py`:

```python
from back_dev_home.msr_image.routes import bp

__all__ = ["bp"]
```

`back_dev_home/msr_image/providers/__init__.py`:

```python
# Intentionally empty: importing this package must NOT drag in office-only
# dependencies (ftp_handler, minio_handler). data.py imports a provider module
# lazily, mirroring the msr_file seam.
```

`back_dev_home/msr_image/tests/__init__.py`: empty file.

`back_dev_home/msr_image/contracts.py`:

```python
"""Shared types for the msr_image feature (phase-agnostic)."""

from typing import Literal, NamedTuple, TypedDict


class ImageLocator(NamedTuple):
    eqp_ip: str
    class_name: str
    msr: str
    name: str


class FetchedImage(NamedTuple):
    data: bytes
    content_type: str
    cond: str | None


class ImageListResponse(TypedDict):
    msr: str
    class_name: str
    images: list[str]
    total: int


class DownloadFailure(TypedDict):
    name: str
    error: str


class DownloadJobStatus(TypedDict):
    job_id: str
    status: Literal["running", "done", "error"]
    done: int
    total: int
    ok: int
    ng: int
    failures: list[DownloadFailure]
```

`back_dev_home/msr_image/errors.py`:

```python
"""MSR image error hierarchy with HTTP status + machine code.

Routes translate these to JSON error responses. Home mock never raises the
office-source variants; office adapter never falls back to mock bytes.
"""


class MsrImageError(Exception):
    status = 500
    code = "msr_image_error"


class InvalidToolIp(MsrImageError):
    status = 400
    code = "invalid_tool_ip"


class ConfigError(MsrImageError):
    status = 500
    code = "office_configuration_error"


class SourceUnavailable(MsrImageError):
    status = 503
    code = "office_source_unavailable"


class ImageNotFound(MsrImageError):
    status = 404
    code = "image_not_found"
```

`back_dev_home/msr_image/paths.py`:

```python
"""Pure FTP path assembly + tool-IP validation (no network, no phase)."""

import ipaddress
from pathlib import PurePosixPath

from back_dev_home.msr_image.errors import InvalidToolIp

_ROOT = "/HITACHI/DEVICE/HD"


def image_dir(class_name: str, msr: str) -> str:
    return f"{_ROOT}/{class_name}/images/{msr}"


def image_path(class_name: str, msr: str, name: str) -> str:
    return f"{image_dir(class_name, msr)}/{name}"


def cond_path(image_path_str: str) -> str:
    """Hidden per-image sidecar: /dir/foo.jpeg -> /dir/.foo.jpeg/cond.txt."""
    p = PurePosixPath(image_path_str)
    return str(p.with_name(f".{p.name}") / "cond.txt")


def validate_tool_ip(ip: str, allowed_subnets: list[str] | None = None) -> str:
    """Return ``ip`` if it is a well-formed IPv4 (and, when a subnet allowlist
    is given, inside it). Raise InvalidToolIp otherwise. The backend opens an
    FTP session to whatever the client sends, so this is the SSRF guard."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError as exc:
        raise InvalidToolIp(f"not an IP address: {ip!r}") from exc
    if not isinstance(addr, ipaddress.IPv4Address):
        raise InvalidToolIp(f"not an IPv4 address: {ip!r}")
    if allowed_subnets:
        for cidr in allowed_subnets:
            if addr in ipaddress.ip_network(cidr.strip(), strict=False):
                return ip
        raise InvalidToolIp(f"IP outside allowed subnets: {ip!r}")
    return ip
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_paths.py -v`
Expected: PASS (6 tests).

Note: `__init__.py` imports `routes.bp`, which does not exist until Task 6. That import is only triggered when something imports `back_dev_home.msr_image` (the app factory in Task 12) — the path tests import `...msr_image.paths`/`.errors` directly, so they pass now.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_image/__init__.py back_dev_home/msr_image/contracts.py \
  back_dev_home/msr_image/errors.py back_dev_home/msr_image/paths.py \
  back_dev_home/msr_image/providers/__init__.py back_dev_home/msr_image/tests/
git commit -m "feat(msr_image): contracts, errors, pure path assembly + IP guard"
```

---

## Task 2: Config resolution

**Files:**
- Create: `back_dev_home/msr_image/config.py`
- Test: `back_dev_home/msr_image/tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_config(env: Mapping[str, str] | None = None) -> ImageConfig` where `ImageConfig` is a frozen dataclass with: `ftp_user: str`, `ftp_password: str`, `ftp_port: int`, `ftp_concurrency: int`, `ftp_timeout: float`, `allowed_subnets: list[str]`, `cache_dir: str`, `cache_bucket: str | None`, `cache_prefix: str`, `ttl_hours: int`, `purge_hour: int`, `job_ttl: int`, `max_jobs: int`.

- [ ] **Step 1: Write the failing test**

`back_dev_home/msr_image/tests/test_config.py`:

```python
from back_dev_home.msr_image.config import load_config


def test_defaults_when_env_empty():
    cfg = load_config({})
    assert cfg.ftp_user == "hitachi"
    assert cfg.ftp_password == "hid"
    assert cfg.ftp_port == 21
    assert cfg.ftp_concurrency == 6
    assert cfg.ttl_hours == 72
    assert cfg.purge_hour == 3
    assert cfg.cache_prefix == "image_cache/"
    assert cfg.allowed_subnets == []


def test_env_overrides():
    cfg = load_config({
        "SKEWNONO_TOOL_FTP_USER": "svc",
        "SKEWNONO_TOOL_FTP_PASSWORD": "pw",
        "SKEWNONO_TOOL_FTP_CONCURRENCY": "10",
        "IMAGE_CACHE_TTL_HOURS": "48",
        "SKEWNONO_TOOL_SUBNETS": "10.0.0.0/8, 192.168.0.0/16",
    })
    assert cfg.ftp_user == "svc"
    assert cfg.ftp_password == "pw"
    assert cfg.ftp_concurrency == 10
    assert cfg.ttl_hours == 48
    assert cfg.allowed_subnets == ["10.0.0.0/8", "192.168.0.0/16"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_config.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

`back_dev_home/msr_image/config.py`:

```python
"""Environment-driven config for msr_image (both phases read the same keys)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    return int(raw) if raw.lstrip("-").isdigit() else default


@dataclass(frozen=True)
class ImageConfig:
    ftp_user: str = "hitachi"
    ftp_password: str = "hid"
    ftp_port: int = 21
    ftp_concurrency: int = 6
    ftp_timeout: float = 8.0
    allowed_subnets: list[str] = field(default_factory=list)
    cache_dir: str = "var/image_cache"
    cache_bucket: str | None = None
    cache_prefix: str = "image_cache/"
    ttl_hours: int = 72
    purge_hour: int = 3
    job_ttl: int = 3600
    max_jobs: int = 2


def load_config(env: Mapping[str, str] | None = None) -> ImageConfig:
    env = os.environ if env is None else env
    subnets_raw = env.get("SKEWNONO_TOOL_SUBNETS", "").strip()
    subnets = [s.strip() for s in subnets_raw.split(",") if s.strip()]
    return ImageConfig(
        ftp_user=env.get("SKEWNONO_TOOL_FTP_USER", "").strip() or "hitachi",
        ftp_password=env.get("SKEWNONO_TOOL_FTP_PASSWORD", "").strip() or "hid",
        ftp_port=_int(env, "SKEWNONO_TOOL_FTP_PORT", 21),
        ftp_concurrency=_int(env, "SKEWNONO_TOOL_FTP_CONCURRENCY", 6),
        ftp_timeout=float(env.get("SKEWNONO_TOOL_FTP_TIMEOUT", "8") or 8),
        allowed_subnets=subnets,
        cache_dir=env.get("IMAGE_CACHE_DIR", "").strip() or "var/image_cache",
        cache_bucket=env.get("SKEWNONO_IMAGE_CACHE_BUCKET", "").strip() or None,
        cache_prefix=env.get("SKEWNONO_IMAGE_CACHE_PREFIX", "").strip() or "image_cache/",
        ttl_hours=_int(env, "IMAGE_CACHE_TTL_HOURS", 72),
        purge_hour=_int(env, "IMAGE_CACHE_PURGE_HOUR", 3),
        job_ttl=_int(env, "SKEWNONO_MSR_IMAGE_JOB_TTL", 3600),
        max_jobs=_int(env, "SKEWNONO_MSR_IMAGE_MAX_JOBS", 2),
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_config.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_image/config.py back_dev_home/msr_image/tests/test_config.py
git commit -m "feat(msr_image): env-driven ImageConfig"
```

---

## Task 3: Disk cache backend

**Files:**
- Create: `back_dev_home/msr_image/cache.py`
- Test: `back_dev_home/msr_image/tests/test_disk_cache.py`

**Interfaces:**
- Consumes: `ImageLocator`, `FetchedImage` (Task 1); `ImageConfig` (Task 2).
- Produces:
  - `ImageCache` `Protocol`: `get(locator) -> FetchedImage | None`, `put(locator, fetched) -> None`, `purge(ttl_hours: int) -> int`.
  - `DiskImageCache(root: str)`.
  - `cache_key(locator) -> str` (module function) → `"{eqp_ip}/{class_name}/{msr}/{name}"`.

- [ ] **Step 1: Write the failing test**

`back_dev_home/msr_image/tests/test_disk_cache.py`:

```python
import os
import time

from back_dev_home.msr_image.cache import DiskImageCache, cache_key
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator

LOC = ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg")
IMG = FetchedImage(b"\xff\xd8jpegbytes", "image/jpeg", "mag=50000\nvac=0.8")


def test_key_is_deterministic():
    assert cache_key(LOC) == "10.0.0.1/ADI/MSR_1/shot01.jpeg"


def test_miss_returns_none(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    assert cache.get(LOC) is None


def test_put_then_get_roundtrips_bytes_type_and_cond(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    cache.put(LOC, IMG)
    got = cache.get(LOC)
    assert got == IMG


def test_put_without_cond_roundtrips(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    no_cond = FetchedImage(b"abc", "image/jpeg", None)
    cache.put(LOC, no_cond)
    assert cache.get(LOC) == no_cond


def test_purge_deletes_old_keeps_fresh(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    cache.put(LOC, IMG)
    # Age the image file 100h into the past.
    key_file = tmp_path / "10.0.0.1" / "ADI" / "MSR_1" / "shot01.jpeg"
    old = time.time() - 100 * 3600
    os.utime(key_file, (old, old))
    assert cache.purge(ttl_hours=72) == 1
    assert cache.get(LOC) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_disk_cache.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

`back_dev_home/msr_image/cache.py`:

```python
"""ImageCache interface + disk backend. MinIO backend is added in Task 11.

Cache key mirrors the semantic locator so on-disk paths are inspectable:
``{eqp_ip}/{class_name}/{msr}/{name}``. The image body lives at that path; its
content-type and cond travel as tiny sidecars (``<file>.type`` / ``<file>.cond``)
so a bytes-only medium needs no metadata channel.
"""

import os
import time
from pathlib import Path
from typing import Protocol

from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator


def cache_key(locator: ImageLocator) -> str:
    return f"{locator.eqp_ip}/{locator.class_name}/{locator.msr}/{locator.name}"


class ImageCache(Protocol):
    def get(self, locator: ImageLocator) -> FetchedImage | None: ...
    def put(self, locator: ImageLocator, fetched: FetchedImage) -> None: ...
    def purge(self, ttl_hours: int) -> int: ...


class DiskImageCache:
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _path(self, locator: ImageLocator) -> Path:
        return self.root / cache_key(locator)

    def get(self, locator: ImageLocator) -> FetchedImage | None:
        path = self._path(locator)
        if not path.is_file():
            return None
        data = path.read_bytes()
        type_file = path.with_name(path.name + ".type")
        cond_file = path.with_name(path.name + ".cond")
        content_type = (
            type_file.read_text(encoding="utf-8") if type_file.is_file() else "application/octet-stream"
        )
        cond = cond_file.read_text(encoding="utf-8") if cond_file.is_file() else None
        return FetchedImage(data, content_type, cond)

    def put(self, locator: ImageLocator, fetched: FetchedImage) -> None:
        path = self._path(locator)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetched.data)
        path.with_name(path.name + ".type").write_text(fetched.content_type, encoding="utf-8")
        cond_file = path.with_name(path.name + ".cond")
        if fetched.cond is not None:
            cond_file.write_text(fetched.cond, encoding="utf-8")
        elif cond_file.exists():
            cond_file.unlink()

    def purge(self, ttl_hours: int) -> int:
        cutoff = time.time() - ttl_hours * 3600
        removed = 0
        if not self.root.exists():
            return 0
        for path in self.root.rglob("*"):
            if not path.is_file() or path.name.endswith((".type", ".cond")):
                continue
            if path.stat().st_mtime < cutoff:
                for sidecar in (path, path.with_name(path.name + ".type"), path.with_name(path.name + ".cond")):
                    if sidecar.exists():
                        sidecar.unlink()
                removed += 1
        return removed
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_disk_cache.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_image/cache.py back_dev_home/msr_image/tests/test_disk_cache.py
git commit -m "feat(msr_image): ImageCache protocol + DiskImageCache"
```

---

## Task 4: Mock provider (offline byte source)

**Files:**
- Create: `back_dev_home/msr_image/providers/mock.py`
- Test: `back_dev_home/msr_image/tests/test_mock_provider.py`

**Interfaces:**
- Consumes: `ImageLocator`, `FetchedImage` (Task 1).
- Produces (the `ImageSource` shape every provider implements):
  - `list_images(eqp_ip: str, class_name: str, msr: str) -> list[str]`
  - `fetch_image(locator: ImageLocator) -> FetchedImage`
  - `download_all(eqp_ip, class_name, msr, names: list[str], on_file, concurrency: int) -> None` where `on_file(name: str, fetched: FetchedImage | None, error: str | None) -> None`.

- [ ] **Step 1: Write the failing test**

`back_dev_home/msr_image/tests/test_mock_provider.py`:

```python
from back_dev_home.msr_image.contracts import ImageLocator
from back_dev_home.msr_image.providers import mock


def test_list_is_deterministic_and_jpeg():
    a = mock.list_images("10.0.0.1", "ADI", "MSR_1")
    b = mock.list_images("10.0.0.1", "ADI", "MSR_1")
    assert a == b
    assert len(a) >= 1
    assert all(n.endswith(".jpeg") for n in a)


def test_fetch_returns_svg_and_synthetic_cond():
    name = mock.list_images("10.0.0.1", "ADI", "MSR_1")[0]
    img = mock.fetch_image(ImageLocator("10.0.0.1", "ADI", "MSR_1", name))
    assert img.content_type == "image/svg+xml"
    assert b"<svg" in img.data
    assert img.cond and "mag" in img.cond.lower()


def test_download_all_invokes_callback_per_name():
    names = mock.list_images("10.0.0.1", "ADI", "MSR_1")
    seen = []
    mock.download_all(
        "10.0.0.1", "ADI", "MSR_1", names,
        on_file=lambda n, f, e: seen.append((n, f is not None, e)),
        concurrency=4,
    )
    assert sorted(n for n, _, _ in seen) == sorted(names)
    assert all(ok and err is None for _, ok, err in seen)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_mock_provider.py -v`
Expected: FAIL — `mock` has no `list_images`.

- [ ] **Step 3: Write the implementation**

`back_dev_home/msr_image/providers/mock.py`:

```python
"""Offline byte source: deterministic SVG placeholders + synthetic listing/cond.

Seeded from the locator so the same MSR always yields the same gallery. Lets the
whole flow (list → serve → cond → download-all → cache → purge) run with no tool,
no OpenSearch, no MinIO.
"""

import hashlib
from collections.abc import Callable

from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator

OnFile = Callable[[str, FetchedImage | None, str | None], None]


def _seed(*parts: str) -> int:
    return int(hashlib.md5("|".join(parts).encode()).hexdigest(), 16)


def list_images(eqp_ip: str, class_name: str, msr: str) -> list[str]:
    count = 3 + _seed(eqp_ip, class_name, msr) % 6  # 3..8 images
    return [f"{msr}_shot{i:02d}.jpeg" for i in range(1, count + 1)]


def _svg(locator: ImageLocator) -> bytes:
    hue = _seed(locator.name) % 360
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240">'
        f'<rect width="240" height="240" fill="hsl({hue},60%,45%)"/>'
        f'<text x="12" y="128" fill="white" font-size="14">{locator.msr}</text>'
        f'<text x="12" y="150" fill="white" font-size="12">{locator.name}</text>'
        f"</svg>"
    ).encode()


def _cond(locator: ImageLocator) -> str:
    s = _seed(locator.name)
    return f"mag={30000 + s % 40000}\nvac={0.5 + (s % 5) / 10:.1f}\npixel={2 + s % 6}nm"


def fetch_image(locator: ImageLocator) -> FetchedImage:
    return FetchedImage(_svg(locator), "image/svg+xml", _cond(locator))


def download_all(
    eqp_ip: str,
    class_name: str,
    msr: str,
    names: list[str],
    on_file: OnFile,
    concurrency: int = 6,
) -> None:
    # Mock is CPU-only; no need for a pool. Match the office callback contract.
    for name in names:
        loc = ImageLocator(eqp_ip, class_name, msr, name)
        on_file(name, fetch_image(loc), None)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_mock_provider.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_image/providers/mock.py back_dev_home/msr_image/tests/test_mock_provider.py
git commit -m "feat(msr_image): mock provider — SVG + synthetic listing/cond"
```

---

## Task 5: Data seam (`data.py`) + cache factory

**Files:**
- Create: `back_dev_home/msr_image/data.py`
- Modify: `back_dev_home/msr_image/cache.py` (add `make_cache`)
- Test: `back_dev_home/msr_image/tests/test_data_seam.py`

**Interfaces:**
- Consumes: `get_data_provider` (`back_dev_home/_runtime/data_provider.py`), `mock` provider (Task 4), `ImageConfig`/`load_config` (Task 2), `DiskImageCache` (Task 3).
- Produces:
  - `data.list_images`, `data.fetch_image`, `data.download_all` — dispatch to the resolved provider.
  - `cache.make_cache(cfg: ImageConfig, provider: str) -> ImageCache` — `DiskImageCache` for mock, `MinioImageCache` for office (MinIO backend lands in Task 11; until then office raises `NotImplementedError` from `make_cache`, unreachable in home tests).

- [ ] **Step 1: Write the failing test**

`back_dev_home/msr_image/tests/test_data_seam.py`:

```python
from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import DiskImageCache, make_cache
from back_dev_home.msr_image.config import load_config


def test_mock_provider_dispatch(monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    names = data.list_images("10.0.0.1", "ADI", "MSR_1")
    assert names and all(n.endswith(".jpeg") for n in names)


def test_make_cache_mock_is_disk(tmp_path):
    cfg = load_config({"IMAGE_CACHE_DIR": str(tmp_path)})
    cache = make_cache(cfg, provider="mock")
    assert isinstance(cache, DiskImageCache)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_data_seam.py -v`
Expected: FAIL — `data` / `make_cache` missing.

- [ ] **Step 3: Write the implementation**

Add to `back_dev_home/msr_image/cache.py`:

```python
def make_cache(cfg, provider: str):
    """Pick the cache backend that matches the byte source.

    ``cfg`` is an ImageConfig (typed loosely to avoid a config import cycle).
    """
    if provider == "office":
        from back_dev_home.msr_image.minio_cache import MinioImageCache
        return MinioImageCache(
            bucket=cfg.cache_bucket, prefix=cfg.cache_prefix
        )
    return DiskImageCache(cfg.cache_dir)
```

`back_dev_home/msr_image/data.py`:

```python
"""Stable msr_image data seam. Picks mock/office via get_data_provider."""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator
from back_dev_home.msr_image.providers import mock as mock_provider


def provider_name() -> str:
    return "office" if get_data_provider("msr_image") == "office" else "mock"


def _provider():
    if provider_name() == "office":
        from back_dev_home.msr_image.providers import office
        return office
    return mock_provider


def list_images(eqp_ip: str, class_name: str, msr: str) -> list[str]:
    return _provider().list_images(eqp_ip, class_name, msr)


def fetch_image(locator: ImageLocator) -> FetchedImage:
    return _provider().fetch_image(locator)


def download_all(eqp_ip, class_name, msr, names, on_file, concurrency=6) -> None:
    _provider().download_all(eqp_ip, class_name, msr, names, on_file, concurrency)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_data_seam.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_image/data.py back_dev_home/msr_image/cache.py \
  back_dev_home/msr_image/tests/test_data_seam.py
git commit -m "feat(msr_image): data seam + cache factory"
```

---

## Task 6: Routes — list + per-image serve (with cond header)

**Files:**
- Create: `back_dev_home/msr_image/routes.py`
- Test: `back_dev_home/msr_image/tests/test_routes_serve.py`

**Interfaces:**
- Consumes: `data.list_images`/`fetch_image`/`provider_name` (Task 5), `make_cache` (Task 5), `load_config` (Task 2), `validate_tool_ip` (Task 1), error hierarchy (Task 1), `ImageLocator`/`ImageListResponse` (Task 1).
- Produces: Flask blueprint `bp` with `GET /msr-images` (list) and `GET /msr-image` (serve). Serve sets `X-Msr-Cond` (URL-encoded) when cond present, `Cache-Control: public, max-age=3600`. `POST /msr-images` + `GET /msr-images/<job_id>` are added in Task 8 (same blueprint).

- [ ] **Step 1: Write the failing test**

`back_dev_home/msr_image/tests/test_routes_serve.py`:

```python
from urllib.parse import unquote

import pytest
from flask import Flask

from back_dev_home.msr_image.routes import bp


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    monkeypatch.setenv("IMAGE_CACHE_DIR", str(tmp_path))
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")
    return app.test_client()


def test_list_returns_names(client):
    r = client.get("/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1")
    assert r.status_code == 200
    body = r.get_json()
    assert body["msr"] == "MSR_1"
    assert body["total"] == len(body["images"])
    assert all(n.endswith(".jpeg") for n in body["images"])


def test_serve_returns_svg_with_cond_header(client):
    names = client.get(
        "/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    ).get_json()["images"]
    r = client.get(
        f"/api/msr-image?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&name={names[0]}"
    )
    assert r.status_code == 200
    assert r.mimetype == "image/svg+xml"
    assert b"<svg" in r.data
    assert "mag" in unquote(r.headers["X-Msr-Cond"]).lower()


def test_serve_second_hit_is_cached(client):
    q = "eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    name = client.get(f"/api/msr-images?{q}").get_json()["images"][0]
    url = f"/api/msr-image?{q}&name={name}"
    assert client.get(url).status_code == 200
    assert client.get(url).status_code == 200  # served from disk cache


def test_missing_params_400(client):
    assert client.get("/api/msr-image?eqp_ip=10.0.0.1&name=x.jpeg").status_code == 400


def test_bad_ip_400(client):
    r = client.get("/api/msr-images?eqp_ip=nope&class_name=ADI&msr=MSR_1")
    assert r.status_code == 400
    assert r.get_json()["code"] == "invalid_tool_ip"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_routes_serve.py -v`
Expected: FAIL — `routes` missing.

- [ ] **Step 3: Write the implementation**

`back_dev_home/msr_image/routes.py`:

```python
"""msr_image blueprint. Phase-agnostic: assembles locators, delegates bytes to
the data seam, caches, and relays. Office knowledge is only in providers/office."""

from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import make_cache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import ImageListResponse, ImageLocator
from back_dev_home.msr_image.errors import MsrImageError
from back_dev_home.msr_image.paths import validate_tool_ip

bp = Blueprint("msr_image", __name__)


def _error(exc: MsrImageError):
    return jsonify({"error": str(exc) or exc.code, "code": exc.code}), exc.status


def _require(*names: str) -> dict[str, str] | None:
    out = {}
    for n in names:
        v = (request.args.get(n) or "").strip()
        if not v:
            return None
        out[n] = v
    return out


@bp.get("/msr-images")
def list_images_route():
    args = _require("eqp_ip", "class_name", "msr")
    if args is None:
        return jsonify({"error": "eqp_ip, class_name, msr are required"}), 400
    cfg = load_config()
    try:
        validate_tool_ip(args["eqp_ip"], cfg.allowed_subnets)
        names = data.list_images(args["eqp_ip"], args["class_name"], args["msr"])
    except MsrImageError as exc:
        return _error(exc)
    body: ImageListResponse = {
        "msr": args["msr"],
        "class_name": args["class_name"],
        "images": names,
        "total": len(names),
    }
    return jsonify(body)


@bp.get("/msr-image")
def serve_image_route():
    args = _require("eqp_ip", "class_name", "msr", "name")
    if args is None:
        return jsonify({"error": "eqp_ip, class_name, msr, name are required"}), 400
    if len(args["name"]) > 256:
        return jsonify({"error": "name too long"}), 400
    cfg = load_config()
    try:
        validate_tool_ip(args["eqp_ip"], cfg.allowed_subnets)
    except MsrImageError as exc:
        return _error(exc)

    locator = ImageLocator(args["eqp_ip"], args["class_name"], args["msr"], args["name"])
    cache = make_cache(cfg, data.provider_name())
    fetched = cache.get(locator)
    if fetched is None:
        try:
            fetched = data.fetch_image(locator)
        except MsrImageError as exc:
            return _error(exc)
        cache.put(locator, fetched)

    headers = {"Cache-Control": "public, max-age=3600"}
    if fetched.cond is not None:
        headers["X-Msr-Cond"] = quote(fetched.cond)
    return Response(fetched.data, mimetype=fetched.content_type, headers=headers)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_routes_serve.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_image/routes.py back_dev_home/msr_image/tests/test_routes_serve.py
git commit -m "feat(msr_image): list + serve routes with X-Msr-Cond header"
```

---

## Task 7: Job registry (memory + Redis)

**Files:**
- Create: `back_dev_home/msr_image/jobs.py`
- Test: `back_dev_home/msr_image/tests/test_jobs.py`

**Interfaces:**
- Consumes: `DownloadJobStatus`, `DownloadFailure` (Task 1).
- Produces:
  - `JobRegistry` `Protocol`: `create(total: int) -> str`, `get(job_id) -> DownloadJobStatus | None`, `record_ok(job_id) -> None`, `record_failure(job_id, name, error) -> None`, `finish(job_id) -> None`.
  - `MemoryJobRegistry()` — thread-safe, in-process.
  - `make_registry(cfg) -> JobRegistry` — memory now; Redis wired in Task 8's app context if `REDIS_*` present (memory is the default and the only one exercised offline).
  - Job ids are generated without `random`/`Date.now` here — use `uuid.uuid4()` (allowed; not the banned `Math.random`/`Date.now` JS shim, this is Python).

- [ ] **Step 1: Write the failing test**

`back_dev_home/msr_image/tests/test_jobs.py`:

```python
import threading

from back_dev_home.msr_image.jobs import MemoryJobRegistry


def test_lifecycle_counts():
    reg = MemoryJobRegistry()
    jid = reg.create(total=3)
    st = reg.get(jid)
    assert st["status"] == "running" and st["total"] == 3 and st["done"] == 0

    reg.record_ok(jid)
    reg.record_failure(jid, "bad.jpeg", "timeout")
    reg.record_ok(jid)
    reg.finish(jid)

    st = reg.get(jid)
    assert st["status"] == "done"
    assert st["done"] == 3 and st["ok"] == 2 and st["ng"] == 1
    assert st["failures"] == [{"name": "bad.jpeg", "error": "timeout"}]


def test_unknown_job_is_none():
    assert MemoryJobRegistry().get("nope") is None


def test_concurrent_increments_are_atomic():
    reg = MemoryJobRegistry()
    jid = reg.create(total=200)

    def worker():
        for _ in range(100):
            reg.record_ok(jid)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert reg.get(jid)["done"] == 200 and reg.get(jid)["ok"] == 200
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_jobs.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the implementation**

`back_dev_home/msr_image/jobs.py`:

```python
"""Download-all job state. We own the observable state (memory at home / single
worker; Redis keys across office workers); ftp_handler/threads only execute."""

import threading
import uuid
from typing import Protocol

from back_dev_home.msr_image.contracts import DownloadJobStatus


class JobRegistry(Protocol):
    def create(self, total: int) -> str: ...
    def get(self, job_id: str) -> DownloadJobStatus | None: ...
    def record_ok(self, job_id: str) -> None: ...
    def record_failure(self, job_id: str, name: str, error: str) -> None: ...
    def finish(self, job_id: str) -> None: ...


class MemoryJobRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, DownloadJobStatus] = {}

    def create(self, total: int) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "done": 0,
                "total": total,
                "ok": 0,
                "ng": 0,
                "failures": [],
            }
        return job_id

    def get(self, job_id: str) -> DownloadJobStatus | None:
        with self._lock:
            st = self._jobs.get(job_id)
            return dict(st) if st is not None else None  # copy: caller can't mutate state

    def record_ok(self, job_id: str) -> None:
        with self._lock:
            st = self._jobs.get(job_id)
            if st is not None:
                st["done"] += 1
                st["ok"] += 1

    def record_failure(self, job_id: str, name: str, error: str) -> None:
        with self._lock:
            st = self._jobs.get(job_id)
            if st is not None:
                st["done"] += 1
                st["ng"] += 1
                st["failures"].append({"name": name, "error": error})

    def finish(self, job_id: str) -> None:
        with self._lock:
            st = self._jobs.get(job_id)
            if st is not None:
                st["status"] = "done"


_DEFAULT_REGISTRY = MemoryJobRegistry()


def default_registry() -> MemoryJobRegistry:
    """Process-wide registry so route handlers and the worker thread share state."""
    return _DEFAULT_REGISTRY
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_jobs.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_image/jobs.py back_dev_home/msr_image/tests/test_jobs.py
git commit -m "feat(msr_image): thread-safe in-memory job registry"
```

Note: Redis-backed registry (office multi-worker) is deferred to office execution — `default_registry()` (memory) is correct for home and single-worker. `MIGRATION.md` (Task 15) records the Redis wiring as an office follow-up; the interface above is what the Redis impl must satisfy.

---

## Task 8: Download-all routes + worker

**Files:**
- Modify: `back_dev_home/msr_image/routes.py`
- Test: `back_dev_home/msr_image/tests/test_routes_download.py`

**Interfaces:**
- Consumes: `data.download_all` (Task 5), `make_cache` (Task 5), `default_registry` (Task 7), `load_config` (Task 2).
- Produces: `POST /msr-images` → `202 {"job_id": ...}`; `GET /msr-images/<job_id>` → `DownloadJobStatus` or 404. The worker runs in a background thread, writes each fetched image to the cache, and updates the registry per file.

- [ ] **Step 1: Write the failing test**

`back_dev_home/msr_image/tests/test_routes_download.py`:

```python
import time

import pytest
from flask import Flask

from back_dev_home.msr_image.cache import DiskImageCache
from back_dev_home.msr_image.contracts import ImageLocator
from back_dev_home.msr_image.routes import bp


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    monkeypatch.setenv("IMAGE_CACHE_DIR", str(tmp_path))
    application = Flask(__name__)
    application.register_blueprint(bp, url_prefix="/api")
    application.config["_cache_dir"] = str(tmp_path)
    return application


def _wait_done(client, job_id, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        st = client.get(f"/api/msr-images/{job_id}").get_json()
        if st["status"] == "done":
            return st
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_download_all_starts_and_completes(app):
    client = app.test_client()
    r = client.post("/api/msr-images", json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"})
    assert r.status_code == 202
    job_id = r.get_json()["job_id"]

    st = _wait_done(client, job_id)
    assert st["total"] == st["done"] == st["ok"] and st["ng"] == 0

    # Every image is now in the cache; a subsequent serve is a cache hit.
    cache = DiskImageCache(app.config["_cache_dir"])
    first = client.get("/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1").get_json()["images"][0]
    assert cache.get(ImageLocator("10.0.0.1", "ADI", "MSR_1", first)) is not None


def test_unknown_job_404(app):
    assert app.test_client().get("/api/msr-images/deadbeef").status_code == 404


def test_download_missing_body_400(app):
    assert app.test_client().post("/api/msr-images", json={"eqp_ip": "10.0.0.1"}).status_code == 400


def test_bad_ip_400(app):
    r = app.test_client().post("/api/msr-images", json={"eqp_ip": "nope", "class_name": "ADI", "msr": "MSR_1"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_routes_download.py -v`
Expected: FAIL — `POST /msr-images` returns 405 (route missing).

- [ ] **Step 3: Write the implementation**

Append to `back_dev_home/msr_image/routes.py` (add imports at top: `import threading`, `from back_dev_home.msr_image import data` already present, `from back_dev_home.msr_image.jobs import default_registry`, `from back_dev_home.msr_image.contracts import ImageLocator` already present):

```python
def _run_download(app, eqp_ip, class_name, msr, names, job_id):
    cfg = load_config()
    cache = make_cache(cfg, data.provider_name())
    registry = default_registry()

    def on_file(name, fetched, error):
        if fetched is not None:
            cache.put(ImageLocator(eqp_ip, class_name, msr, name), fetched)
            registry.record_ok(job_id)
        else:
            registry.record_failure(job_id, name, error or "unknown error")

    try:
        data.download_all(eqp_ip, class_name, msr, names, on_file, cfg.ftp_concurrency)
    finally:
        registry.finish(job_id)


@bp.post("/msr-images")
def download_all_route():
    payload = request.get_json(silent=True) or {}
    eqp_ip = str(payload.get("eqp_ip") or "").strip()
    class_name = str(payload.get("class_name") or "").strip()
    msr = str(payload.get("msr") or "").strip()
    if not (eqp_ip and class_name and msr):
        return jsonify({"error": "eqp_ip, class_name, msr are required"}), 400

    cfg = load_config()
    try:
        validate_tool_ip(eqp_ip, cfg.allowed_subnets)
        names = data.list_images(eqp_ip, class_name, msr)
    except MsrImageError as exc:
        return _error(exc)

    registry = default_registry()
    job_id = registry.create(total=len(names))
    thread = threading.Thread(
        target=_run_download,
        args=(None, eqp_ip, class_name, msr, names, job_id),
        daemon=True,
    )
    thread.start()
    return jsonify({"job_id": job_id}), 202


@bp.get("/msr-images/<job_id>")
def poll_job_route(job_id: str):
    st = default_registry().get(job_id)
    if st is None:
        return jsonify({"error": "unknown job", "code": "unknown_job"}), 404
    return jsonify(st)
```

Add the two new imports at the top of the file:

```python
import threading

from back_dev_home.msr_image.jobs import default_registry
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_routes_download.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the whole msr_image suite**

Run: `.venv/bin/pytest back_dev_home/msr_image/ -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/msr_image/routes.py back_dev_home/msr_image/tests/test_routes_download.py
git commit -m "feat(msr_image): async download-all job routes + worker"
```

---

## Task 9: Cache purge scheduler

**Files:**
- Create: `back_dev_home/msr_image/scheduler.py`
- Modify: `back_dev_home/requirements.txt`
- Test: `back_dev_home/msr_image/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `make_cache` (Task 5), `load_config` (Task 2), `data.provider_name` (Task 5).
- Produces: `purge_now(cfg=None) -> int` (purges the active cache; used by tests and the cron) and `start_purge_scheduler(app) -> BackgroundScheduler | None` (registers a daily cron at `cfg.purge_hour`).

- [ ] **Step 1: Add the dependency**

Append to `back_dev_home/requirements.txt`:

```text
apscheduler>=3.10
```

Run: `.venv/bin/pip install 'apscheduler>=3.10'`

- [ ] **Step 2: Write the failing test**

`back_dev_home/msr_image/tests/test_scheduler.py`:

```python
import os
import time

from back_dev_home.msr_image.cache import DiskImageCache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator
from back_dev_home.msr_image.scheduler import purge_now


def test_purge_now_removes_expired(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    cfg = load_config({"IMAGE_CACHE_DIR": str(tmp_path), "IMAGE_CACHE_TTL_HOURS": "72"})
    cache = DiskImageCache(str(tmp_path))
    loc = ImageLocator("10.0.0.1", "ADI", "MSR_1", "a.jpeg")
    cache.put(loc, FetchedImage(b"x", "image/jpeg", None))
    aged = tmp_path / "10.0.0.1" / "ADI" / "MSR_1" / "a.jpeg"
    old = time.time() - 100 * 3600
    os.utime(aged, (old, old))

    assert purge_now(cfg) == 1
    assert cache.get(loc) is None
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_scheduler.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Write the implementation**

`back_dev_home/msr_image/scheduler.py`:

```python
"""Nightly cache purge. Home deletes disk files; office sweeps the MinIO cache
prefix by last_modified (MinioImageCache.purge). Duplicate runs are idempotent."""

import logging

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import make_cache
from back_dev_home.msr_image.config import ImageConfig, load_config

logger = logging.getLogger(__name__)


def purge_now(cfg: ImageConfig | None = None) -> int:
    cfg = cfg or load_config()
    cache = make_cache(cfg, data.provider_name())
    removed = cache.purge(cfg.ttl_hours)
    logger.info("msr_image cache purge removed %d objects", removed)
    return removed


def start_purge_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler

    cfg = load_config()
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        purge_now,
        trigger="cron",
        hour=cfg.purge_hour,
        id="msr_image_cache_purge",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    app.extensions["msr_image_scheduler"] = scheduler
    return scheduler
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_scheduler.py -v`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/msr_image/scheduler.py back_dev_home/requirements.txt \
  back_dev_home/msr_image/tests/test_scheduler.py
git commit -m "feat(msr_image): nightly cache purge scheduler"
```

---

## Task 10: Remove image code from msr_file

**Files:**
- Modify: `back_dev_home/msr_file/routes.py:31-52` (delete `msr_image` route)
- Modify: `back_dev_home/msr_file/data.py` (delete `get_msr_image` façade + cache_clear line)
- Modify: `back_dev_home/msr_file/providers/mock.py` (delete `get_msr_image`)
- Modify: `back_dev_home/msr_file/providers/office_example.py:448-453` (delete `get_msr_image` + remove from `__all__`)
- Test: existing `back_dev_home/msr_file/tests/` must still pass.

**Interfaces:**
- Consumes: nothing new.
- Produces: `msr_file` no longer exposes any image endpoint/function. `/api/msr-file` and `/api/msr-files` unchanged.

- [ ] **Step 1: Find every image reference in msr_file**

Run: `grep -rnE "msr.image|get_msr_image|msr_image" back_dev_home/msr_file/`
Expected: references in `routes.py`, `data.py`, `providers/mock.py`, `providers/office_example.py`, and possibly `tests/`.

- [ ] **Step 2: Delete the `msr-image` route**

In `back_dev_home/msr_file/routes.py`, remove the entire `@bp.get("/msr-image")` function (the `msr_image` view, lines ~31–52) and drop `get_msr_image` from the `from back_dev_home.msr_file.data import ...` line.

- [ ] **Step 3: Delete the data façade**

In `back_dev_home/msr_file/data.py`, remove `get_msr_image` from `__all__`, delete the `def get_msr_image(...)` function, and delete the line `get_msr_image.cache_clear = mock_provider.get_msr_image.cache_clear`.

- [ ] **Step 4: Delete the provider implementations**

In `back_dev_home/msr_file/providers/mock.py`, delete the `get_msr_image` function (and its cache decorator, if any) and remove it from that module's `__all__`. In `back_dev_home/msr_file/providers/office_example.py`, delete the `def get_msr_image(*args, **kwargs)` stub (lines ~448–453) and remove `"get_msr_image"` from `__all__`.

- [ ] **Step 5: Update or remove msr_file image tests**

Run: `grep -rnE "msr.image|get_msr_image" back_dev_home/msr_file/tests/`
For each hit, delete the test function that exercised the old image endpoint/SVG (that behavior now lives in `msr_image`). Do not weaken measurement-data tests.

- [ ] **Step 6: Run the msr_file suite**

Run: `.venv/bin/pytest back_dev_home/msr_file/ -v`
Expected: PASS with no image references remaining.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/msr_file/
git commit -m "refactor(msr_file): remove image endpoint (moved to msr_image feature)"
```

---

## Task 11: MinIO cache backend (office)

**Files:**
- Create: `back_dev_home/msr_image/minio_cache.py`
- Test: `back_dev_home/msr_image/tests/test_minio_cache.py`

**Interfaces:**
- Consumes: `ImageLocator`, `FetchedImage` (Task 1); `cache_key` (Task 3).
- Produces: `MinioImageCache(bucket, prefix, client_factory=None)` satisfying `ImageCache`. Lazy-imports `minio_handler`. cond + content-type ride as MinIO user metadata (`x-msr-cond` url-encoded, `x-msr-content-type`). `purge(ttl_hours)` lists the cache prefix and deletes objects whose `last_modified` is older than the cutoff (NOT `delete_older_than`, which is date-folder based).

- [ ] **Step 1: Write the failing test (with a fake MinioObject)**

`back_dev_home/msr_image/tests/test_minio_cache.py`:

```python
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, unquote

from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator
from back_dev_home.msr_image.minio_cache import MinioImageCache

LOC = ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg")
IMG = FetchedImage(b"\xff\xd8jpeg", "image/jpeg", "mag=50000")


class _Stat:
    def __init__(self, metadata, last_modified):
        self.metadata = metadata
        self.last_modified = last_modified


class _Obj:
    def __init__(self, object_name, last_modified):
        self.object_name = object_name
        self.last_modified = last_modified


class FakeMinio:
    """In-memory stand-in for minio_handler.MinioObject (only what we use)."""

    def __init__(self):
        self.store = {}  # key -> (bytes, metadata, last_modified)

    def put(self, key, data, *, content_type="application/octet-stream", metadata=None, **kw):
        self.store[key] = (bytes(data), dict(metadata or {}), datetime.now(timezone.utc))

    def exists(self, key, **kw):
        return key in self.store

    def get(self, key, **kw):
        return self.store[key][0]

    def stat(self, key, **kw):
        _, metadata, lm = self.store[key]
        # minio returns user metadata with an x-amz-meta- prefix; emulate it.
        prefixed = {f"x-amz-meta-{k}": v for k, v in metadata.items()}
        return _Stat(prefixed, lm)

    def list(self, prefix=None, *, recursive=True, **kw):
        for key, (_, _, lm) in list(self.store.items()):
            yield _Obj(key, lm)

    def delete_many(self, keys, **kw):
        for k in keys:
            self.store.pop(k, None)
        return []


def _cache():
    fake = FakeMinio()
    return MinioImageCache(bucket="b", prefix="image_cache/", client_factory=lambda: fake), fake


def test_miss_returns_none():
    cache, _ = _cache()
    assert cache.get(LOC) is None


def test_put_then_get_roundtrips_with_metadata():
    cache, fake = _cache()
    cache.put(LOC, IMG)
    key = "image_cache/10.0.0.1/ADI/MSR_1/shot01.jpeg"
    assert key in fake.store
    assert fake.store[key][1]["x-msr-cond"] == quote("mag=50000")
    got = cache.get(LOC)
    assert got.data == IMG.data
    assert got.content_type == "image/jpeg"
    assert got.cond == "mag=50000"


def test_shared_hit_across_instances():
    cache_a, fake = _cache()
    cache_a.put(LOC, IMG)
    cache_b = MinioImageCache(bucket="b", prefix="image_cache/", client_factory=lambda: fake)
    assert cache_b.get(LOC).data == IMG.data


def test_purge_deletes_expired_by_last_modified():
    cache, fake = _cache()
    cache.put(LOC, IMG)
    key = "image_cache/10.0.0.1/ADI/MSR_1/shot01.jpeg"
    data, meta, _ = fake.store[key]
    fake.store[key] = (data, meta, datetime.now(timezone.utc) - timedelta(hours=100))
    assert cache.purge(ttl_hours=72) == 1
    assert cache.get(LOC) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_minio_cache.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the implementation**

`back_dev_home/msr_image/minio_cache.py`:

```python
"""Shared MinIO cache for office. Any worker/user reads what any other wrote.

cond + content-type ride as MinIO user metadata (small; cond.txt is a few
lines). Expiry is a last_modified sweep over the cache prefix — minio_handler's
delete_older_than is date-folder based and would fight a content-addressed key,
so we list + delete_many instead.
"""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, unquote

from back_dev_home.msr_image.cache import cache_key
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator

_COND_META = "x-msr-cond"
_TYPE_META = "x-msr-content-type"


def _default_client(bucket, prefix):
    # Lazy: office-only dependency, keeps home boot free of minio_handler.
    from minio_handler import MinioObject

    client = MinioObject()
    if bucket:
        client = client.use_bucket(bucket)
    return client.use_prefix(prefix)


class MinioImageCache:
    def __init__(self, bucket, prefix="image_cache/", client_factory: Callable[[], object] | None = None):
        self.bucket = bucket
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"
        self._factory = client_factory or (lambda: _default_client(bucket, self.prefix))
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = self._factory()
        return self._client

    def _key(self, locator: ImageLocator) -> str:
        return f"{self.prefix}{cache_key(locator)}"

    def get(self, locator: ImageLocator) -> FetchedImage | None:
        key = self._key(locator)
        if not self.client.exists(key):
            return None
        data = self.client.get(key)
        stat = self.client.stat(key)
        meta = _user_metadata(stat)
        cond_raw = meta.get(_COND_META)
        content_type = meta.get(_TYPE_META, "application/octet-stream")
        return FetchedImage(data, content_type, unquote(cond_raw) if cond_raw else None)

    def put(self, locator: ImageLocator, fetched: FetchedImage) -> None:
        metadata = {_TYPE_META: fetched.content_type}
        if fetched.cond is not None:
            metadata[_COND_META] = quote(fetched.cond)
        self.client.put(
            self._key(locator),
            fetched.data,
            content_type=fetched.content_type,
            metadata=metadata,
        )

    def purge(self, ttl_hours: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        stale = [
            obj.object_name
            for obj in self.client.list(prefix=self.prefix, recursive=True)
            if _as_utc(obj.last_modified) < cutoff
        ]
        if not stale:
            return 0
        self.client.delete_many(stale)
        return len(stale)


def _user_metadata(stat) -> dict[str, str]:
    """Strip the ``x-amz-meta-`` prefix MinIO adds to user metadata keys."""
    raw = getattr(stat, "metadata", {}) or {}
    out = {}
    for key, value in raw.items():
        lk = key.lower()
        out[lk[len("x-amz-meta-"):] if lk.startswith("x-amz-meta-") else lk] = value
    return out


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_minio_cache.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_image/minio_cache.py back_dev_home/msr_image/tests/test_minio_cache.py
git commit -m "feat(msr_image): shared MinIO cache backend with metadata cond + sweep"
```

---

## Task 12: App-factory wiring

**Files:**
- Modify: `back_dev_home/__init__.py` (blueprint auto-registration already loops features; verify `msr_image` is picked up), rate-limit exemption (`msr_file.msr_image` → `msr_image.*`), start purge scheduler in `create_app`.
- Test: `back_dev_home/msr_image/tests/test_app_wiring.py`

**Interfaces:**
- Consumes: `bp` (Task 1/6/8), `start_purge_scheduler` (Task 9).
- Produces: `create_app()` registers `msr_image` under `/api`, exempts its 4 endpoints from the rate limit, and starts the purge scheduler.

- [ ] **Step 1: Inspect current blueprint registration and exemption**

Run: `sed -n '36,60p;118,170p' back_dev_home/__init__.py`
Confirm how features are discovered/registered and where `msr_file.msr_image` is exempted (lines ~48–51).

- [ ] **Step 2: Write the failing test**

`back_dev_home/msr_image/tests/test_app_wiring.py`:

```python
def test_app_registers_msr_image(monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    from back_dev_home import create_app

    app = create_app()
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/msr-images" in rules
    assert "/api/msr-image" in rules
    assert "/api/msr-images/<job_id>" in rules

    client = app.test_client()
    r = client.get("/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1")
    assert r.status_code == 200
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_app_wiring.py -v`
Expected: FAIL — routes absent or exemption error, depending on current factory.

- [ ] **Step 4: Wire the factory**

In `back_dev_home/__init__.py`:
1. If features are registered by an explicit list, add `msr_image`. If auto-discovered by scanning `back_dev_home/*/__init__.py` for `bp`, no change is needed (the new `__init__.py` exports `bp`) — confirm in Step 1.
2. Replace the old exemption:

```python
    # OLD:
    # image_view = app.view_functions.get("msr_file.msr_image")
    # if image_view is not None:
    #     limiter.exempt(image_view)
    # NEW: the gallery fans out image GETs across the whole msr_image blueprint.
    for endpoint, view in app.view_functions.items():
        if endpoint.startswith("msr_image."):
            limiter.exempt(view)
```

3. In `create_app`, after blueprint registration and `_install_rate_limit(app)`, start the scheduler:

```python
    from back_dev_home.msr_image.scheduler import start_purge_scheduler
    start_purge_scheduler(app)
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_app_wiring.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `.venv/bin/pytest back_dev_home/ -q`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/__init__.py back_dev_home/msr_image/tests/test_app_wiring.py
git commit -m "feat(msr_image): register blueprint, exempt from rate limit, start purge scheduler"
```

---

## Task 13: `eqp_ip` on the meas_hist row

**Files:**
- Modify: `back_dev_home/meas_hist/contracts.py` (add `eqp_ip: str` to `MeasHistRow`)
- Modify: `back_dev_home/meas_hist/providers/mock.py` (synthesize `eqp_ip`)
- Modify: `back_dev_home/meas_hist/providers/office_example.py` (map the doc's `eqp_ip`)
- Test: `back_dev_home/meas_hist/tests/` (extend an existing row test)

**Interfaces:**
- Consumes: nothing new.
- Produces: every `MeasHistRow` carries `eqp_ip: str`, so the frontend picker can pass it to `msr_image`.

- [ ] **Step 1: Find how mock builds a row and where eqp_ip should come from**

Run: `grep -nE "eqp_id|eqp_ip|MeasHistRow|def .*row|ip_prefix" back_dev_home/meas_hist/providers/mock.py back_dev_home/sem_list/providers/mock.py`
The `sem_list` mock already generates an `eqp_ip` (`f"{ip_prefix}.{a}.{b}.{c}"`). Mirror that shape here so mock IPs look consistent.

- [ ] **Step 2: Write/extend the failing test**

Add to the meas_hist row test (e.g. `back_dev_home/meas_hist/tests/test_mock.py` — match the existing filename found via `ls back_dev_home/meas_hist/tests/`):

```python
def test_row_has_eqp_ip():
    from back_dev_home.meas_hist import data

    rows = data.search_meas_hist(...)  # use the existing test's call shape
    row = rows[0]
    parts = row["eqp_ip"].split(".")
    assert len(parts) == 4 and all(p.isdigit() for p in parts)
```

(Adapt `search_meas_hist(...)` to the actual data entrypoint the existing tests use.)

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/meas_hist/tests/ -k eqp_ip -v`
Expected: FAIL — `KeyError: 'eqp_ip'`.

- [ ] **Step 4: Implement**

1. `contracts.py`: add `eqp_ip: str` to `MeasHistRow` (place it right after `eqp_id`).
2. `providers/mock.py`: when building each row dict, add `"eqp_ip": <synthesized ip>`. Reuse the same seeded generator the mock uses for eqp_id so the IP is deterministic per tool. If the mock copies fields from a `sem_list` row, copy `eqp_ip` from there too.
3. `providers/office_example.py`: map the OpenSearch doc's `eqp_ip` field into the row (the `meas_hist_cdsem`/`_hvsem` docs already have `eqp_ip -> text`, per `docs/datatables/meas_hist.txt`). Add `eqp_ip=_text(src.get("eqp_ip"))` alongside the other field mappings.

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/meas_hist/tests/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/meas_hist/
git commit -m "feat(meas_hist): expose eqp_ip on the row so images can be fetched"
```

---

## Task 14: Frontend row type + `useMsrImageApi`

**Files:**
- Modify: `front-dev-home/app/composables/useMeasHistApi.ts` (add `eqp_ip: string` to the row type)
- Create: `front-dev-home/app/composables/useMsrImageApi.ts`
- Modify: `front-dev-home/app/composables/useMsrFileApi.ts` (remove `msrImageUrl`)

**Interfaces:**
- Consumes: the meas_hist row (now with `eqp_ip`), `joinApiPath`/base-url helper used by `useMsrFileApi.ts`.
- Produces:
  - `imageListUrl(eqp_ip, class_name, msr) -> string`
  - `imageUrl(eqp_ip, class_name, msr, name) -> string` (plain `<img :src>` for thumbnails; ignores the cond header)
  - `fetchImageWithCond(eqp_ip, class_name, msr, name) -> Promise<{ blobUrl: string, cond: string | null }>` (detail views)
  - `fetchImageList(eqp_ip, class_name, msr) -> Promise<{ images: string[], total: number }>`
  - `startDownloadAll(eqp_ip, class_name, msr) -> Promise<string>` (job_id)
  - `pollJob(job_id) -> Promise<DownloadJobStatus>`

- [ ] **Step 1: Find the row type and base-url helper**

Run: `grep -nE "eqp_id|interface .*Row|type .*Row|joinApiPath|useApiBase|const base" front-dev-home/app/composables/useMeasHistApi.ts front-dev-home/app/composables/useMsrFileApi.ts`

- [ ] **Step 2: Add `eqp_ip` to the meas_hist row type**

In `front-dev-home/app/composables/useMeasHistApi.ts`, add `eqp_ip: string` to the row interface/type (right after `eqp_id: string`), matching the backend `MeasHistRow`.

- [ ] **Step 3: Write the composable**

`front-dev-home/app/composables/useMsrImageApi.ts` (mirror the base-url pattern in `useMsrFileApi.ts` — replace `joinApiPath(base, ...)` with whatever that file uses):

```ts
export interface DownloadJobStatus {
  job_id: string
  status: 'running' | 'done' | 'error'
  done: number
  total: number
  ok: number
  ng: number
  failures: { name: string; error: string }[]
}

export function useMsrImageApi() {
  const base = useApiBase() // same helper useMsrFileApi.ts uses

  const q = (eqp_ip: string, class_name: string, msr: string) =>
    `eqp_ip=${encodeURIComponent(eqp_ip)}&class_name=${encodeURIComponent(class_name)}&msr=${encodeURIComponent(msr)}`

  const imageListUrl = (eqp_ip: string, class_name: string, msr: string) =>
    `${joinApiPath(base, '/msr-images')}?${q(eqp_ip, class_name, msr)}`

  const imageUrl = (eqp_ip: string, class_name: string, msr: string, name: string) =>
    `${joinApiPath(base, '/msr-image')}?${q(eqp_ip, class_name, msr)}&name=${encodeURIComponent(name)}`

  const fetchImageList = async (eqp_ip: string, class_name: string, msr: string) => {
    return await $fetch<{ images: string[]; total: number }>(imageListUrl(eqp_ip, class_name, msr))
  }

  const fetchImageWithCond = async (eqp_ip: string, class_name: string, msr: string, name: string) => {
    const res = await fetch(imageUrl(eqp_ip, class_name, msr, name))
    if (!res.ok) throw new Error(`image ${name}: ${res.status}`)
    const condRaw = res.headers.get('X-Msr-Cond')
    const blob = await res.blob()
    return { blobUrl: URL.createObjectURL(blob), cond: condRaw ? decodeURIComponent(condRaw) : null }
  }

  const startDownloadAll = async (eqp_ip: string, class_name: string, msr: string) => {
    const res = await $fetch<{ job_id: string }>(joinApiPath(base, '/msr-images'), {
      method: 'POST',
      body: { eqp_ip, class_name, msr },
    })
    return res.job_id
  }

  const pollJob = async (job_id: string) =>
    await $fetch<DownloadJobStatus>(`${joinApiPath(base, '/msr-images')}/${encodeURIComponent(job_id)}`)

  return { imageListUrl, imageUrl, fetchImageList, fetchImageWithCond, startDownloadAll, pollJob }
}
```

- [ ] **Step 4: Remove `msrImageUrl` from `useMsrFileApi.ts`**

Delete the `msrImageUrl` function (lines ~234–235) and remove it from the returned object (line ~237). Consumers are migrated in Task 15.

- [ ] **Step 5: Type-check**

Run: `cd front-dev-home && npx nuxi typecheck` (or the repo's configured typecheck script — check `package.json`).
Expected: no errors in the two new/edited files (there will be errors in the components still calling `msrImageUrl` — fixed in Task 15; if typecheck is all-or-nothing, do Steps 4–5 together with Task 15).

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/composables/useMsrImageApi.ts \
  front-dev-home/app/composables/useMeasHistApi.ts \
  front-dev-home/app/composables/useMsrFileApi.ts
git commit -m "feat(msr-image): useMsrImageApi composable + eqp_ip on meas_hist row"
```

---

## Task 15: Migrate gallery components + add download-all button

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/gallery/ImageViewer.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/position/SiteEvidenceDrawer.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/AlignImages.vue`

**Interfaces:**
- Consumes: `useMsrImageApi` (Task 14), the selected MSR's `eqp_ip`/`class_name`/`msr` (available from the meas_hist row / analyze selection — trace the prop each component receives).

- [ ] **Step 1: Trace how each component gets its MSR context**

Run: `grep -nE "msrImageUrl|:src|eqp_ip|class_name|\\bmsr\\b|props|defineProps" front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue front-dev-home/app/components/ebeam/skewvoir/gallery/ImageViewer.vue front-dev-home/app/components/ebeam/skewvoir/position/SiteEvidenceDrawer.vue front-dev-home/app/components/ebeam/skewvoir/dashboard/AlignImages.vue`
Identify, per component, where `eqp_ip`, `class_name`, `msr` come from. If a component lacks `eqp_ip`, thread it down from the parent that holds the selected row (the analyze/workspace state that carries the meas_hist row).

- [ ] **Step 2: Swap thumbnails to the new `imageUrl`**

In `Gallery.vue` and `AlignImages.vue`, replace `msrImageUrl(name)` with `imageUrl(eqp_ip, class_name, msr, name)` from `useMsrImageApi()`. Replace the enumeration source: instead of iterating pickle `mp_image_name` fields, call `fetchImageList(eqp_ip, class_name, msr)` (in `onMounted`/`watch`) and render `images`. Keep the existing loading/empty states.

- [ ] **Step 3: Switch detail views to `fetchImageWithCond`**

In `ImageViewer.vue` and `SiteEvidenceDrawer.vue`, replace the direct `<img :src="msrImageUrl(...)">` with a `fetch`-loaded blob URL so the cond header is read:

```ts
const { fetchImageWithCond } = useMsrImageApi()
const blobUrl = ref<string | null>(null)
const cond = ref<string | null>(null)

watch(() => props.name, async (name) => {
  if (blobUrl.value) URL.revokeObjectURL(blobUrl.value)
  if (!name) { blobUrl.value = null; cond.value = null; return }
  const r = await fetchImageWithCond(props.eqp_ip, props.class_name, props.msr, name)
  blobUrl.value = r.blobUrl
  cond.value = r.cond
}, { immediate: true })

onBeforeUnmount(() => { if (blobUrl.value) URL.revokeObjectURL(blobUrl.value) })
```

Bind `<img :src="blobUrl">` and render `cond` (e.g. a `<pre>` panel) when present.

- [ ] **Step 4: Add the "전체 다운로드" button + progress**

In `Gallery.vue`, add a button that calls `startDownloadAll(eqp_ip, class_name, msr)` then polls:

```ts
const { startDownloadAll, pollJob } = useMsrImageApi()
const job = ref<DownloadJobStatus | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

async function downloadAll() {
  const jobId = await startDownloadAll(props.eqp_ip, props.class_name, props.msr)
  timer = setInterval(async () => {
    job.value = await pollJob(jobId)
    if (job.value.status === 'done' && timer) { clearInterval(timer); timer = null }
  }, 1000)
}

onBeforeUnmount(() => { if (timer) clearInterval(timer) })
```

Render progress as `{{ job.done }}/{{ job.total }}` with `job.failures` surfaced (never hidden). After `done`, the gallery `<img>` GETs are cache hits.

- [ ] **Step 5: Verify in the running app**

Use the `verify` skill (Flask mock + Nuxt SPA). With `SKEWNONO_MSR_IMAGE_PROVIDER=mock`:
- Open a MSR → gallery shows N SVG placeholders (from `fetchImageList`).
- Open a detail view → image renders + condition panel shows synthetic cond.
- Click "전체 다운로드" → progress runs to `total/total`, then thumbnails load instantly (cache hits).

Screenshot to `.playwright-mcp/screenshots/msr-image-gallery.png`.

- [ ] **Step 6: Type-check + commit**

Run: `cd front-dev-home && npx nuxi typecheck`
Expected: no errors.

```bash
git add front-dev-home/app/components/ebeam/skewvoir/
git commit -m "feat(skewvoir): gallery via tool image list, cond in detail views, download-all button"
```

---

## Task 16: MIGRATION.md + office adapter skeleton

**Files:**
- Create: `back_dev_home/msr_image/MIGRATION.md`
- Create: `back_dev_home/msr_image/providers/office_example.py`
- Modify: `.gitignore`
- Test: `back_dev_home/msr_image/tests/test_office_template.py`

**Interfaces:**
- Consumes: `paths` (Task 1), `FetchedImage`/`ImageLocator` (Task 1), errors (Task 1), `FtpClient` (`ftp_handler.core.client`).
- Produces: office `list_images`/`fetch_image`/`download_all` with the same signatures the mock has (Task 4). Path assembly + IP handling verifiable at home via injected fake FtpClient.

- [ ] **Step 1: Ignore the office copy and cache dir**

Append to `.gitignore`:

```text
var/
back_dev_home/msr_image/providers/office.py
```

- [ ] **Step 2: Write the failing test (fake FtpClient)**

`back_dev_home/msr_image/tests/test_office_template.py`:

```python
from back_dev_home.msr_image.contracts import ImageLocator
from back_dev_home.msr_image.providers import office_example as office


class FakeFtp:
    """Records the paths requested; returns canned bytes. Context-manager like FtpClient."""

    instances = []

    def __init__(self, **kw):
        self.kw = kw
        self.listed = None
        FakeFtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def list_dir(self, remote_dir, pattern=None):
        self.listed = (remote_dir, pattern)
        return ["shot01.jpeg", "shot02.jpeg", "notes.txt"]

    def download(self, remote_path):
        if remote_path.endswith("cond.txt"):
            return b"mag=50000\nvac=0.8"
        return b"\xff\xd8jpeg:" + remote_path.encode()


def test_list_images_filters_jpeg(monkeypatch):
    monkeypatch.setattr(office, "FtpClient", FakeFtp)
    names = office.list_images("10.0.0.1", "ADI", "MSR_1", _config=office._test_config())
    assert names == ["shot01.jpeg", "shot02.jpeg"]


def test_fetch_image_reads_image_and_cond(monkeypatch):
    monkeypatch.setattr(office, "FtpClient", FakeFtp)
    img = office.fetch_image(
        ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg"), _config=office._test_config()
    )
    assert img.content_type == "image/jpeg"
    assert img.data.startswith(b"\xff\xd8jpeg")
    assert img.cond == "mag=50000\nvac=0.8"


def test_download_all_reports_each(monkeypatch):
    monkeypatch.setattr(office, "FtpClient", FakeFtp)
    seen = []
    office.download_all(
        "10.0.0.1", "ADI", "MSR_1", ["shot01.jpeg", "shot02.jpeg"],
        on_file=lambda n, f, e: seen.append((n, f is not None, e)),
        concurrency=2, _config=office._test_config(),
    )
    assert sorted(n for n, _, _ in seen) == ["shot01.jpeg", "shot02.jpeg"]
    assert all(ok and err is None for _, ok, err in seen)
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_office_template.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Write the office skeleton**

`back_dev_home/msr_image/providers/office_example.py`:

```python
# TEMPLATE — copy to office.py at the office, then verify against a real tool.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 msr_image adapter: tool FTP -> Flask relay. Pure-FTP, no OpenSearch.

The frontend sends eqp_ip/class_name/msr/name; routes validate the IP and pass a
locator here. This module assembles the /HITACHI path, lists the dir, and fetches
image + cond over ftp_handler's FtpClient (vendored, instantiated only).
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

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
    return [e for e in entries if e.lower().endswith((".jpeg", ".jpg"))]


def _fetch(ftp: FtpClient, class_name, msr, name) -> FetchedImage:
    img_path = image_path(class_name, msr, name)
    try:
        data = ftp.download(img_path)
    except Exception as exc:
        raise ImageNotFound(f"image not found: {name}") from exc
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
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest back_dev_home/msr_image/tests/test_office_template.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Write MIGRATION.md**

`back_dev_home/msr_image/MIGRATION.md` (Korean, formal endings, MD060 tables) covering: office is pure-FTP (no OpenSearch); `cp office_example.py office.py`; env keys (`SKEWNONO_TOOL_FTP_*`, `SKEWNONO_TOOL_SUBNETS`, `SKEWNONO_IMAGE_CACHE_BUCKET`/`_PREFIX`); the MinIO cache prefix must be separate from measurement-data buckets; Redis-backed `JobRegistry` is an office follow-up for multi-worker (`gunicorn -w N`); native lifecycle-by-tag is an optional upgrade (needs `s3:PutBucketLifecycle` + extending `minio_handler` in both copies); Verify commands:

```bash
SKEWNONO_MSR_IMAGE_PROVIDER=office .venv/bin/pytest back_dev_home/msr_image/tests/test_office_template.py
SKEWNONO_MSR_IMAGE_PROVIDER=office .venv/bin/python -c "from back_dev_home.msr_image import data; print(data.list_images('<tool-ip>', '<class>', '<msr>'))"
```

Run: `npm run lint:md`
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/msr_image/providers/office_example.py \
  back_dev_home/msr_image/MIGRATION.md \
  back_dev_home/msr_image/tests/test_office_template.py .gitignore
git commit -m "feat(msr_image): office FTP adapter skeleton + MIGRATION doc"
```

---

## Task 17: Full-suite verification + docs

**Files:**
- Modify: `back_dev_home/.env.example` (document new env keys)

- [ ] **Step 1: Backend suite**

Run: `.venv/bin/pytest back_dev_home/ -q`
Expected: all PASS.

- [ ] **Step 2: Provider-dispatch sanity**

Run: `SKEWNONO_MSR_IMAGE_PROVIDER=office .venv/bin/pytest back_dev_home/msr_image/tests/test_office_template.py -q`
Expected: PASS (office template runs without a real tool via the fake).

- [ ] **Step 3: Document env keys**

Add to `back_dev_home/.env.example`: `SKEWNONO_MSR_IMAGE_PROVIDER`, `SKEWNONO_TOOL_FTP_USER`/`_PASSWORD`/`_PORT`/`_TIMEOUT`, `SKEWNONO_TOOL_FTP_CONCURRENCY`, `SKEWNONO_TOOL_SUBNETS`, `IMAGE_CACHE_DIR`, `SKEWNONO_IMAGE_CACHE_BUCKET`, `SKEWNONO_IMAGE_CACHE_PREFIX`, `IMAGE_CACHE_TTL_HOURS`, `IMAGE_CACHE_PURGE_HOUR`, `SKEWNONO_MSR_IMAGE_MAX_JOBS`, `SKEWNONO_MSR_IMAGE_JOB_TTL` — each with a one-line comment and the default.

- [ ] **Step 4: Markdown lint**

Run: `npm run lint:md`
Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/.env.example
git commit -m "docs(msr_image): document tool-FTP + cache env keys"
```

---

## Self-Review Notes

- **Spec coverage:** §3 endpoints → Tasks 6/8; §4.2 path assembly → Task 1; §4.3 IP guard → Task 1 + routes; §4.4 bounded pool → Task 16 `download_all`; §4.5 cache interface + two backends → Tasks 3/11; §4.6 sweep (app-side, not `delete_older_than`) → Task 11 `purge`; §6.2 cond header → Task 6; §6.3 `eqp_ip` on row → Task 13/14; §7 error contract → Task 1 errors + route handlers; mock offline flow → Tasks 4–9; frontend → Tasks 14/15; scheduler → Task 9/12; msr_file cleanup → Task 10; MIGRATION → Task 16.
- **Spec divergence (documented):** the spec text says "delete_older_than sweep"; the plan uses a `list()`+`delete_many()` last_modified sweep because `delete_older_than` is date-folder based and would break content-addressed keys. Patch the spec's §4.5/§4.6 wording to "last_modified sweep" after the plan is approved.
- **Type consistency:** `ImageSource` shape (`list_images`/`fetch_image`/`download_all` + `on_file(name, FetchedImage|None, error|None)`) is identical across mock (Task 4) and office (Task 16); `ImageCache` (`get`/`put`/`purge`) identical across disk (Task 3) and MinIO (Task 11); `JobRegistry` (`create`/`get`/`record_ok`/`record_failure`/`finish`) defined once (Task 7) and consumed in Task 8.
