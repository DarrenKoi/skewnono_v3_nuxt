"""Phase 3 SPA serving: the mount that only ever runs in production.

``register_spa`` is wired in ``create_app`` behind ``is_cloud()``, so nothing
here executes at home or at the office localhost — a defect in it is invisible
until the cloud host is already serving it. These tests stand a real Flask app
in front of a fake build tree under tmp_path instead of a real
``front-dev-home/.output/public``, which does not exist in a fresh checkout.

Every request path in the app is either an ``/api/*`` endpoint or a
client-side route the SPA resolves in the browser (``ssr: false``), so the two
invariants that decide whether a deploy works at all are: any unknown non-API
path must answer index.html, and ``/api/*`` must never be answered with it.
"""

import re

import pytest
from flask import Flask, g

from back_dev_home._runtime import env
from back_dev_home._spa import serving


INDEX_MARK = "<!-- SPA INDEX -->"


@pytest.fixture
def build(tmp_path, monkeypatch):
    """A minimal stand-in for `npm run build` output, aimed at by spa_dir().

    Mirrors the shapes the mount treats differently: content-hashed bundles
    under _nuxt/, plain public/ assets copied to the root, and index.html.
    """
    root = tmp_path / "front-dev-home" / ".output" / "public"
    (root / "_nuxt").mkdir(parents=True)
    (root / "index.html").write_text(INDEX_MARK, encoding="utf-8")
    (root / "_nuxt" / "entry.abc12345.js").write_text("BUNDLE", encoding="utf-8")
    (root / "favicon.ico").write_text("ICON", encoding="utf-8")
    monkeypatch.setattr(serving, "spa_dir", lambda: root)
    return root


@pytest.fixture
def client(build):
    # static_folder=None mirrors create_app: Flask's default /static/<filename>
    # rule outranks the SPA catch-all and would shadow anything the build ships
    # under /static/. Keep this in step with the factory or these tests stop
    # describing production.
    app = Flask(__name__, static_folder=None)

    @app.get("/api/sem-list")
    def _sem_list():
        return {"rows": []}

    serving.register_spa(app)

    # /login is registered by the auth blueprint in cloud mode; register one
    # after the catch-all too, because Werkzeug matches by rule specificity
    # rather than registration order and the deploy must not depend on it.
    @app.get("/login")
    def _login():
        return "LOGIN"

    return app.test_client()


def test_unknown_paths_are_answered_with_the_index(client):
    """The SPA routes in the browser: Flask has never heard of /sem-list or of
    a deep workspace URL, and both must still boot the app rather than 404.
    A reload on any page other than / is exactly this request."""
    for path in ("/", "/sem-list", "/ebeam/hitachi/storage", "/skewvoir/1/detail"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert INDEX_MARK in resp.get_data(as_text=True), path


def test_the_fallback_never_swallows_an_api_path(client):
    """An unknown /api/* path must stay a 404. Answering it with index.html
    would hand $fetch a 200 full of HTML, which surfaces in the SPA as a JSON
    parse error naming no endpoint — the worst possible symptom to debug from
    a cloud host."""
    resp = client.get("/api/does-not-exist")

    assert resp.status_code == 404
    assert INDEX_MARK not in resp.get_data(as_text=True)


def test_registered_routes_still_win_over_the_catch_all(client):
    """The catch-all is `/<path:path>`, which overlaps every blueprint rule."""
    assert client.get("/api/sem-list").get_json() == {"rows": []}
    assert client.get("/login").get_data(as_text=True) == "LOGIN"


def test_build_assets_are_served_from_the_build_dir(client):
    assert client.get("/favicon.ico").get_data(as_text=True) == "ICON"
    assert client.get("/_nuxt/entry.abc12345.js").get_data(as_text=True) == "BUNDLE"


def test_hashed_bundles_are_cached_immutably_and_the_index_is_not(client):
    """Nuxt content-hashes _nuxt/ filenames, so those bytes never change in
    place and can be cached for a year. index.html must NOT be, or a deploy
    keeps serving the old bundle references from the browser cache."""
    bundle = client.get("/_nuxt/entry.abc12345.js")
    index = client.get("/sem-list")

    assert "immutable" in bundle.headers["Cache-Control"]
    assert "immutable" not in index.headers.get("Cache-Control", "")
    assert index.headers.get("ETag")  # conditional revalidation still applies


@pytest.mark.parametrize(
    "path",
    [
        "/../secret.txt",
        "/../../secret.txt",
        "/../../../secret.txt",
        "/..%2fsecret.txt",
        "/%2e%2e/secret.txt",
        "/_nuxt/../../secret.txt",
        "/a/..%252f..%252f..%252fsecret.txt",
    ],
)
def test_traversal_cannot_read_a_file_outside_the_build(client, build, path):
    """The catch-all feeds an arbitrary URL segment to send_from_directory.

    In the cloud bundle the build dir sits three levels under the deploy root,
    which also holds back_dev_home/ and the .env carrying the Redis and
    OpenSearch credentials — so an escape reads the app's own secrets.
    send_from_directory rejects the unsafe path and the request falls through
    to index.html; assert the bytes never appear either way.

    A decoy is planted at every level between the build dir and the deploy
    root, so a traversal of any depth would actually find something to leak.
    """
    for level in (build.parent, build.parent.parent, build.parent.parent.parent):
        (level / "secret.txt").write_text("TOPSECRET", encoding="utf-8")

    resp = client.get(path)

    assert "TOPSECRET" not in resp.get_data(as_text=True)
    assert resp.status_code in (200, 404)


def test_a_missing_build_mounts_nothing_instead_of_failing_at_boot(
    tmp_path, monkeypatch, caplog
):
    """A cloud host that starts before `npm run build` ran, and every home and
    office-localhost checkout, has no .output/public. The app must still boot —
    the API is what the Nuxt dev server proxies to — and must say why."""
    monkeypatch.setattr(serving, "spa_dir", lambda: tmp_path / "never-built")
    app = Flask(__name__)

    with caplog.at_level("WARNING"):
        serving.register_spa(app)

    assert "/<path:path>" not in {rule.rule for rule in app.url_map.iter_rules()}
    assert "SPA dir missing" in caplog.text


def test_a_half_built_tree_404s_rather_than_500s(tmp_path, monkeypatch):
    """Directory present, index.html not: an interrupted or partially copied
    deploy. Every route degrades to 404, not to a traceback."""
    root = tmp_path / "public"
    root.mkdir()
    monkeypatch.setattr(serving, "spa_dir", lambda: root)
    app = Flask(__name__)
    serving.register_spa(app)

    assert app.test_client().get("/").status_code == 404
    assert app.test_client().get("/sem-list").status_code == 404


def test_create_app_claims_no_static_route_of_its_own():
    """The SPA owns every non-/api path, so Flask must not claim /static/.

    `Flask(__name__)` registers /static/<filename> against back_dev_home/static/
    — a directory that does not exist — and that rule outranks the SPA
    catch-all. Anything the SPA shipped under /static/ answered 404 in Phase 3
    while the real file sat unread in the build. `create_app` now passes
    static_folder=None; this fails if that ever comes back.

    Asserted against the real `create_app` rather than a hand-built Flask app,
    because the bug lived in how the factory constructs Flask — a stand-in
    would have kept passing while production stayed broken.
    """
    from back_dev_home import create_app

    rules = [str(rule) for rule in create_app().url_map.iter_rules()]
    assert not [rule for rule in rules if rule.startswith("/static/")]


def test_a_static_path_in_the_build_is_served_not_shadowed(client, build):
    """The behaviour the fix buys: /static/* reaches the SPA mount.

    The `client` fixture mirrors the factory (static_folder=None), so this
    exercises the same construction production uses.
    """
    (build / "static").mkdir()
    (build / "static" / "a.txt").write_text("PUBLIC-STATIC", encoding="utf-8")

    response = client.get("/static/a.txt")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "PUBLIC-STATIC"


def test_the_public_dir_has_no_static_subdir_to_collide_with():
    """Belt and braces: nothing ships under public/static today either."""
    shipped_public = env.project_root() / "front-dev-home" / "public"
    assert not (shipped_public / "static").exists()


def test_spa_dir_matches_the_path_the_deploy_tooling_hardcodes():
    """spa_dir() is project_root()/front-dev-home/.output/public, and
    project_root() is parents[2] of _runtime/env.py. scripts/deploy/pack.py and
    scripts/deploy/preflight_cloud.py both spell that path out literally, so moving
    env.py one directory would make Flask look somewhere the bundle never
    puts the build — a UI that 404s on a host whose preflight passed."""
    root = env.project_root()

    assert (root / "back_dev_home" / "_runtime" / "env.py").is_file()
    assert (root / "front-dev-home").is_dir()
    assert env.spa_dir() == root / "front-dev-home" / ".output" / "public"


def _flag_capturing_client(build):
    """A client that reports whether the mount flagged the request static.

    The flag lives on `g`, so it has to be read inside the request — an
    after_request hook registered after the mount is the same position the
    real activity middleware occupies.
    """
    app = Flask(__name__, static_folder=None)

    @app.get("/api/sem-list")
    def _sem_list():
        return {"rows": []}

    serving.register_spa(app)
    seen: list[bool] = []

    @app.after_request
    def _capture(response):
        seen.append(getattr(g, serving.STATIC_FILE_FLAG, False))
        return response

    return app.test_client(), seen


def test_only_a_real_file_is_flagged_static(build):
    """What the logging skip keys on. Assets are flagged; everything answered
    with index.html is not, so app boot and deep-link reloads keep logging."""
    client, seen = _flag_capturing_client(build)

    for path in ("/_nuxt/entry.abc12345.js", "/favicon.ico"):
        client.get(path)
        assert seen.pop() is True, path

    for path in ("/", "/sem-list", "/ebeam/hitachi/storage"):
        client.get(path)
        assert seen.pop() is False, path


def test_a_missing_asset_is_not_flagged_so_a_broken_deploy_stays_visible(build):
    """send_from_directory raises NotFound for an absent file and the mount
    swallows it into the index.html fallback — a 200, not a 404. Flagging that
    as static would hide the one symptom a bad deploy produces."""
    client, seen = _flag_capturing_client(build)

    response = client.get("/_nuxt/never-built.99999999.js")

    assert response.status_code == 200
    assert INDEX_MARK in response.get_data(as_text=True)
    assert seen.pop() is False


def test_api_routes_are_never_flagged_static(build):
    client, seen = _flag_capturing_client(build)

    client.get("/api/sem-list")

    assert seen.pop() is False


def test_the_logging_middleware_reads_the_same_flag_name():
    """Cross-module pin. `_logging/activity.py` spells the attribute literally
    instead of importing it, so that `create_app` can keep deferring this
    module behind is_cloud(). If the two drift, the skip silently stops
    working and the cloud index fills with bundle requests again."""
    source = (
        env.project_root() / "back_dev_home" / "_logging" / "activity.py"
    ).read_text(encoding="utf-8")

    assert f'"{serving.STATIC_FILE_FLAG}"' in source


def test_cache_control_year_is_a_real_max_age(client):
    """Guard the literal: a typo in the seconds count is silent."""
    header = client.get("/_nuxt/entry.abc12345.js").headers["Cache-Control"]
    seconds = int(re.search(r"max-age=(\d+)", header).group(1))

    assert seconds == 365 * 24 * 60 * 60
