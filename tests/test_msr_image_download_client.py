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
