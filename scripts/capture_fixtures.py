"""Capture frozen JSON fixtures from a running Flask :5000 mock server.

각 피처의 `__fixtures__/<endpoint>.json` 을 갱신합니다. 사무실 LLM 이
"이 형태로 결과를 만들어라" 라고 요구할 수 있는 구체 예시이자,
office data.py 의 회귀 테스트 기준선입니다.

사용법:
    python scripts/capture_fixtures.py

전제 조건: Flask 가 :5000 에서 동작 중이어야 합니다 (PyCharm 에서 기동).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
FLASK_BASE = "http://localhost:5000"


# (feature_dir, fixture_name, "/api/<path>") tuples. 쿼리 파라미터가 있는
# 엔드포인트는 명시적으로 적습니다 — 픽스처는 "기본 호출 + 대표적 필터"
# 두 가지 경우를 모두 캡처해 사무실 측 형태 검증의 폭을 넓힙니다.
ENDPOINTS: list[tuple[str, str, str]] = [
    # sem_list
    ("sem_list", "sem-list.json", "/api/sem-list"),

    # announcements
    ("announcements", "announcements.json", "/api/announcements"),

    # afm
    ("afm", "afm-tools.json", "/api/afm/tools"),
    ("afm", "afm-files-default.json", "/api/afm/files"),
    ("afm", "afm-files-mapc01.json", "/api/afm/files?tool=MAPC01"),
    ("afm", "afm-activities.json", "/api/afm/activities?limit=20"),
    ("afm", "afm-analytics.json", "/api/afm/analytics?days=7"),

    # cdsem device statistics
    ("ebeam/cdsem/device_statistics", "r3-device-grp.json",
     "/api/cdsem/device-statistics/r3-device-grp"),
    ("ebeam/cdsem/device_statistics", "device-desc.json",
     "/api/cdsem/device-statistics/device-desc"),
    ("ebeam/cdsem/device_statistics", "device-desc-m11-m12.json",
     "/api/cdsem/device-statistics/device-desc?fac_id=M11,M12"),
    ("ebeam/cdsem/device_statistics", "recipe-statistics.json",
     "/api/cdsem/device-statistics/recipe-statistics?lot_cds=R000,R001"),
    ("ebeam/cdsem/device_statistics", "recipe-trend.json",
     "/api/cdsem/device-statistics/recipe-trend?lot_cds=R000,R001"),

    # hitachi storage (shared CD-SEM / HV-SEM)
    ("ebeam/hitachi/storage", "storage-cdsem.json", "/api/cdsem/storage"),
    ("ebeam/hitachi/storage", "storage-cdsem-r3.json", "/api/cdsem/storage?fac_id=R3"),
    ("ebeam/hitachi/storage", "storage-cdsem-ppid-unavailable.json", "/api/cdsem/ppid-unavailable"),
    ("ebeam/hitachi/storage", "storage-hvsem.json", "/api/hvsem/storage"),
    ("ebeam/hitachi/storage", "storage-hvsem-ppid-unavailable.json", "/api/hvsem/ppid-unavailable"),

    # hitachi recipe-tat (tool_slug in URL; URL is authoritative)
    ("ebeam/hitachi/recipe_tat", "ranking-cdsem.json", "/api/cdsem/recipe-tat/ranking"),
    ("ebeam/hitachi/recipe_tat", "ranking-hvsem.json", "/api/hvsem/recipe-tat/ranking"),
    ("ebeam/hitachi/recipe_tat", "summary-cdsem.json", "/api/cdsem/recipe-tat/summary"),
    ("ebeam/hitachi/recipe_tat", "daily-trend-cdsem.json", "/api/cdsem/recipe-tat/daily-trend"),
    ("ebeam/hitachi/recipe_tat", "devices-cdsem.json", "/api/cdsem/recipe-tat/devices"),
]


def _fetch(url: str) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _truncate(payload: Any, max_rows: int = 30) -> Any:
    """Cap large arrays so fixtures stay reviewable.

    프론트엔드는 수천 행을 받지만 픽스처는 형태 검증용입니다. 길이 자체가
    의미 있는 경우(예: ppid-unavailable 의 streak 분포)는 max_rows 가
    충분히 크게 설정되어 있고, 형태만 보면 되는 경우는 30 행으로 줄여
    사무실 LLM 컨텍스트 비용을 아낍니다.
    """
    if isinstance(payload, list):
        return [_truncate(item, max_rows) for item in payload[:max_rows]]
    if isinstance(payload, dict):
        result: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, list):
                result[key] = [_truncate(item, max_rows) for item in value[:max_rows]]
            else:
                result[key] = _truncate(value, max_rows)
        return result
    return payload


def main() -> int:
    failures = 0
    for feature_dir, fixture_name, path in ENDPOINTS:
        url = f"{FLASK_BASE}{path}"
        target = REPO_ROOT / "back_dev_home" / feature_dir / "__fixtures__" / fixture_name
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            payload = _fetch(url)
        except urllib.error.URLError as exc:
            print(f"[FAIL] {path} -> {exc}", file=sys.stderr)
            failures += 1
            continue

        truncated = _truncate(payload)
        target.write_text(
            json.dumps(truncated, indent=2, ensure_ascii=False, sort_keys=False),
            encoding="utf-8",
        )
        size_kb = target.stat().st_size / 1024
        print(f"[ OK ] {path:<60} -> {target.relative_to(REPO_ROOT)}  ({size_kb:.1f} KB)")

    if failures:
        print(f"\n{failures} endpoint(s) failed. Flask :5000 가 실행 중인지 확인하세요.",
              file=sys.stderr)
        return 1
    print(f"\n{len(ENDPOINTS)} 개 픽스처를 갱신했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
