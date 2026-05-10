"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

원본:        (사무실 측 Redis / OpenSearch / MinIO 라이브 핑)
계약:        docs/api-contracts/health.yaml
픽스처:      없음 — 라이브 응답이라 픽스처 캡처는 무의미합니다.

홈에서는 OpenSearch · MinIO 실서비스가 없으므로 항상 "정상" 상태에 고정 latency 만
돌려줍니다. 사무실 측은 동일 시그니처로 실제 핑을 시간 측정해 채우면 됩니다.

권장 office 구현 (요지):
    redis:      redis.Redis(...).ping()                      # ms = 측정시간
    opensearch: ops_store.create_client().ping()             # ms = 측정시간
    minio:      minio_store.create_client().list_buckets()   # ms = 측정시간

각각 try/except 로 감싸 예외 시 status="down", latency_ms=None, detail=에러 요약.
"""

from datetime import datetime, timezone
from typing import Literal, TypedDict


__all__ = ["ServiceHealth", "ServicesHealthResponse", "get_services_health"]


Status = Literal["up", "down"]


class ServiceHealth(TypedDict):
    id: str
    label: str
    status: Status
    latency_ms: int | None
    detail: str


class ServicesHealthResponse(TypedDict):
    checked_at: str
    services: list[ServiceHealth]


# checked_at 만 호출 시각을 반영해 프론트의 "checked Ns ago" 라벨이 갱신됩니다.
_HOME_SERVICES: list[ServiceHealth] = [
    {"id": "redis",      "label": "Redis",      "status": "up", "latency_ms": 2,  "detail": "6.2.7 · 1 node"},
    {"id": "opensearch", "label": "OpenSearch", "status": "up", "latency_ms": 14, "detail": "2.11 · 3 nodes · green"},
    {"id": "minio",      "label": "MinIO",      "status": "up", "latency_ms": 6,  "detail": "12 buckets"},
]


def get_services_health() -> ServicesHealthResponse:
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "services": _HOME_SERVICES,
    }
