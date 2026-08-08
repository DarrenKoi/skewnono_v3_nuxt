from urllib.parse import quote, unquote

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
    assert all(n.endswith((".jpeg", ".tif")) for n in body["images"])


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


def _first_tif_name(client) -> str:
    names = client.get(
        "/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&ext=tif"
    ).get_json()["images"]
    assert names, "the mock always emits at least one .tif"
    return names[0]


def test_serve_tif_without_preview_keeps_the_tiff_label(client):
    """The download link sends no preview flag and must get the original —
    at home that is the SVG placeholder labeled image/tiff (the label is what
    keeps the no-preview TIFF path reachable offline)."""
    name = _first_tif_name(client)
    r = client.get(f"/api/msr-image?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&name={quote(name)}")
    assert r.status_code == 200
    assert r.mimetype == "image/tiff"


def test_serve_tif_with_preview_is_browser_renderable(client):
    """?preview=1 must never answer image/tiff — office-side it converts the
    bytes to WebP; at home the mock's SVG placeholder is relabeled to the SVG
    it actually is. Both render in an <img>."""
    name = _first_tif_name(client)
    r = client.get(
        f"/api/msr-image?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&name={quote(name)}&preview=1"
    )
    assert r.status_code == 200
    assert r.mimetype == "image/svg+xml"
    assert "X-Msr-Cond" in r.headers, "the cond must survive the preview rendition"


def test_serve_preview_converts_real_tiff_bytes(client, monkeypatch):
    """Office shape: the provider returns REAL TIFF bytes; preview=1 serves
    WebP while the plain URL keeps serving the original."""
    from io import BytesIO

    from PIL import Image

    from back_dev_home.msr_image.contracts import FetchedImage

    buf = BytesIO()
    Image.new("L", (16, 16), 128).save(buf, "TIFF")
    tiff = buf.getvalue()
    monkeypatch.setattr(
        "back_dev_home.msr_image.data.fetch_image",
        lambda locator: FetchedImage(tiff, "image/tiff", "mag=1"),
    )
    q = "eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_REAL&name=real01.tif"
    plain = client.get(f"/api/msr-image?{q}")
    assert plain.mimetype == "image/tiff" and plain.data == tiff

    r = client.get(f"/api/msr-image?{q}&preview=1")
    assert r.status_code == 200
    assert r.mimetype == "image/webp"
    assert r.data[:4] == b"RIFF" and r.data[8:12] == b"WEBP"


def test_serve_preview_is_a_noop_on_jpeg_names(client):
    names = client.get(
        "/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&ext=jpg"
    ).get_json()["images"]
    q = f"eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&name={quote(names[0])}"
    plain = client.get(f"/api/msr-image?{q}")
    previewed = client.get(f"/api/msr-image?{q}&preview=1")
    assert previewed.mimetype == plain.mimetype
    assert previewed.data == plain.data


def test_missing_params_400(client):
    assert client.get("/api/msr-image?eqp_ip=10.0.0.1&name=x.jpeg").status_code == 400


def test_bad_ip_400(client):
    r = client.get("/api/msr-images?eqp_ip=nope&class_name=ADI&msr=MSR_1")
    assert r.status_code == 400
    assert r.get_json()["code"] == "invalid_tool_ip"


def test_serve_rejects_path_traversal_name(client):
    # A ../ name would escape IMAGE_CACHE_DIR (and the tool image dir); reject it.
    r = client.get("/api/msr-image?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&name=..%2f..%2fpasswd")
    assert r.status_code == 400
    assert r.get_json()["code"] == "invalid_locator"


def test_list_rejects_path_traversal_class_name(client):
    r = client.get("/api/msr-images?eqp_ip=10.0.0.1&class_name=..%2fADI&msr=MSR_1")
    assert r.status_code == 400
    assert r.get_json()["code"] == "invalid_locator"


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


def test_preview_filename_follows_the_converted_bytes(client):
    """A converted response must not keep the original extension: saving it
    would produce a file that does not open as its name claims. At home the
    mock's .tif is SVG-labeled-as-TIFF, so preview relabels it to image/svg+xml
    — the same rename path a real office TIFF takes to .webp."""
    q = "eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    names = client.get(f"/api/msr-images?{q}").get_json()["images"]
    tif = next(n for n in names if n.endswith(".tif"))

    r = client.get(f"/api/msr-image?{q}&name={tif}&preview=1")
    assert r.status_code == 200
    cd = r.headers["Content-Disposition"]
    assert cd.startswith("inline;")
    assert f'filename="{tif}"' not in cd
    assert f'filename="{tif[:-4]}.svg"' in cd


def test_download_path_keeps_the_tools_own_filename(client):
    """The counterpart guard: WITHOUT preview nothing is converted, so the name
    is passed through untouched even though the mock's bytes are SVG under a
    .tif name. 원본 다운로드 promises the tool's file, name included."""
    q = "eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    names = client.get(f"/api/msr-images?{q}").get_json()["images"]
    tif = next(n for n in names if n.endswith(".tif"))

    r = client.get(f"/api/msr-image?{q}&name={tif}")
    assert r.status_code == 200
    assert f'filename="{tif}"' in r.headers["Content-Disposition"]


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


def test_list_ext_filter_covers_all_office_extension_spellings(client, monkeypatch):
    # The mock provider only ever emits .jpeg/.tif (MIGRATION.md), so every
    # other test above exercises _EXT_GROUPS against just those two spellings.
    # Office tools write four spellings -- .jpeg/.jpg/.tif/.tiff -- so a
    # regression in the .jpg or .tiff branch would pass every test at home.
    # Route around the mock here and hand list_images() a synthetic listing
    # that covers all four, plus a mixed-case name and a non-image name.
    synthetic = [
        "shot01.jpeg",
        "shot02.jpg",
        "shot03.tif",
        "shot04.tiff",
        "SHOT05.JPG",
        "SHOT06.TIFF",
        "readme.txt",
    ]
    monkeypatch.setattr(
        "back_dev_home.msr_image.data.list_images",
        lambda eqp_ip, class_name, msr: list(synthetic),
    )
    q = "eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1"
    jpg = client.get(f"/api/msr-images?{q}&ext=jpg").get_json()["images"]
    tif = client.get(f"/api/msr-images?{q}&ext=tif").get_json()["images"]
    assert sorted(jpg) == sorted(["shot01.jpeg", "shot02.jpg", "SHOT05.JPG"])
    assert sorted(tif) == sorted(["shot03.tif", "shot04.tiff", "SHOT06.TIFF"])
    assert "readme.txt" not in jpg
    assert "readme.txt" not in tif


def test_list_rejects_unknown_ext(client):
    # A silent empty list would read as "this MSR has no images".
    r = client.get("/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1&ext=png")
    assert r.status_code == 400
    assert "ext" in r.get_json()["error"]
