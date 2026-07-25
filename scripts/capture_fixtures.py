"""Capture frozen JSON fixtures from a running Flask mock server.

각 피처의 `__fixtures__/<endpoint>.json` 을 갱신합니다. 사무실 LLM 이
"이 형태로 결과를 만들어라" 라고 요구할 수 있는 구체 예시이자,
office data.py 의 회귀 테스트 기준선입니다.

사용법:
    python -m scripts.capture_fixtures              # 기본 :5050 (댁)
    PORT=5000 python -m scripts.capture_fixtures    # 다른 포트의 Flask

전제 조건: Flask 가 해당 포트에서 동작 중이어야 합니다.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent.parent

# 픽스처 트리의 뿌리. 테스트가 tmp_path 로 갈아끼우므로 함수 안에서
# 모듈 전역을 읽습니다 — 기본 인자로 굳히면 monkeypatch 가 먹지 않습니다.
BACKEND_ROOT = REPO_ROOT / "back_dev_home"

# 댁(Phase 1) Flask 는 :5050 입니다 — :5000 은 macOS AirPlay 와 충돌합니다.
# 사무실(Phase 2) Flask 는 :5000 이므로 포트는 고정할 수 없습니다. index.py
# 와 같은 PORT 노브를 읽어, 두 위치에서 코드 수정 없이 겨냥합니다.
DEFAULT_PORT = 5050


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

    # hitachi hardware (equipment-first path; tool_slug + eqp_id + service)
    ("ebeam/hitachi/hardware", "hardware-bsm.json",
     "/api/cdsem/hardware/ECXDX204/bsm?fab_name=M16B&start=2026-04-24&end=2026-05-24"),
    ("ebeam/hitachi/hardware", "hardware-reso-center.json",
     "/api/cdsem/hardware/ECXDX204/reso-center?fab_name=M16B&start=2026-04-24&end=2026-05-24"),
    ("ebeam/hitachi/hardware", "hardware-fdc.json",
     "/api/cdsem/hardware/ECXDX204/fdc?fab_name=M16B&start=2026-05-17&end=2026-05-24"),
    ("ebeam/hitachi/hardware", "hardware-mdc.json",
     "/api/cdsem/hardware/ECXDX204/mdc?fab_name=M16B&end=2026-05-24"),
    ("ebeam/hitachi/hardware", "hardware-sce.json",
     "/api/cdsem/hardware/ECXDX204/sce?fab_name=M16B&end=2026-05-24"),
    ("ebeam/hitachi/hardware", "hardware-bm-pm.json",
     "/api/cdsem/hardware/ECXDX204/bm-pm?fab_name=M16B"),
]


def flask_base() -> str:
    """Base URL of the Flask instance to read from, resolved at call time.

    `PORT` 가 있으면 그 포트, 없으면 :5050. 상수로 얼려두면 반대편 위치에서
    이 스크립트가 조용히 엉뚱한 포트를 찔러 "응답 실패" 로만 보입니다.
    """
    return f"http://localhost:{os.environ.get('PORT') or DEFAULT_PORT}"


def fixture_path(feature_dir: str, fixture_name: str) -> Path:
    """Where one endpoint's frozen fixture lives. check_contract 와 공유합니다."""
    return BACKEND_ROOT / feature_dir / "__fixtures__" / fixture_name


def display_path(path: Path) -> str:
    """Repo-relative when possible — 테스트는 픽스처 뿌리를 tmp_path 로 옮깁니다."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


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


def capture(
    endpoints: list[tuple[str, str, str]],
    fetch: Callable[[str], Any] | None = None,
) -> list[str]:
    """Write one fixture per endpoint; return the API paths that failed.

    `fetch` 를 주입 가능하게 둔 이유는 테스트뿐입니다 — 이 스크립트가 실제
    픽스처를 덮어쓰는 유일한 경로이므로, 라이브 Flask 없이도 쓰기 경로를
    검증할 수 있어야 합니다. `None` 은 실제 HTTP 입니다.
    """
    fetch = fetch or _fetch
    failures: list[str] = []
    base = flask_base()
    for feature_dir, fixture_name, path in endpoints:
        url = f"{base}{path}"
        target = fixture_path(feature_dir, fixture_name)

        try:
            payload = fetch(url)
        except urllib.error.URLError as exc:
            print(f"[FAIL] {path} -> {exc}", file=sys.stderr)
            failures.append(path)
            continue

        # 응답을 받은 뒤에 만듭니다 — 실패한 엔드포인트나 오타 난 feature_dir
        # 이 빈 __fixtures__/ 디렉터리를 남기면 안 됩니다.
        target.parent.mkdir(parents=True, exist_ok=True)
        truncated = _truncate(payload)
        target.write_text(
            json.dumps(truncated, indent=2, ensure_ascii=False, sort_keys=False),
            encoding="utf-8",
        )
        size_kb = target.stat().st_size / 1024
        print(f"[ OK ] {path:<60} -> {display_path(target)}  ({size_kb:.1f} KB)")

    return failures


def main() -> int:
    failures = capture(ENDPOINTS)

    if failures:
        print(
            f"\n{len(failures)} endpoint(s) failed. "
            f"Flask {flask_base()} 가 실행 중인지 확인하세요.",
            file=sys.stderr,
        )
        return 1
    print(f"\n{len(ENDPOINTS)} 개 픽스처를 갱신했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
