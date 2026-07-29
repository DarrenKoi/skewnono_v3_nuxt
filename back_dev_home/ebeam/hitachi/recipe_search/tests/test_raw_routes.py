"""Routes for the raw-recipe folder: param-detail, align-detail, recipe-image.

Half of these are guard tests, and they are not ceremony: the client names FTP
paths on all three endpoints, so ``validate_segment`` and ``validate_tool_ip``
are the only thing between a query string and an FTP session to an arbitrary
host. msr_image faces the same exposure and the guards are shared with it.
"""

import pytest
from flask import Flask

from back_dev_home.ebeam.hitachi.recipe_search import routes


LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}


@pytest.fixture()
def client():
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
