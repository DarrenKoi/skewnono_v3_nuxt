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
