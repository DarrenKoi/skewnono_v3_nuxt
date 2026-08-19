"""Figure serving — ``GET /api/chat/figures/<figure_id>``.

The seam under test is the HTTP boundary, not the storage read: Phase 2 swaps
the disk read for MinIO and every test here must survive that untouched.
"""

import pytest
from flask import Flask, g

from back_dev_home.chat.routes import bp

# A real WebP header, so a test can never pass on bytes the browser would
# refuse. The payload past the header is irrelevant to the route.
WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 24

# The office's actual id shape, {doc_id}_p{page}_i{idx} (office 확인
# 2026-08-19). The dot in the doc_id is the point: it is what the original
# ^[A-Za-z0-9_-]{1,128}$ would have rejected, 404ing every real figure while
# every mock fixture kept passing.
OFFICE_FIGURE_ID = "CG6300_1.HHTSEM_SYSTEM_p100_i0"


@pytest.fixture
def figures_dir(tmp_path, monkeypatch):
    directory = tmp_path / "figures"
    directory.mkdir()
    monkeypatch.setenv("SKEWNONO_CHAT_FIGURES_DIR", str(directory))
    return directory


@pytest.fixture
def client(figures_dir):
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")

    @app.before_request
    def _uid():
        g.user_id = "u1"

    return app.test_client()


def test_serving_a_figure_returns_its_webp_bytes(client, figures_dir):
    """Catches the office's real id format being rejected by id validation."""
    (figures_dir / f"{OFFICE_FIGURE_ID}.webp").write_bytes(WEBP_BYTES)

    response = client.get(f"/api/chat/figures/{OFFICE_FIGURE_ID}")

    assert response.status_code == 200
    assert response.mimetype == "image/webp"
    assert response.data == WEBP_BYTES


def test_a_figure_that_is_not_stored_is_not_found(client):
    """Catches an unextracted figure surfacing as a 500 instead of a 404."""
    response = client.get(f"/api/chat/figures/{OFFICE_FIGURE_ID}")

    assert response.status_code == 404


# Ids that survive Werkzeug's own path normalization and arrive at the view.
# Anything containing a slash — encoded or not — is refused by routing before
# this blueprint runs, so it is deliberately NOT listed here: asserting it
# would test Werkzeug rather than this route's validation.
MALFORMED_IDS = [
    pytest.param("..", id="parent-directory"),
    pytest.param(".", id="current-directory"),
    pytest.param("foo$bar", id="punctuation-outside-the-charset"),
    pytest.param("sp ace", id="space"),
    pytest.param("nul%00x", id="nul-byte"),
    pytest.param("a" * 129, id="over-the-128-char-cap"),
]


@pytest.mark.parametrize("figure_id", MALFORMED_IDS)
def test_a_malformed_id_is_refused(client, figure_id):
    """Catches unvalidated ids reaching storage.

    ``nul%00x`` is the one that bites: a NUL byte makes ``open()`` raise
    ``ValueError``, not ``OSError``, so an unvalidated id 500s rather than
    404ing. The 128-char cap matters for the same reason on the Phase 2 MinIO
    path, where an oversized key is a wasted network round trip.
    """
    response = client.get(f"/api/chat/figures/{figure_id}")

    assert response.status_code == 404


def test_a_valid_id_is_confined_to_the_figures_directory(
    client, tmp_path, figures_dir
):
    """Catches the served path being assembled outside the configured store.

    Planted as a real readable file beside the store: the claim is
    "unreachable", and only a file that genuinely exists can prove the route
    never reached it.
    """
    (tmp_path / "outsider.webp").write_bytes(WEBP_BYTES)

    response = client.get("/api/chat/figures/outsider")

    assert response.status_code == 404
    assert response.data != WEBP_BYTES


def test_a_served_figure_is_cacheable(client, figures_dir):
    """Catches figures being refetched on every render of a thread.

    Manual figures are immutable once extracted, and one answer can cite
    several of them, so a no-store default would re-download the set each time
    the user scrolls back through a conversation.
    """
    (figures_dir / f"{OFFICE_FIGURE_ID}.webp").write_bytes(WEBP_BYTES)

    response = client.get(f"/api/chat/figures/{OFFICE_FIGURE_ID}")

    assert response.headers["Cache-Control"] == "public, max-age=3600"


def test_no_figure_store_configured_is_not_found(client, monkeypatch, figures_dir):
    """Catches an unset figure store 500ing instead of reporting no figure.

    A deployment whose manuals were indexed without figure extraction is a
    normal state, not a misconfiguration — the SPA renders the citation
    without a thumbnail and nothing else changes.
    """
    (figures_dir / f"{OFFICE_FIGURE_ID}.webp").write_bytes(WEBP_BYTES)
    monkeypatch.delenv("SKEWNONO_CHAT_FIGURES_DIR")

    response = client.get(f"/api/chat/figures/{OFFICE_FIGURE_ID}")

    assert response.status_code == 404
