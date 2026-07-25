"""Characterization tests for the vendored ``minio_handler`` package.

``minio_handler`` is one of the office swap surfaces for the file/image
features (``msr_file`` fetches its pickle from MinIO; ``msr_image`` caches
fetched images there), and it shipped with no package-local tests at all —
the gap ``openwiki/testing/guidance.md`` calls out. These tests pin the
**current** behaviour of the pure logic so a future edit to the upstream
``flask_modules`` copy can be diffed against something.

Scope and constraints:

* ``minio_handler/`` is a **vendored copy**; nothing here edits it. Where the
  pinned behaviour is a trap rather than a feature, the test says so in its
  docstring instead of "fixing" the source.
* Company MinIO is unreachable from home, so every test injects a fake client
  (``MinioObject(client=fake)``) — no socket is ever opened. If one of these
  takes measurable time, something started dialling.
* Office credentials are scoped to the ``user/2067928/`` prefix and anything
  outside it answers ``AccessDenied``, **not** ``NotFound``. The error-mapping
  tests below exist to keep that distinction from collapsing: mapping
  ``AccessDenied`` to "missing" would turn a permissions problem into an
  apparently empty result, and there are no bucket-level permissions to fall
  back on (native lifecycle rules are impossible; expiry is an app-level
  purge).
"""

import importlib.util
import io
import json
import pickle
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from minio.error import S3Error

from minio_handler import MinioConfig, MinioObject
from minio_handler import base as minio_base
from minio_handler import object as minio_object


_REPO_ROOT = Path(__file__).resolve().parents[1]

# Captured before the autouse fixture below starts stubbing it out, so the one
# test that has to observe the real filesystem still can.
_REAL_MODULE_VALUES = minio_base._module_values


@pytest.fixture(autouse=True)
def no_office_minio_config(monkeypatch):
    """Neutralize ``minio_handler/minio_config.py`` for the whole module.

    That file is gitignored and carries the office ENDPOINT / ACCESS_KEY /
    SECRET_KEY / BUCKET / PREFIX. Both ``MinioConfig.from_env`` and
    ``MinioBase.__init__`` read it, so without this fixture every default-value
    and prefix-fallback assertion below would pass at home and fail at the
    office — the one place these swap surfaces actually run. Stubbing the
    lookup makes the file's presence irrelevant to the pinned behaviour.
    """
    monkeypatch.setattr(minio_base, "_module_values", lambda attr_map: {})


# ── fakes ────────────────────────────────────────────────────────────────────


class FakeStatObject:
    """Stand-in for a listing entry / stat result: only ``object_name`` matters."""

    def __init__(self, object_name: str) -> None:
        self.object_name = object_name


class RecordingClient:
    """Records every call the wrapper makes, returns canned listings.

    Deliberately not a MinIO mock — the point is to capture the *exact* bucket
    and key strings the wrapper composes, because a separator off-by-one only
    ever fails against the real service.
    """

    def __init__(self, listing: list[str] | None = None) -> None:
        self.listing = listing or []
        self.list_calls: list[dict] = []
        self.removed: list[str] = []
        self.puts: list[dict] = []

    def list_objects(self, **kwargs):
        # Captured as **kwargs (not named params with defaults) so a test can
        # assert that a key was NEVER SENT, not merely sent as None.
        self.list_calls.append(dict(kwargs))
        return [FakeStatObject(name) for name in self.listing]

    def remove_objects(self, bucket_name, targets):
        self.removed = [target.name for target in targets]
        return []

    def remove_object(self, bucket_name, key):
        self.removed = [key]

    def put_object(self, bucket, key, stream, length, content_type=None,
                   metadata=None, part_size=0):
        self.puts.append(
            {
                "bucket": bucket,
                "key": key,
                "body": stream.read(),
                "length": length,
                "content_type": content_type,
                "metadata": metadata,
                "part_size": part_size,
            }
        )
        return "etag"


def _store(client, *, bucket="skewnono", prefix="user/2067928/") -> MinioObject:
    """A MinioObject bound to an injected client and the office prefix scope."""
    return MinioObject(client=client, bucket=bucket, prefix=prefix)


# ── prefix scoping: key assembly ─────────────────────────────────────────────


def test_default_prefix_is_stored_without_surrounding_slashes():
    """``prefix`` is normalized once at construction, not at every call.

    The office prefix is written as ``"user/2067928/"`` in config but stored
    stripped, so ``_resolve_key`` can join with exactly one separator. Pinning
    the stored form catches a change that would start emitting ``//``.
    """
    store = _store(RecordingClient(), prefix="/user/2067928/")
    assert store.default_prefix == "user/2067928"


def test_resolve_key_joins_prefix_and_key_with_one_separator():
    """The load-bearing join: office creds only permit ``user/2067928/*``.

    One separator too few silently addresses a *different* namespace; one too
    many creates an empty path segment. Both fail only against real MinIO.
    """
    store = _store(RecordingClient())
    assert store._resolve_key("image_cache/abc") == "user/2067928/image_cache/abc"


def test_resolve_key_strips_a_leading_slash_from_the_caller_key():
    """A caller passing an absolute-looking key must not escape the prefix.

    ``"/image_cache/abc"`` reads like a root path; the wrapper treats it as
    relative so the scoped prefix always wins.
    """
    store = _store(RecordingClient())
    assert store._resolve_key("/image_cache/abc") == "user/2067928/image_cache/abc"


def test_resolve_key_does_not_normalize_parent_traversal():
    """``..`` is NOT resolved — it survives verbatim into the object key.

    S3/MinIO keys are opaque strings, so this does not actually escape the
    prefix (the literal key ``user/2067928/../x`` is stored under the scoped
    prefix and answers ``AccessDenied`` nowhere). Pinned because it looks like
    a traversal hole and is not one; a future "fix" that collapses ``..``
    would change stored key names and orphan existing objects.
    """
    store = _store(RecordingClient())
    assert store._resolve_key("../other/x") == "user/2067928/../other/x"


def test_use_prefix_none_clears_the_scope_so_keys_pass_through():
    """``use_prefix(None)`` is how ``msr_image``'s MinIO cache stays the sole
    prefix source — the cache composes the full key itself and needs the
    client to add nothing on top."""
    store = _store(RecordingClient()).use_prefix(None)
    assert store.default_prefix is None
    assert store._resolve_key("image_cache/abc") == "image_cache/abc"


def test_resolve_bucket_prefers_the_call_argument_over_the_default():
    store = _store(RecordingClient(), bucket="default-bucket")
    assert store._resolve_bucket(None) == "default-bucket"
    assert store._resolve_bucket("other") == "other"


def test_resolve_bucket_without_any_bucket_is_an_error_not_a_guess():
    """No bucket anywhere must fail loudly; a guessed bucket would be an
    ``AccessDenied`` from the far side of the network."""
    store = MinioObject(client=RecordingClient(), bucket=None, prefix=None)
    with pytest.raises(ValueError, match="bucket name is required"):
        store._resolve_bucket(None)


# ── prefix scoping: listing ──────────────────────────────────────────────────


def test_list_composes_the_prefix_and_always_appends_a_trailing_slash():
    """``list("image_cache")`` lists the *folder*, never a name prefix.

    The wrapper rstrips and re-appends ``/``, so a partial basename can never
    be used as an S3 key prefix through this API — see the next test.
    """
    client = RecordingClient()
    list(_store(client).list("image_cache"))
    assert client.list_calls[-1]["prefix"] == "user/2067928/image_cache/"


def test_list_with_a_partial_basename_silently_becomes_a_folder_query():
    """``list("shot")`` searches ``.../shot/``, NOT keys beginning ``shot``.

    A real S3 prefix query would match ``shot01.jpeg``; this wrapper cannot
    express that. Callers that want name-prefix matching must list the parent
    folder and filter in Python (or use ``delete_matching``'s predicate).
    Pinned because the method name invites the opposite assumption.
    """
    client = RecordingClient()
    list(_store(client).list("shot"))
    assert client.list_calls[-1]["prefix"] == "user/2067928/shot/"


def test_list_without_an_argument_falls_back_to_the_scoped_prefix():
    client = RecordingClient()
    list(_store(client).list())
    assert client.list_calls[-1]["prefix"] == "user/2067928/"
    assert client.list_calls[-1]["recursive"] is True


def test_list_omits_the_prefix_key_entirely_when_nothing_is_scoped():
    """An unscoped client lists the whole bucket — no empty-string prefix is
    sent, which some S3 implementations reject."""
    client = RecordingClient()
    list(MinioObject(client=client, bucket="b", prefix=None).list())
    assert "prefix" not in client.list_calls[-1]


def test_list_forwards_start_after_only_when_given():
    client = RecordingClient()
    store = _store(client)
    list(store.list("image_cache"))
    assert "start_after" not in client.list_calls[-1]
    list(store.list("image_cache", start_after="user/2067928/image_cache/k"))
    assert client.list_calls[-1]["start_after"] == "user/2067928/image_cache/k"


# ── the double-prefix trap ───────────────────────────────────────────────────


def test_delete_many_re_resolves_keys_but_list_already_returned_resolved_ones():
    """THE trap: ``list()`` yields FULL keys, ``delete_many()`` prefixes again.

    Feeding ``obj.object_name`` from ``list()`` straight into ``delete_many()``
    on a prefixed client produces ``user/2067928/user/2067928/...`` — and an
    S3 delete of a non-existent key is not an error, so the sweep reports
    success while deleting nothing. ``msr_image``'s ``MinioImageCache`` avoids
    this by holding a ``use_prefix(None)`` client; this test is the executable
    record of *why* that line exists.

    Not fixed here: ``minio_handler`` is a vendored copy of ``flask_modules``
    and the change would have to land in both copies.
    """
    client = RecordingClient()
    store = _store(client)
    store.delete_many(["user/2067928/image_cache/a"])
    assert client.removed == ["user/2067928/user/2067928/image_cache/a"]


def test_delete_prefix_is_safe_because_it_never_re_resolves_listed_names():
    """``delete_prefix`` lists and deletes internally, so the keys it hands to
    ``remove_objects`` are already resolved exactly once — the same round trip
    that breaks in ``delete_many`` is correct here."""
    client = RecordingClient(listing=["user/2067928/image_cache/a", "user/2067928/image_cache/b"])
    _store(client).delete_prefix("image_cache/")
    assert client.removed == ["user/2067928/image_cache/a", "user/2067928/image_cache/b"]


def test_delete_prefix_refuses_to_run_unscoped():
    """No prefix and no default prefix would wipe the entire bucket. It raises
    instead — the one guard rail in the delete family."""
    store = MinioObject(client=RecordingClient(), bucket="b", prefix=None)
    with pytest.raises(ValueError, match="non-empty prefix"):
        store.delete_prefix("")


def test_delete_matching_filters_on_the_full_stored_key():
    """The predicate sees ``object_name`` as stored — prefix included — so a
    date embedded mid-key can be matched. Non-matches are never sent."""
    client = RecordingClient(
        listing=[
            "user/2067928/sem/2026-06-11/a.dat",
            "user/2067928/sem/2026-06-12/b.dat",
        ]
    )
    _store(client).delete_matching(lambda key: "2026-06-11" in key, prefix="sem")
    assert client.removed == ["user/2067928/sem/2026-06-11/a.dat"]


def test_delete_family_issues_no_request_for_an_empty_target_set():
    """An empty batch returns ``[]`` without calling ``remove_objects`` —
    minio-py's bulk delete is a generator and an empty one is a wasted round
    trip at best."""
    client = RecordingClient(listing=[])
    store = _store(client)
    assert store.delete_many([]) == []
    assert store.delete_prefix("image_cache/") == []
    assert store.delete_matching(lambda key: True, prefix="image_cache") == []
    assert client.removed == []


# ── error mapping ────────────────────────────────────────────────────────────


def _s3_error(code: str) -> S3Error:
    return S3Error(
        response=None,
        code=code,
        message=code,
        resource="/skewnono/user/2067928/k",
        request_id="req-1",
        host_id="host-1",
    )


class StatClient:
    """Answers ``stat_object`` with a chosen S3 error code (or success)."""

    def __init__(self, code: str | None) -> None:
        self.code = code

    def stat_object(self, bucket, key):
        if self.code is None:
            return FakeStatObject(key)
        raise _s3_error(self.code)


@pytest.mark.parametrize("code", ["NoSuchKey", "NoSuchObject", "NotFound"])
def test_exists_maps_only_genuine_absence_to_false(code):
    """The three "the object is not there" codes collapse to ``False``."""
    assert _store(StatClient(code)).exists("k") is False


def test_exists_re_raises_access_denied_instead_of_reporting_missing():
    """AccessDenied must NOT look like a missing object.

    Office MinIO credentials are scoped to ``user/2067928/``; a key outside
    that prefix answers ``AccessDenied``, not ``NotFound``. If ``exists`` swallowed
    it, a misconfigured prefix would present as "cache empty" and every read
    would silently fall through to a re-fetch from the tool FTP — a
    permissions bug wearing an empty-result costume. This is the single most
    important assertion in this file.
    """
    with pytest.raises(S3Error) as excinfo:
        _store(StatClient("AccessDenied")).exists("k")
    assert excinfo.value.code == "AccessDenied"


def test_exists_returns_true_when_stat_succeeds():
    assert _store(StatClient(None)).exists("k") is True


class GetClient:
    """``get_object`` succeeds for most keys and raises for keys containing
    ``"bad"`` — enough to exercise ``get_many``'s per-key isolation."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def get_object(self, bucket, key, offset=0, length=0):
        self.seen.append(key)
        if "bad" in key:
            raise RuntimeError(f"boom {key}")
        return _Body(b'{"v": 1}')


class _Body:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.closed = False
        self.released = False

    def read(self):
        return self.payload

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


def test_get_many_isolates_a_failing_key_and_keeps_the_rest():
    """One bad key must not sink a batch; it lands in ``errors`` keyed by the
    key the CALLER asked for (not the resolved one), so the caller can match
    it back to its own input."""
    client = GetClient()
    result = _store(client).get_many(["a.json", "bad.json", "b.json"])
    assert list(result.objects) == ["a.json", "b.json"]
    assert list(result.errors) == ["bad.json"]
    assert "user/2067928/bad.json" in str(result.errors["bad.json"])


def test_get_many_resolves_every_requested_key_through_the_prefix():
    client = GetClient()
    _store(client).get_many(["a.json", "b.json"])
    assert client.seen == ["user/2067928/a.json", "user/2067928/b.json"]


def test_get_many_treats_a_decode_failure_like_a_download_failure():
    """``decode`` runs inside the per-key guard, so a corrupt body is reported
    rather than raised — the documented reason a single ``decode`` is allowed
    for a whole batch."""
    result = _store(GetClient()).get_many(["a.json"], decode=lambda body: 1 / 0)
    assert result.objects == {}
    assert isinstance(result.errors["a.json"], ZeroDivisionError)


def test_get_always_releases_the_connection():
    """A leaked connection under fan-out exhausts the pool long before it
    surfaces as an error, so the ``finally`` is pinned."""
    body = _Body(b"raw")

    class OneShot:
        def get_object(self, bucket, key, offset=0, length=0):
            return body

    assert _store(OneShot()).get("k") == b"raw"
    assert body.closed and body.released


# ── serialization helpers ────────────────────────────────────────────────────


def test_put_json_sets_the_charset_bearing_content_type():
    """Downstream MIME sniffing depends on the exact string, and
    ``ensure_ascii=False`` means the body really is UTF-8."""
    client = RecordingClient()
    _store(client).put_json("j.json", {"a": 1})
    put = client.puts[-1]
    assert put["key"] == "user/2067928/j.json"
    assert put["content_type"] == "application/json; charset=utf-8"
    assert json.loads(put["body"].decode("utf-8")) == {"a": 1}


def test_put_pickle_round_trips_through_the_recorded_body():
    """``msr_file``'s office adapter reads its payload with ``get_pickle``;
    this pins that the writer's bytes are a plain pickle of the value, not a
    double-pickle."""
    client = RecordingClient()
    _store(client).put_pickle("p.pkl", {"rows": [1, 2]})
    put = client.puts[-1]
    assert put["content_type"] == "application/octet-stream"
    assert pickle.loads(put["body"]) == {"rows": [1, 2]}


def test_put_computes_the_length_for_in_memory_bytes():
    client = RecordingClient()
    _store(client).put("b.bin", b"1234")
    assert client.puts[-1]["length"] == 4


def test_put_requires_a_part_size_for_a_stream_of_unknown_length():
    """Without it minio-py cannot chunk the upload; failing here beats failing
    mid-transfer."""
    with pytest.raises(ValueError, match="part_size is required"):
        _store(RecordingClient()).put("s.bin", io.BytesIO(b"xyz"), length=-1)


def test_put_accepts_a_stream_when_a_part_size_is_supplied():
    client = RecordingClient()
    _store(client).put("s.bin", io.BytesIO(b"xyz"), length=-1, part_size=1024)
    assert (client.puts[-1]["length"], client.puts[-1]["part_size"]) == (-1, 1024)


# ── date-folder retention walk ───────────────────────────────────────────────


_TREE = {
    "kpo/anchor/": ["kpo/anchor/2026/", "kpo/anchor/latest/", "kpo/anchor/26/"],
    "kpo/anchor/2026/": ["kpo/anchor/2026/06/", "kpo/anchor/2026/6/", "kpo/anchor/2026/13/"],
    "kpo/anchor/2026/06/": [
        "kpo/anchor/2026/06/11/",
        "kpo/anchor/2026/06/12/",
        "kpo/anchor/2026/06/31/",
        "kpo/anchor/2026/06/x.txt",
    ],
    "kpo/anchor/2026/13/": ["kpo/anchor/2026/13/01/"],
}


class TreeClient:
    """Serves the folder tree above: non-recursive listings return common
    prefixes, recursive listings return two payload objects per folder."""

    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.recursive_prefixes: list[str] = []

    def list_objects(self, bucket_name=None, prefix=None, recursive=False, **kwargs):
        if recursive:
            self.recursive_prefixes.append(prefix)
            return [FakeStatObject(prefix + "obj1"), FakeStatObject(prefix + "obj2")]
        return [FakeStatObject(name) for name in _TREE.get(prefix, [])]

    def remove_objects(self, bucket_name, targets):
        self.deleted = [target.name for target in targets]
        return []


def _tree_store(client) -> MinioObject:
    return MinioObject(client=client, bucket="skewnono", prefix="kpo")


def test_list_date_folders_skips_every_segment_that_is_not_a_padded_date():
    """``latest/``, a 2-digit year, an unpadded month, month 13, day 31 of
    June and a stray file all have to be skipped — discovery runs next to
    live data and must never crash on a neighbour."""
    folders = _tree_store(TreeClient()).list_date_folders("anchor")
    assert [f.date for f in folders] == [date(2026, 6, 11), date(2026, 6, 12)]


def test_list_date_folders_returns_paths_that_feed_straight_back_into_list():
    """The returned path is the full stored prefix including ``default_prefix``
    and a trailing slash, so it can be handed to ``list``/``remove_objects``
    without further composition."""
    folders = _tree_store(TreeClient()).list_date_folders("anchor")
    assert folders[0].path == "kpo/anchor/2026/06/11/"


def test_delete_older_than_keeps_the_cutoff_day_itself(monkeypatch):
    """Cutoff is ``today_KST - days`` and the comparison is strict ``<``, so
    the last ``days`` days INCLUDING today survive. Run on 2026-07-11 with
    ``days=30`` the cutoff is 2026-06-11 and that folder is kept."""
    monkeypatch.setattr(minio_object, "_today_kst", lambda: date(2026, 7, 11))
    result = _tree_store(TreeClient()).delete_older_than(30, "anchor", dry_run=True)
    assert result.folders == []


def test_delete_older_than_dry_run_selects_without_deleting(monkeypatch):
    monkeypatch.setattr(minio_object, "_today_kst", lambda: date(2026, 7, 11))
    client = TreeClient()
    result = _tree_store(client).delete_older_than(29, "anchor", dry_run=True)
    assert [f.date for f in result.folders] == [date(2026, 6, 11)]
    assert result.errors == []
    assert client.deleted == []


def test_delete_older_than_narrows_the_recursive_listing_to_the_day_subtree(monkeypatch):
    """Each selected day is listed under ``anchor/YYYY/MM/DD/`` so MinIO does
    the narrowing — the alternative is walking millions of sibling objects."""
    monkeypatch.setattr(minio_object, "_today_kst", lambda: date(2026, 7, 11))
    client = TreeClient()
    _tree_store(client).delete_older_than(29, "anchor")
    assert client.recursive_prefixes == ["kpo/anchor/2026/06/11/"]
    assert client.deleted == [
        "kpo/anchor/2026/06/11/obj1",
        "kpo/anchor/2026/06/11/obj2",
    ]


def test_parse_segment_requires_exact_zero_padded_width():
    assert minio_object._parse_segment("a/2026/", 4) == 2026
    assert minio_object._parse_segment("a/06/", 2) == 6
    assert minio_object._parse_segment("a/6/", 2) is None
    assert minio_object._parse_segment("a/2026/", 2) is None
    assert minio_object._parse_segment("a/latest/", 4) is None


# ── configuration ────────────────────────────────────────────────────────────


def test_config_defaults_are_a_local_insecure_endpoint(monkeypatch):
    """The safe default is localhost with no credentials — a fresh clone with
    no ``.env`` must never accidentally point at the office cluster."""
    for name in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY",
                 "MINIO_SECURE", "MINIO_REGION", "MINIO_CERT_CHECK"):
        monkeypatch.delenv(name, raising=False)
    config = MinioConfig.from_env()
    assert config.endpoint == "localhost:9000"
    assert config.access_key is None and config.secret_key is None
    assert config.secure is False


def test_blank_credentials_become_none_but_a_blank_endpoint_keeps_the_default(monkeypatch):
    """Asymmetric on purpose: an exported-but-empty key means "no auth",
    while an empty endpoint would be unusable so the default stands."""
    monkeypatch.setenv("MINIO_ENDPOINT", "")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "")
    monkeypatch.setenv("MINIO_SECRET_KEY", "")
    config = MinioConfig.from_env()
    assert config.endpoint == "localhost:9000"
    assert config.access_key is None and config.secret_key is None


@pytest.mark.parametrize(
    "raw,expected",
    [("1", True), ("true", True), ("YES", True), ("on", True),
     ("0", False), ("false", False), ("no", False), ("Off", False)],
)
def test_secure_flag_accepts_the_documented_boolean_spellings(monkeypatch, raw, expected):
    monkeypatch.setenv("MINIO_SECURE", raw)
    assert MinioConfig.from_env().secure is expected


def test_an_unparseable_boolean_fails_loudly(monkeypatch):
    """Silently defaulting ``MINIO_SECURE=maybe`` to False would downgrade the
    connection to plain HTTP without anyone noticing."""
    monkeypatch.setenv("MINIO_SECURE", "maybe")
    with pytest.raises(ValueError, match="Invalid boolean value"):
        MinioConfig.from_env()


def test_explicit_overrides_beat_the_environment(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "from-env:9000")
    assert MinioConfig.from_env(endpoint="explicit:9000").endpoint == "explicit:9000"


def test_region_is_omitted_from_client_kwargs_when_unset():
    """minio-py treats an explicit ``region=None`` differently from an absent
    one on some S3 backends."""
    assert "region" not in MinioConfig().to_client_kwargs()
    assert MinioConfig(region="kr").to_client_kwargs()["region"] == "kr"


def test_a_missing_gitignored_minio_config_module_is_tolerated():
    """``minio_handler/minio_config.py`` carries the office BUCKET/PREFIX and
    is gitignored, so it is absent on a fresh clone. Its absence must not
    raise — that is what lets the same tree boot at home.

    This is the ONE test that deliberately bypasses the ``no_office_minio_config``
    fixture (it calls the real lookup captured at import), because absence
    tolerance can only be observed when the file really is absent. Every other
    test in this file is fixture-neutralized and passes on both checkouts.
    """
    if importlib.util.find_spec("minio_handler.minio_config") is not None:
        pytest.skip("minio_config.py is present (office checkout)")
    assert _REAL_MODULE_VALUES({"bucket": "BUCKET"}) == {}
    assert MinioObject(client=RecordingClient(), bucket="b").default_prefix is None


def test_injecting_a_client_never_constructs_a_real_one(monkeypatch):
    """Every test in this file relies on this: passing ``client=`` must not
    reach ``minio.Minio``. If it ever did, the suite would start dialling an
    endpoint that is unreachable from home.

    The second half proves the sentinel is actually wired: omitting ``client``
    DOES go through ``_minio_class``, so the first assertion is a real
    observation rather than a patch nobody's code path visits.
    """
    def explode():
        raise AssertionError("constructed a real MinIO client")

    monkeypatch.setattr(minio_base, "_minio_class", explode)
    MinioObject(client=RecordingClient(), bucket="b", prefix="user/2067928/")
    with pytest.raises(AssertionError, match="constructed a real MinIO client"):
        MinioObject(bucket="b")


def test_importing_the_package_does_not_import_the_minio_sdk():
    """Import-time side effects, pinned deliberately.

    ``minio_handler`` defers ``from minio import Minio`` into ``_minio_class``,
    so importing the package neither constructs a client nor drags in the SDK.
    That is what lets a home process import it for the pure key-assembly logic
    with no office dependency installed.

    Run in a subprocess because this test module itself imports ``minio.error``
    at the top — in-process, ``sys.modules`` is already polluted.
    """
    probe = (
        "import sys; import minio_handler; "
        "print('minio' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=_REPO_ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "False"


def test_client_and_connection_overrides_are_mutually_exclusive():
    """Passing both is always a mistake — the overrides would be silently
    dropped onto an already-built client."""
    with pytest.raises(ValueError, match="Client overrides cannot be used"):
        MinioObject(client=RecordingClient(), bucket="b", endpoint="other:9000")
