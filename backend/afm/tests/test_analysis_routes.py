"""Route tests for the analysis-image gallery (Flask test_client)."""

from urllib.parse import quote

import pytest
from flask import Flask

from backend.afm import data
from backend.afm.providers import mock
from backend.afm.routes import bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")
    return app.test_client()


def _capture_row():
    field = mock.IMAGE_TYPE_FIELDS["capture"]
    for row in data.list_afm_files(None):
        names = row.get(field, [])
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


def _tiff_row():
    field = mock.IMAGE_TYPE_FIELDS["tiff"]
    for row in data.list_afm_files(None):
        names = row.get(field, [])
        if names:
            return row, names
    raise AssertionError("no tiff row")


def test_only_result_images_offer_an_original(client):
    row, _ = _tiff_row()
    fn = quote(row["filename"], safe="")
    tiff = client.get(f"/api/afm/files/{fn}/images/tiff?tool={row['tool_name']}").get_json()["data"]
    capture = client.get(f"/api/afm/files/{fn}/images/capture?tool={row['tool_name']}").get_json()["data"]
    assert all("/tiff/" in img["original_url"] for img in tiff)
    assert all("original_url" not in img for img in capture)


def test_original_url_downloads_a_real_tiff_under_its_stored_name(client):
    row, names = _tiff_row()
    fn = quote(row["filename"], safe="")
    listed = client.get(f"/api/afm/files/{fn}/images/tiff?tool={row['tool_name']}").get_json()["data"]
    r = client.get(listed[0]["original_url"])
    assert r.status_code == 200
    assert r.mimetype == "image/tiff"
    # TIFF magic: little- or big-endian byte-order mark + 42.
    assert r.data[:4] in (b"II*\x00", b"MM\x00*")
    stored_name = names[0].rsplit(".", 1)[0] + ".tiff"
    disposition = r.headers["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert f"filename*=UTF-8''{quote(stored_name)}" in disposition
    assert r.data == client.get(listed[0]["original_url"]).data


def test_original_route_404s_for_an_unknown_image_or_measurement(client):
    row, names = _tiff_row()
    fn = quote(row["filename"], safe="")
    nm = quote(names[0], safe="")
    tool = row["tool_name"]
    assert client.get(f"/api/afm/files/{fn}/tiff/not-real.webp?tool={tool}").status_code == 404
    assert client.get(f"/api/afm/files/no-such-file/tiff/{nm}?tool={tool}").status_code == 404


def test_tiff_zip_holds_every_original_of_the_measurement(client):
    import io
    import zipfile

    row, names = _tiff_row()
    fn = quote(row["filename"], safe="")
    r = client.get(f"/api/afm/files/{fn}/tiff.zip?tool={row['tool_name']}")
    assert r.status_code == 200
    assert r.mimetype == "application/zip"
    assert r.headers["Content-Disposition"].startswith("attachment;")
    archive = zipfile.ZipFile(io.BytesIO(r.data))
    # The Result list holds each webp and, beside it, the original it came from.
    originals = [n for n in names if n.endswith(".tiff")]
    assert originals and len(originals) * 2 == len(names)
    assert archive.namelist() == originals
    first = archive.read(archive.namelist()[0])
    nm = quote(names[0], safe="")
    assert first == client.get(f"/api/afm/files/{fn}/tiff/{nm}?tool={row['tool_name']}").data


def test_tiff_zip_404s_for_an_unknown_measurement(client):
    assert client.get("/api/afm/files/no-such-file/tiff.zip").status_code == 404
