# MSR 이미지 tool FTP 수집 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve MSR SEM images by fetching them live from tool FTP servers (office) or generating SVG placeholders (home), with a disk cache, an async "download all" job, and a nightly cache purge.

**Architecture:** A new feature-sliced backend package `back_dev_home/msr_image/` with a single home↔office seam (`ImageSource` = `providers/mock.py` ↔ `providers/office.py`) selected by `get_data_provider("msr_image")`. Phase-agnostic machinery — disk `ImageCache` (keyed via `ftp_handler.local_target`), an async job runner over `ftp_handler.BackgroundJobs`, and an APScheduler purge — runs identically in both phases. `ftp_handler` is used unmodified.

**Tech Stack:** Flask blueprint, `ftp_handler` (vendored: `FtpFleetDownloader`, `save_to_dir`, `local_target`, `BackgroundJobs`), APScheduler, Python `unittest`; Nuxt 4 composable + Vue component; Node built-in test runner.

**Design spec:** `docs/superpowers/specs/2026-07-15-msr-image-tool-fetch-design.md`

## Global Constraints

- **`ftp_handler` is vendored — never modify it here.** If a change is ever unavoidable, make the identical edit in both this repo and `/Users/daeyoung/Codes/flask_modules/ftp_handler/`. This plan requires no such change.
- **No mock fallback for office errors.** Office source failure surfaces as JSON: `500` (config), `503` (`office_source_unavailable`), `404` (image absent). Never a fabricated image.
- **Provider dispatch via `get_data_provider("msr_image")`** (env `SKEWNONO_MSR_IMAGE_PROVIDER`, global `SKEWNONO_DATA_PROVIDER`, default `mock`). Office-only deps are lazy-imported inside the office branch, never at home startup.
- **Backend tests use `unittest`**, run with `python -m unittest tests.<module> -v`.
- **Secrets via env only, never committed.** Cache dir is git-ignored.
- **Markdown:** run `npm run lint:md` after editing any `.md`; use MD060 compact tables.
- **Commits:** conventional-commit subjects; end every commit message with these two trailer lines:

```text
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01MPUWVscZUKXrfHGtJCA9JN
```

---

### Task 1: Scaffold `msr_image` feature, move the SVG mock, keep `/msr-image` parity

**Files:**
- Create: `back_dev_home/msr_image/__init__.py`
- Create: `back_dev_home/msr_image/contracts.py`
- Create: `back_dev_home/msr_image/providers/__init__.py`
- Create: `back_dev_home/msr_image/providers/mock.py`
- Create: `back_dev_home/msr_image/data.py`
- Create: `back_dev_home/msr_image/routes.py`
- Modify: `back_dev_home/msr_file/routes.py` (remove the `/msr-image` route + `get_msr_image` import)
- Modify: `back_dev_home/msr_file/data.py` (remove `get_msr_image` + its `__all__` entry)
- Modify: `back_dev_home/__init__.py` (rate-limit exemption `msr_file.msr_image` → `msr_image.msr_image`)
- Test: `tests/test_msr_image.py`

**Interfaces:**
- Produces:
  - `contracts.ImageLocator` = `TypedDict{name: str, host?: str, path_fields?: dict[str,str]}`
  - `contracts.DownloadOutcome` = `TypedDict{ok: int, ng: int, failures: list[dict]}`
  - `contracts.OnProgress` = `Callable[[], None]`
  - `contracts.ImageSourceError` / `ImageConfigError` / `ImageUnavailableError` / `ImageNotFoundError`
  - `providers.mock.resolve(ImageLocator) -> tuple[str, str]`, `mock.fetch_one(ImageLocator) -> tuple[bytes, str]`, `mock.fetch_all(list[ImageLocator], Path, OnProgress) -> DownloadOutcome`
  - `data.serve_image(ImageLocator) -> tuple[bytes, str]`
  - Blueprint `bp` (name `"msr_image"`) exposing `GET /msr-image`

- [ ] **Step 1: Write the failing test**

Create `tests/test_msr_image.py`:

```python
"""Tests for the msr_image feature — home/mock image serving."""

from __future__ import annotations

import os
import tempfile
import unittest

from back_dev_home import create_app


class MsrImageRouteTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["SKEWNONO_MSR_IMAGE_PROVIDER"] = "mock"
        os.environ["SKEWNONO_IMAGE_PURGE_ENABLED"] = "0"
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["IMAGE_CACHE_DIR"] = self._tmp.name  # hermetic; never touches var/
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        os.environ.pop("SKEWNONO_MSR_IMAGE_PROVIDER", None)
        os.environ.pop("SKEWNONO_IMAGE_PURGE_ENABLED", None)
        os.environ.pop("IMAGE_CACHE_DIR", None)
        self._tmp.cleanup()

    def test_msr_image_returns_svg(self):
        resp = self.client.get("/api/msr-image?name=UNIT_TEST_001.tif")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/svg+xml")
        self.assertIn(b"<svg", resp.data)

    def test_msr_image_is_deterministic(self):
        a = self.client.get("/api/msr-image?name=SAME.tif").data
        b = self.client.get("/api/msr-image?name=SAME.tif").data
        self.assertEqual(a, b)

    def test_missing_name_is_400(self):
        self.assertEqual(self.client.get("/api/msr-image").status_code, 400)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_msr_image -v`
Expected: FAIL — `create_app` registers no `/api/msr-image` under `msr_image` yet, so the mock route 404s (or the old `msr_file` route serves it — either way `test_msr_image_returns_svg` still passes, but the app has two conflicting routes; the remove-and-move below makes ownership unambiguous). If run before any edits: `404` on the new endpoint name.

- [ ] **Step 3: Create the package files**

`back_dev_home/msr_image/__init__.py`:

```python
from back_dev_home.msr_image.routes import bp


__all__ = ["bp"]
```

`back_dev_home/msr_image/providers/__init__.py`:

```python
"""Image source adapters. Provider modules are deliberately NOT imported here so
office-only dependencies stay out of the home startup path."""
```

`back_dev_home/msr_image/contracts.py`:

```python
"""Wire + internal contracts for msr_image (phase-agnostic — no office deps)."""

from __future__ import annotations

from typing import Callable, NotRequired, TypedDict


class ImageLocator(TypedDict):
    # mp_image filename. Always present. The mock keys the cache on it; the
    # office path builder appends it to the tool image folder.
    name: str
    # Office-only, sourced from the meas_hist_cdsem search row (absent in home).
    host: NotRequired[str]                 # tool IP (eqp_ip)
    path_fields: NotRequired[dict[str, str]]  # office path template inputs


class DownloadOutcome(TypedDict):
    ok: int
    ng: int
    failures: list[dict]  # {host, remote_path, error}


class DownloadJobStatus(TypedDict):
    job_id: str
    status: str          # running | done | error
    done: int
    total: int
    ok: int
    ng: int
    failures: list[dict]
    error: NotRequired[str]


# Called once per image that lands. Must be thread-safe on our side.
OnProgress = Callable[[], None]


class ImageSourceError(Exception):
    """Base for office image-source failures. The mock never raises these."""


class ImageConfigError(ImageSourceError):
    """Missing/invalid office config (e.g. FTP creds). -> HTTP 500."""


class ImageUnavailableError(ImageSourceError):
    """Tool FTP unreachable / timed out. -> HTTP 503. No mock fallback."""


class ImageNotFoundError(ImageSourceError):
    """Tool reports the image does not exist. -> HTTP 404."""
```

`back_dev_home/msr_image/providers/mock.py` (the SVG body is moved verbatim from `msr_file/data.py::get_msr_image`, lines 561–622, minus the `@lru_cache`):

```python
"""Home/mock image source — deterministic SVG placeholders.

Same machine as office: the cache, serve, and download-all flow all run for
real; only the bytes are generated instead of fetched, so the whole UX is
testable offline. The office build swaps this module for providers/office.py.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

from back_dev_home.msr_image.contracts import (
    DownloadOutcome,
    ImageLocator,
    OnProgress,
)
from ftp_handler.direct_downloader import local_target

_MIMETYPE = "image/svg+xml"


def _seed(name: str) -> int:
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _svg(name: str) -> str:
    name = (name or "").strip()
    seed = _seed(name) if name else 0
    rng = random.Random(seed)
    size = 400

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">',
        '<defs>',
        f'<filter id="grain"><feTurbulence type="fractalNoise" '
        f'baseFrequency="{0.55 + rng.random() * 0.35:.3f}" numOctaves="2" seed="{seed % 100}"/>'
        '<feColorMatrix type="saturate" values="0"/>'
        '<feComponentTransfer><feFuncA type="linear" slope="0.16"/></feComponentTransfer></filter>',
        '</defs>',
        f'<rect width="{size}" height="{size}" fill="#16161a"/>',
    ]

    if rng.random() < 0.5:
        count = rng.randint(6, 12)
        gap = size / count
        for i in range(count):
            shade = rng.randint(90, 200)
            parts.append(
                f'<rect x="{i * gap + gap * 0.15:.1f}" y="18" width="{gap * 0.6:.1f}" '
                f'height="{size - 56}" fill="rgb({shade},{shade},{shade})" opacity="0.82"/>'
            )
    else:
        cols, rows_n = rng.randint(5, 8), rng.randint(5, 8)
        cw, ch = size / (cols + 1), (size - 56) / (rows_n + 1)
        radius = min(cw, ch) * 0.28
        for cx in range(1, cols + 1):
            for cy in range(1, rows_n + 1):
                shade = rng.randint(120, 230)
                parts.append(
                    f'<circle cx="{cx * cw:.1f}" cy="{cy * ch + 8:.1f}" r="{radius:.1f}" '
                    f'fill="rgb({shade},{shade},{shade})" opacity="0.85"/>'
                )

    parts.append(f'<rect width="{size}" height="{size}" filter="url(#grain)"/>')
    parts.append(f'<rect x="{size - 110}" y="{size - 26}" width="80" height="5" fill="#fff"/>')
    parts.append(
        f'<text x="{size - 70}" y="{size - 32}" fill="#fff" font-size="13" '
        'font-family="monospace" text-anchor="middle">200 nm</text>'
    )
    short = name if len(name) <= 26 else name[:25] + "…"
    parts.append(
        f'<text x="12" y="22" fill="#cfcfcf" font-size="11" font-family="monospace">{_xml_escape(short)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def resolve(locator: ImageLocator) -> tuple[str, str]:
    # Mock images live under host "mock"; the ".svg" suffix makes the cached file
    # self-describing so the mimetype is guessable from the path on a cache hit.
    return "mock", f"{locator['name']}.svg"


def fetch_one(locator: ImageLocator) -> tuple[bytes, str]:
    return _svg(locator["name"]).encode("utf-8"), _MIMETYPE


def fetch_all(
    locators: list[ImageLocator], root: Path, on_progress: OnProgress
) -> DownloadOutcome:
    for loc in locators:
        host, remote_path = resolve(loc)
        target = local_target(root, host, remote_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_svg(loc["name"]).encode("utf-8"))
        on_progress()
    return {"ok": len(locators), "ng": 0, "failures": []}
```

`back_dev_home/msr_image/data.py`:

```python
"""SWAP SURFACE — msr_image provider selection.

routes.py imports only this module. Provider-specific wiring lives in
providers/mock.py or providers/office.py; office-only deps are lazy-imported.
"""

from __future__ import annotations

from types import ModuleType

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.msr_image.contracts import ImageLocator


def _provider() -> ModuleType:
    if get_data_provider("msr_image") == "office":
        from back_dev_home.msr_image.providers import office
        return office
    from back_dev_home.msr_image.providers import mock
    return mock


def serve_image(locator: ImageLocator) -> tuple[bytes, str]:
    """(bytes, mimetype) for one image. Cache is added in Task 2."""
    return _provider().fetch_one(locator)
```

`back_dev_home/msr_image/routes.py`:

```python
from flask import Blueprint, Response, jsonify, request

from back_dev_home.msr_image.data import serve_image


bp = Blueprint("msr_image", __name__)


def _locator_from_args() -> dict | None:
    name = (request.args.get("name") or "").strip()
    if not name or len(name) > 256:
        return None
    locator: dict = {"name": name}
    host = (request.args.get("host") or "").strip()
    if host:
        locator["host"] = host
    return locator


@bp.get("/msr-image")
def msr_image():
    """Serve a SEM micrograph. Home: mock SVG. Office: fetched from the tool.
    The route + URL contract stay identical across phases."""
    locator = _locator_from_args()
    if locator is None:
        return jsonify({"error": "name query param is required (<=256 chars)"}), 400
    data, mimetype = serve_image(locator)
    return Response(
        data, mimetype=mimetype, headers={"Cache-Control": "public, max-age=3600"}
    )
```

- [ ] **Step 4: Remove the old image route from `msr_file`**

In `back_dev_home/msr_file/routes.py` line 3, change:

```python
from back_dev_home.msr_file.data import get_msr_file, get_msr_image
```

to:

```python
from back_dev_home.msr_file.data import get_msr_file
```

Delete the entire `@bp.get("/msr-image")` handler (`msr_image` function, the block spanning the current lines 31–52).

In `back_dev_home/msr_file/data.py`: delete the `get_msr_image` function (current lines 560–622, including its `@lru_cache(maxsize=512)` decorator) and remove `"get_msr_image",` from the `__all__` list (current line 50). If `_xml_escape` (current lines 556–557) is now unused in `data.py`, delete it too. Leave `get_msr_file` untouched.

- [ ] **Step 5: Move the rate-limit exemption to the new endpoint**

In `back_dev_home/__init__.py` `_install_rate_limit`, change the exemption target:

```python
    image_view = app.view_functions.get("msr_image.msr_image")
    if image_view is not None:
        limiter.exempt(image_view)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m unittest tests.test_msr_image -v`
Expected: PASS (3 tests). Also run `python -m unittest tests.test_msr_file -v` — Expected: PASS (unchanged; nothing referenced `get_msr_image`).

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/msr_image tests/test_msr_image.py \
  back_dev_home/msr_file/routes.py back_dev_home/msr_file/data.py back_dev_home/__init__.py
git commit -m "feat(msr-image): scaffold feature, move SVG mock, keep /msr-image parity"
```

---

### Task 2: Disk `ImageCache` + serve-from-cache

**Files:**
- Create: `back_dev_home/msr_image/cache.py`
- Modify: `back_dev_home/msr_image/data.py` (route serve through the cache)
- Modify: `.gitignore` (add `var/`)
- Test: `tests/test_msr_image_cache.py`

**Interfaces:**
- Consumes: `providers.mock.resolve/fetch_one`, `contracts.ImageLocator`
- Produces:
  - `cache.default_cache_dir() -> Path`
  - `cache.guess_mimetype(str) -> str`
  - `cache.ImageCache(root: Path | None)` with `.root: Path`, `.path_for(host, remote_path) -> Path`, `.get_or_fetch(locator, provider) -> tuple[bytes, str]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_msr_image_cache.py`:

```python
"""Tests for the disk image cache."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from back_dev_home.msr_image.cache import ImageCache, guess_mimetype
from back_dev_home.msr_image.providers import mock


class ImageCacheTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = ImageCache(root=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_miss_fetches_writes_and_returns(self):
        data, mimetype = self.cache.get_or_fetch({"name": "A.tif"}, mock)
        self.assertIn(b"<svg", data)
        self.assertEqual(mimetype, "image/svg+xml")
        target = self.cache.path_for("mock", "A.tif.svg")
        self.assertTrue(target.exists())

    def test_hit_reads_from_disk_without_regenerating(self):
        self.cache.get_or_fetch({"name": "B.tif"}, mock)
        target = self.cache.path_for("mock", "B.tif.svg")
        target.write_bytes(b"<svg>SENTINEL</svg>")  # prove the 2nd call reads disk
        data, _ = self.cache.get_or_fetch({"name": "B.tif"}, mock)
        self.assertEqual(data, b"<svg>SENTINEL</svg>")

    def test_path_for_is_deterministic(self):
        self.assertEqual(
            self.cache.path_for("mock", "C.tif.svg"),
            self.cache.path_for("mock", "C.tif.svg"),
        )

    def test_guess_mimetype(self):
        self.assertEqual(guess_mimetype("x.svg"), "image/svg+xml")
        self.assertEqual(guess_mimetype("x.jpeg"), "image/jpeg")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_msr_image_cache -v`
Expected: FAIL with `ModuleNotFoundError: back_dev_home.msr_image.cache`.

- [ ] **Step 3: Create `cache.py`**

```python
"""Disk image cache under IMAGE_CACHE_DIR.

Keyed (host, remote_path) via ftp_handler.local_target so the office
save_to_dir sink (Task 5) writes land at exactly the paths a later serve reads.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from back_dev_home.msr_image.contracts import ImageLocator
from ftp_handler.direct_downloader import local_target


def default_cache_dir() -> Path:
    env = os.environ.get("IMAGE_CACHE_DIR")
    if env:
        return Path(env)
    # <project>/var/image_cache — parents[2] = repo root from
    # back_dev_home/msr_image/cache.py
    return Path(__file__).resolve().parents[2] / "var" / "image_cache"


def guess_mimetype(remote_path: str) -> str:
    mime, _ = mimetypes.guess_type(remote_path)
    return mime or "application/octet-stream"


class ImageCache:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_cache_dir()

    def path_for(self, host: str, remote_path: str) -> Path:
        return local_target(self.root, host, remote_path)

    def get_or_fetch(self, locator: ImageLocator, provider) -> tuple[bytes, str]:
        host, remote_path = provider.resolve(locator)
        target = self.path_for(host, remote_path)
        if target.exists():
            return target.read_bytes(), guess_mimetype(remote_path)
        data, mimetype = provider.fetch_one(locator)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return data, mimetype
```

- [ ] **Step 4: Route `serve_image` through the cache**

Replace `back_dev_home/msr_image/data.py`'s `serve_image` and add a cache accessor:

```python
from back_dev_home.msr_image.cache import ImageCache


def _cache() -> ImageCache:
    # Stateless (just a root path); constructed per call so IMAGE_CACHE_DIR is
    # read fresh — keeps tests hermetic. The job-runner singleton is Task 3.
    return ImageCache()


def serve_image(locator: ImageLocator) -> tuple[bytes, str]:
    """(bytes, mimetype) for one image — cache hit or provider fetch + cache."""
    return _cache().get_or_fetch(locator, _provider())
```

(Add the `from back_dev_home.msr_image.cache import ImageCache` import at the top; remove the now-superseded direct `_provider().fetch_one` body.)

- [ ] **Step 5: Git-ignore the cache dir**

Append to `.gitignore`:

```gitignore
# Local image cache (msr_image tool fetch)
var/
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m unittest tests.test_msr_image_cache tests.test_msr_image -v`
Expected: PASS (7 tests total). Confirm nothing was written into the repo: `git status --porcelain var/ 2>/dev/null` prints nothing.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/msr_image/cache.py back_dev_home/msr_image/data.py \
  tests/test_msr_image_cache.py .gitignore
git commit -m "feat(msr-image): disk cache + serve-from-cache"
```

---

### Task 3: Async "download all" — job runner + endpoints

**Files:**
- Create: `back_dev_home/msr_image/jobs.py`
- Modify: `back_dev_home/msr_image/data.py` (add `start_download_all`, `download_status`)
- Modify: `back_dev_home/msr_image/routes.py` (add `POST /msr-images`, `GET /msr-images/<job_id>`)
- Test: `tests/test_msr_image_jobs.py`

**Interfaces:**
- Consumes: `contracts.{ImageLocator, DownloadJobStatus}`, `providers.mock.fetch_all`, `cache.ImageCache.root`, `ftp_handler.web_app.BackgroundJobs`
- Produces:
  - `jobs.ImageDownloadJobs(max_jobs: int | None)` with `.submit(locators, root, fetch_all) -> str` and `.status(job_id) -> DownloadJobStatus | None`
  - `data.start_download_all(list[ImageLocator]) -> str`
  - `data.download_status(str) -> DownloadJobStatus | None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_msr_image_jobs.py`:

```python
"""Tests for the async download-all job runner (in-memory store)."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from back_dev_home.msr_image.jobs import ImageDownloadJobs
from back_dev_home.msr_image.providers import mock


def _wait_done(jobs, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = jobs.status(job_id)
        if status and status["status"] in ("done", "error"):
            return status
        time.sleep(0.02)
    raise AssertionError("job did not finish in time")


class ImageDownloadJobsTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.jobs = ImageDownloadJobs(max_jobs=2)

    def tearDown(self):
        self._tmp.cleanup()

    def test_submit_runs_to_done_with_counts(self):
        locators = [{"name": f"IMG_{i}.tif"} for i in range(5)]
        job_id = self.jobs.submit(locators, self.root, mock.fetch_all)
        status = _wait_done(self.jobs, job_id)
        self.assertEqual(status["status"], "done")
        self.assertEqual(status["ok"], 5)
        self.assertEqual(status["ng"], 0)
        self.assertEqual(status["done"], status["total"])
        self.assertEqual(status["total"], 5)
        # Files landed in the cache dir.
        self.assertTrue((self.root / "mock").exists())

    def test_unknown_job_id_is_none(self):
        self.assertIsNone(self.jobs.status("does-not-exist"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_msr_image_jobs -v`
Expected: FAIL with `ModuleNotFoundError: back_dev_home.msr_image.jobs`.

- [ ] **Step 3: Create `jobs.py`**

```python
"""Async 'download all' for an MSR's images — off the request thread.

ftp_handler.BackgroundJobs is used ONLY as the in-process executor; the
observable job state (status, progress, failures) lives in our own store so a
poll can read it. Home/single-worker uses this in-memory store; multi-worker
office swaps a Redis-backed store with the same submit/status interface
(see docs/back-end/office-sources/msr-image.md). ftp_handler is not modified.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from uuid import uuid4

from back_dev_home.msr_image.contracts import (
    DownloadJobStatus,
    DownloadOutcome,
    ImageLocator,
)
from ftp_handler.web_app import BackgroundJobs

FetchAll = Callable[[list[ImageLocator], Path, Callable[[], None]], DownloadOutcome]


@dataclass
class _JobState:
    total: int
    status: str = "running"
    done: int = 0
    ok: int = 0
    ng: int = 0
    failures: list[dict] = field(default_factory=list)
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class ImageDownloadJobs:
    """Submit a fleet download on a background thread; poll its status."""

    def __init__(self, *, max_jobs: int | None = None) -> None:
        workers = max_jobs or int(os.environ.get("SKEWNONO_MSR_IMAGE_MAX_JOBS", "2"))
        self._pool = BackgroundJobs(max_workers=workers)
        self._states: dict[str, _JobState] = {}
        self._lock = threading.Lock()

    def submit(
        self, locators: list[ImageLocator], root: Path, fetch_all: FetchAll
    ) -> str:
        job_id = uuid4().hex
        state = _JobState(total=len(locators))
        with self._lock:
            self._states[job_id] = state

        def _bump() -> None:
            with state.lock:
                state.done += 1

        def _work() -> None:
            try:
                outcome = fetch_all(locators, root, _bump)
                with state.lock:
                    state.ok = outcome["ok"]
                    state.ng = outcome["ng"]
                    state.failures = outcome["failures"]
                    state.status = "done"
            except Exception as exc:  # noqa: BLE001 - any failure becomes job state
                with state.lock:
                    state.status = "error"
                    state.error = f"{type(exc).__name__}: {exc}"

        self._pool.submit(_work)
        return job_id

    def status(self, job_id: str) -> DownloadJobStatus | None:
        with self._lock:
            state = self._states.get(job_id)
        if state is None:
            return None
        with state.lock:
            out: DownloadJobStatus = {
                "job_id": job_id,
                "status": state.status,
                "done": state.done,
                "total": state.total,
                "ok": state.ok,
                "ng": state.ng,
                "failures": list(state.failures),
            }
            if state.error is not None:
                out["error"] = state.error
            return out
```

- [ ] **Step 4: Add dispatch helpers to `data.py`**

Add to `back_dev_home/msr_image/data.py` (the job runner IS a singleton — it holds the thread pool and job state):

```python
from functools import lru_cache

from back_dev_home.msr_image.contracts import DownloadJobStatus
from back_dev_home.msr_image.jobs import ImageDownloadJobs


@lru_cache(maxsize=1)
def _jobs() -> ImageDownloadJobs:
    return ImageDownloadJobs()


def start_download_all(locators: list[ImageLocator]) -> str:
    return _jobs().submit(locators, _cache().root, _provider().fetch_all)


def download_status(job_id: str) -> DownloadJobStatus | None:
    return _jobs().status(job_id)
```

- [ ] **Step 5: Add the endpoints to `routes.py`**

Update the import and add two handlers in `back_dev_home/msr_image/routes.py`:

```python
from back_dev_home.msr_image.data import (
    download_status,
    serve_image,
    start_download_all,
)

MAX_BULK_IMAGES = 2000


@bp.post("/msr-images")
def msr_images_download_all():
    """Kick off a background fleet download into the cache; return a job id."""
    payload = request.get_json(silent=True) or {}
    images = payload.get("images")
    if not isinstance(images, list) or not images:
        return jsonify({"error": "images must be a non-empty list"}), 400
    if len(images) > MAX_BULK_IMAGES:
        return jsonify({"error": f"images exceeds the {MAX_BULK_IMAGES} limit"}), 400

    locators: list[dict] = []
    for item in images:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or len(name) > 256:
            continue
        loc: dict = {"name": name}
        host = item.get("host")
        if isinstance(host, str) and host.strip():
            loc["host"] = host.strip()
        path_fields = item.get("path_fields")
        if isinstance(path_fields, dict):
            loc["path_fields"] = {str(k): str(v) for k, v in path_fields.items()}
        locators.append(loc)

    if not locators:
        return jsonify({"error": "no valid images"}), 400
    return jsonify({"job_id": start_download_all(locators)}), 202


@bp.get("/msr-images/<job_id>")
def msr_images_status(job_id: str):
    status = download_status(job_id)
    if status is None:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(status)
```

- [ ] **Step 6: Add an HTTP-level test and run all**

Append to `tests/test_msr_image.py` (inside `MsrImageRouteTestCase`):

```python
    def test_download_all_returns_202_then_polls_done(self):
        import time
        body = {"images": [{"name": f"G_{i}.tif"} for i in range(3)]}
        resp = self.client.post("/api/msr-images", json=body)
        self.assertEqual(resp.status_code, 202)
        job_id = resp.get_json()["job_id"]

        deadline = time.time() + 5
        status = None
        while time.time() < deadline:
            status = self.client.get(f"/api/msr-images/{job_id}").get_json()
            if status["status"] in ("done", "error"):
                break
            time.sleep(0.02)
        self.assertEqual(status["status"], "done")
        self.assertEqual(status["ok"], 3)

    def test_download_all_empty_is_400(self):
        self.assertEqual(
            self.client.post("/api/msr-images", json={"images": []}).status_code, 400
        )

    def test_unknown_job_is_404(self):
        self.assertEqual(self.client.get("/api/msr-images/nope").status_code, 404)
```

Run: `python -m unittest tests.test_msr_image_jobs tests.test_msr_image -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/msr_image/jobs.py back_dev_home/msr_image/data.py \
  back_dev_home/msr_image/routes.py tests/test_msr_image_jobs.py tests/test_msr_image.py
git commit -m "feat(msr-image): async download-all job + poll endpoints"
```

---

### Task 4: Nightly cache purge (APScheduler) + `create_app` wiring

**Files:**
- Create: `back_dev_home/msr_image/scheduler.py`
- Modify: `back_dev_home/__init__.py` (start the scheduler in `create_app`)
- Modify: `back_dev_home/requirements.txt` (add `apscheduler`)
- Test: `tests/test_msr_image_scheduler.py`

**Interfaces:**
- Produces:
  - `scheduler.purge_old(root: Path, ttl_hours: float, *, now: float | None = None) -> int`
  - `scheduler.start_purge_scheduler(app) -> None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_msr_image_scheduler.py`:

```python
"""Tests for the image-cache nightly purge (pure function + wiring guard)."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from back_dev_home.msr_image.scheduler import purge_old, start_purge_scheduler


class PurgeOldTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_deletes_old_keeps_fresh(self):
        old = self.root / "mock" / "old.svg"
        fresh = self.root / "mock" / "fresh.svg"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_bytes(b"<svg/>")
        fresh.write_bytes(b"<svg/>")
        # Age `old` past the 24h TTL.
        stale = time.time() - 25 * 3600
        os.utime(old, (stale, stale))

        removed = purge_old(self.root, ttl_hours=24)
        self.assertEqual(removed, 1)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_missing_root_is_zero(self):
        self.assertEqual(purge_old(self.root / "nope", ttl_hours=24), 0)


class StartSchedulerGuardTestCase(unittest.TestCase):
    def test_disabled_is_noop(self):
        os.environ["SKEWNONO_IMAGE_PURGE_ENABLED"] = "0"
        try:
            class _App:
                extensions: dict = {}
            app = _App()
            start_purge_scheduler(app)  # must not raise, must not register
            self.assertNotIn("msr_image_purge_scheduler", app.extensions)
        finally:
            os.environ.pop("SKEWNONO_IMAGE_PURGE_ENABLED", None)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_msr_image_scheduler -v`
Expected: FAIL with `ModuleNotFoundError: back_dev_home.msr_image.scheduler`.

- [ ] **Step 3: Create `scheduler.py`**

```python
"""Nightly purge of the image cache.

APScheduler cron started in create_app. Single-process by nature; under
multi-worker the cron runs per worker but duplicate deletes are harmless.
purge_old is a pure function so it is unit-tested without a scheduler.
"""

from __future__ import annotations

import os
import time
from pathlib import Path


def purge_old(root: Path, ttl_hours: float, *, now: float | None = None) -> int:
    """Delete files older than ttl_hours under root. Returns the count removed."""
    root = Path(root)
    if not root.exists():
        return 0
    cutoff = (now if now is not None else time.time()) - ttl_hours * 3600
    removed = 0
    for path in root.rglob("*"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed


def start_purge_scheduler(app) -> None:
    """Register a nightly purge cron on `app`. No-op when disabled via env."""
    if os.environ.get("SKEWNONO_IMAGE_PURGE_ENABLED", "1") != "1":
        return

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    from back_dev_home.msr_image.cache import default_cache_dir

    ttl = float(os.environ.get("IMAGE_CACHE_TTL_HOURS", "24"))
    hour = int(os.environ.get("IMAGE_CACHE_PURGE_HOUR", "3"))
    root = default_cache_dir()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        lambda: purge_old(root, ttl),
        CronTrigger(hour=hour),
        id="msr_image_purge",
        replace_existing=True,
    )
    scheduler.start()
    app.extensions["msr_image_purge_scheduler"] = scheduler
```

- [ ] **Step 4: Wire it into `create_app`**

In `back_dev_home/__init__.py` `create_app`, after `_install_rate_limit(app)` and before `return app`:

```python
    from .msr_image.scheduler import start_purge_scheduler
    start_purge_scheduler(app)

    return app
```

- [ ] **Step 5: Add the dependency**

Append to `back_dev_home/requirements.txt`:

```text
apscheduler>=3.10
```

Install it: `pip install "apscheduler>=3.10"`

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m unittest tests.test_msr_image_scheduler tests.test_msr_image -v`
Expected: PASS. (The `test_msr_image` suite sets `SKEWNONO_IMAGE_PURGE_ENABLED=0`, so `create_app` starts no scheduler thread there.)

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/msr_image/scheduler.py back_dev_home/__init__.py \
  back_dev_home/requirements.txt tests/test_msr_image_scheduler.py
git commit -m "feat(msr-image): nightly APScheduler cache purge"
```

---

### Task 5: Office `FtpImageSource` + fake-downloader tests + error mapping + connection note

**Files:**
- Create: `back_dev_home/msr_image/providers/office.py`
- Modify: `back_dev_home/msr_image/routes.py` (map `ImageSourceError` subclasses to HTTP; parse `image_dir` arg)
- Create: `docs/back-end/office-sources/msr-image.md`
- Test: `tests/test_msr_image_office.py`

**Interfaces:**
- Consumes: `ftp_handler.direct_downloader.{FtpFleetDownloader, HostSpec, group_files_by_host, save_to_dir}`, `cache.guess_mimetype`, `contracts.{ImageConfigError, ImageUnavailableError, ImageNotFoundError, DownloadOutcome, OnProgress}`
- Produces:
  - `office.resolve(ImageLocator) -> tuple[str, str]`
  - `office.fetch_one(ImageLocator, *, downloader=None) -> tuple[bytes, str]`
  - `office.fetch_all(list[ImageLocator], Path, OnProgress, *, downloader=None) -> DownloadOutcome`

- [ ] **Step 1: Write the failing test** (fake downloader — no real FTP)

Create `tests/test_msr_image_office.py`:

```python
"""Office image source, exercised with a fake ftp_handler downloader."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path

from back_dev_home.msr_image.contracts import ImageConfigError
from back_dev_home.msr_image.providers import office


@dataclass
class _FakeFile:
    host: str
    remote_path: str
    data: bytes


@dataclass
class _FakeFailure:
    host: str
    error: str
    remote_path: str | None = None


@dataclass
class _FakeReport:
    files: list = field(default_factory=list)
    failures: list = field(default_factory=list)

    @property
    def ok(self):
        return len(self.files)

    @property
    def ng(self):
        return len(self.failures)


class _FakeDownloader:
    """Duck-types FtpFleetDownloader.download for the two office code paths."""

    def __init__(self, *, payload=b"\xff\xd8JPEGBYTES", fail_all=False):
        self.payload = payload
        self.fail_all = fail_all

    def download(self, specs, *, on_file=None):
        files, failures = [], []
        for spec in specs:
            for path in spec.files:
                if self.fail_all:
                    failures.append(_FakeFailure(spec.host, "550 No such file", path))
                    continue
                if on_file is not None:
                    on_file(spec.host, path, self.payload)
                    files.append(_FakeFile(spec.host, path, b""))
                else:
                    files.append(_FakeFile(spec.host, path, self.payload))
        return _FakeReport(files=files, failures=failures)


LOC = {"name": "S09.jpeg", "host": "10.0.0.9", "path_fields": {"image_dir": "/IMAGES/D1"}}


class OfficeResolveTestCase(unittest.TestCase):
    def test_resolve_builds_path(self):
        self.assertEqual(office.resolve(LOC), ("10.0.0.9", "/IMAGES/D1/S09.jpeg"))

    def test_missing_host_raises_config_error(self):
        with self.assertRaises(ImageConfigError):
            office.resolve({"name": "x.jpeg", "path_fields": {"image_dir": "/D"}})

    def test_missing_image_dir_raises_config_error(self):
        with self.assertRaises(ImageConfigError):
            office.resolve({"name": "x.jpeg", "host": "10.0.0.1"})


class OfficeFetchTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_fetch_one_returns_bytes_and_mimetype(self):
        data, mimetype = office.fetch_one(LOC, downloader=_FakeDownloader())
        self.assertEqual(data, b"\xff\xd8JPEGBYTES")
        self.assertEqual(mimetype, "image/jpeg")

    def test_fetch_all_writes_cache_and_counts(self):
        seen = []
        outcome = office.fetch_all(
            [LOC], self.root, lambda: seen.append(1), downloader=_FakeDownloader()
        )
        self.assertEqual(outcome["ok"], 1)
        self.assertEqual(outcome["ng"], 0)
        self.assertEqual(len(seen), 1)
        self.assertTrue((self.root / "10.0.0.9" / "IMAGES" / "D1" / "S09.jpeg").exists())

    def test_fetch_all_reports_failures(self):
        outcome = office.fetch_all(
            [LOC], self.root, lambda: None, downloader=_FakeDownloader(fail_all=True)
        )
        self.assertEqual(outcome["ok"], 0)
        self.assertEqual(outcome["ng"], 1)
        self.assertEqual(outcome["failures"][0]["host"], "10.0.0.9")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_msr_image_office -v`
Expected: FAIL with `ModuleNotFoundError: back_dev_home.msr_image.providers.office`.

- [ ] **Step 3: Create `providers/office.py`**

```python
"""Office image source — real bytes from the tool FTP via ftp_handler (unmodified).

Activated by SKEWNONO_MSR_IMAGE_PROVIDER=office. download() fetches, save_to_dir()
streams to the cache dir, and local_target() (cache.py) recovers the same paths.
The one office-confirmed detail is the remote-path template (_build_remote_path);
see docs/back-end/office-sources/msr-image.md.
"""

from __future__ import annotations

import os
from pathlib import Path

from back_dev_home.msr_image.cache import guess_mimetype
from back_dev_home.msr_image.contracts import (
    DownloadOutcome,
    ImageConfigError,
    ImageLocator,
    ImageNotFoundError,
    ImageUnavailableError,
    OnProgress,
)
from ftp_handler.direct_downloader import (
    FtpFleetDownloader,
    HostSpec,
    group_files_by_host,
    save_to_dir,
)


def _build_remote_path(locator: ImageLocator) -> str:
    """Assemble the tool FTP path for an image.

    확인 필요 (office): the exact folder field(s) and template come from the
    meas_hist_cdsem row — documented in the office source note. Here we consume
    path_fields["image_dir"] + the filename; swapping this template is the only
    office change needed.
    """
    fields = locator.get("path_fields") or {}
    image_dir = fields.get("image_dir")
    if not image_dir:
        raise ImageConfigError("locator.path_fields.image_dir is required")
    return f"{image_dir.rstrip('/')}/{locator['name']}"


def resolve(locator: ImageLocator) -> tuple[str, str]:
    host = (locator.get("host") or "").strip()
    if not host:
        raise ImageConfigError("locator.host (eqp_ip) is required for office")
    return host, _build_remote_path(locator)


def _make_downloader() -> FtpFleetDownloader:
    user = os.environ.get("SKEWNONO_TOOL_FTP_USER")
    password = os.environ.get("SKEWNONO_TOOL_FTP_PASSWORD")
    if not user or not password:
        raise ImageConfigError("SKEWNONO_TOOL_FTP_USER/PASSWORD not set")
    port = int(os.environ.get("SKEWNONO_TOOL_FTP_PORT", "21"))
    return FtpFleetDownloader(user=user, password=password, port=port)


def fetch_one(
    locator: ImageLocator, *, downloader: FtpFleetDownloader | None = None
) -> tuple[bytes, str]:
    host, remote_path = resolve(locator)
    dl = downloader or _make_downloader()
    report = dl.download([HostSpec(host, files=[remote_path])])
    if report.files:
        return report.files[0].data, guess_mimetype(remote_path)
    err = report.failures[0].error if report.failures else "unknown error"
    if "550" in err or "No such file" in err:
        raise ImageNotFoundError(f"{host}:{remote_path} — {err}")
    raise ImageUnavailableError(f"{host}:{remote_path} — {err}")


def fetch_all(
    locators: list[ImageLocator],
    root: Path,
    on_progress: OnProgress,
    *,
    downloader: FtpFleetDownloader | None = None,
) -> DownloadOutcome:
    specs = group_files_by_host(resolve(loc) for loc in locators)
    dl = downloader or _make_downloader()
    report = dl.download(
        specs, on_file=save_to_dir(root, then=lambda h, rp, d: on_progress())
    )
    failures = [
        {"host": f.host, "remote_path": f.remote_path, "error": f.error}
        for f in report.failures
    ]
    return {"ok": report.ok, "ng": report.ng, "failures": failures}
```

- [ ] **Step 4: Map office errors + parse `image_dir` in `routes.py`**

Update `back_dev_home/msr_image/routes.py`. Add the imports:

```python
from back_dev_home.msr_image.contracts import (
    ImageConfigError,
    ImageNotFoundError,
    ImageUnavailableError,
)
```

Extend `_locator_from_args` to carry the office path field:

```python
    image_dir = (request.args.get("image_dir") or "").strip()
    if image_dir:
        locator["path_fields"] = {"image_dir": image_dir}
    return locator
```

Wrap the serve call in `msr_image()`:

```python
    try:
        data, mimetype = serve_image(locator)
    except ImageNotFoundError:
        return jsonify({"error": "image not found"}), 404
    except ImageConfigError:
        return jsonify({"error": "office_configuration_error"}), 500
    except ImageUnavailableError:
        return jsonify({"error": "office_source_unavailable"}), 503
    return Response(
        data, mimetype=mimetype, headers={"Cache-Control": "public, max-age=3600"}
    )
```

- [ ] **Step 5: Write the office connection note**

Create `docs/back-end/office-sources/msr-image.md`:

```markdown
# msr-image office source

## Source
- 종류: tool FTP (이미지) + meas_hist_cdsem OpenSearch (IP·경로 필드)
- 자격/포트: `SKEWNONO_TOOL_FTP_USER`, `SKEWNONO_TOOL_FTP_PASSWORD`, `SKEWNONO_TOOL_FTP_PORT`
- 소유 팀과 read 권한: <확인 필요>

## Field mapping
| Contract field | Source field | Conversion | Null/unknown rule |
| --- | --- | --- | --- |
| `host` | meas_hist_cdsem tool IP | 그대로 | <확인 필요: 필드명·반환 권한> |
| `path_fields.image_dir` | meas_hist_cdsem 이미지 폴더 | 템플릿 조립 | <확인 필요: 필드·규칙> |
| `name` | mp_image 파일명 | 그대로 | 없으면 요청 제외 |

## Query semantics
- `_build_remote_path`: `{image_dir}/{name}` (현재 기본값). 실제 템플릿 확정 후 이 함수만 교체.
- 이미지 포맷/확장자: <확인 필요: `.jpeg` 가정>

## Runtime
- timeout/retry: `FtpFleetDownloader` 기본(connect 8s, host 60s)
- 예상/최대 이미지 수: MSR당 수백 장
- cache/freshness: 디스크 캐시 ~1일, 야간 purge
- partial failure: `failures[]`로 보고, 은닉 금지
- 다중 worker job 상태: Redis 백엔드로 `ImageDownloadJobs` 교체(같은 submit/status 계약)

## Security
- 반환 금지 필드: 자격 증명, 실제 장비 IP는 로그/응답에 남기지 않음
- 익명화 규칙: 실 경로·IP는 이 노트에 기록하지 않음

## Acceptance
- unit fixture cases: `tests/test_msr_image_office.py` (fake downloader)
- integration command: office에서 `SKEWNONO_MSR_IMAGE_PROVIDER=office` smoke
- go/no-go threshold: 대표 MSR 갤러리가 캐시에서 relay, 실패는 명시적 오류
```

Run: `npm run lint:md`
Expected: 0 errors.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m unittest tests.test_msr_image_office tests.test_msr_image -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/msr_image/providers/office.py back_dev_home/msr_image/routes.py \
  docs/back-end/office-sources/msr-image.md tests/test_msr_image_office.py
git commit -m "feat(msr-image): office FTP source, error contract, connection note"
```

---

### Task 6: Frontend — download-all helper, composable, and Gallery button

**Files:**
- Create: `front-dev-home/app/utils/msrImage.ts`
- Create: `front-dev-home/app/utils/msrImage.test.ts`
- Modify: `front-dev-home/app/composables/useMsrFileApi.ts` (add `startImageDownload`, `getImageJob`)
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue` (button + progress)

**Interfaces:**
- Consumes: `data.start_download_all` via `POST /api/msr-images`; `data.download_status` via `GET /api/msr-images/<id>`
- Produces:
  - `msrImage.ImageDownloadItem` = `{ name: string, host?: string, image_dir?: string }`
  - `msrImage.buildDownloadAllBody(items) -> { images: Record<string, unknown>[] }`
  - `useMsrFileApi().startImageDownload(items) -> Promise<string>`
  - `useMsrFileApi().getImageJob(jobId) -> Promise<ImageDownloadJob>`

- [ ] **Step 1: Write the failing unit test** (Node built-in runner)

Create `front-dev-home/app/utils/msrImage.test.ts`:

```typescript
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildDownloadAllBody } from './msrImage'

test('buildDownloadAllBody: names only (home)', () => {
  const body = buildDownloadAllBody([{ name: 'A.tif' }, { name: 'B.tif' }])
  assert.deepEqual(body, { images: [{ name: 'A.tif' }, { name: 'B.tif' }] })
})

test('buildDownloadAllBody: office locator fields', () => {
  const body = buildDownloadAllBody([{ name: 'S.jpeg', host: '10.0.0.1', image_dir: '/D1' }])
  assert.deepEqual(body, {
    images: [{ name: 'S.jpeg', host: '10.0.0.1', path_fields: { image_dir: '/D1' } }]
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `front-dev-home/`): `node --test "app/utils/msrImage.test.ts"`
Expected: FAIL — `Cannot find module './msrImage'`.

- [ ] **Step 3: Create `app/utils/msrImage.ts`**

```typescript
export interface ImageDownloadItem {
  name: string
  host?: string
  image_dir?: string
}

// Builds the POST /api/msr-images body. Home sends only `name`; office adds the
// tool IP + path field the backend assembles the FTP path from.
export const buildDownloadAllBody = (items: ImageDownloadItem[]) => ({
  images: items.map((it) => {
    const img: Record<string, unknown> = { name: it.name }
    if (it.host) img.host = it.host
    if (it.image_dir) img.path_fields = { image_dir: it.image_dir }
    return img
  })
})
```

- [ ] **Step 4: Run the unit test to verify it passes**

Run (from `front-dev-home/`): `node --test "app/utils/msrImage.test.ts"`
Expected: PASS (2 tests).

- [ ] **Step 5: Add the composable methods**

In `front-dev-home/app/composables/useMsrFileApi.ts`, add the import at the top:

```typescript
import { buildDownloadAllBody, type ImageDownloadItem } from '~/utils/msrImage'
```

Add this interface near the other exports (after `MsrFileParams`):

```typescript
export interface ImageDownloadJob {
  job_id: string
  status: 'running' | 'done' | 'error'
  done: number
  total: number
  ok: number
  ng: number
  failures: { host: string, remote_path: string | null, error: string }[]
  error?: string
}
```

Inside `useMsrFileApi`, before the `return`, add:

```typescript
  const startImageDownload = async (items: ImageDownloadItem[]): Promise<string> => {
    const res = await $fetch<{ job_id: string }>(
      joinApiPath(base, '/msr-images'),
      { method: 'POST', body: buildDownloadAllBody(items) }
    )
    return res.job_id
  }

  const getImageJob = async (jobId: string): Promise<ImageDownloadJob> =>
    await $fetch<ImageDownloadJob>(joinApiPath(base, `/msr-images/${jobId}`))
```

Extend the return:

```typescript
  return { fetchMsrFile, fetchMsrFiles, msrImageUrl, startImageDownload, getImageJob }
```

- [ ] **Step 6: Add the button + progress to `Gallery.vue`**

In `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue`, insert this control bar as the first child inside the `v-else-if="images.length"` grid block's parent (i.e. immediately before the `<div ... grid ...>`), and add the script logic.

Template — add just above the grid `<div>`:

```vue
    <div
      v-if="images.length"
      class="mb-2 flex items-center gap-2"
    >
      <UButton
        size="xs"
        color="neutral"
        variant="soft"
        icon="i-lucide-download"
        :loading="downloading"
        :disabled="downloading"
        @click="downloadAll"
      >
        전체 다운로드
      </UButton>
      <span
        v-if="jobTotal"
        class="font-mono text-[10px] text-(--sk-ink-subtle)"
      >
        {{ jobDone }} / {{ jobTotal }}{{ jobError ? ' · 실패' : '' }}
      </span>
    </div>
```

Script — add inside `<script setup lang="ts">`:

```typescript
const { msrImageUrl, startImageDownload, getImageJob } = useMsrFileApi()

const downloading = ref(false)
const jobDone = ref(0)
const jobTotal = ref(0)
const jobError = ref(false)

const downloadAll = async () => {
  if (downloading.value || !images.value.length) return
  downloading.value = true
  jobError.value = false
  jobDone.value = 0
  jobTotal.value = images.value.length
  try {
    // Home sends names only; office locator fields are added in Phase 2/3.
    const jobId = await startImageDownload(images.value.map(i => ({ name: i.name })))
    for (;;) {
      const job = await getImageJob(jobId)
      jobDone.value = job.done
      jobTotal.value = job.total
      if (job.status === 'done') break
      if (job.status === 'error') { jobError.value = true; break }
      await new Promise(r => setTimeout(r, 1000))
    }
  } catch {
    jobError.value = true
  } finally {
    downloading.value = false
  }
}
```

(Replace the existing `const { msrImageUrl } = useMsrFileApi()` line with the destructure above.)

- [ ] **Step 7: Manual smoke**

Start the app per the `verify` skill (Flask mock on :5050 + Nuxt). Open a skewvoir MSR with images, switch to the SEM Gallery view:
1. Images render (mock SVGs) via `<img>` — unchanged.
2. Click **전체 다운로드** → button shows loading, `N / N` counter advances to complete.
3. Confirm the cache populated: `find var/image_cache/mock -type f | head` lists `.svg` files.
4. Reload the gallery — images still render (now served from the disk cache).

- [ ] **Step 8: Commit**

```bash
git add front-dev-home/app/utils/msrImage.ts front-dev-home/app/utils/msrImage.test.ts \
  front-dev-home/app/composables/useMsrFileApi.ts \
  front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue
git commit -m "feat(msr-image): download-all button + poll in SEM gallery"
```

---

## Final verification

Run the whole backend suite and the frontend unit test:

```bash
python -m unittest discover tests -v
cd front-dev-home && node --test "app/**/*.test.ts"
```

Expected: all pass. Then do the Task 6 manual smoke once more end-to-end.
