"""A broken teammate package under backend/contrib/ is skipped, not fatal.

Core feature packages keep failing loud (the existing RuntimeError on a
missing `bp`); only the contrib area loads fail-soft. Pinned here so a
future tidy-up of the discovery loop cannot quietly re-couple the two.
"""

import textwrap

import pytest

import backend
from backend import create_app


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(backend, "load_dotenv", lambda *a, **k: None)


@pytest.fixture
def broken_contrib():
    """A contrib package whose import raises, placed in the real package tree
    (the factory rglobs the on-disk backend/ dir) and removed afterwards."""
    import shutil
    from pathlib import Path

    pkg = Path(backend.__file__).parent / "contrib" / "zz_broken_test_pkg"
    pkg.mkdir(parents=True, exist_ok=False)
    (pkg / "__init__.py").write_text("from .routes import bp\n")
    (pkg / "routes.py").write_text(textwrap.dedent("""
        from flask import Blueprint
        bp = Blueprint("zz_broken_test_pkg", __name__)
        raise ImportError("simulated office-only import failure")
    """))
    try:
        yield "backend.contrib.zz_broken_test_pkg"
    finally:
        shutil.rmtree(pkg)


def test_broken_contrib_package_is_skipped_and_named(broken_contrib):
    app = create_app()
    assert app.config["SKEWNONO_CONTRIB_FAILED"] == [broken_contrib]
    assert "/api/health/services" in {r.rule for r in app.url_map.iter_rules()}
    assert not any("zz_broken" in r.rule for r in app.url_map.iter_rules())
