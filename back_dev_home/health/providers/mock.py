"""SWAP SURFACE — 동일 시그니처/TypedDict 로 사무실/홈 양쪽에서 사용합니다.

원본:        (사무실 측 Redis / OpenSearch / MinIO 라이브 핑)
계약:        docs/api-contracts/health.yaml
픽스처:      없음 — 라이브 응답이라 픽스처 캡처는 무의미합니다.

동작 규칙:
- Redis      : ping() 으로 왕복 시간을 잰다.
- OpenSearch : 인덱스 `meas_hist_cdsem` 의 최신 도큐먼트를 `timestamp` 로 정렬해 가져온 뒤,
               타임스탬프가 1시간 이내이면 "up", 더 오래되었으면 "down (stale)".
- MinIO      : OS 최신 도큐먼트의 `minio_path` (형식: "bucket/key") 를 stat() 으로 조회해
               last_modified 가 1시간 이내이면 "up".

홈 환경에서는 세 서버 모두 실제로 떠 있지 않습니다. `get_mode()` 가 office 가
아니면 프로브를 아예 시도하지 않고 canned 응답을 즉시 돌려줍니다 — 홈 .env 의
REDIS_HOST 는 사무실 호스트라 "설정돼 있지만 도달 불가" 이고, 프로브를 돌리면
요청마다 connect timeout(2s) 만큼 블록되기 때문입니다. office 모드에서만 라이브
프로브를 수행하며, 각 체커는 try/except 로 묶여 있어 연결 실패·라이브러리 미설치
같은 예외가 발생하면 detail 앞에 `mock · ` 접두사를 단 "up" 응답으로 폴백합니다.
(office 모드 + 이 파일: office.py 를 아직 cp 하지 않은 사무실 장비의 하이브리드
경로 — 모드가 office 이므로 라이브 프로브가 그대로 동작합니다.)
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from back_dev_home._runtime.data_provider import get_mode
from back_dev_home.health.contracts import ServiceHealth, ServicesHealthResponse


__all__ = ["get_services_health"]


FRESHNESS_WINDOW = timedelta(hours=1)
OS_INDEX = "meas_hist_cdsem"
OS_TIME_FIELD = "timestamp"


_MOCK_REDIS: ServiceHealth = {
    "id": "redis", "label": "Redis", "status": "up",
    "latency_ms": 2, "detail": "mock · 6.2.7 · 1 node",
}
_MOCK_OPENSEARCH: ServiceHealth = {
    "id": "opensearch", "label": "OpenSearch", "status": "up",
    "latency_ms": 14, "detail": "mock · 2.11 · 3 nodes · green",
}
_MOCK_MINIO: ServiceHealth = {
    "id": "minio", "label": "MinIO", "status": "up",
    "latency_ms": 6, "detail": "mock · 12 buckets",
}

def _mock_latest_doc() -> dict[str, Any]:
    # 호출 시점 기준으로 timestamp 를 계산해 모듈 로드 후 시간이 흘러도
    # _check_minio 가 "신선" 한 도큐먼트로 보도록 유지한다.
    return {
        "timestamp": (_now() - timedelta(minutes=3)).isoformat(),
        "minio_path": "meas-raw/cdsem/mock/latest.json",
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _format_age(delta: timedelta) -> str:
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h{minutes:02d}m" if minutes else f"{hours}h"
    days, hours = divmod(hours, 24)
    return f"{days}d{hours:02d}h" if hours else f"{days}d"


def _parse_minio_path(path: str) -> tuple[str, str]:
    bucket, sep, key = path.partition("/")
    if not sep or not bucket or not key:
        raise ValueError(f"invalid minio_path {path!r}; expected 'bucket/key'")
    return bucket, key


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _check_redis() -> ServiceHealth:
    try:
        import redis  # type: ignore[import-not-found]
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            password=os.environ.get("REDIS_PASSWORD") or None,
            socket_timeout=2,
            socket_connect_timeout=2,
            # redis-py 8 retries 3× with exponential backoff by default, so a
            # host that silently drops SYNs (office REDIS_HOST reached from
            # home) blocks ~26s despite the 2s timeouts — long enough that the
            # landing page's health card never resolves. One attempt only:
            # this is a liveness probe, a retry adds nothing.
            retry=Retry(NoBackoff(), retries=0),
        )
        started = time.perf_counter()
        client.ping()
        latency = _elapsed_ms(started)
        return {
            "id": "redis", "label": "Redis", "status": "up",
            "latency_ms": latency, "detail": "ping ok",
        }
    except Exception:
        return _MOCK_REDIS


def _check_opensearch_latest() -> tuple[ServiceHealth, dict[str, Any] | None]:
    try:
        from ops_store import OSSearch

        search = OSSearch(index=OS_INDEX)
        started = time.perf_counter()
        result = search.latest(OS_TIME_FIELD, size=1)
        latency = _elapsed_ms(started)

        hits = (result or {}).get("hits", {}).get("hits", []) if result else []
        if not hits:
            return ({
                "id": "opensearch", "label": "OpenSearch", "status": "down",
                "latency_ms": latency, "detail": f"no data in {OS_INDEX}",
            }, None)

        doc = hits[0].get("_source", {}) or {}
        ts = _parse_ts(doc[OS_TIME_FIELD])
        age = _now() - ts
        if age <= FRESHNESS_WINDOW:
            return ({
                "id": "opensearch", "label": "OpenSearch", "status": "up",
                "latency_ms": latency,
                "detail": f"latest {_format_age(age)} ago · {OS_INDEX}",
            }, doc)
        return ({
            "id": "opensearch", "label": "OpenSearch", "status": "down",
            "latency_ms": latency,
            "detail": f"stale: latest {_format_age(age)} ago",
        }, doc)
    except Exception:
        return _MOCK_OPENSEARCH, _mock_latest_doc()


def _check_minio(latest_doc: dict[str, Any] | None) -> ServiceHealth:
    try:
        path = (latest_doc or {}).get("minio_path") if latest_doc else None
        if not path:
            return {
                "id": "minio", "label": "MinIO", "status": "down",
                "latency_ms": None, "detail": "no minio_path in latest os doc",
            }

        bucket, key = _parse_minio_path(path)

        from minio.error import S3Error  # type: ignore[import-not-found]
        from minio_handler import MinioObject

        store = MinioObject(bucket=bucket)
        started = time.perf_counter()
        try:
            stat = store.stat(key)
        except S3Error as err:
            latency = _elapsed_ms(started)
            return {
                "id": "minio", "label": "MinIO", "status": "down",
                "latency_ms": latency,
                "detail": f"missing: {bucket}/{key} ({err.code})",
            }
        latency = _elapsed_ms(started)

        ts = _parse_ts(stat.last_modified)
        age = _now() - ts
        if age <= FRESHNESS_WINDOW:
            return {
                "id": "minio", "label": "MinIO", "status": "up",
                "latency_ms": latency,
                "detail": f"latest object {_format_age(age)} ago · {bucket}",
            }
        return {
            "id": "minio", "label": "MinIO", "status": "down",
            "latency_ms": latency,
            "detail": f"stale: object {_format_age(age)} ago",
        }
    except Exception:
        return _MOCK_MINIO


def get_services_health() -> ServicesHealthResponse:
    # Mode, not reachability: home's .env carries the office REDIS_HOST, so
    # probing from home is not "try and fall back" — it is a guaranteed
    # connect-timeout block on every call. Only office mode probes live.
    if get_mode() != "office":
        return {
            "checked_at": _now().isoformat(timespec="seconds"),
            "services": [_MOCK_REDIS, _MOCK_OPENSEARCH, _MOCK_MINIO],
        }
    redis_h = _check_redis()
    os_h, latest_doc = _check_opensearch_latest()
    minio_h = _check_minio(latest_doc)
    return {
        "checked_at": _now().isoformat(timespec="seconds"),
        "services": [redis_h, os_h, minio_h],
    }
