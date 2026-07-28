"""Characterization tests for the vendored ``ops_store`` package.

``ops_store`` is the OpenSearch half of the office data layer: every office
adapter that reads an index goes through ``OSSearch``, the production log
handler writes through ``OSDoc.bulk``, and ``ops_index_mgmt/*.py`` provisions
indices through ``OSIndex``. It shipped with no package-local tests — the gap
``openwiki/testing/guidance.md`` names alongside ``minio_handler`` and
``ftp_handler``.

These pin **current** behaviour of the pure logic: query-body assembly, hit
extraction, scroll pagination, JSON normalization, and the bulk-conflict
accounting. ``ops_store/`` is a **vendored copy** of an upstream
``flask_modules`` package and nothing here edits it.

The office OpenSearch cluster is unreachable from home, so every service is
constructed with an injected fake client and no request leaves the process.
"""

import subprocess
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from ops_store import OSConfig, OSDoc, OSIndex, OSSearch, normalize_document
from ops_store import base as ops_base
from ops_store.index import _build_rollover_summary, _summarize_aliases
from ops_store.search import _build_range_clause, _hit_to_record, _hits_from_result


_REPO_ROOT = Path(__file__).resolve().parents[1]


# ── connection configuration ─────────────────────────────────────────────────


def test_basic_auth_must_be_all_or_nothing():
    """Half-configured credentials would send an anonymous request that fails
    with a 401 far from the config mistake that caused it."""
    with pytest.raises(ValueError, match="both user and password"):
        OSConfig(user="skewnono001", password=None)
    with pytest.raises(ValueError, match="both user and password"):
        OSConfig(user=None, password="secret")


def test_omitting_both_credentials_is_a_valid_anonymous_config():
    config = OSConfig(user=None, password=None)
    assert config.http_auth is None
    assert "http_auth" not in config.to_client_kwargs()


def test_the_scheme_follows_use_ssl_rather_than_being_configured_twice():
    """One flag, one source of truth — a mismatched scheme/port pair is the
    classic "works on my laptop" OpenSearch failure."""
    assert OSConfig(host="h", port=9200, use_ssl=False).hosts == [
        {"host": "h", "port": 9200, "scheme": "http"}
    ]
    assert OSConfig(host="h", use_ssl=True).hosts[0]["scheme"] == "https"


def test_the_default_port_is_the_tls_one():
    """Office clusters sit behind 443; defaulting to 9200 would make every
    unconfigured call hang on a closed port."""
    assert OSConfig().port == 443


def test_ca_certs_are_omitted_from_client_kwargs_unless_set():
    assert "ca_certs" not in OSConfig().to_client_kwargs()
    assert OSConfig(ca_certs="/etc/ca.pem").to_client_kwargs()["ca_certs"] == "/etc/ca.pem"


def test_extra_client_kwargs_win_over_the_derived_ones():
    """The documented escape hatch for a cluster that needs a transport option
    this dataclass does not model."""
    config = OSConfig(timeout=30, extra_client_kwargs={"timeout": 90, "pool_maxsize": 20})
    kwargs = config.to_client_kwargs()
    assert kwargs["timeout"] == 90 and kwargs["pool_maxsize"] == 20


def test_from_env_reads_the_opensearch_prefixed_variables(monkeypatch):
    monkeypatch.setenv("OPENSEARCH_HOST", "os.example")
    monkeypatch.setenv("OPENSEARCH_PORT", "9200")
    monkeypatch.setenv("OPENSEARCH_USER", "u")
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "p")
    monkeypatch.setenv("OPENSEARCH_USE_SSL", "false")
    config = OSConfig.from_env()
    assert (config.host, config.port, config.use_ssl) == ("os.example", 9200, False)


def test_blank_credentials_become_none_so_the_xor_guard_still_holds(monkeypatch):
    """Exporting both as empty is how a deployment turns auth off; exporting
    only one must still trip the all-or-nothing guard."""
    monkeypatch.setenv("OPENSEARCH_USER", "")
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "")
    assert OSConfig.from_env().http_auth is None

    monkeypatch.setenv("OPENSEARCH_USER", "u")
    with pytest.raises(ValueError, match="both user and password"):
        OSConfig.from_env()


def test_an_unparseable_boolean_env_var_fails_loudly(monkeypatch):
    """Silently defaulting ``OPENSEARCH_USE_SSL=maybe`` to False would send
    credentials over plaintext."""
    monkeypatch.setenv("OPENSEARCH_USE_SSL", "maybe")
    with pytest.raises(ValueError, match="Invalid boolean value"):
        OSConfig.from_env()


def test_injecting_a_client_never_constructs_a_real_one(monkeypatch):
    """Every test in this file depends on this: passing ``client=`` must not
    reach ``opensearchpy.OpenSearch``, which would try to resolve a host that
    does not exist from home.

    The second half proves the sentinel is live — omitting ``client`` DOES go
    through ``_opensearch_class`` — so the first assertion is a real
    observation and not a patch on an unvisited path.
    """
    def explode():
        raise AssertionError("constructed a real OpenSearch client")

    monkeypatch.setattr(ops_base, "_opensearch_class", explode)
    OSSearch(client=object(), index="idx")
    with pytest.raises(AssertionError, match="constructed a real OpenSearch client"):
        OSSearch(index="idx")


def test_importing_the_package_does_not_require_opensearchpy():
    """No import-time SDK dependency — matching ``minio_handler``.

    This used to assert the opposite. ``ops_store/search.py`` did ``from
    opensearchpy.exceptions import NotFoundError`` at module scope and
    ``ops_store/__init__.py`` imports ``search``, so ``import ops_store``
    hard-required ``opensearchpy`` even for a caller that only wanted
    ``OSConfig`` or ``normalize_document``. Upstream moved that import into
    ``_is_not_found_error``, which returns False when the package is absent
    rather than exploding at import; ``base._opensearch_class`` and
    ``document``'s ``helpers`` import were already deferred the same way.

    So the whole package is now importable without the SDK, and only the calls
    that actually talk to a cluster need it. Pinned in this direction so a
    future edit that reintroduces a module-scope ``opensearchpy`` import — and
    with it a hard dependency for every consumer — fails here.

    Run in a subprocess because this module imports ``ops_store`` at the top,
    so ``sys.modules`` is already populated in-process.
    """
    probe = "import sys; import ops_store; print('opensearchpy' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=_REPO_ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "False"


def test_client_and_connection_overrides_are_mutually_exclusive():
    with pytest.raises(ValueError, match="Client overrides cannot be used"):
        OSSearch(client=object(), index="idx", host="other")


def test_resolving_an_index_without_one_anywhere_is_an_error_not_a_wildcard():
    """A missing index silently becoming ``_all`` would search the whole
    cluster — slow at best, a data leak at worst."""
    with pytest.raises(ValueError, match="index name is required"):
        OSSearch(client=object())._resolve_index(None)


def test_a_per_call_index_overrides_the_default():
    service = OSSearch(client=object(), index="default-idx")
    assert service._resolve_index(None) == "default-idx"
    assert service._resolve_index("other-idx") == "other-idx"
    assert service.use_index("changed")._resolve_index(None) == "changed"


# ── hit extraction ───────────────────────────────────────────────────────────


def test_a_hit_becomes_a_copy_of_its_source():
    """A copy, not the ``_source`` dict itself — callers mutate records (the
    DataFrame path certainly does) and must not edit the response in place."""
    hit = {"_id": "1", "_source": {"a": 1}}
    record = _hit_to_record(hit, include_meta=False)
    record["a"] = 99
    assert hit["_source"]["a"] == 1


def test_metadata_is_merged_into_the_record_only_when_requested():
    hit = {"_id": "1", "_index": "idx", "_score": 2.0, "_source": {"a": 1}}
    assert _hit_to_record(hit, include_meta=False) == {"a": 1}
    assert _hit_to_record(hit, include_meta=True) == {
        "a": 1, "_id": "1", "_index": "idx", "_score": 2.0
    }


def test_a_hit_without_source_falls_back_to_docvalue_fields():
    """A query using ``fields`` (or ``_source: false``) returns no ``_source``;
    without this fallback every such search would yield empty records."""
    assert _hit_to_record({"fields": {"a": [1]}}, include_meta=False) == {"a": [1]}


def test_a_hit_with_neither_source_nor_fields_yields_an_empty_record():
    assert _hit_to_record({"_id": "1"}, include_meta=False) == {}


def test_hits_are_extracted_defensively_from_a_partial_response():
    """A timed-out or shard-failed response can be missing ``hits`` entirely;
    a non-dict entry inside it is dropped rather than crashing the caller."""
    assert _hits_from_result({}) == []
    assert _hits_from_result({"hits": None}) == []
    assert _hits_from_result({"hits": {"hits": [{"a": 1}, "junk", None]}}) == [{"a": 1}]


# ── query-body assembly ──────────────────────────────────────────────────────


def test_the_range_clause_defaults_to_the_last_seven_days():
    assert _build_range_clause("timestamp", None, None) == {
        "range": {"timestamp": {"gte": "now-7d", "lte": "now"}}
    }


def test_days_and_hours_compose_into_one_date_math_expression():
    """``now-7d-3h`` is a single OpenSearch date-math string, not two clauses;
    passing both narrows the window rather than widening it."""
    assert _build_range_clause("ts", 7, 3)["range"]["ts"]["gte"] == "now-7d-3h"


def test_hours_alone_suppresses_the_seven_day_default():
    """The default only applies when BOTH are None — ``hours=6`` must not
    silently become ``now-7d-6h``."""
    assert _build_range_clause("ts", None, 6)["range"]["ts"]["gte"] == "now-6h"


class RecordingSearchClient:
    """Captures the body of every ``search`` call and returns a canned hit."""

    def __init__(self, result: dict | None = None) -> None:
        self.bodies: list[dict] = []
        self.indices_used: list[str] = []
        self.result = result if result is not None else {"hits": {"hits": []}}

    def search(self, index=None, body=None, **kwargs):
        self.indices_used.append(index)
        self.bodies.append(body)
        return self.result

    def count(self, index=None, body=None):
        self.indices_used.append(index)
        self.bodies.append(body)
        return {"count": 0}


def test_bool_omits_every_clause_the_caller_did_not_supply():
    """An empty ``must``/``should``/``filter`` key changes OpenSearch scoring
    semantics (an empty ``should`` with ``minimum_should_match`` matches
    nothing), so unused clauses must not be sent at all."""
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").bool(filter=[{"term": {"a": 1}}])
    assert client.bodies[-1]["query"]["bool"] == {"filter": [{"term": {"a": 1}}]}


def test_filter_terms_drops_fields_whose_value_list_is_empty():
    """An empty ``terms`` list matches nothing, so a filter the caller left
    unset would silently zero out the whole result set."""
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").filter_terms({"fab": ["M16"], "step": []})
    assert client.bodies[-1]["query"]["bool"]["filter"] == [{"terms": {"fab": ["M16"]}}]


def test_filter_terms_with_no_usable_filters_sends_no_filter_clause():
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").filter_terms({"fab": []})
    assert client.bodies[-1]["query"]["bool"] == {}


def test_minimum_should_match_wraps_the_terms_in_a_nested_bool():
    """Without the wrapper the clauses sit in ``filter`` and are ANDed;
    ``minimum_should_match`` only means anything inside a ``should``."""
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").filter_terms(
        {"fab": ["M16"], "step": ["P1"]}, minimum_should_match=1
    )
    nested = client.bodies[-1]["query"]["bool"]["filter"][0]["bool"]
    assert nested["minimum_should_match"] == 1
    assert len(nested["should"]) == 2


def test_knn_without_filters_skips_the_bool_wrapper():
    """A bare knn query is faster than one wrapped in a single-clause bool."""
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").knn("vec", [0.1, 0.2], k=3)
    assert client.bodies[-1]["query"] == {"knn": {"vec": {"vector": [0.1, 0.2], "k": 3}}}


def test_knn_with_filters_moves_the_vector_query_under_must():
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").knn(
        "vec", [0.1], filters=[{"term": {"fab": "M16"}}]
    )
    bool_clause = client.bodies[-1]["query"]["bool"]
    assert "knn" in bool_clause["must"][0]
    assert bool_clause["filter"] == [{"term": {"fab": "M16"}}]


def test_hybrid_requires_at_least_one_of_its_two_arms_to_match():
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").hybrid(
        "query text", text_field="body", vector_field="vec", vector=[0.1]
    )
    bool_clause = client.bodies[-1]["query"]["bool"]
    assert bool_clause["minimum_should_match"] == 1
    assert len(bool_clause["should"]) == 2


def test_range_search_keeps_the_user_query_scoring_and_the_window_filtering():
    """The time window belongs in ``filter`` (no scoring contribution); the
    caller's query stays in ``must`` so relevance still ranks."""
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").range_search(
        days=1, query={"match": {"msg": "x"}}
    )
    body = client.bodies[-1]
    assert body["query"]["bool"]["must"] == [{"match": {"msg": "x"}}]
    assert body["query"]["bool"]["filter"][0]["range"]["timestamp"]["gte"] == "now-1d"
    assert body["sort"] == [{"timestamp": {"order": "desc"}}]


def test_range_search_without_a_query_sends_the_bare_range_clause():
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").range_search(hours=2)
    assert "bool" not in client.bodies[-1]["query"]


def test_aggregate_defaults_to_size_zero_so_no_hits_are_shipped_back():
    """An aggregation that also returns 10 documents wastes bandwidth on every
    dashboard refresh."""
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").aggregate({"a": {"terms": {"field": "f"}}})
    assert client.bodies[-1]["size"] == 0
    assert "query" not in client.bodies[-1]


def test_unique_values_reads_the_bucket_keys_out_of_the_aggregation():
    client = RecordingSearchClient(
        {"aggregations": {"unique_values": {"buckets": [{"key": "M16"}, {"key": "M14"}]}}}
    )
    assert OSSearch(client=client, index="idx").unique_values("fab") == ["M16", "M14"]


def test_unique_values_is_empty_when_the_aggregation_is_absent():
    """A mapping without the field returns no aggregation block at all; the
    caller gets ``[]`` rather than a KeyError."""
    assert OSSearch(client=RecordingSearchClient({}), index="idx").unique_values("fab") == []


def test_sample_only_seeds_the_random_score_when_a_seed_is_given():
    """An unseeded ``random_score`` is genuinely random per call; a seeded one
    needs a field to hash and uses ``_seq_no``. Sending an empty seed dict
    would quietly change which of the two you get."""
    client = RecordingSearchClient()
    service = OSSearch(client=client, index="idx")
    service.sample()
    assert client.bodies[-1]["query"]["function_score"]["random_score"] == {}
    service.sample(seed=7)
    assert client.bodies[-1]["query"]["function_score"]["random_score"] == {
        "seed": 7, "field": "_seq_no"
    }


def test_count_sends_an_empty_body_when_no_query_is_supplied():
    client = RecordingSearchClient()
    OSSearch(client=client, index="idx").count()
    assert client.bodies[-1] == {}


# ── scroll pagination ────────────────────────────────────────────────────────


class ScrollClient:
    """Serves a fixed number of scroll pages then an empty one.

    ``clear_scroll`` calls are recorded because a leaked scroll context holds
    segment files open on every data node until it times out.
    """

    def __init__(self, pages: list[list[dict]]) -> None:
        self.pages = pages
        self.page_index = 0
        self.cleared: list[str] = []
        self.search_body: dict | None = None
        self.scroll_window: str | None = None

    def search(self, index=None, body=None, scroll=None):
        self.search_body = body
        self.scroll_window = scroll
        return {"_scroll_id": "scroll-1", "hits": {"hits": self.pages[0]}}

    def scroll(self, scroll_id=None, scroll=None):
        self.page_index += 1
        page = self.pages[self.page_index] if self.page_index < len(self.pages) else []
        return {"_scroll_id": f"scroll-{self.page_index + 1}", "hits": {"hits": page}}

    def clear_scroll(self, scroll_id=None):
        self.cleared.append(scroll_id)


def _hits(*values: int) -> list[dict]:
    return [{"_source": {"i": value}} for value in values]


def test_scrolling_concatenates_every_page_until_one_comes_back_empty():
    client = ScrollClient([_hits(0, 1), _hits(2), []])
    hits = OSSearch(client=client, index="idx")._search_all_hits({}, batch_size=2)
    assert [hit["_source"]["i"] for hit in hits] == [0, 1, 2]


def test_batch_size_is_injected_as_the_request_size():
    """``size`` on a scrolling search is the PAGE size, not a total cap — the
    caller's ``batch_size`` has to land here or every page is the default 10."""
    client = ScrollClient([_hits(0), []])
    OSSearch(client=client, index="idx")._search_all_hits({"query": {}}, batch_size=500)
    assert client.search_body["size"] == 500


def test_the_caller_body_is_not_mutated_by_the_injected_size():
    """The same body dict is often reused across calls (``range_dataframe_all``
    builds one and passes it down); mutating it would leak a stale ``size``."""
    body = {"query": {"match_all": {}}}
    OSSearch(client=ScrollClient([[]]), index="idx")._search_all_hits(body, batch_size=7)
    assert body == {"query": {"match_all": {}}}


def test_the_scroll_context_is_always_cleared_even_on_the_last_id():
    """Clearing uses the MOST RECENT scroll id — OpenSearch invalidates the
    whole context from it, and clearing a stale id leaks the live one."""
    client = ScrollClient([_hits(0), _hits(1), []])
    OSSearch(client=client, index="idx")._search_all_hits({}, batch_size=1)
    assert client.cleared == ["scroll-3"]


def test_max_rows_stops_scrolling_early_and_truncates_the_result():
    """The point of ``max_rows`` is to stop pulling pages, not merely to slice
    at the end — an unbounded scroll over a log index is an OOM."""
    client = ScrollClient([_hits(0, 1), _hits(2, 3), []])
    hits = OSSearch(client=client, index="idx")._search_all_hits(
        {}, batch_size=2, max_rows=3
    )
    assert [hit["_source"]["i"] for hit in hits] == [0, 1, 2]
    assert client.page_index == 1  # stopped after the second page, never asked for a third


def test_the_scroll_window_is_forwarded_to_the_initial_search():
    client = ScrollClient([[]])
    OSSearch(client=client, index="idx")._search_all_hits({}, scroll="5m")
    assert client.scroll_window == "5m"


# ── document normalization ───────────────────────────────────────────────────


def test_non_string_keys_are_stringified_for_json():
    """OpenSearch field names are strings; an int key from a DataFrame column
    would serialize inconsistently across json backends."""
    assert normalize_document({1: "v"}) == {"1": "v"}


def test_missing_values_of_every_flavour_collapse_to_none():
    """``NaN`` is not valid JSON and ``NaT``/``pd.NA`` are not serializable at
    all; a single ``null`` is what the mapping expects for "no value"."""
    normalized = normalize_document({"nan": float("nan"), "none": None})
    assert normalized == {"nan": None, "none": None}


def test_a_nan_decimal_is_also_none_but_a_real_one_becomes_a_float():
    normalized = normalize_document({"ok": Decimal("1.5"), "bad": Decimal("NaN")})
    assert normalized == {"ok": 1.5, "bad": None}


def test_temporal_values_become_iso_strings_and_durations_become_seconds():
    """ISO-8601 is what a ``date`` mapping parses; a timedelta has no date
    mapping at all so it is expressed as a number."""
    normalized = normalize_document({
        "dt": datetime(2026, 1, 2, 3, 4),
        "d": date(2026, 1, 2),
        "t": time(3, 4),
        "td": timedelta(minutes=1, seconds=30),
    })
    assert normalized == {
        "dt": "2026-01-02T03:04:00",
        "d": "2026-01-02",
        "t": "03:04:00",
        "td": 90.0,
    }


def test_numpy_scalars_and_arrays_are_reduced_to_python_builtins():
    """``np.int64`` is not JSON-serializable; frames coming out of pandas are
    full of them."""
    normalized = normalize_document({
        "scalar": np.int64(3),
        "zero_dim": np.array(4),
        "array": np.array([1, 2]),
    })
    assert normalized == {"scalar": 3, "zero_dim": 4, "array": [1, 2]}
    assert all(isinstance(value, int) for value in normalized["array"])


def test_sets_become_lists_because_json_has_no_set():
    assert normalize_document({"s": frozenset({1})}) == {"s": [1]}


def test_normalization_recurses_through_nested_containers():
    """A NaN buried in a nested list is exactly as unserializable as one at
    the top level."""
    assert normalize_document({"a": {"b": [float("nan"), 1]}}) == {"a": {"b": [None, 1]}}


def test_a_string_is_never_mistaken_for_a_missing_value():
    """``pandas.isna`` on a string is False, but the short-circuit above it
    matters: an empty string must survive as an empty string."""
    assert normalize_document({"s": "", "b": b"x"}) == {"s": "", "b": b"x"}


# ── bulk write accounting ────────────────────────────────────────────────────


class BulkRecordingDoc(OSDoc):
    """Intercepts ``_run_bulk`` so the action stream can be inspected without
    an opensearch-py helper or a cluster."""

    canned: tuple[int, list] = (0, [])

    def _run_bulk(self, actions, *, chunk_size, refresh, raise_on_error):
        self.actions = list(actions)
        self.chunk_size = chunk_size
        self.raise_on_error = raise_on_error
        return self.canned


def test_bulk_create_lifts_the_id_field_out_of_the_stored_source():
    """The id becomes ``_id``; leaving it in ``_source`` too would duplicate it
    in every document and in every search result."""
    service = BulkRecordingDoc(client=object(), index="idx")
    service.canned = (1, [])
    service.bulk_create([{"_id": "abc", "value": 1}])
    action = service.actions[0]
    assert action["_op_type"] == "create"
    assert action["_id"] == "abc"
    assert action["_source"] == {"value": 1}


def test_bulk_create_counts_a_409_as_skipped_not_as_an_error():
    """``create`` is used precisely so a re-run does not overwrite; the
    resulting id collisions are the expected outcome, not a failure. Counting
    them as errors would make every idempotent re-run look broken."""
    service = BulkRecordingDoc(client=object(), index="idx")
    service.canned = (
        1,
        [{"create": {"status": 409, "_id": "dup"}},
         {"create": {"status": 400, "_id": "bad"}}],
    )
    result = service.bulk_create([{"_id": "a"}, {"_id": "dup"}, {"_id": "bad"}])
    assert (result.created, result.skipped) == (1, 1)
    assert result.errors == [{"create": {"status": 400, "_id": "bad"}}]


def test_bulk_create_never_raises_on_item_errors():
    """It always returns a result object, so a partial failure is reported
    rather than aborting the ingest mid-batch."""
    service = BulkRecordingDoc(client=object(), index="idx")
    service.canned = (0, [{"create": {"status": 400}}])
    service.bulk_create([{"_id": "a"}])
    assert service.raise_on_error is False


def test_bulk_index_only_sets_an_id_when_the_field_is_present_and_not_null():
    """A row with no usable id gets NO ``_id`` at all, so OpenSearch generates
    one and the row is stored as its own document.

    The guard matters because ``bulk_index`` assigns ``source[id_field]`` raw
    (unlike ``bulk_create`` / ``bulk_index_dataframe``, which ``str()`` it):
    without the ``is not None`` check a null id would go on the wire as JSON
    ``null`` and the bulk item would be rejected.
    """
    service = BulkRecordingDoc(client=object(), index="idx")
    service.canned = (3, [])
    service.bulk_index(
        [{"key": "a"}, {"key": None}, {"other": 1}], id_field="key"
    )
    assert [action.get("_id") for action in service.actions] == ["a", None, None]


def test_bulk_index_normalizes_only_when_asked():
    """Normalization walks every value of every document, so it is opt-in for
    payloads already known to be JSON-safe."""
    service = BulkRecordingDoc(client=object(), index="idx")
    service.canned = (1, [])
    service.bulk_index([{"when": date(2026, 1, 2)}], normalize=True)
    assert service.actions[0]["_source"] == {"when": "2026-01-02"}


def test_the_chunk_size_falls_back_to_the_config_value():
    """``bulk_chunk`` is a per-cluster tuning knob; ignoring it would send the
    library default and can trip the cluster's bulk size limit."""
    service = BulkRecordingDoc(client=object(), config=OSConfig(bulk_chunk=42), index="idx")
    service.canned = (0, [])
    service.bulk_index([])
    assert service.chunk_size == 42


def test_without_a_config_the_chunk_size_defaults_to_five_hundred():
    service = BulkRecordingDoc(client=object(), index="idx")
    service.canned = (0, [])
    service.bulk_index([])
    assert service.chunk_size == 500


class MgetClient:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.bodies: list[dict] = []

    def mget(self, index=None, body=None):
        self.bodies.append(body)
        return {"docs": self.docs}


def test_exists_many_matches_docs_by_id_not_by_response_position():
    """The response is keyed back to the REQUESTED ids by ``_id``.

    The fake deliberately answers out of order and omits one id entirely, so a
    positional ``zip`` implementation would mis-map ``a`` to ``b``'s verdict
    and drop ``c`` — this test bites, where a same-order fake would not.
    Every requested id must appear, including ones the cluster never mentioned.
    """
    client = MgetClient([{"_id": "b", "found": False}, {"_id": "a", "found": True}])
    result = OSDoc(client=client, index="idx").exists_many(["a", "b", "c"])
    assert result == {"a": True, "b": False, "c": False}


def test_exists_many_ignores_ids_the_caller_never_asked_about():
    """A stray ``_id`` in the response must not appear in the answer — the
    caller iterates the result expecting exactly its own key set."""
    client = MgetClient([{"_id": "a", "found": True}, {"_id": "stray", "found": True}])
    assert OSDoc(client=client, index="idx").exists_many(["a"]) == {"a": True}


def test_exists_many_asks_the_cluster_not_to_send_the_documents_back():
    """Existence checks over a wide id list would otherwise drag every
    ``_source`` across the wire."""
    client = MgetClient([])
    OSDoc(client=client, index="idx").exists_many(["a"])
    assert client.bodies[0]["docs"] == [{"_id": "a", "_source": False}]


def test_get_many_returns_the_source_for_found_ids_and_none_otherwise():
    """Also out of order, for the same reason as ``exists_many`` above: the
    mapping is by ``_id``, and a not-found doc yields ``None`` rather than
    being omitted from the result."""
    client = MgetClient([
        {"_id": "b", "found": False},
        {"_id": "a", "found": True, "_source": {"v": 1}},
    ])
    result = OSDoc(client=client, index="idx").get_many(["a", "b", "c"])
    assert result == {"a": {"v": 1}, "b": None, "c": None}


def test_an_empty_id_list_short_circuits_before_any_request():
    """An mget with zero docs is rejected by some OpenSearch versions."""
    client = MgetClient([])
    service = OSDoc(client=client, index="idx")
    assert service.exists_many([]) == {} and service.get_many([]) == {}
    assert client.bodies == []


def test_refresh_is_only_sent_when_the_caller_asks_for_it():
    """``refresh`` forces a segment flush; sending it by default would make
    every single-document write far more expensive."""
    class IndexClient:
        def __init__(self):
            self.kwargs = []

        def index(self, **kwargs):
            self.kwargs.append(kwargs)
            return {}

    client = IndexClient()
    service = OSDoc(client=client, index="idx")
    service.index({"a": 1})
    assert "refresh" not in client.kwargs[-1] and "id" not in client.kwargs[-1]
    service.index({"a": 1}, doc_id="x", refresh="wait_for")
    assert client.kwargs[-1]["refresh"] == "wait_for" and client.kwargs[-1]["id"] == "x"


def test_upsert_sends_doc_as_upsert_while_update_does_not():
    """``update`` on a missing id is a 404; ``upsert`` creates it. The single
    flag is the whole difference and is easy to lose in a refactor."""
    class UpdateClient:
        def __init__(self):
            self.bodies = []

        def update(self, **kwargs):
            self.bodies.append(kwargs["body"])
            return {}

    client = UpdateClient()
    service = OSDoc(client=client, index="idx")
    service.update("x", {"a": 1})
    service.upsert("x", {"a": 1})
    assert "doc_as_upsert" not in client.bodies[0]
    assert client.bodies[1]["doc_as_upsert"] is True


# ── alias / rollover introspection ───────────────────────────────────────────


_ALIAS_PAYLOAD = {
    "skewnono_logging-000002": {"aliases": {"skewnono_logging": {"is_write_index": True}}},
    "skewnono_logging-000001": {"aliases": {"skewnono_logging": {}}},
    "unaliased_index": {"aliases": {}},
}


def test_alias_summary_folds_backing_indices_and_names_the_write_index():
    """``ops_index_mgmt/skewnono_logging.py`` refuses to provision unless this
    reports a real rollover alias, so the summary is a safety gate on a
    production log index, not a convenience."""
    summary = _summarize_aliases(_ALIAS_PAYLOAD)
    assert summary == {
        "skewnono_logging": {
            "backing_indices": ["skewnono_logging-000001", "skewnono_logging-000002"],
            "write_index": "skewnono_logging-000002",
        }
    }


def test_an_index_with_no_aliases_contributes_nothing():
    assert _summarize_aliases({"plain": {"aliases": {}}}) == {}


def test_the_rollover_summary_is_reachable_from_the_alias_or_its_write_index():
    """``describe()`` is called with either name depending on what exists, so
    both entry points must resolve to the same verdict."""
    summary = _summarize_aliases(_ALIAS_PAYLOAD)
    by_alias = _build_rollover_summary(
        "skewnono_logging", is_index=False, is_alias=True, alias_summary=summary
    )
    by_index = _build_rollover_summary(
        "skewnono_logging-000002", is_index=True, is_alias=False, alias_summary=summary
    )
    assert by_alias == by_index
    assert by_alias["ready"] is True and by_alias["uses_numbered_suffix"] is True


def test_a_name_outside_any_alias_reports_not_ready_rather_than_raising():
    verdict = _build_rollover_summary(
        "unaliased_index", is_index=True, is_alias=False,
        alias_summary=_summarize_aliases(_ALIAS_PAYLOAD),
    )
    assert verdict == {
        "alias": None, "backing_indices": [], "write_index": None,
        "ready": False, "uses_numbered_suffix": False,
    }


def test_an_alias_whose_write_index_lacks_a_numeric_suffix_is_flagged():
    """ISM rollover requires the ``-NNNNNN`` suffix to compute the next index
    name; an alias pointing at a bare name would silently never roll over."""
    summary = _summarize_aliases({"logs_plain": {"aliases": {"logs": {"is_write_index": True}}}})
    verdict = _build_rollover_summary("logs", is_index=False, is_alias=True, alias_summary=summary)
    assert verdict["ready"] is True
    assert verdict["uses_numbered_suffix"] is False


class MissingIndexClient:
    class indices:
        @staticmethod
        def exists(index=None):
            return False

        @staticmethod
        def exists_alias(name=None):
            return False


def test_describing_a_missing_index_returns_a_shaped_absence_not_an_error():
    """Callers branch on ``exists``; raising would force every provisioning
    script to wrap the call in a try/except just to ask a question."""
    described = OSIndex(client=MissingIndexClient(), index="nope").describe()
    assert described["exists"] is False
    assert described["resource_type"] == "missing"
    assert described["rollover"]["ready"] is False


class CreateRecordingIndices:
    """Captures the body handed to ``indices.create``."""

    def __init__(self) -> None:
        self.body: dict | None = None

    def create(self, index=None, body=None):
        self.body = body
        return {}


class CreateClient:
    def __init__(self) -> None:
        self.indices = CreateRecordingIndices()


def test_create_fills_in_shard_settings_without_overriding_explicit_ones():
    """``settings`` wins where it overlaps — a caller that pinned
    ``number_of_shards`` meant it."""
    client = CreateClient()
    OSIndex(client=client, index="idx").create(settings={"number_of_shards": 5}, shards=1)
    settings = client.indices.body["settings"]
    assert settings["number_of_shards"] == 5
    assert settings["number_of_replicas"] == 0
    assert settings["refresh_interval"] == "30s"


def test_create_omits_empty_mappings_and_aliases_blocks():
    """An empty ``mappings`` block is not the same as no block on some
    OpenSearch versions — it can disable dynamic mapping inheritance."""
    client = CreateClient()
    OSIndex(client=client, index="idx").create(mappings={}, aliases={})
    assert set(client.indices.body) == {"settings"}
