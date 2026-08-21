"""Gate for the server-side cache in front of the raw-recipe image fetch.

Before this cache the route was "FTP to memory to response" — every viewer
paid a full visit to the tool. That was tolerable while the only caller was
recipe open, which a person reaches deliberately. live_alarm changes the
arithmetic: several engineers open the same hot ALIGNMENT FAIL, one after
another, against the tool that is currently failing to align.

`single_flight` alone does not cover it — it collapses CONCURRENT callers, and
these arrive sequentially. The cache is what makes the second viewer free.

The cache lives in the same MinIO prefix as msr_image's, deliberately: office
retention is enforced twice (this app's nightly job and a flask_modules Airflow
DAG) and a second prefix would be invisible to the second sweep.
"""

import pytest
from flask import Flask

from back_dev_home.ebeam.recipe_search import rawfiles, routes
from back_dev_home.msr_image.cache import cache_key
from back_dev_home.msr_image.contracts import ImageLocator


LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}


def _cache_locator(name):
    return {**LOCATOR, "name": name}


class TestRecipeImageCacheKey:
    def test_names_the_raw_folder_path(self):
        assert rawfiles.recipe_image_cache_key(_cache_locator("IMAP0001.jpeg")) == (
            "10.1.2.3/CLS/IDW_A/IDP_B/IMAP0001.jpeg"
        )

    def test_cannot_collide_with_an_msr_image_key(self):
        # Both live under one MinIO prefix, so this is what keeps a recipe
        # image from being served as a measurement image. An msr key has FOUR
        # segments and this has FIVE, and `msr` can never contain a "/" —
        # validate_segment rejects it before any key is built.
        msr_key = cache_key(ImageLocator("10.1.2.3", "CLS", "IDW_A", "IDP_B"))
        recipe_key = rawfiles.recipe_image_cache_key(_cache_locator("IDP_B"))
        assert msr_key.count("/") == 3
        assert recipe_key.count("/") == 4
        assert msr_key != recipe_key


@pytest.fixture()
def cached_client(tmp_path, monkeypatch):
    """A client whose byte source counts its visits to the tool."""
    from back_dev_home.msr_image.config import ImageConfig

    cfg = ImageConfig(cache_dir=str(tmp_path))
    monkeypatch.setattr(routes, "load_config", lambda: cfg)

    visits = []

    def _fetch(locator, name):
        visits.append((dict(locator), name))
        return b"IMAGEBYTES", "image/jpeg"

    monkeypatch.setattr(routes, "fetch_recipe_image", _fetch)

    app = Flask(__name__)
    app.register_blueprint(routes.bp, url_prefix="/api")
    return app.test_client(), visits


def _image_url(name="IMAP0001.jpeg"):
    return (
        "/api/cdsem/recipe-search/recipe-image"
        f"?eqp_ip=10.1.2.3&class_name=CLS&idw=IDW_A&idp=IDP_B&name={name}"
    )


class TestRecipeImageCache:
    def test_the_second_viewer_does_not_visit_the_tool(self, cached_client):
        client, visits = cached_client
        first = client.get(_image_url())
        second = client.get(_image_url())
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.data == b"IMAGEBYTES"
        assert len(visits) == 1

    def test_a_different_image_is_a_separate_visit(self, cached_client):
        client, visits = cached_client
        client.get(_image_url("IMAP0001.jpeg"))
        client.get(_image_url("IMAP0002.jpeg"))
        assert len(visits) == 2
