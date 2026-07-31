"""The health mock's mode gate: home never dials, office probes live.

Home's .env carries the office REDIS_HOST — set but unreachable — so "try and
fall back" is not free there: every /api/health/services call would block the
full connect timeout before producing the same canned rows. Mode answers the
home/office question; reachability does not.

Office machines that have not yet cp'd health/providers/office.py still route
through this module in office mode, and for them the live probes are the
point — the gate must not swallow that hybrid path.
"""

from back_dev_home.health.providers import mock as health_mock


def _never_probe(*_a, **_k):
    raise AssertionError("mock mode must not dial any backing service")


def test_mock_mode_answers_canned_rows_without_probing(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.setattr(health_mock, "_check_redis", _never_probe)
    monkeypatch.setattr(health_mock, "_check_opensearch_latest", _never_probe)
    monkeypatch.setattr(health_mock, "_check_minio", _never_probe)

    result = health_mock.get_services_health()

    assert [s["id"] for s in result["services"]] == ["redis", "opensearch", "minio"]
    assert all(s["status"] == "up" for s in result["services"])
    assert all(s["detail"].startswith("mock · ") for s in result["services"])
    assert result["checked_at"]


def test_office_mode_still_runs_the_live_probes(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    calls: list[str] = []
    monkeypatch.setattr(
        health_mock,
        "_check_redis",
        lambda: calls.append("redis") or health_mock._MOCK_REDIS,
    )
    monkeypatch.setattr(
        health_mock,
        "_check_opensearch_latest",
        lambda: calls.append("opensearch") or (health_mock._MOCK_OPENSEARCH, None),
    )
    monkeypatch.setattr(
        health_mock,
        "_check_minio",
        lambda _doc: calls.append("minio") or health_mock._MOCK_MINIO,
    )

    health_mock.get_services_health()

    assert calls == ["redis", "opensearch", "minio"]
