"""Routes for the raw-recipe folder: param-detail, align-detail, recipe-image.

Half of these are guard tests, and they are not ceremony: the client names FTP
paths on all three endpoints, so ``validate_segment`` and ``validate_tool_ip``
are the only thing between a query string and an FTP session to an arbitrary
host. msr_image faces the same exposure and the guards are shared with it.
"""

import pytest
from flask import Flask

from back_dev_home.ebeam.recipe_search import routes


LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # A per-test cache dir. The image route caches what it fetches (see
    # test_recipe_image_cache.py), and the default cache_dir is a real shared
    # folder -- so without this one test's successful fetch becomes another
    # test's cache hit, and the "unreachable tool is a 503" case silently
    # passes as a 200.
    from back_dev_home.msr_image.config import ImageConfig

    monkeypatch.setattr(routes, "load_config", lambda: ImageConfig(cache_dir=str(tmp_path)))
    app = Flask(__name__)
    app.register_blueprint(routes.bp, url_prefix="/api")
    return app.test_client()


def _item(**overrides):
    item = {"locator": LOCATOR, "parameter": "Para_1",
            "slots": {"img_meas2": "PRMS0001"}}
    item.update(overrides)
    return item


# ── param-detail ──────────────────────────────────────────────────────────


def test_param_detail_returns_one_entry_per_item_in_order(client):
    response = client.post("/api/cdsem/recipe-search/param-detail", json={
        "items": [
            _item(parameter="Para_A"),
            _item(parameter="Para_B"),
        ]
    })
    assert response.status_code == 200
    assert [row["parameter"] for row in response.get_json()] == [
        "Para_A", "Para_B",
    ]


def test_param_detail_rejects_an_unknown_tool_slug(client):
    response = client.post("/api/xxsem/recipe-search/param-detail",
                           json={"items": [_item()]})
    assert response.status_code == 400


def test_param_detail_rejects_an_empty_item_list(client):
    response = client.post("/api/cdsem/recipe-search/param-detail",
                           json={"items": []})
    assert response.status_code == 400


def test_param_detail_rejects_a_missing_body(client):
    response = client.post("/api/cdsem/recipe-search/param-detail")
    assert response.status_code == 400


def test_param_detail_caps_the_item_list(client):
    items = [_item(parameter=f"P{i}") for i in range(201)]
    response = client.post("/api/cdsem/recipe-search/param-detail",
                           json={"items": items})
    assert response.status_code == 400


@pytest.mark.parametrize("bad", ["../../etc/passwd", "a/b", "a\\b", "..", "a\x00b"])
def test_param_detail_rejects_a_traversing_slot_value(client, bad):
    """The slot value becomes a filename inside the raw folder."""
    response = client.post("/api/cdsem/recipe-search/param-detail", json={
        "items": [_item(slots={"img_meas2": bad})]
    })
    assert response.status_code == 400


def test_param_detail_trims_surrounding_whitespace_rather_than_rejecting(client):
    """Stripped before validation, as msr_image's routes do — stray whitespace
    around a copied value is a transport artefact, not an attack. The guard
    still sees the trimmed value, so a separator inside it is caught."""
    response = client.post("/api/cdsem/recipe-search/param-detail", json={
        "items": [_item(slots={"img_meas2": "  PRMS0001  "})]
    })
    assert response.status_code == 200
    assert response.get_json()[0]["amp"]["source"] == "PRMS0001"


def test_param_detail_accepts_the_empty_sentinel_as_a_slot_value(client):
    """'non' is a legitimate value, not an attack — it means "no file"."""
    response = client.post("/api/cdsem/recipe-search/param-detail", json={
        "items": [_item(slots={"img_meas2": "non", "img_add2": "non"})]
    })
    assert response.status_code == 200
    assert response.get_json()[0]["amp"] is None


@pytest.mark.parametrize("bad_ip", ["evil.example.com", "999.1.1.1", "", "::1"])
def test_param_detail_rejects_a_non_ipv4_eqp_ip(client, bad_ip):
    """The SSRF gate: the backend opens an FTP session to this value."""
    response = client.post("/api/cdsem/recipe-search/param-detail", json={
        "items": [_item(locator={**LOCATOR, "eqp_ip": bad_ip})]
    })
    assert response.status_code == 400


def test_param_detail_rejects_a_traversing_locator_segment(client):
    response = client.post("/api/cdsem/recipe-search/param-detail", json={
        "items": [_item(locator={**LOCATOR, "class_name": "../.."})]
    })
    assert response.status_code == 400


def test_param_detail_rejects_a_non_object_locator(client):
    response = client.post("/api/cdsem/recipe-search/param-detail", json={
        "items": [_item(locator="10.1.2.3")]
    })
    assert response.status_code == 400


# ── align-detail ──────────────────────────────────────────────────────────


def test_align_detail_returns_sorted_unique_points(client):
    response = client.get("/api/cdsem/recipe-search/align-detail",
                          query_string={**LOCATOR, "p_numbers": "3,1,2,1"})
    assert response.status_code == 200
    assert [p["P_No"] for p in response.get_json()["points"]] == [1, 2, 3]


def test_align_detail_rejects_non_integer_p_numbers(client):
    response = client.get("/api/cdsem/recipe-search/align-detail",
                          query_string={**LOCATOR, "p_numbers": "1,two"})
    assert response.status_code == 400


def test_align_detail_with_no_p_numbers_returns_no_points(client):
    response = client.get("/api/cdsem/recipe-search/align-detail",
                          query_string={**LOCATOR, "p_numbers": ""})
    assert response.status_code == 200
    assert response.get_json()["points"] == []


def test_align_detail_rejects_a_bad_locator(client):
    response = client.get("/api/cdsem/recipe-search/align-detail",
                          query_string={**LOCATOR, "eqp_ip": "nope",
                                        "p_numbers": "1"})
    assert response.status_code == 400


# ── recipe-image ──────────────────────────────────────────────────────────


def test_recipe_image_serves_bytes_with_a_cache_header(client):
    response = client.get("/api/cdsem/recipe-search/recipe-image",
                          query_string={**LOCATOR, "name": "IMMP0001.jpeg"})
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert response.data


@pytest.mark.parametrize("flag", ["1", "true", "yes", "TRUE", " 1 "])
def test_recipe_image_preview_flag_opts_in(client, flag):
    """The allowlist is shared with msr_image (msr_image/preview.py's
    wants_preview), so this route must accept exactly the same spellings. It
    parsed the flag with its own inline copy of the expression until
    2026-08-09; two copies of a rule that gets deliberately tightened later is
    two rules."""
    response = client.get("/api/cdsem/recipe-search/recipe-image",
                          query_string={**LOCATOR, "name": "IMMP0001.jpeg",
                                        "preview": flag})
    assert response.status_code == 200
    assert response.data


@pytest.mark.parametrize("flag", ["", "0", "no", "maybe", "2"])
def test_recipe_image_unknown_preview_values_serve_the_original(client, flag):
    """Conservative by design: anything the allowlist does not recognise —
    including a future spelling — gets the untouched bytes, which is what
    every caller got before previews existed."""
    plain = client.get("/api/cdsem/recipe-search/recipe-image",
                       query_string={**LOCATOR, "name": "IMMP0001.jpeg"})
    response = client.get("/api/cdsem/recipe-search/recipe-image",
                          query_string={**LOCATOR, "name": "IMMP0001.jpeg",
                                        "preview": flag})
    assert response.status_code == 200
    assert response.data == plain.data
    assert response.mimetype == plain.mimetype


def test_recipe_image_rejects_a_traversing_name(client):
    response = client.get("/api/cdsem/recipe-search/recipe-image",
                          query_string={**LOCATOR, "name": "../../../etc/passwd"})
    assert response.status_code == 400


def test_recipe_image_rejects_a_missing_name(client):
    response = client.get("/api/cdsem/recipe-search/recipe-image",
                          query_string=LOCATOR)
    assert response.status_code == 400


def test_recipe_image_404s_when_the_provider_cannot_find_it(client, monkeypatch):
    """A missing image must be a real 404, not a 200 carrying JSON — otherwise
    <img> decodes the error body as a picture and shows nothing useful."""
    def _absent(_locator, name):
        raise LookupError(name)

    monkeypatch.setattr(routes, "fetch_recipe_image", _absent)
    response = client.get("/api/cdsem/recipe-search/recipe-image",
                          query_string={**LOCATOR, "name": "IMMP9999.jpeg"})
    assert response.status_code == 404


def test_an_unreachable_tool_is_503_not_a_silent_200(client, monkeypatch):
    """A dead tool must not read as 'this recipe has no settings'.

    Every block coming back None on a 200 is exactly what a healthy recipe with
    no files looks like, so the two have to be distinguishable. 503 is
    msr_image's existing SourceUnavailable status, reused rather than reinvented.
    """
    from back_dev_home.msr_image.errors import SourceUnavailable

    def _down(_items):
        raise SourceUnavailable("raw-recipe folder unreachable on 10.1.2.3")

    monkeypatch.setattr(routes, "get_param_detail", _down)
    response = client.post("/api/cdsem/recipe-search/param-detail",
                           json={"items": [_item()]})
    assert response.status_code == 503
    assert response.get_json()["code"] == "office_source_unavailable"


def test_an_unreachable_tool_on_the_image_route_is_not_a_404(client, monkeypatch):
    from back_dev_home.msr_image.errors import SourceUnavailable

    def _down(_locator, _name):
        raise SourceUnavailable("unreachable")

    monkeypatch.setattr(routes, "fetch_recipe_image", _down)
    response = client.get("/api/cdsem/recipe-search/recipe-image",
                          query_string={**LOCATOR, "name": "IMMP0001.jpeg"})
    assert response.status_code == 503


def test_align_detail_caps_the_point_list(client):
    response = client.get("/api/cdsem/recipe-search/align-detail",
                          query_string={**LOCATOR,
                                        "p_numbers": ",".join(str(i) for i in range(300))})
    assert response.status_code == 400


# ── align-images ──────────────────────────────────────────────────────────


def test_align_images_names_both_optics(client):
    response = client.get(
        "/api/cdsem/recipe-search/align-images"
        "?recipe_name=MONITOR/CD_TOP_01&fab_name=M14A&eqp_id=CG6300_01"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert [img["optic"] for img in body["images"]] == ["OM", "SEM"]
    assert body["requested_eqp_id"] == "CG6300_01"


def test_every_align_image_the_screen_is_told_to_fetch_resolves(client):
    """The round trip the modal actually makes, end to end over HTTP.

    This is the shape of the production defect reported on 2026-08-22: the
    align-images response is a work list, and every entry on it becomes an
    <img src>. A name on that list that the folder does not hold is not a
    quiet miss -- `recipe-image` has to answer 404, because a per-file GET has
    nowhere to drop a missing file to, and the console fills up with them.

    Runs across many recipes because the shapes differ: most hold both align
    points, some hold only the OM.
    """
    for n in range(1, 25):
        listed = client.get(
            f"/api/cdsem/recipe-search/align-images"
            f"?recipe_name=MONITOR/CD_TOP_{n:02d}&fab_name=M14A&eqp_id=CG6300_01"
        )
        assert listed.status_code == 200
        body = listed.get_json()
        for image in body["images"]:
            fetched = client.get(
                "/api/cdsem/recipe-search/recipe-image",
                query_string={**body["locator"], "name": image["name"]},
            )
            assert fetched.status_code == 200, (
                f"{body['recipe_name']} published {image['name']}, "
                f"which the tool answered {fetched.status_code} for"
            )


def test_align_images_rejects_an_unknown_tool_slug(client):
    response = client.get(
        "/api/xxsem/recipe-search/align-images?recipe_name=MONITOR/CD_TOP_01"
    )
    assert response.status_code == 400


def test_align_images_requires_a_recipe_name(client):
    response = client.get("/api/cdsem/recipe-search/align-images?eqp_id=CG6300_01")
    assert response.status_code == 400


def test_align_images_rejects_a_joined_multi_fab_name(client):
    """The 2026-09-01 live-alarm defect, at the seam that can see it.

    The board's align modal was handed the ROUTE segment instead of the
    alarming row's own fab, so selecting two fabs sent ``fab_name=r3,r4``. The
    mock ignores fab_name entirely and answered 200, which is why this only
    ever failed at the office -- there the name builds a Redis key that does
    not exist and a keyword term that matches nothing, and the screen says the
    tool is unreachable. The reader now refuses the list, so the same mistake
    on any single-fab endpoint is red at home.
    """
    response = client.get(
        "/api/cdsem/recipe-search/align-images"
        "?recipe_name=MONITOR/CD_TOP_01&fab_name=r3,r4&eqp_id=CG6300_01"
    )
    assert response.status_code == 400
