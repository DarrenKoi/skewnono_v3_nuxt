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


def test_scoped_download_fetches_exactly_the_named_images(app):
    """`names` skips the tool listing and warms only the caller's files —
    the parameter-scoped cache warmer's contract."""
    client = app.test_client()
    listed = client.get(
        "/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    ).get_json()["images"]
    wanted, skipped = listed[:2], listed[2]

    r = client.post(
        "/api/msr-images",
        json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1", "names": wanted},
    )
    assert r.status_code == 202
    st = _wait_done(client, r.get_json()["job_id"])
    assert st["total"] == st["ok"] == len(wanted)

    cache = DiskImageCache(app.config["_cache_dir"])
    for name in wanted:
        assert cache.get(ImageLocator("10.0.0.1", "ADI", "MSR_1", name)) is not None
    assert cache.get(ImageLocator("10.0.0.1", "ADI", "MSR_1", skipped)) is None


def test_scoped_download_skips_names_already_cached(app):
    """Re-warms (parameter switches, post-429 refires) must not pull files the
    cache already holds from the tool again."""
    client = app.test_client()
    listed = client.get(
        "/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    ).get_json()["images"]
    cached, fresh = listed[0], listed[1]

    warm = client.post(
        "/api/msr-images",
        json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1", "names": [cached]},
    )
    _wait_done(client, warm.get_json()["job_id"])

    r = client.post(
        "/api/msr-images",
        json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1", "names": [cached, fresh]},
    )
    st = _wait_done(client, r.get_json()["job_id"])
    assert st["total"] == st["ok"] == 1  # only the uncached file was fetched


def test_scoped_download_empty_names_means_everything(app):
    """[] is 'no scope', not 'fetch nothing' — same as omitting the key."""
    client = app.test_client()
    listed = client.get(
        "/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    ).get_json()["images"]

    r = client.post(
        "/api/msr-images",
        json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1", "names": []},
    )
    assert r.status_code == 202
    assert _wait_done(client, r.get_json()["job_id"])["total"] == len(listed)


def test_scoped_download_rejects_bad_names(app):
    client = app.test_client()
    base = {"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"}

    assert client.post("/api/msr-images", json={**base, "names": "a.jpeg"}).status_code == 400
    assert client.post("/api/msr-images", json={**base, "names": [1, 2]}).status_code == 400
    assert client.post("/api/msr-images", json={**base, "names": ["../escape.jpeg"]}).status_code == 400
    assert (
        client.post("/api/msr-images", json={**base, "names": ["a.jpeg"] * 501}).status_code
        == 400
    )


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


def test_routes_use_the_selected_registry(app, monkeypatch):
    """Every route must resolve its registry through make_registry.

    Hardcoding the process-memory singleton would leave the office Redis
    registry unreachable no matter how the instance is configured. Swapping in
    a distinct registry proves all three touch points route through the
    selector: the POST that mints the job, the worker thread that counts, and
    the poll that reads it back.
    """
    from back_dev_home.msr_image import routes as routes_mod
    from back_dev_home.msr_image.jobs import MemoryJobRegistry

    selected = MemoryJobRegistry()
    monkeypatch.setattr(routes_mod, "make_registry", lambda cfg, provider: selected)

    client = app.test_client()
    r = client.post(
        "/api/msr-images", json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"}
    )
    assert r.status_code == 202
    job_id = r.get_json()["job_id"]

    assert selected.get(job_id) is not None, "job was minted somewhere else"
    st = _wait_done(client, job_id)  # polled back out of the selected registry
    assert st["ok"] >= 1
    assert selected.get(job_id)["status"] == "done"  # worker counted here too


def test_download_all_rejects_at_max_jobs(app, monkeypatch):
    # max_jobs=0 → running_count() (>=0) always trips the cap, so a new job is
    # refused with 429 (spec §9 SKEWNONO_MSR_IMAGE_MAX_JOBS).
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_MAX_JOBS", "0")
    r = app.test_client().post(
        "/api/msr-images", json={"eqp_ip": "10.0.0.1", "class_name": "ADI", "msr": "MSR_1"}
    )
    assert r.status_code == 429
    assert r.get_json()["code"] == "too_many_jobs"
