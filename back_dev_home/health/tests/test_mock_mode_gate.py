"""The health mock's mode gate: home never dials, office probes live — and
office never fakes a green row.

Home's .env carries the office REDIS_HOST — set but unreachable — so "try and
fall back" is not free there: every /api/health/services call would block the
full connect timeout before producing the same canned rows. Mode answers the
home/office question; reachability does not.

Office machines that have not yet cp'd health/providers/office.py still route
through this module in office mode, and for them the live probes are the
point — the gate must not swallow that hybrid path, and a failed probe there
must read "down", not the canned mock row.
"""

import minio_handler
import ops_store
import pytest

from back_dev_home.health.providers import mock as health_mock
from back_dev_home.health.providers import probe_common as probe


def _never_probe(*_a, **_k):
    raise AssertionError("mock mode must not dial any backing service")


def _boom(message):
    def factory(*_a, **_k):
        raise ConnectionError(message)

    return factory


@pytest.fixture
def all_probes_fail(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    monkeypatch.setattr(probe, "redis_client", _boom("redis-office-host:6379 refused"))
    monkeypatch.setattr(ops_store, "OSSearch", _boom("os-office-host:9200 refused"))
    monkeypatch.setattr(
        minio_handler, "MinioObject", _boom("minio-office-host:9000 refused")
    )


def test_mock_mode_answers_canned_rows_without_probing(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.setattr(probe, "check_redis", _never_probe)
    monkeypatch.setattr(probe, "check_opensearch", _never_probe)
    monkeypatch.setattr(probe, "check_minio", _never_probe)

    result = health_mock.get_services_health()

    assert [s["id"] for s in result["services"]] == ["redis", "opensearch", "minio"]
    assert all(s["status"] == "up" for s in result["services"])
    assert all(s["detail"].startswith("mock · ") for s in result["services"])
    assert result["checked_at"].endswith("Z")


def test_mock_rows_are_copies_not_the_module_dicts(monkeypatch):
    """A caller that annotates a row must not poison every later response."""
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")

    first = health_mock.get_services_health()["services"]
    first[0]["detail"] = "scribbled on"
    second = health_mock.get_services_health()["services"]

    assert second[0]["detail"] == "mock · 6.2.7 · 1 node"
    assert health_mock._MOCK_REDIS["detail"] == "mock · 6.2.7 · 1 node"


def test_office_mode_still_runs_the_live_probes(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    calls: list[str] = []
    monkeypatch.setattr(
        probe,
        "check_redis",
        lambda capture=None: calls.append("redis") or dict(health_mock._MOCK_REDIS),
    )
    monkeypatch.setattr(
        probe,
        "check_opensearch",
        lambda capture=None: calls.append("opensearch")
        or dict(health_mock._MOCK_OPENSEARCH),
    )
    monkeypatch.setattr(
        probe,
        "check_minio",
        lambda capture=None: calls.append("minio") or dict(health_mock._MOCK_MINIO),
    )

    health_mock.get_services_health()

    assert calls == ["redis", "opensearch", "minio"]


def test_the_request_path_passes_no_capture(monkeypatch):
    """capture is what turns the probes into real server work (SCAN, a long
    listing). The HTTP path must never ask for it."""
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    seen: list = []
    monkeypatch.setattr(
        probe,
        "check_redis",
        lambda capture=None: seen.append(capture) or dict(health_mock._MOCK_REDIS),
    )
    monkeypatch.setattr(
        probe,
        "check_opensearch",
        lambda capture=None: dict(health_mock._MOCK_OPENSEARCH),
    )
    monkeypatch.setattr(
        probe, "check_minio", lambda capture=None: dict(health_mock._MOCK_MINIO)
    )

    health_mock.get_services_health()

    assert seen == [None]


def test_office_mode_never_fakes_up_when_a_probe_fails(all_probes_fail):
    """The regression this file exists for: an office machine without
    office.py used to render a real Redis outage as a green "up · mock" row,
    because every probe's `except` returned the canned mock value."""
    result = health_mock.get_services_health()

    assert [s["id"] for s in result["services"]] == ["redis", "opensearch", "minio"]
    assert all(s["status"] == "down" for s in result["services"])
    assert all("mock" not in s["detail"] for s in result["services"])
    # docs/api-contracts/health.yaml: "null when status is down".
    assert all(s["latency_ms"] is None for s in result["services"])


def test_probe_failure_detail_names_the_class_not_the_host(all_probes_fail):
    """/api/health/services is open to every user, so the client-facing detail
    must not carry the driver's message — that is where internal hostnames and
    ports live."""
    result = health_mock.get_services_health()

    rendered = str(result)
    assert "office-host" not in rendered
    assert "6379" not in rendered
    for service in result["services"]:
        assert service["detail"] == "probe failed (ConnectionError)"


def test_probe_failure_logs_the_full_reason_server_side(monkeypatch, caplog):
    """The detail the client does not get still has to reach an operator."""
    monkeypatch.setattr(probe, "redis_client", _boom("redis-office-host:6379 refused"))

    with caplog.at_level("WARNING", logger="skewnono.health"):
        probe.check_redis()

    assert "redis-office-host:6379 refused" in caplog.text
