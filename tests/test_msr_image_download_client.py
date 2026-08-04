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
    for bad in (
        "../escape.jpeg",
        "a/b.jpeg",
        "",
        ".",
        "..",
        # C1: absolute POSIX path -- Path("out") / this discards "out" entirely.
        "/Users/victim/.ssh",
        # C1: Windows drive-relative form -- no leading slash, so it clears a
        # "/"-only check, yet PureWindowsPath still treats it as an escape.
        "C:evil.exe",
        "C:\\evil.exe",
        "name\x00.jpeg",  # NUL
        "name\x01.jpeg",  # other control char
        " name.jpeg",  # leading whitespace
        "name.jpeg ",  # trailing whitespace
    ):
        with pytest.raises(ValueError):
            mod.safe_filename(bad)


def test_download_msr_rejects_unsafe_msr_directory(mod, tmp_path, monkeypatch):
    """C1: row["msr"] becomes a directory name and must be validated too, not
    just the image name -- and the check must happen before any network call."""

    def fake_call(base, path, token, *, params=None, method="GET", body=None, raw=False):
        raise AssertionError(f"must not call the API for an unsafe msr: {path}")

    monkeypatch.setattr(mod, "api_call", fake_call)
    row = {"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "C:evil.exe"}

    with pytest.raises(ValueError):
        mod.download_msr("http://x", "tok", row, tmp_path, ext="jpg")


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
            return b"BYTES:" + params["name"].encode(), "image/jpeg"
        raise AssertionError(path)

    monkeypatch.setattr(mod, "api_call", fake_call)
    row = {"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"}

    written, failed = mod.download_msr("http://x", "tok", row, tmp_path, ext="jpg")
    assert (written, failed) == (2, 0)
    assert (tmp_path / "MSR_1" / "a.jpeg").read_bytes() == b"BYTES:a.jpeg"
    assert not list((tmp_path / "MSR_1").glob("*.part"))

    # The warm POST must be scoped to the listed names, not unscoped.
    post = [c for c in calls if c[0] == "POST"][0]
    assert post[3]["names"] == ["a.jpeg", "b.jpeg"]
    # The listing must carry the ext filter through.
    listing = [c for c in calls if c[0] == "GET" and c[1] == "/api/msr-images"][0]
    assert listing[2]["ext"] == "jpg"

    # Second run re-downloads nothing.
    assert mod.download_msr("http://x", "tok", row, tmp_path, ext="jpg") == (0, 0)


def test_download_msr_call_order_and_scoped_warm(mod, tmp_path, monkeypatch):
    """I4: the entire point of this client is list -> scoped warm -> fetch.
    Assert the sequence explicitly, with a file already on disk so a warm
    scoped to `pending` is distinguishable from one that reposts everything.
    """
    calls = []

    def fake_call(base, path, token, *, params=None, method="GET", body=None, raw=False):
        calls.append((method, path, params, body))
        if path == "/api/msr-images" and method == "GET":
            return {"images": ["a.jpeg", "b.jpeg", "c.jpeg"], "total": 3}
        if path == "/api/msr-images" and method == "POST":
            return {"job_id": "job1"}
        if path.startswith("/api/msr-images/"):
            return {"status": "done", "done": 2, "total": 2, "ok": 2, "ng": 0, "failures": []}
        if path == "/api/msr-image":
            return b"BYTES:" + params["name"].encode(), "image/jpeg"
        raise AssertionError(path)

    monkeypatch.setattr(mod, "api_call", fake_call)
    row = {"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_ORDER"}

    target = tmp_path / "MSR_ORDER"
    target.mkdir()
    (target / "a.jpeg").write_bytes(b"already-here")

    written, failed = mod.download_msr("http://x", "tok", row, tmp_path, ext="jpg")
    assert (written, failed) == (2, 0)

    kinds = [(method, path) for method, path, _params, _body in calls]
    list_index = kinds.index(("GET", "/api/msr-images"))
    warm_index = kinds.index(("POST", "/api/msr-images"))
    fetch_indices = [i for i, (method, path) in enumerate(kinds) if path == "/api/msr-image"]

    assert list_index < warm_index, "warm must not precede the listing"
    assert fetch_indices, "expected image fetches"
    assert all(warm_index < i for i in fetch_indices), "fetches must come after the warm"

    warm_call = calls[warm_index]
    assert warm_call[3]["names"] == ["b.jpeg", "c.jpeg"], (
        "warm must be scoped to the still-pending names, not the full listing "
        "(a.jpeg already exists on disk)"
    )


def test_download_msr_batches_warm_over_max_names(mod, tmp_path, monkeypatch):
    """I5: a pending list over the server's 500-name cap must be chunked, or
    the warm POST 400s and the whole run degrades to serial FTP fetches."""
    names = [f"{i:04d}.jpeg" for i in range(750)]
    warm_bodies = []

    def fake_call(base, path, token, *, params=None, method="GET", body=None, raw=False):
        if path == "/api/msr-images" and method == "GET":
            return {"images": names, "total": len(names)}
        if path == "/api/msr-images" and method == "POST":
            warm_bodies.append(body["names"])
            return {"job_id": f"job{len(warm_bodies)}"}
        if path.startswith("/api/msr-images/"):
            return {"status": "done"}
        if path == "/api/msr-image":
            return b"x", "image/jpeg"
        raise AssertionError(path)

    monkeypatch.setattr(mod, "api_call", fake_call)
    row = {"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_BIG"}

    written, failed = mod.download_msr("http://x", "tok", row, tmp_path, ext="jpg")
    assert (written, failed) == (750, 0)
    assert len(warm_bodies) == 2
    assert all(len(batch) <= 500 for batch in warm_bodies)
    assert [n for batch in warm_bodies for n in batch] == names


def test_download_msr_skips_non_image_content_type(mod, tmp_path, monkeypatch):
    """I2: a 200 with an HTML body (proxy/captive-portal) must not be saved as
    if it were the image, and must count as a failure."""

    def fake_call(base, path, token, *, params=None, method="GET", body=None, raw=False):
        if path == "/api/msr-images" and method == "GET":
            return {"images": ["a.jpeg"], "total": 1}
        if path == "/api/msr-images" and method == "POST":
            return {"job_id": "job1"}
        if path.startswith("/api/msr-images/"):
            return {"status": "done"}
        if path == "/api/msr-image":
            return b"<html>captive portal</html>", "text/html"
        raise AssertionError(path)

    monkeypatch.setattr(mod, "api_call", fake_call)
    row = {"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_HTML"}

    written, failed = mod.download_msr("http://x", "tok", row, tmp_path, ext="jpg")
    assert (written, failed) == (0, 1)
    assert not (tmp_path / "MSR_HTML" / "a.jpeg").exists()


def test_download_msr_treats_empty_body_as_failure(mod, tmp_path, monkeypatch):
    """I2: a zero-length 200 body must not be written and must count as a
    failure, even when the content-type claims to be an image."""

    def fake_call(base, path, token, *, params=None, method="GET", body=None, raw=False):
        if path == "/api/msr-images" and method == "GET":
            return {"images": ["a.jpeg"], "total": 1}
        if path == "/api/msr-images" and method == "POST":
            return {"job_id": "job1"}
        if path.startswith("/api/msr-images/"):
            return {"status": "done"}
        if path == "/api/msr-image":
            return b"", "image/jpeg"
        raise AssertionError(path)

    monkeypatch.setattr(mod, "api_call", fake_call)
    row = {"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_EMPTY"}

    written, failed = mod.download_msr("http://x", "tok", row, tmp_path, ext="jpg")
    assert (written, failed) == (0, 1)
    assert not (tmp_path / "MSR_EMPTY" / "a.jpeg").exists()


def test_main_returns_nonzero_when_a_download_fails(mod, tmp_path, monkeypatch):
    """I3: per-file/per-row failures must surface as a non-zero exit code,
    not just a printed message with an unconditional `return 0`."""
    monkeypatch.setenv("SKEWNONO_TOKEN", "tok")
    monkeypatch.setattr(
        mod, "search",
        lambda *a, **k: [{"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1", "eqp_id": "EQ1"}],
    )
    monkeypatch.setattr(mod, "download_msr", lambda *a, **k: (0, 1))

    code = mod.main(["--lot", "KPB266344", "--out", str(tmp_path)])
    assert code == 1


def test_main_returns_nonzero_when_a_row_raises_api_error(mod, tmp_path, monkeypatch):
    """I3: a whole-row ApiError is still printed and skipped (per-row
    resilience is kept), but it must not let the run exit 0."""
    monkeypatch.setenv("SKEWNONO_TOKEN", "tok")
    monkeypatch.setattr(
        mod, "search",
        lambda *a, **k: [{"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1", "eqp_id": "EQ1"}],
    )

    def boom(*a, **k):
        raise mod.ApiError(500, "boom", "server error")

    monkeypatch.setattr(mod, "download_msr", boom)

    code = mod.main(["--lot", "KPB266344", "--out", str(tmp_path)])
    assert code == 1


def test_main_returns_zero_when_everything_succeeds(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_TOKEN", "tok")
    monkeypatch.setattr(
        mod, "search",
        lambda *a, **k: [{"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1", "eqp_id": "EQ1"}],
    )
    monkeypatch.setattr(mod, "download_msr", lambda *a, **k: (3, 0))

    code = mod.main(["--lot", "KPB266344", "--out", str(tmp_path)])
    assert code == 0


def test_api_error_carries_code(mod):
    err = mod.ApiError(401, "invalid_token", "API token invalid or revoked")
    assert err.status == 401
    assert err.code == "invalid_token"
    assert "invalid_token" in str(err)
