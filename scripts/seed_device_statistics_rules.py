"""Seed the office device-statistics measurement rules (fixes the R3 rules 404).

증상: 사무실에서 comparison 페이지가 GET
/api/cdsem/device-statistics/rules?fac_id=R3 에 404 를 받고, Lot 요약의
health 가 전부 "룰 없음", 판정 범위가 전부 0 으로 나옵니다 (2026-08-04 관측).

원인: 룰은 사무실 DB 에서 읽는 값이 아니라 **이 앱이 소유하는 상태**입니다
(rule-editor-structure.md §2). office 어댑터는 Redis 해시
``v3_device_statistics_rules`` 의 발행본만 읽으므로, 최초 1회 발행 전에는
어느 fab 도 404 입니다.

이 스크립트는 mock 의 seed(``providers/rules.py`` — D8/D19 매트릭스, 집에서
프론트엔드가 판정에 쓰는 것과 동일한 RuleVersion)를 그대로 발행합니다. 즉
집 화면과 사무실 화면이 같은 룰에서 출발합니다.

이미 발행본이 있으면 **덮어쓰지 않습니다** — 발행본에는 사무실에서의 편집이
실려 있을 수 있고, 조용한 덮어쓰기는 그 상태를 파괴합니다. 갈아엎으려면
``--force`` 를 명시하십시오.

Run FROM THE REPO ROOT at the office (reads REDIS_* from back_dev_home/.env
exactly like the adapter does):

    .venv/bin/python -m scripts.seed_device_statistics_rules
    .venv/bin/python -m scripts.seed_device_statistics_rules --force

확인:

    curl "http://localhost:5000/api/cdsem/device-statistics/rules?fac_id=R3"
"""

from __future__ import annotations

import sys

from back_dev_home.ebeam.cdsem.device_statistics.providers.rules import (
    get_rules as seed_rules,
)

try:
    from back_dev_home.ebeam.cdsem.device_statistics.providers.office import (
        RULES_KEY,
        get_rules as published_rules,
        publish_rules,
    )
except ImportError as exc:
    print(
        "office 어댑터가 없습니다 — 이 스크립트는 사무실 전용입니다.\n"
        "먼저: cd back_dev_home/ebeam/cdsem/device_statistics/providers "
        "&& cp office_example.py office.py\n"
        f"(ImportError: {exc})"
    )
    raise SystemExit(2) from exc


# rules.py 의 seed 는 R3 전용입니다 (D22 — M-fab 룰 폐기). fab 이 늘면 이
# 목록만 넓힙니다.
FABS = ("R3",)


def main() -> int:
    force = "--force" in sys.argv[1:]
    failures = 0

    for fac_id in FABS:
        seed = seed_rules(fac_id)
        if seed is None:
            print(f"[{fac_id}] mock seed 가 없습니다 — providers/rules.py 확인")
            failures += 1
            continue

        current = published_rules(fac_id)
        if current is not None and not force:
            print(
                f"[{fac_id}] 이미 발행됨 (version {current['version']}, "
                f"edited_by {current['edited_by']!r}, edited_at {current['edited_at']}) "
                "— 덮어쓰려면 --force"
            )
            continue

        publish_rules(fac_id, seed)

        # 발행 직후 어댑터의 읽기 경로로 round-trip 검증 — hset 성공과 "route 가
        # 200 을 준다" 사이에는 직렬화 형식이 끼어 있습니다.
        readback = published_rules(fac_id)
        if readback is None:
            print(f"[{fac_id}] 발행했으나 다시 읽히지 않습니다 — {RULES_KEY!r} 확인")
            failures += 1
            continue

        print(
            f"[{fac_id}] 발행 완료 -> {RULES_KEY!r} "
            f"(version {readback['version']}, cells {len(readback['cells'])}개)"
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
