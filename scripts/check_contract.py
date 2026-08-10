"""Verify that a running Flask returns shapes matching the frozen fixtures.

사무실 스왑 직후 실 Flask 가 댁 측 기대 형태를 깨뜨리지 않았는지 검증합니다.
구체적으로 다음을 확인합니다.

1. 모든 엔드포인트가 응답을 반환합니다.
2. 응답의 최상위 키 집합이 픽스처와 일치합니다.
3. 배열의 첫 행 키 집합이 픽스처의 첫 행과 일치합니다.
4. 각 키의 값 타입(파이썬 기본 타입)이 픽스처와 일치합니다.

값의 동등성은 보지 않습니다 - 모의와 실 데이터는 값이 다른 것이 정상입니다.
구조만 봅니다.

사용법:
    python -m scripts.check_contract              # 기본 :5050
    PORT=5000 python -m scripts.check_contract    # Flask 를 :5000 으로 띄운 경우

포트는 Flask 를 어떻게 띄웠는지에 맞춥니다 - index.py 기본값도 :5050 입니다.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# capture_fixtures.py 와 엔드포인트 목록·포트 해석·픽스처 경로·fetch 를 모두
# 공유합니다 - 두 스크립트가 같은 서버의 같은 파일을 보아야 비교가 의미 있습니다.
# 리포 뿌리를 넣어 `python scripts/check_contract.py` 로 직접 실행해도
# `scripts` 패키지로 한 번만 import 되게 합니다 - 최상위 `capture_fixtures`
# 로 import 하면 모듈이 두 벌 생겨 테스트의 monkeypatch 가 새 나갑니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.capture_fixtures import (  # noqa: E402
    ENDPOINTS,
    _fetch,
    display_path,
    fixture_path,
    flask_base,
)


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
        # 첫 행끼리 비교 - 동질 배열 가정
        issues.extend(_diff_shape(expected[0], actual[0], f"{path}[0]"))
        return issues

    return issues


@dataclass(frozen=True)
class Outcome:
    """One endpoint's verdict.

    `skip` 은 통과도 실패도 아닙니다 - 픽스처가 없는 엔드포인트는 분모에서
    빠지므로, "28 / 28 통과" 가 실제로는 두 피처를 건너뛴 결과일 수 있습니다.
    그 사실이 요약에 드러나야 하므로 상태를 세 가지로 구분합니다.
    """

    path: str
    status: str  # "ok" | "fail" | "skip"
    reason: str = ""  # skip 사유 또는 응답 실패 메시지
    issues: tuple[str, ...] = field(default_factory=tuple)


def check_endpoints(
    endpoints: list[tuple[str, str, str]],
    fetch: Callable[[str], Any] | None = None,
) -> Iterator[Outcome]:
    """Compare every endpoint against its fixture, yielding as it goes.

    제너레이터인 이유는 CLI 가 결과를 한 줄씩 흘려 보여주기 때문입니다 -
    응답이 30초씩 걸리는 사무실 Flask 를 상대로 마지막에 몰아 찍으면
    어디서 멈췄는지 알 수 없습니다. `fetch=None` 은 실제 HTTP 이며, 주입은
    라이브 Flask 없이 이 오케스트레이션(픽스처 누락 → skip, 응답 실패 →
    fail)을 테스트하려는 것입니다 - 기본 인자로 굳히지 않는 이유는 main()
    경로도 `_fetch` monkeypatch 로 검증할 수 있어야 하기 때문입니다.
    """
    fetch = fetch or _fetch
    base = flask_base()
    for feature_dir, fixture_name, path in endpoints:
        target = fixture_path(feature_dir, fixture_name)
        if not target.exists():
            yield Outcome(path, "skip", f"픽스처 없음: {display_path(target)}")
            continue

        try:
            actual = fetch(f"{base}{path}")
        except urllib.error.URLError as exc:
            yield Outcome(path, "fail", f"응답 실패 {exc}")
            continue

        expected = json.loads(target.read_text(encoding="utf-8"))
        issues = _diff_shape(expected, actual)
        yield Outcome(path, "fail" if issues else "ok", issues=tuple(issues))


def _report(outcome: Outcome) -> None:
    if outcome.status == "skip":
        print(f"[SKIP] {outcome.path} ({outcome.reason})")
        return
    if outcome.status == "ok":
        print(f"[ OK ] {outcome.path}")
        return

    suffix = f": {outcome.reason}" if outcome.reason else ""
    print(f"[FAIL] {outcome.path}{suffix}")
    for issue in outcome.issues[:20]:
        print(f"       - {issue}")
    if len(outcome.issues) > 20:
        print(f"       ... ({len(outcome.issues) - 20} 개 추가)")


def main() -> int:
    outcomes: list[Outcome] = []
    for outcome in check_endpoints(ENDPOINTS):
        outcomes.append(outcome)
        _report(outcome)

    fails = sum(1 for o in outcomes if o.status == "fail")
    total = sum(1 for o in outcomes if o.status != "skip")
    skipped = len(outcomes) - total

    tail = f" ({skipped} 개 건너뜀)" if skipped else ""
    print(f"\n{total - fails} / {total} 통과{tail}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
