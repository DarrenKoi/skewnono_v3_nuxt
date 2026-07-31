"""The office adapter and the probes it delegates to, driven against fakes.

`providers/office_example.py` is what gets `cp`'d to `office.py`, so it is the
code that actually answers the health card at the office — and none of it can
be exercised there before it ships. These fakes stand in for the three servers
so the success and failure path of every probe, the "office never fakes up"
invariant, and the request path's refusal to do extra server work are all
pinned from home.
"""

from datetime import timedelta

import minio_handler
import ops_store
import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.health.contracts import ServicesHealthResponse
from back_dev_home.health.providers import office_example as office
from back_dev_home.health.providers import probe_common as probe


class FakeRedis:
    def __init__(self):
        self.calls: list[str] = []

    def ping(self):
        self.calls.append("ping")
        return True

    def dbsize(self):
        self.calls.append("dbsize")
        return 42

    def scan(self, cursor=0, count=10):
        self.calls.append("scan")
        return 0, [b"v3_df_sem_avail", b"v3_df_sem_version"]


class FakeEntry:
    def __init__(self, object_name, size=0):
        self.object_name = object_name
        self.size = size
        self.last_modified = None


class FakeStore:
    """MinIO stand-in whose listing is endless — the point is that the request
    path stops early instead of materializing whatever the prefix holds."""

    def __init__(self, entries=None):
        self.default_bucket = "user"
        self.default_prefix = "2067928"
        self.config = None
        self._entries = entries
        self.consumed = 0

    def list(self, recursive=False):
        if self._entries is not None:
            yield from self._entries
            return
        index = 0
        while True:
            self.consumed += 1
            index += 1
            yield FakeEntry(f"2067928/folder-{index}/")


def _fake_search(doc, total=1):
    hits = [{"_source": doc}] if doc is not None else []

    class FakeSearch:
        def __init__(self, index):
            self.index = index

        def latest(self, field, size=1):
            return {"hits": {"total": {"value": total}, "hits": hits}}

    return FakeSearch


def _boom(message):
    def factory(*_a, **_k):
        raise ConnectionError(message)

    return factory


@pytest.fixture(autouse=True)
def no_env_loading(monkeypatch):
    """The probes self-load back_dev_home/.env; tests must not depend on
    whether that file exists in this checkout."""
    monkeypatch.setattr(probe, "load_env_file", lambda *_a, **_k: None)
    monkeypatch.setattr(office, "load_env_file", lambda *_a, **_k: None)


@pytest.fixture
def all_services_up(monkeypatch):
    redis = FakeRedis()
    store = FakeStore()
    monkeypatch.setattr(probe, "redis_client", lambda: redis)
    monkeypatch.setattr(
        ops_store, "OSSearch", _fake_search({"timestamp": probe.now().isoformat()})
    )
    monkeypatch.setattr(minio_handler, "MinioObject", lambda *_a, **_k: store)
    return redis, store


@pytest.fixture
def all_services_down(monkeypatch):
    monkeypatch.setattr(probe, "redis_client", _boom("redis-host-7:6379 refused"))
    monkeypatch.setattr(ops_store, "OSSearch", _boom("os-host-2:9200 refused"))
    monkeypatch.setattr(minio_handler, "MinioObject", _boom("minio-host-9:9000 nope"))


def test_redis_probe_is_a_ping_and_nothing_more(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(probe, "redis_client", lambda: client)

    result = probe.check_redis()

    assert result["status"] == "up"
    assert result["detail"] == "ping ok"
    assert isinstance(result["latency_ms"], int)
    # DBSIZE + SCAN are capture-path work, not request-path work.
    assert client.calls == ["ping"]


def test_redis_probe_failure_is_down_without_the_driver_message(monkeypatch):
    monkeypatch.setattr(probe, "redis_client", _boom("redis-host-7:6379 refused"))

    result = probe.check_redis()

    assert result["status"] == "down"
    assert result["detail"] == "probe failed (ConnectionError)"
    assert result["latency_ms"] is None
    assert "redis-host-7" not in str(result)


def test_opensearch_probe_is_up_on_a_fresh_doc(monkeypatch):
    doc = {"timestamp": (probe.now() - timedelta(minutes=3)).isoformat()}
    monkeypatch.setattr(ops_store, "OSSearch", _fake_search(doc))

    result = probe.check_opensearch()

    assert result["status"] == "up"
    assert result["detail"] == "latest 3m ago · meas_hist_cdsem"


def test_opensearch_probe_is_down_on_a_stale_doc(monkeypatch):
    doc = {"timestamp": (probe.now() - timedelta(hours=5)).isoformat()}
    monkeypatch.setattr(ops_store, "OSSearch", _fake_search(doc))

    result = probe.check_opensearch()

    assert result["status"] == "down"
    assert result["detail"].startswith("stale: latest 5h ago")
    # A real round trip happened, so the latency is meaningful here — unlike
    # the failure rows, which report null per the contract doc.
    assert isinstance(result["latency_ms"], int)


def test_opensearch_probe_is_down_on_an_empty_index(monkeypatch):
    monkeypatch.setattr(ops_store, "OSSearch", _fake_search(None, total=0))

    result = probe.check_opensearch()

    assert result["status"] == "down"
    assert result["detail"] == "no data in meas_hist_cdsem"


def test_opensearch_schema_drift_is_not_reported_as_a_failed_probe(monkeypatch):
    """The cluster answered; the time field was renamed. Calling that a failed
    probe sends an operator hunting a network problem that isn't there."""
    monkeypatch.setattr(ops_store, "OSSearch", _fake_search({"ts": "2026-07-31"}))

    result = probe.check_opensearch()

    assert result["status"] == "down"
    assert result["detail"] == "unusable timestamp in latest doc"


def test_opensearch_probe_failure_is_down_without_the_driver_message(monkeypatch):
    monkeypatch.setattr(ops_store, "OSSearch", _boom("os-host-2:9200 refused"))

    result = probe.check_opensearch()

    assert result["status"] == "down"
    assert result["detail"] == "probe failed (ConnectionError)"
    assert "os-host-2" not in str(result)


def test_minio_probe_stops_after_a_bounded_sample(monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(minio_handler, "MinioObject", lambda *_a, **_k: store)

    result = probe.check_minio()

    assert result["status"] == "up"
    assert result["detail"] == "connected · user/2067928"
    assert store.consumed == probe.LIST_SAMPLE


def test_minio_probe_calls_an_empty_prefix_up_but_says_so(monkeypatch):
    monkeypatch.setattr(
        minio_handler, "MinioObject", lambda *_a, **_k: FakeStore(entries=[])
    )

    result = probe.check_minio()

    assert result["status"] == "up"
    assert result["detail"] == "connected · user/2067928 is empty"


def test_minio_probe_failure_is_down_without_the_driver_message(monkeypatch):
    monkeypatch.setattr(minio_handler, "MinioObject", _boom("minio-host-9:9000 nope"))

    result = probe.check_minio()

    assert result["status"] == "down"
    assert result["detail"] == "probe failed (ConnectionError)"
    assert "minio-host-9" not in str(result)


def test_office_returns_the_three_contract_rows_in_order(all_services_up):
    result = office.get_services_health()

    assert_matches(result, ServicesHealthResponse)
    assert [s["id"] for s in result["services"]] == ["redis", "opensearch", "minio"]
    assert all(s["status"] == "up" for s in result["services"])
    assert result["checked_at"].endswith("Z")


def test_office_never_fakes_up_and_never_raises(all_services_down):
    """Three rows, all honest: a total outage must still answer the contract
    rather than raise out of the provider or fall back to a green row."""
    result = office.get_services_health()

    assert_matches(result, ServicesHealthResponse)
    assert [s["status"] for s in result["services"]] == ["down", "down", "down"]
    assert all("mock" not in s["detail"] for s in result["services"])


def test_the_request_path_captures_nothing(all_services_up):
    """Capture is what makes the probes do extra server work, so the HTTP path
    must not ask for it — and there is no module-level dict for a concurrent
    request to scribble into either."""
    redis, store = all_services_up

    office.get_services_health()

    assert redis.calls == ["ping"]
    assert store.consumed == probe.LIST_SAMPLE
    assert not hasattr(office, "_RAW")


def test_the_standalone_run_dumps_the_raw_payloads(monkeypatch, capsys):
    """The self-check exists to show what came off the wire, so the assertions
    are on what it printed — a green "up" line proves nothing by itself."""
    redis = FakeRedis()
    monkeypatch.setattr(probe, "redis_client", lambda: redis)
    monkeypatch.setattr(
        ops_store,
        "OSSearch",
        _fake_search({"timestamp": probe.now().isoformat(), "eqp_id": "TP01"}),
    )
    monkeypatch.setattr(minio_handler, "MinioObject", lambda *_a, **_k: FakeStore())

    assert office._main() == 0

    out = capsys.readouterr().out
    assert "all services up" in out
    assert '"dbsize": 42' in out
    assert '"eqp_id"' in out
    assert '"bucket": "user"' in out
    # The capture path is what earns the extra reads.
    assert "scan" in redis.calls


def test_the_standalone_run_exits_nonzero_when_a_service_is_down(all_services_down):
    assert office._main() == 1
