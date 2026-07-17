"""Route tests for the analysis-image gallery (Flask test_client)."""

from urllib.parse import quote

import pytest
from flask import Flask

from back_dev_home.afm import data
from back_dev_home.afm.providers import mock
from back_dev_home.afm.routes import bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")
    return app.test_client()


def _capture_row():
    field = mock.IMAGE_TYPE_FIELDS["capture"]
    for row in data.list_afm_files(None):
        names = [n for n in row.get(field, []) if n != "no files"]
        if names:
            return row, names
    raise AssertionError("no capture row")


def test_list_route_returns_images(client):
    row, names = _capture_row()
    fn = quote(row["filename"], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/capture?tool={row['tool_name']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["count"] == len(names)
    assert [img["name"] for img in body["data"]] == names
    assert body["tool"] == row["tool_name"]


def test_list_route_unknown_type_404(client):
    row, _ = _capture_row()
    fn = quote(row["filename"], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/bogus?tool={row['tool_name']}")
    assert r.status_code == 404


def test_serve_route_returns_svg(client):
    row, names = _capture_row()
    fn = quote(row["filename"], safe="")
    nm = quote(names[0], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/capture/{nm}?tool={row['tool_name']}")
    assert r.status_code == 200
    assert r.mimetype == "image/svg+xml"
    assert r.get_data(as_text=True).startswith("<svg")


def test_serve_route_missing_name_404(client):
    row, _ = _capture_row()
    fn = quote(row["filename"], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/capture/not-real.png?tool={row['tool_name']}")
    assert r.status_code == 404


def test_serve_route_unknown_type_404(client):
    row, names = _capture_row()
    fn = quote(row["filename"], safe="")
    nm = quote(names[0], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/bogus/{nm}?tool={row['tool_name']}")
    assert r.status_code == 404
