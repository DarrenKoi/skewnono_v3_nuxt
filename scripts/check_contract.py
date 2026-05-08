"""Verify that running Flask :5000 returns shapes matching frozen fixtures.

사무실 스왑 직후 실 Flask 가 댁 측 기대 형태를 깨뜨리지 않았는지 검증합니다.
구체적으로 다음을 확인합니다.

1. 모든 엔드포인트가 응답을 반환합니다.
2. 응답의 최상위 키 집합이 픽스처와 일치합니다.
3. 배열의 첫 행 키 집합이 픽스처의 첫 행과 일치합니다.
4. 각 키의 값 타입(파이썬 기본 타입)이 픽스처와 일치합니다.

값의 동등성은 보지 않습니다 — 모의와 실 데이터는 값이 다른 것이 정상입니다.
구조만 봅니다.

사용법:
    python scripts/check_contract.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# capture_fixtures.py 와 동일한 엔드포인트 목록을 공유합니다.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_fixtures import ENDPOINTS, FLASK_BASE, REPO_ROOT  # noqa: E402


def _fetch(url: str) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def _diff_shape(expected: Any, actual: Any, path: str = "$") -> list[str]:
    """Return a list of human-readable shape differences."""
    issues: list[str] = []

    if _type_name(expected) != _type_name(actual):
        issues.append(
            f"{path}: 타입 불일치 expected={_type_name(expected)} actual={_type_name(actual)}"
        )
        return issues

    if isinstance(expected, dict):
        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys()) if isinstance(actual, dict) else set()
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        for key in sorted(missing):
            issues.append(f"{path}.{key}: 키 누락")
        for key in sorted(extra):
            issues.append(f"{path}.{key}: 새 키 발견 (계약 갱신 필요?)")
        for key in sorted(expected_keys & actual_keys):
            issues.extend(_diff_shape(expected[key], actual[key], f"{path}.{key}"))
        return issues

    if isinstance(expected, list):
        if not expected:
            return issues  # 비어 있는 배열은 형태 정보가 없음
        if not isinstance(actual, list):
            return issues  # 위에서 이미 잡힘
        if not actual:
            issues.append(f"{path}: 실제 배열이 비어 있어 행 형태를 비교할 수 없습니다")
            return issues
        # 첫 행끼리 비교 — 동질 배열 가정
        issues.extend(_diff_shape(expected[0], actual[0], f"{path}[0]"))
        return issues

    return issues


def main() -> int:
    total = 0
    fails = 0
    for feature_dir, fixture_name, path in ENDPOINTS:
        fixture_path = (
            REPO_ROOT / "back_dev_home" / feature_dir / "__fixtures__" / fixture_name
        )
        if not fixture_path.exists():
            print(f"[SKIP] {path} (픽스처 없음: {fixture_path.relative_to(REPO_ROOT)})")
            continue

        total += 1
        url = f"{FLASK_BASE}{path}"
        try:
            actual = _fetch(url)
        except urllib.error.URLError as exc:
            print(f"[FAIL] {path}: 응답 실패 {exc}")
            fails += 1
            continue

        expected = json.loads(fixture_path.read_text(encoding="utf-8"))
        issues = _diff_shape(expected, actual)

        if issues:
            print(f"[FAIL] {path}")
            for issue in issues[:20]:
                print(f"       - {issue}")
            if len(issues) > 20:
                print(f"       ... ({len(issues) - 20} 개 추가)")
            fails += 1
        else:
            print(f"[ OK ] {path}")

    print(f"\n{total - fails} / {total} 통과")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
