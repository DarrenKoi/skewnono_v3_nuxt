"""Figure serving — ``GET /api/chat/figures/<figure_id>``.

The seam under test is the HTTP boundary, not the storage read. The disk tests
came first; the MinIO tests at the bottom were added with the office store and
the disk tests survived that untouched — which is the property they exist for.
"""

import pytest
from flask import Flask, g

from back_dev_home.chat import figures
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


# ---------------------------------------------------------------------------
# Office store — MinIO, selected by the knowledge provider (office 확인
# 2026-08-27: user/2067928/hitachi_sem/manual_figures/{figure_id}.webp).
# ---------------------------------------------------------------------------


class _NotFound(Exception):
    """Shaped like minio's S3Error: the code rides on ``.code``."""

    code = "NoSuchKey"


class _Denied(Exception):
    code = "AccessDenied"


class FakeMinio:
    def __init__(self, objects, *, raise_with=None):
        self.objects = objects
        self.raise_with = raise_with
        self.gets = []

    def get(self, key):
        self.gets.append(key)
        if self.raise_with is not None:
            raise self.raise_with
        if key not in self.objects:
            raise _NotFound()
        return self.objects[key]


@pytest.fixture
def minio(monkeypatch):
    """Route figure reads at a fake MinIO and report every key it was asked for."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.delenv("SKEWNONO_CHAT_FIGURE_PREFIX", raising=False)
    fake = FakeMinio({})
    monkeypatch.setattr(figures, "_client_factory", lambda: fake)
    figures.reset_client()
    yield fake
    figures.reset_client()


def test_office_figures_come_from_minio_below_the_namespace_prefix(client, minio):
    """Catches the key template drifting from the office layout.

    The user namespace (``2067928/``) is the MinIO client's own default prefix,
    so the key this module hands to ``get()`` starts at ``hitachi_sem/`` —
    spelling the namespace here too would double it and 404 every figure.
    """
    minio.objects[f"hitachi_sem/manual_figures/{OFFICE_FIGURE_ID}.webp"] = WEBP_BYTES

    response = client.get(f"/api/chat/figures/{OFFICE_FIGURE_ID}")

    assert response.status_code == 200
    assert response.mimetype == "image/webp"
    assert response.data == WEBP_BYTES
    assert minio.gets == [f"hitachi_sem/manual_figures/{OFFICE_FIGURE_ID}.webp"]


def test_office_figure_prefix_is_configurable_per_tool_family(client, minio, monkeypatch):
    """Catches ``hitachi_sem/`` being hardcoded — it is a tool-family axis."""
    monkeypatch.setenv("SKEWNONO_CHAT_FIGURE_PREFIX", "/other_sem/manual_figures")
    minio.objects[f"other_sem/manual_figures/{OFFICE_FIGURE_ID}.webp"] = WEBP_BYTES

    response = client.get(f"/api/chat/figures/{OFFICE_FIGURE_ID}")

    assert response.status_code == 200
    assert minio.gets == [f"other_sem/manual_figures/{OFFICE_FIGURE_ID}.webp"]


def test_an_office_figure_missing_from_minio_is_not_found(client, minio):
    """Catches minio's NoSuchKey surfacing as a 500 instead of a 404."""
    response = client.get(f"/api/chat/figures/{OFFICE_FIGURE_ID}")

    assert response.status_code == 404


def test_an_office_storage_error_is_a_miss_but_leaves_a_trace(client, minio, caplog):
    """Catches a scoped-credential AccessDenied masquerading as "not extracted".

    The response must stay 404 (no existence oracle), but a non-miss error
    has to be visible somewhere or a misconfigured bucket is indistinguishable
    from a manual indexed without figures.
    """
    minio.raise_with = _Denied()

    with caplog.at_level("WARNING", logger="back_dev_home.chat.figures"):
        response = client.get(f"/api/chat/figures/{OFFICE_FIGURE_ID}")

    assert response.status_code == 404
    assert any("AccessDenied" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("figure_id", MALFORMED_IDS)
def test_a_malformed_id_never_reaches_minio(client, minio, figure_id):
    """Catches validation being skipped on the office path — a wasted round
    trip at best, a key outside the figure prefix at worst."""
    response = client.get(f"/api/chat/figures/{figure_id}")

    assert response.status_code == 404
    assert minio.gets == []


def test_the_office_store_ignores_the_disk_directory(client, minio, figures_dir):
    """Catches the disk fallback surviving into office mode.

    A figure on the office host's disk is not the figure the office index
    minted the id for; with the knowledge provider on office, only MinIO
    answers, and a miss there is a miss.
    """
    (figures_dir / f"{OFFICE_FIGURE_ID}.webp").write_bytes(WEBP_BYTES)

    response = client.get(f"/api/chat/figures/{OFFICE_FIGURE_ID}")

    assert response.status_code == 404
    assert minio.gets == [f"hitachi_sem/manual_figures/{OFFICE_FIGURE_ID}.webp"]
