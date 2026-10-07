"""Route tests for the analysis-image gallery (Flask test_client)."""

from urllib.parse import quote, unquote

import pytest
from flask import Flask

from backend.afm import data
from backend.afm.providers import mock
from backend.afm.routes import bp

pytestmark = pytest.mark.usefixtures("mock_provider")


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")
    return app.test_client()


def _capture_row():
    field = mock.IMAGE_TYPE_FIELDS["capture"]
    for row in data.list_afm_files(None):
        names = [name for name in row.get(field, []) if name.endswith(".webp")]
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


def test_every_image_type_offers_its_original_in_its_own_format(client):
    # Result .tiff, align .bmp, capture .png, tip .png (_C_PR) / .bmp (C_Result).
    formats = {"tiff": {"image/tiff"}, "align": {"image/bmp"}, "capture": {"image/png"},
               "tip": {"image/png", "image/bmp"}}
    for image_type, expected in formats.items():
        field = mock.IMAGE_TYPE_FIELDS[image_type]
        row = next(r for r in data.list_afm_files(None) if any(not n.endswith(".webp") for n in r[field]))
        fn, tool = quote(row["filename"], safe=""), row["tool_name"]
        listed = client.get(f"/api/afm/files/{fn}/images/{image_type}?tool={tool}").get_json()["data"]
        assert listed and all("/tiff/" in image["original_url"] for image in listed)
        seen = set()
        for image in listed:
            r = client.get(image["original_url"])
            assert r.status_code == 200
            stored = image["name"].rsplit(".", 1)[0]
            # Downloaded under the original's own stored name.
            assert stored in unquote(r.headers["Content-Disposition"])
            seen.add(r.mimetype)
        assert seen == expected


def test_originals_zip_holds_the_open_types_originals(client):
    import io
    import zipfile

    row = next(r for r in data.list_afm_files(None) if r["align_dir_list"])
    fn, tool = quote(row["filename"], safe=""), row["tool_name"]
    r = client.get(f"/api/afm/files/{fn}/tiff.zip?type=align&tool={tool}")
    assert r.status_code == 200 and r.mimetype == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
    assert sorted(names) == sorted(n for n in row["align_dir_list"] if n.endswith(".bmp"))
    assert client.get(f"/api/afm/files/{fn}/tiff.zip?type=nope&tool={tool}").status_code == 404


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


def test_images_zip_holds_every_listed_image_of_the_type(client):
    import io
    import zipfile

    row, _ = _capture_row()
    fn = quote(row["filename"], safe="")
    tool = row["tool_name"]
    listed = client.get(f"/api/afm/files/{fn}/images/capture?tool={tool}").get_json()["data"]
    r = client.get(f"/api/afm/files/{fn}/images.zip?type=capture&tool={tool}")
    assert r.status_code == 200
    assert r.mimetype == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(r.data))
    assert archive.namelist() == [image["name"] for image in listed]
    assert archive.read(listed[0]["name"]) == client.get(listed[0]["url"]).data


def test_images_zip_404s_for_an_unknown_type_or_measurement(client):
    row, _ = _capture_row()
    fn = quote(row["filename"], safe="")
    assert client.get(f"/api/afm/files/{fn}/images.zip?type=nope").status_code == 404
    assert client.get("/api/afm/files/no-such-file/images.zip?type=capture").status_code == 404


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


def test_a_stored_webp_is_cacheable_and_a_mock_svg_is_not(client, monkeypatch):
    from backend.afm import routes

    row, names = _capture_row()
    url = f"/api/afm/files/{quote(row['filename'], safe='')}/images/capture/{quote(names[0], safe='')}?tool={row['tool_name']}"
    assert "Cache-Control" not in client.get(url).headers
    monkeypatch.setattr(routes, "get_analysis_image_svg", lambda *args: b"RIFF....WEBP")
    stored = client.get(url)
    assert stored.mimetype == "image/webp" and stored.headers["Cache-Control"] == "private, max-age=3600"
