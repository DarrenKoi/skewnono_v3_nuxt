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


def test_download_all_rejects_at_max_jobs(app, monkeypatch):
    # max_jobs=0 → running_count() (>=0) always trips the cap, so a new job is
    # refused with 429 (spec §9 SKEWNONO_MSR_IMAGE_MAX_JOBS).
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_MAX_JOBS", "0")
    r = app.test_client().post(
        "/api/msr-images", json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"}
    )
    assert r.status_code == 429
    assert r.get_json()["code"] == "too_many_jobs"
