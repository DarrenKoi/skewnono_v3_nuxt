# MSR Image Download API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users pull metrology images to their local PCs from Python and `curl`, by documenting and packaging the API path that already exists — plus two small endpoint ergonomics fixes.

**Architecture:** No new data path. `GET /api/meas-hist/search` already resolves lot/recipe/date to `(eqp_ip, class_name, msr)`; `GET /api/msr-images` lists; `GET /api/msr-image` transfers bytes; `Authorization: Bearer skn_…` already authenticates all three. This plan adds a `Content-Disposition` header, an `ext` filter applied in `routes.py` (never in the provider seam), a stdlib-only reference client, and a Korean guide.

**Tech Stack:** Flask blueprints, pytest, Python 3.14 (`.venv/bin/python`), markdownlint-cli2.

**Spec:** `docs/superpowers/specs/2026-08-04-msr-image-download-api-design.md`

## Global Constraints

- **Never modify** `back_dev_home/msr_image/data.py`, `providers/mock.py`, `providers/office_example.py`, or `contracts.py`. `data.list_images()` must keep its exact 3-argument signature `(eqp_ip, class_name, msr)`. Widening it forces every office checkout to run `python -m scripts.sync_office_adapters msr_image` before it will boot.
- **Never modify** the rate limiter. `msr_image` is already exempt and already regression-tested at `tests/test_rate_limit.py:61`.
- Run backend tests as `.venv/bin/python -m pytest` **from the repo root** — the `-m` form is what puts the root on `sys.path`.
- Run `npm run lint:md` from the repo root after any Markdown edit. Enforced rules are only MD031 (blank lines around fences), MD040 (language on fences), MD060 (`compact` table style).
- Korean docs use `~입니다.` / `~합니다.` endings.
- The reference client is **standard library only** — no `requests`, no third-party imports. It runs on user PCs that may have no `pip install`.
- Commit only files you personally edited, with explicit pathspecs. `git add -A` / `git add .` / `git commit -a` are banned — other agent sessions share this working tree.
- This is multi-file work, so it runs in a `git worktree` (see Task 0), not the main checkout.

---

### Task 0: Create the isolated worktree

**Files:**

- Create: `../skewnono-msr-image-api/` (worktree on branch `work/msr-image-api`)

**Interfaces:**

- Consumes: nothing
- Produces: the working directory every later task runs in

- [ ] **Step 1: Create the worktree from the repo root**

```bash
git worktree add ../skewnono-msr-image-api -b work/msr-image-api
```

- [ ] **Step 2: Confirm the tests run there before changing anything**

```bash
cd ../skewnono-msr-image-api && .venv/bin/python -m pytest back_dev_home/msr_image -q
```

Expected: all pass. If `.venv` is missing in the worktree, use the main checkout's interpreter by absolute path — do not create a second venv.

**Note on skip counts:** the worktree lacks the gitignored `providers/office.py` files, so some office tests legitimately skip. Compare `passed + skipped` totals against the main checkout, not `passed` alone.

---

### Task 1: `Content-Disposition` on `GET /api/msr-image`

**Files:**

- Modify: `back_dev_home/msr_image/routes.py:71-94`
- Test: `back_dev_home/msr_image/tests/test_routes_serve.py`

**Interfaces:**

- Consumes: `quote` from `urllib.parse` (already imported at `routes.py:5`)
- Produces: `_content_disposition(name: str) -> str`, a module-level helper in `routes.py`. No other task calls it.

- [ ] **Step 1: Write the failing tests**

Append to `back_dev_home/msr_image/tests/test_routes_serve.py`:

```python
def test_serve_sets_content_disposition_filename(client):
    q = "eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    name = client.get(f"/api/msr-images?{q}").get_json()["images"][0]
    r = client.get(f"/api/msr-image?{q}&name={name}")
    assert r.status_code == 200
    cd = r.headers["Content-Disposition"]
    # inline, not attachment: the gallery reads these bytes through <img> and
    # fetch(); inline is neutral there while curl -OJ still picks the name up.
    assert cd.startswith("inline;")
    assert f'filename="{name}"' in cd


def test_serve_escapes_quote_in_filename(client):
    # validate_segment rejects / \ and control chars but NOT a double quote,
    # so the quote is the one character that can break out of the header's
    # quoted-string. It must arrive escaped, not raw.
    name = 'sh"ot.jpeg'
    r = client.get(
        "/api/msr-image?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&name=" + quote(name)
    )
    assert r.status_code == 200
    cd = r.headers["Content-Disposition"]
    assert '\\"' in cd
    assert 'filename="sh"ot.jpeg"' not in cd


def test_serve_handles_non_ascii_filename(client):
    # Werkzeug encodes header values as latin-1 and raises on anything else,
    # so a non-ASCII name must not reach the quoted-string form unencoded.
    name = "샷01.jpeg"
    r = client.get(
        "/api/msr-image?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&name=" + quote(name)
    )
    assert r.status_code == 200
    cd = r.headers["Content-Disposition"]
    assert "filename*=UTF-8''" in cd
```

Add `quote` to that file's imports — change line 1 from `from urllib.parse import unquote` to:

```python
from urllib.parse import quote, unquote
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python -m pytest back_dev_home/msr_image/tests/test_routes_serve.py -k "disposition or escapes_quote or non_ascii" -v
```

Expected: 3 FAIL with `KeyError: 'Content-Disposition'`.

- [ ] **Step 3: Add the helper to `routes.py`**

Insert after `_require` (i.e. after `routes.py:46`):

```python
def _content_disposition(name: str) -> str:
    """RFC 6266 disposition for a caller-supplied image filename.

    ``inline``, not ``attachment``: the gallery reads these bytes through
    ``<img :src>`` and ``fetch()`` + blob, and inline is neutral for both
    while ``curl -OJ`` still picks the filename up either way. The target
    audience is Python and curl, so attachment would add browser-behavior
    risk for no gain.

    Both parameter forms are emitted. ``validate_locator`` rejects ``/``,
    ``\\`` and control chars but NOT a double quote, so the quoted-string
    form is escaped rather than trusted; and a non-ASCII name cannot ride
    in it at all, because Werkzeug encodes header values as latin-1 and
    raises on anything else.
    """
    ascii_name = name.encode("ascii", "replace").decode("ascii")
    escaped = ascii_name.replace("\\", "\\\\").replace('"', '\\"')
    return f"inline; filename=\"{escaped}\"; filename*=UTF-8''{quote(name, safe='')}"
```

- [ ] **Step 4: Emit the header in `serve_image_route`**

Replace `routes.py:91` (`headers = {"Cache-Control": "public, max-age=3600"}`) with:

```python
    headers = {
        "Cache-Control": "public, max-age=3600",
        "Content-Disposition": _content_disposition(args["name"]),
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/msr_image/tests/test_routes_serve.py -v
```

Expected: all PASS, including the pre-existing tests.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/msr_image/routes.py back_dev_home/msr_image/tests/test_routes_serve.py
git commit -m "feat(msr_image): send Content-Disposition with an escaped filename

External Python/curl callers download these bytes to disk, so the response
should name the file. inline rather than attachment: the gallery reads the
same URL through <img> and fetch(), where inline is neutral, and curl -OJ
takes the name from either form.

validate_segment rejects / \\ and control chars but not a double quote, so
the quoted-string form is escaped; a filename*=UTF-8'' form is emitted
alongside it because Werkzeug encodes headers as latin-1 and would raise on
a non-ASCII name."
```

---

### Task 2: `ext` filter on `GET /api/msr-images`

**Files:**

- Modify: `back_dev_home/msr_image/routes.py:49-68`
- Test: `back_dev_home/msr_image/tests/test_routes_serve.py`
- Test: `back_dev_home/msr_image/tests/test_data_seam.py`

**Interfaces:**

- Consumes: `data.list_images(eqp_ip, class_name, msr)` — unchanged 3-arg call
- Produces: `_EXT_GROUPS: dict[str, tuple[str, ...]]` in `routes.py`. No other task imports it.

- [ ] **Step 1: Write the failing tests**

Append to `back_dev_home/msr_image/tests/test_routes_serve.py`:

```python
def test_list_ext_jpg_returns_only_jpeg_family(client):
    r = client.get("/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&ext=jpg")
    assert r.status_code == 200
    images = r.get_json()["images"]
    assert images
    assert all(n.endswith((".jpg", ".jpeg")) for n in images)
    assert r.get_json()["total"] == len(images)


def test_list_ext_tif_returns_only_tiff_family(client):
    r = client.get("/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&ext=tif")
    assert r.status_code == 200
    assert all(n.endswith((".tif", ".tiff")) for n in r.get_json()["images"])


def test_list_without_ext_is_unchanged(client):
    # Regression guard for the gallery: it sends no ext and must keep seeing
    # every file the provider returns.
    q = "eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    everything = client.get(f"/api/msr-images?{q}").get_json()["images"]
    jpg = client.get(f"/api/msr-images?{q}&ext=jpg").get_json()["images"]
    tif = client.get(f"/api/msr-images?{q}&ext=tif").get_json()["images"]
    assert sorted(everything) == sorted(jpg + tif)
    assert len(everything) > len(jpg)  # the mock always emits at least one .tif


def test_list_rejects_unknown_ext(client):
    # A silent empty list would read as "this MSR has no images".
    r = client.get("/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&ext=png")
    assert r.status_code == 400
    assert "ext" in r.get_json()["error"]
```

Append to `back_dev_home/msr_image/tests/test_data_seam.py`:

```python
def test_list_images_seam_signature_is_three_args():
    """The ext filter lives in routes.py, deliberately, and must stay there.

    Pushing it into the provider would widen this signature, and every office
    checkout's gitignored providers/office.py is a COPY -- it would keep the
    old signature and the app factory would fail to boot until someone ran
    `python -m scripts.sync_office_adapters msr_image`. Filtering a returned
    list is presentation, not data access.
    """
    import inspect

    params = list(inspect.signature(data.list_images).parameters)
    assert params == ["eqp_ip", "class_name", "msr"]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python -m pytest back_dev_home/msr_image/tests/test_routes_serve.py -k ext -v
.venv/bin/python -m pytest back_dev_home/msr_image/tests/test_data_seam.py -k signature -v
```

Expected: the four `ext` tests FAIL (unknown `ext` is currently ignored, so `ext=png` returns 200). The signature test PASSES already — it is a guard against future change, not a red test.

- [ ] **Step 3: Add the extension groups to `routes.py`**

Insert after `bp = Blueprint("msr_image", __name__)` (i.e. after `routes.py:17`):

```python
# Tools are not consistent about which spelling they write -- office serves
# .jpeg/.jpg/.tif/.tiff (MIGRATION.md, office 확인 2026-07-24) while the mock
# emits only .jpeg/.tif. Grouping means a caller never has to know which
# spelling a given tool happened to use.
_EXT_GROUPS: dict[str, tuple[str, ...]] = {
    "jpg": (".jpg", ".jpeg"),
    "tif": (".tif", ".tiff"),
}
```

- [ ] **Step 4: Apply the filter in `list_images_route`**

In `list_images_route`, replace the body between `cfg = load_config()` and the `body:` assignment so it reads:

```python
    cfg = load_config()
    ext = (request.args.get("ext") or "").strip().lower()
    if ext and ext not in _EXT_GROUPS:
        allowed = ", ".join(sorted(_EXT_GROUPS))
        return jsonify({"error": f"unknown ext {ext!r}; allowed: {allowed}"}), 400
    try:
        validate_tool_ip(args["eqp_ip"], cfg.allowed_subnets)
        validate_segment(args["class_name"], "class_name")
        validate_segment(args["msr"], "msr")
        names = data.list_images(args["eqp_ip"], args["class_name"], args["msr"])
    except MsrImageError as exc:
        return _error(exc)
    if ext:
        suffixes = _EXT_GROUPS[ext]
        names = [n for n in names if n.lower().endswith(suffixes)]
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/msr_image -q
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/msr_image/routes.py \
        back_dev_home/msr_image/tests/test_routes_serve.py \
        back_dev_home/msr_image/tests/test_data_seam.py
git commit -m "feat(msr_image): add ext=jpg|tif filter to the image listing

Users pulling images to their PC to LOOK at them want the JPEG previews,
not the TIFF originals a browser cannot render. Extensions are grouped
because tools are inconsistent about .jpg/.jpeg and .tif/.tiff.

The filter is applied in routes.py, not in the provider: data.list_images()
keeps its 3-arg signature so no office.py copy needs resyncing, and
filtering a returned list is presentation rather than data access. A
contract test pins the signature so the filter cannot drift into the seam.

An unknown ext is a 400 rather than an empty list, which would otherwise
read as 'this MSR has no images'."
```

---

### Task 3: Reference client

**Files:**

- Create: `scripts/clients/msr_image_download.py`
- Test: `tests/test_msr_image_download_client.py`

**Interfaces:**

- Consumes: the endpoints from Tasks 1–2 and the pre-existing `/api/meas-hist/search`
- Produces: `build_url`, `ApiError`, `safe_filename`, `download_msr`, `main` — all in `scripts/clients/msr_image_download.py`. Task 4 quotes this file's usage in the guide.

**Critical design note for the implementer:** the order of calls is `list → warm(names) → fetch`, **not** `warm → list → fetch`. Two reasons. Office-side, `GET /api/msr-images` is an FTP listing call and `POST /api/msr-images` does its own listing internally, so warming first costs two listings instead of one. And passing `names` to the POST (`routes.py:155-161`) scopes the warm job to exactly the files the `ext` filter kept, so a user asking for JPEGs does not make the tool serve TIFFs nobody wanted. `routes.py:123-126` additionally drops names already in cache, so a re-run warms nothing.

There is no `scripts/__init__.py` in this repo; scripts are loaded by path in tests (see `tests/test_inspect_redis_key_script.py`). Do not add one.

- [ ] **Step 1: Write the failing test**

Create `tests/test_msr_image_download_client.py`:

```python
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "clients" / "msr_image_download.py"


def _load():
    spec = importlib.util.spec_from_file_location("msr_image_download", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load()


def test_build_url_encodes_params(mod):
    url = mod.build_url("http://x/", "/api/msr-image", {"name": "a b.jpeg", "msr": "M1"})
    assert url.startswith("http://x/api/msr-image?")
    assert "name=a+b.jpeg" in url or "name=a%20b.jpeg" in url
    assert "msr=M1" in url


def test_safe_filename_rejects_traversal(mod):
    assert mod.safe_filename("shot01.jpeg") == "shot01.jpeg"
    for bad in ("../escape.jpeg", "a/b.jpeg", "", ".", ".."):
        with pytest.raises(ValueError):
            mod.safe_filename(bad)


def test_download_msr_writes_files_and_skips_existing(mod, tmp_path, monkeypatch):
    calls = []

    def fake_call(base, path, token, *, params=None, method="GET", body=None, raw=False):
        calls.append((method, path, params, body))
        if path == "/api/msr-images" and method == "GET":
            return {"images": ["a.jpeg", "b.jpeg"], "total": 2}
        if path == "/api/msr-images" and method == "POST":
            return {"job_id": "job1"}
        if path.startswith("/api/msr-images/"):
            return {"status": "done", "done": 2, "total": 2, "ok": 2, "ng": 0, "failures": []}
        if path == "/api/msr-image":
            return b"BYTES:" + params["name"].encode()
        raise AssertionError(path)

    monkeypatch.setattr(mod, "api_call", fake_call)
    row = {"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"}

    written = mod.download_msr("http://x", "tok", row, tmp_path, ext="jpg")
    assert written == 2
    assert (tmp_path / "MSR_1" / "a.jpeg").read_bytes() == b"BYTES:a.jpeg"
    assert not list((tmp_path / "MSR_1").glob("*.part"))

    # The warm POST must be scoped to the listed names, not unscoped.
    post = [c for c in calls if c[0] == "POST"][0]
    assert post[3]["names"] == ["a.jpeg", "b.jpeg"]
    # The listing must carry the ext filter through.
    listing = [c for c in calls if c[0] == "GET" and c[1] == "/api/msr-images"][0]
    assert listing[2]["ext"] == "jpg"

    # Second run re-downloads nothing.
    assert mod.download_msr("http://x", "tok", row, tmp_path, ext="jpg") == 0


def test_api_error_carries_code(mod):
    err = mod.ApiError(401, "invalid_token", "API token invalid or revoked")
    assert err.status == 401
    assert err.code == "invalid_token"
    assert "invalid_token" in str(err)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_msr_image_download_client.py -v
```

Expected: FAIL — the script file does not exist yet.

- [ ] **Step 3: Write the client**

Create `scripts/clients/msr_image_download.py`:

```python
#!/usr/bin/env python3
"""Download SKEWNONO metrology images to this PC.

Standard library only, on purpose -- this file is meant to be copied to a
user's machine, and a controlled in-house PC may have no `pip install`.

    export SKEWNONO_TOKEN=skn_...
    python msr_image_download.py --lot KPB266344 --ext jpg --out ./images

Mint the token in the web UI: settings page -> API tokens. The plaintext is
shown exactly once.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE = "http://skewnono.skhynix.com"
SEARCH_PATH = "/api/meas-hist/search"
LIST_PATH = "/api/msr-images"
IMAGE_PATH = "/api/msr-image"
TIMEOUT = 60


class ApiError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"HTTP {status} [{code}] {message}")
        self.status = status
        self.code = code
        self.message = message


def build_url(base: str, path: str, params: dict | None = None) -> str:
    url = base.rstrip("/") + path
    if params:
        url += "?" + urlencode(params)
    return url


def api_call(base, path, token, *, params=None, method="GET", body=None, raw=False):
    """One HTTP call. Returns parsed JSON, or raw bytes when raw=True."""
    data = json.dumps(body).encode() if body is not None else None
    req = Request(build_url(base, path, params), data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            payload = resp.read()
    except HTTPError as exc:
        detail = exc.read()
        try:
            parsed = json.loads(detail)
        except ValueError:
            parsed = {}
        raise ApiError(
            exc.code, parsed.get("code", ""), parsed.get("error", exc.reason or "")
        ) from None
    except URLError as exc:
        raise ApiError(0, "unreachable", str(exc.reason)) from None
    return payload if raw else json.loads(payload)


def call_with_retry(fn, attempts: int = 5):
    """Retry only 429. Everything else is either fatal or the caller's to handle.

    Only the search call can 429 -- the msr_image blueprint is exempt from the
    per-user API budget -- but the helper is shared for simplicity.
    """
    delay = 1.0
    for attempt in range(attempts):
        try:
            return fn()
        except ApiError as exc:
            if exc.status != 429 or attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2


def safe_filename(name: str) -> str:
    """The server validates these names, but this function writes to the
    user's disk -- re-check rather than trust a remote value."""
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError(f"unsafe filename: {name!r}")
    return name


def search(base, token, *, lot=None, recipe=None, eq=None, msr=None,
           date_from=None, date_to=None, limit=50) -> list[dict]:
    params = {"limit": limit}
    # NOTE: `lot` matches lot_id (e.g. KPB266344), NOT the 3-char lot_cd.
    # Passing a lot_cd returns zero rows with no error.
    for key, value in (("lot", lot), ("recipe", recipe), ("eq", eq), ("msr", msr),
                       ("from", date_from), ("to", date_to)):
        if value:
            params[key] = value
    body = call_with_retry(lambda: api_call(base, SEARCH_PATH, token, params=params))
    return body["rows"]


def warm(base, token, row, names) -> None:
    """Ask the server to pull these files from the tool in parallel.

    Skipping this step is the single biggest performance mistake a client can
    make: office-side every uncached GET is a serial FTP round-trip to the
    tool, while the warm job fetches with SKEWNONO_TOOL_FTP_CONCURRENCY (6)
    connections. The job is scoped to `names` so an ext filter is honored and
    files already cached are not refetched.
    """
    payload = {
        "eqp_ip": row["eqp_ip"],
        "class_name": row["class_name"],
        "msr": row["msr"],
        "names": names,
    }
    try:
        job = api_call(base, LIST_PATH, token, method="POST", body=payload)
    except ApiError as exc:
        print(f"  warm skipped ({exc.code or exc.status}); fetching directly")
        return
    job_id = job["job_id"]
    for _ in range(600):
        try:
            status = api_call(base, f"{LIST_PATH}/{job_id}", token)
        except ApiError:
            return  # job expired or unknown; the GETs below still work
        if status["status"] != "running":
            if status["status"] == "error":
                # A whole-job failure still leaves the cache partly warm, and
                # per-file failures surface individually on the GETs below.
                print("  warm job reported error; continuing")
            return
        time.sleep(0.5)


def download_msr(base, token, row, out_dir, *, ext=None) -> int:
    """List, warm, then fetch one MSR's images. Returns files newly written."""
    params = {"eqp_ip": row["eqp_ip"], "class_name": row["class_name"], "msr": row["msr"]}
    if ext:
        params["ext"] = ext
    names = api_call(base, LIST_PATH, token, params=params)["images"]
    if not names:
        return 0

    target = out_dir / row["msr"]
    target.mkdir(parents=True, exist_ok=True)
    pending = [n for n in names if not (target / safe_filename(n)).exists()]
    if not pending:
        return 0

    warm(base, token, row, pending)

    written = 0
    for name in pending:
        dest = target / safe_filename(name)
        try:
            payload = api_call(
                base, IMAGE_PATH, token, params={**params, "name": name}, raw=True
            )
        except ApiError as exc:
            print(f"  {name}: {exc}")
            continue
        # Write to .part and rename, so an interrupted run never leaves a
        # truncated file that the exists() check above would later skip.
        part = dest.with_suffix(dest.suffix + ".part")
        part.write_bytes(payload)
        part.replace(dest)
        written += 1
    return written


def main(argv=None) -> int:
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("SKEWNONO_BASE_URL", DEFAULT_BASE))
    parser.add_argument("--lot", help="lot_id, e.g. KPB266344 (NOT the 3-char lot_cd)")
    parser.add_argument("--recipe")
    parser.add_argument("--eq", help="equipment id, e.g. ECDX285")
    parser.add_argument("--msr")
    parser.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="YYYY-MM-DD")
    parser.add_argument("--ext", choices=("jpg", "tif"), help="omit for every file")
    parser.add_argument("--limit", type=int, default=50, help="max MSRs to process")
    parser.add_argument("--out", default="./msr_images")
    args = parser.parse_args(argv)

    token = os.environ.get("SKEWNONO_TOKEN")
    if not token:
        print("SKEWNONO_TOKEN is not set. Mint one in the web UI: settings -> API tokens.")
        return 2
    if not any((args.lot, args.recipe, args.eq, args.msr)):
        print("Give at least one of --lot / --recipe / --eq / --msr.")
        return 2

    out_dir = Path(args.out)
    try:
        rows = search(
            args.base_url, token, lot=args.lot, recipe=args.recipe, eq=args.eq,
            msr=args.msr, date_from=args.date_from, date_to=args.date_to,
            limit=args.limit,
        )
    except ApiError as exc:
        print(f"search failed: {exc}")
        return 1

    if not rows:
        print("No measurements matched. Note that --lot takes a lot_id "
              "(KPB266344), not a lot_cd (KPB).")
        return 1

    print(f"{len(rows)} measurement(s) matched.")
    total = 0
    for row in rows:
        print(f"- {row['msr']} ({row['eqp_id']})")
        try:
            total += download_msr(args.base_url, token, row, out_dir, ext=args.ext)
        except ApiError as exc:
            print(f"  failed: {exc}")
    print(f"Done. {total} new file(s) under {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_msr_image_download_client.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Smoke-run against the home Flask mock**

In one terminal, from the repo root: `.venv/bin/python index.py`. In another:

```bash
SKEWNONO_TOKEN=unused .venv/bin/python scripts/clients/msr_image_download.py \
  --base-url http://localhost:5050 --limit 2 --ext jpg --out /tmp/msr_smoke
```

The mock accepts any bearer value only if a token exists; if it 401s, instead export nothing and add `--base-url` with a `LASTUSER` cookie flow, or mint a token via the running app's settings page. Expected: files appear under `/tmp/msr_smoke/<msr>/`, and a second run reports `0 new file(s)`.

- [ ] **Step 6: Commit**

```bash
git add scripts/clients/msr_image_download.py tests/test_msr_image_download_client.py
git commit -m "feat(scripts): stdlib reference client for MSR image download

Copy-one-file client for users pulling images to their PC from Python. No
third-party imports, because a controlled in-house PC may have no
pip install.

The call order is list -> scoped warm -> fetch, not warm -> list -> fetch.
Office-side both the listing endpoint and the warm job do an FTP listing, so
warming first costs two; and passing names to the POST scopes the warm to
what the ext filter kept, so asking for JPEGs does not make the tool serve
TIFFs. Skipping the warm entirely turns N images into N serial FTP round
trips, which is the mistake this file exists to prevent.

Files are written via .part and renamed, so an interrupted run cannot leave
a truncated file that the resume check would later skip."
```

---

### Task 4: Korean usage guide

**Files:**

- Create: `docs/back-end/msr-image-download.md`

**Interfaces:**

- Consumes: everything from Tasks 1–3
- Produces: nothing code-level

- [ ] **Step 1: Write the guide**

Create `docs/back-end/msr-image-download.md` covering, in this order, in Korean with `~입니다.`/`~합니다.` endings:

1. **개요** — who this is for (Python/curl users) and what it produces (image files on their PC).
2. **토큰 발급** — settings page → API tokens, plaintext shown once, link to `api-tokens.md`. State that issuing requires a browser session: a script cannot mint its own token (`api_tokens/routes.py:16-27`).
3. **4단계 흐름** — a fenced `text` block:

```text
1. GET  /api/meas-hist/search   lot/recipe/eq/기간  → rows (eqp_ip, class_name, msr)
2. GET  /api/msr-images         ext=jpg             → 파일명 목록
3. POST /api/msr-images         names=[...]         → warm job (job_id)
4. GET  /api/msr-image          name=…              → 이미지 바이트
```

1. **파라미터 표** — one compact table per endpoint. For search, state explicitly that `lot`은 `lot_id`(예: `KPB266344`)와 일치하며 `lot_cd`(예: `KPB`)를 넣으면 **오류 없이 0건**이 반환됩니다.
2. **curl 예시** — three fenced `bash` blocks: single image with `-OJ`, listing with `ext=jpg`, warm job POST with a JSON body.
3. **Python 예시** — point at `scripts/clients/msr_image_download.py`, show the command line, and quote the `download_msr` call order.
4. **3번을 먼저 호출하면 안 되는 이유** — the two-listings and unscoped-warm argument from Task 3's design note.
5. **TIFF 안내** — browsers cannot render TIFF; `ext=jpg` is the viewable set.
6. **오류 표** — reproduce the spec §7 table.
7. **rate limit** — images are exempt (`tests/test_rate_limit.py:61`); only the search call counts against 20 req / 5 s.

- [ ] **Step 2: Lint**

```bash
npm run lint:md
```

Expected: `Summary: 0 error(s)`.

- [ ] **Step 3: Commit**

```bash
git add docs/back-end/msr-image-download.md
git commit -m "docs(back-end): guide for downloading MSR images via the API

Korean walkthrough for Python and curl users: token issuance, the four-step
endpoint flow, parameter tables, and the error table.

Two traps get explicit callouts. --lot matches lot_id, not lot_cd, and a
lot_cd returns zero rows with no error. And the warm job must be called
after the listing with a names scope, not before it, or the tool does two
FTP listings and serves files the ext filter would have dropped."
```

---

### Task 5: `api-tokens.md` SSO cleanup — separate commit

**Files:**

- Modify: `docs/back-end/api-tokens.md:42,44,46`
- Modify: `back_dev_home/_auth/middleware.py:26`

**Interfaces:**

- Consumes: nothing
- Produces: nothing. **Documentation and comments only — no behavior changes, no test changes.**

- [ ] **Step 1: Fix the middleware decision table**

In `docs/back-end/api-tokens.md`, replace rows 1, 3 and 5 of the table at lines 40-46. The corrected table:

```markdown
| 순서 | 조건 | 결과 |
| --- | --- | --- |
| 1 | `/api/*` 요청 + `Authorization: Bearer skn_...` 헤더 | 토큰 조회 → 일치하면 `g.user_id = 소유자`, `g.api_token_id = 토큰 ID` |
| 2 | `LASTUSER` 신원 쿠키 | `g.user_id` 설정 (`SOURCE_COOKIE`) |
| 3 | 사용자가 직접 선언한 신원 | `g.user_id` 설정 (`SOURCE_DECLARED`) — 쿠키보다 아래입니다 |
| 4 | 위 모두 실패 | 단계별 대체 신원 (`IdentityProvider.fallback_identity()`) — 홈은 개발용 대역, 클라우드는 `anonymous` |
| 5 | 신원이 전혀 없고 `/api/*` | 401 응답 |
| 6 | 신원이 전혀 없고 그 외 경로 | 그대로 통과 — SPA mount가 응답합니다 |
```

Then replace the paragraph at line 48 (`순서가 중요합니다…`) so it keeps the "token before cookie" point but drops the SSO framing, and replace line 50's SSO reference with the 401-not-redirect point. Add one sentence recording why row 6 is a fallthrough:

> Phase 3에서 이 자리에 SSO 리다이렉트를 넣었다가 브라우저가 앱과 로그인
> 사이를 무한히 오간 사례가 있어, 지금은 통과시킵니다
> (`_auth/middleware.py:130-142`).

- [ ] **Step 2: Fix the stale docstring in the middleware**

In `back_dev_home/_auth/middleware.py:26`, change:

```python
      matched=False           → no Authorization header, fall through to SSO
```

to:

```python
      matched=False           → no Authorization header, fall through to cookie
```

- [ ] **Step 3: Confirm nothing behavioral changed**

```bash
.venv/bin/python -m pytest back_dev_home/_auth tests/test_app_factory_session.py -q
npm run lint:md
```

Expected: all PASS, `Summary: 0 error(s)`.

- [ ] **Step 4: Commit**

```bash
git add docs/back-end/api-tokens.md back_dev_home/_auth/middleware.py
git commit -m "docs(back-end): drop the removed SSO login flow from api-tokens.md

The middleware decision table still listed a /login public path and claimed
an unauthenticated non-API request redirects to SSO. There is no /login
route (_auth/routes.py:7 calls it 'the old SSO login route'), and the
request falls through to the SPA mount instead -- middleware.py's own
comment records that shipping a redirect there once looped the browser
between the app and SSO in Phase 3.

Rewritten around what the code does: bearer token, then LASTUSER cookie,
then declared identity, then the per-phase fallback. Comment-and-docs only;
no behavior change, which is why no test changes accompany it.

This file is about to be linked from the new MSR image download guide as
required reading, so its first and last rows should not be wrong."
```

---

### Task 6: Full verification and merge

**Files:** none modified

- [ ] **Step 1: Run the whole backend suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: all pass. Baseline before this work was 2502 tests. Remember the worktree has no `providers/office.py`, so compare `passed + skipped`, not `passed`.

- [ ] **Step 2: Verify the gallery in a browser**

This is the check promised in spec §4.1 — the claim that `Content-Disposition: inline` is neutral for `<img>` was reasoned from the spec, not observed.

Start Flask (`.venv/bin/python index.py`) and Nuxt (`npm run dev` in `front-dev-home/`), then drive Playwright MCP to a skewvoir workspace, open the 이미지 갤러리 view, and confirm:

- thumbnails render (they are SVG at home, which still exercises the header path)
- opening the viewer shows an image, not a download prompt
- a `.tif` entry still shows the download fallback link
- screenshot to `.playwright-mcp/screenshots/msr-image-gallery-content-disposition.png`

- [ ] **Step 3: Verify the new listing filter in the running app**

```bash
curl -s -b LASTUSER=local-dev \
  'http://localhost:5050/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&ext=jpg' | head -c 300
curl -s -b LASTUSER=local-dev -o /dev/null -w '%{http_code}\n' \
  'http://localhost:5050/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&ext=png'
```

Expected: only `.jpeg` names in the first; `400` from the second.

- [ ] **Step 4: Merge and tear the worktree down**

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git merge --ff-only work/msr-image-api && git push
git worktree remove ../skewnono-msr-image-api && git branch -d work/msr-image-api
git worktree list   # must show the main tree alone
```

If `--ff-only` refuses, `main` moved while you worked. Rebase the branch and re-run the full suite before merging — a clean auto-merge can still produce broken office-only code that home tests pass.

---

## Self-Review

**Spec coverage:**

| Spec § | Task |
| --- | --- |
| §4 `Content-Disposition` | Task 1 |
| §5 `ext` filter, routes-not-provider | Task 2 (+ signature guard) |
| §6 reference client, stdlib, warm ordering | Task 3 |
| §6.3 resume | Task 3 (with `.part` atomicity — see deviation below) |
| §7 error handling | Task 3 (`ApiError`, `call_with_retry`, warm fallbacks) |
| §8 Korean guide | Task 4 |
| §9 tests: header, ext, default unchanged, signature, client, browser | Tasks 1, 2, 3, 6 |
| §10 `api-tokens.md` cleanup, separate commit | Task 5 |

**Deviations from the spec, deliberate:**

1. **§6.1 call order reversed.** The spec has `warm → list → fetch`; the plan has `list → scoped warm → fetch`. Rationale in Task 3's design note: it costs one FTP listing instead of two and honors the `ext` filter when warming. Strictly better, same result.
2. **`.part` + rename added to §6.3.** Plain skip-if-exists would permanently skip a file truncated by an interrupted run, which contradicts the spec's own claim that a re-run resumes. Two lines.

**Type consistency:** `api_call` is the single HTTP entry point and is monkeypatched by name in the client test; `download_msr`, `safe_filename`, `build_url`, `ApiError` are used with identical signatures in the test and the implementation. `_EXT_GROUPS` and `_content_disposition` are private to `routes.py` and referenced by no other task.
