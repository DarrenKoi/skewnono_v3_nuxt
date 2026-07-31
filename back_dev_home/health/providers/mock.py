"""SWAP SURFACE — 동일 시그니처/TypedDict 로 사무실/홈 양쪽에서 사용합니다.

원본:        (사무실 측 Redis / OpenSearch / MinIO 라이브 핑)
계약:        docs/api-contracts/health.yaml
픽스처:      없음 — 라이브 응답이라 픽스처 캡처는 무의미합니다.

이 파일이 담당하는 것은 **모드 게이트와 canned 응답뿐**입니다. 실제 프로브
세 개(Redis PING / OpenSearch 최신 도큐먼트 신선도 / MinIO bucket-prefix
나열)는 `probe_common.py` 한 곳에만 있고 office 어댑터도 같은 함수를 호출합니다
— 예전에는 두 파일이 프로브를 각각 복사해 두었고, 그래서 MinIO 체이닝 제거가
office 쪽에만 반영되는 드리프트가 실제로 발생했습니다.

`get_mode()` 가 office 가 아니면 프로브를 아예 시도하지 않고 canned 응답을
(호출마다 새 복사본으로) 즉시 돌려줍니다. 홈 .env 의 REDIS_HOST 는 사무실
호스트라 "설정돼 있지만 도달 불가" 이고, 프로브를 돌리면 요청마다 connect
timeout 만큼 블록되기 때문입니다 — 도달성이 아니라 **모드**가 판단 기준입니다.

office 모드 + 이 파일(office.py 를 아직 cp 하지 않은 사무실 장비의 하이브리드
경로)에서는 라이브 프로브를 그대로 수행하며, 프로브 실패는 canned "up" 으로
폴백하지 않고 `status: "down"` 으로 드러냅니다 — 진짜 Redis 장애가 초록색
"up · mock" 으로 렌더링되면 헬스 카드가 존재 이유를 잃기 때문입니다.
"""

from __future__ import annotations

from back_dev_home._runtime.data_provider import get_mode
from back_dev_home.health.contracts import ServiceHealth, ServicesHealthResponse
from back_dev_home.health.providers import probe_common as probe


__all__ = ["get_services_health"]


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


def _mock_rows() -> list[ServiceHealth]:
    # 호출마다 복사본: 모듈 전역 dict 를 그대로 돌려주면 호출자가 한 번
    # 변형했을 때 이후 모든 응답이 오염된다.
    return [dict(_MOCK_REDIS), dict(_MOCK_OPENSEARCH), dict(_MOCK_MINIO)]


def get_services_health() -> ServicesHealthResponse:
    if get_mode() != "office":
        return {"checked_at": probe.checked_at(), "services": _mock_rows()}
    # capture 를 넘기지 않는 호출 = 요청 경로. 프로브는 liveness 확인만 하고
    # 서버에 추가 작업(SCAN, 전체 목록 실체화)을 시키지 않는다.
    return probe.probe_services()
