from scripts.verify.probe_office_endpoints import CATALOG
from scripts.verify.probe_office_endpoints import _do_auth_probe


def test_catalog_sweep_includes_recipe_image_endpoint():
    assert {
        "method": "GET",
        "path": "/api/{tool_slug}/recipe-search/recipe-image",
        "auth": "토큰 가능",
        "example": {
            "path": "/cdsem/recipe-search/recipe-image",
            "query": {
                "eqp_ip": "10.1.2.3",
                "class_name": "CLS",
                "idw": "IDW_A",
                "idp": "IDP_B",
                "name": "IMMP0004.jpeg",
            },
        },
    } in CATALOG


def test_auth_probe_allows_the_known_implicit_home_identity_when_requested():
    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

    class Requests:
        def __init__(self):
            self.responses = iter([Response(200), Response(401), Response(200)])

        def get(self, *args, **kwargs):
            return next(self.responses)

    assert _do_auth_probe(
        Requests(), "http://localhost:5050", "skn_test", 1.0,
        allow_implicit_identity=True,
    ) == []
