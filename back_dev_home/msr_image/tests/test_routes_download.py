import threading
import time

import pytest
from flask import Flask

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import DiskImageCache
from back_dev_home.msr_image.contracts import ImageLocator
from back_dev_home.msr_image.errors import SourceUnavailable
from back_dev_home.msr_image.routes import bp


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    monkeypatch.setenv("IMAGE_CACHE_DIR", str(tmp_path))
    application = Flask(__name__)
    application.register_blueprint(bp, url_prefix="/api")
    application.config["_cache_dir"] = str(tmp_path)
    return application


def _wait_settled(client, job_id, timeout=5.0):
    """Poll until the job leaves 'running' — settled means done OR error."""
    end = time.time() + timeout
    while time.time() < end:
        st = client.get(f"/api/msr-images/{job_id}").get_json()
        if st["status"] != "running":
            return st
        time.sleep(0.02)
    raise AssertionError("job did not settle")


def _wait_done(client, job_id, timeout=5.0):
    st = _wait_settled(client, job_id, timeout)
    assert st["status"] == "done", f"job ended {st['status']}: {st}"
    return st


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


def test_post_returns_202_before_the_listing_finishes(app, monkeypatch):
    """The POST must not wait on the directory listing — office-side that is an
    FTP round-trip to the tool, the slowest thing in the whole request.

    A status-code assertion alone cannot tell the two designs apart (both answer
    202), so this blocks list_images to make its *location* observable: run
    synchronously it stalls the POST and `total` is already final; run in the
    worker the POST answers at once and `total` is still unknown.
    """
    release = threading.Event()
    real_list = data.list_images

    def blocking_list(eqp_ip, class_name, msr):
        release.wait(timeout=5)
        return real_list(eqp_ip, class_name, msr)

    monkeypatch.setattr(data, "list_images", blocking_list)
    client = app.test_client()

    r = client.post(
        "/api/msr-images", json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"}
    )
    assert r.status_code == 202
    job_id = r.get_json()["job_id"]

    # Listing still in flight: the job exists and is running, size not yet known.
    st = client.get(f"/api/msr-images/{job_id}").get_json()
    assert st["status"] == "running"
    assert st["total"] == 0

    release.set()
    st = _wait_done(client, job_id)
    assert st["total"] >= 1  # the listing filled the real count in
    assert st["total"] == st["done"] == st["ok"]
    assert st["ng"] == 0


def test_listing_failure_ends_the_job_in_error(app, monkeypatch):
    """A listing failure is now a job outcome, not a POST outcome.

    The client already holds a job_id by the time listing runs, so the failure
    has to surface through polling as 'error' — never 'done', which a client
    would read as a successful download that happened to find no images.
    """
    def boom(eqp_ip, class_name, msr):
        raise SourceUnavailable("tool listing failed")

    monkeypatch.setattr(data, "list_images", boom)
    client = app.test_client()

    r = client.post(
        "/api/msr-images", json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"}
    )
    assert r.status_code == 202
    job_id = r.get_json()["job_id"]
    assert _wait_settled(client, job_id)["status"] == "error"


def test_download_all_rejects_at_max_jobs(app, monkeypatch):
    # max_jobs=0 → running_count() (>=0) always trips the cap, so a new job is
    # refused with 429 (spec §9 SKEWNONO_MSR_IMAGE_MAX_JOBS).
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_MAX_JOBS", "0")
    r = app.test_client().post(
        "/api/msr-images", json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"}
    )
    assert r.status_code == 429
    assert r.get_json()["code"] == "too_many_jobs"
