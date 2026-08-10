"""para_* 버킷 — 파라미터의 측정 point 수를 다섯 **구간**으로 나눕니다.

    x <= 5           para_5
    5 < x <= 9       para_9
    9 < x <= 13      para_13
    13 < x <= 16     para_16
    16 < x           para_over_16

이름의 숫자는 그 구간의 **상한**입니다. ``para_over_16`` 만 위가 열려 있습니다.

정정 이력 (2026-08-10) — 그 전까지는 point 수가 16/13/9/5 와 **정확히 같은**
파라미터만 셌습니다. 실물 문서 한 건이 ``{"EDGE": 10, "LEVEL": 4, "WAFER": 10}``
으로 확인되면서(docs/datatables/idp_ver.txt) 그 정의가 무너졌습니다 — 세 값 모두
네 숫자 밖이라 recipe 전체가 ``para_all = 0`` 이 되었고, 화면의 100% 누적 막대는
빈 칸이 됩니다. 구간으로 바꾸면 **모든 파라미터가 정확히 한 버킷에 들어가므로**
``para_all`` 은 곧 파라미터 총 개수이고 네(이제 다섯) 퍼센트의 합은 항상 100 입니다.
"이 값을 total 로 쓸지 버킷 합으로 쓸지" 라는 오래된 질문도 여기서 사라집니다.

버킷을 한 곳에서만 정의하는 이유는 소비자가 셋이기 때문입니다 — mock 두 표면
(``providers/statistics.py``, ``providers/recipe_population.py``)과 office 어댑터.
경계를 각자 들고 있으면 집과 사무실이 같은 recipe 를 다르게 세고, 그 차이는 예외가
아니라 "숫자가 조금 다르다" 로만 나타납니다.

프론트엔드에 같은 목록이 있습니다 (``app/utils/paraTrendSeries.ts`` 의
``PARA_KEYS``). 언어가 갈라 두 벌이 된 것이므로 한쪽만 고치면 안 됩니다.
"""

from __future__ import annotations

from collections.abc import Mapping


# 낮은 구간부터. 화면의 색 램프와 누적 막대 순서가 이 순서를 뒤집어 씁니다.
PARA_BUCKETS: tuple[str, ...] = (
    "para_5",
    "para_9",
    "para_13",
    "para_16",
    "para_over_16",
)

# (상한, 버킷 이름). 위에서부터 처음으로 ``x <= 상한`` 인 것이 그 파라미터의
# 버킷이고, 어디에도 안 걸리면 열린 구간입니다.
_UPPER_BOUNDS: tuple[tuple[int, str], ...] = (
    (5, "para_5"),
    (9, "para_9"),
    (13, "para_13"),
    (16, "para_16"),
)

OVERFLOW_BUCKET = "para_over_16"


def bucket_for(point_count: int) -> str:
    """이 point 수가 들어갈 버킷 이름. **항상 하나가 나옵니다.**

    0 이나 음수도 ``para_5`` 로 들어갑니다 — 원천에 그런 값이 있는지는 확인된 바
    없지만, 있다면 어느 버킷에도 안 들어가 조용히 사라지는 것보다 가장 낮은
    구간에 보이는 편이 낫습니다.
    """
    for bound, name in _UPPER_BOUNDS:
        if point_count <= bound:
            return name
    return OVERFLOW_BUCKET


# CD 측정량을 논하는 자리에 낄 수 없는 파라미터 이름 (user-confirmed 2026-08-05).
# 대문자로 적은 것은 **비교용 정규형**입니다 — 실물 표기는 "Dummy"/"Align" 처럼
# 첫 글자만 대문자입니다. 어느 표기로 와도 걸려야 하므로 비교 전에 올립니다.
#
# 프론트엔드 ``outlierDetect.isOutlierExemptParam`` 과 **같은 규칙**입니다
# (이름이 그 낱말로 시작하거나 끝나면 참, 한복판에 우연히 든 것은 거짓).
_NON_MEASUREMENT_WORDS = ("DUMMY", "ALIGN")


def is_measurement_param(name: str) -> bool:
    """이 파라미터가 "얼마나 많이 쟀는가" 에 포함되는가.

    Dummy 는 자리를 채우는 placeholder 이고 Align 은 정렬(addressing)용이라
    측정이 아니라 측정을 위한 준비입니다 — 둘 다 point 수가 1~3 이며 통계에
    들어가면 안 됩니다 (user-confirmed 2026-08-10). 실물의 "16 초과는 전체
    파라미터의 2~5%" 라는 수치도 이 둘을 빼고 센 것입니다.
    """
    upper = (name or "").strip().upper()
    return not any(
        upper.startswith(word) or upper.endswith(word)
        for word in _NON_MEASUREMENT_WORDS
    )


def count_points(parameters: Mapping[str, int]) -> dict[str, int]:
    """``{이름: point 수}`` -> 버킷별 파라미터 개수 (모든 버킷 키를 채웁니다).

    **이름을 받는 것이 요점입니다.** point 수만 받으면 호출하는 쪽이 비측정
    파라미터를 거르는 것을 잊을 수 있고, 그 실수는 예외가 아니라 "para 합계가
    조금 크다" 로만 나타납니다. 거르는 자리를 여기 하나로 두어 mock 과 office
    가 같은 모집단을 세게 합니다.
    """
    counts = {name: 0 for name in PARA_BUCKETS}
    for name, point_count in parameters.items():
        if is_measurement_param(name):
            counts[bucket_for(int(point_count))] += 1
    return counts


def para_block(counts: Mapping[str, int]) -> dict[str, float]:
    """버킷별 개수 -> 계약의 ``para_*`` 블록 (개수 + 합계 + 퍼센트).

    ``RecipeInfoRow`` 와 ``SummaryRow`` 가 같은 블록을 쓰므로, 버킷이 하나 늘 때
    고쳐야 할 자리가 여기 하나입니다. 예전에는 dict 리터럴 네 벌에 키를 손으로
    적어 두어, 한 벌만 빠뜨려도 그 화면만 조용히 옛 모양을 냈습니다.
    """
    numbers = {name: int(counts.get(name, 0)) for name in PARA_BUCKETS}
    total = sum(numbers.values())
    block: dict[str, float] = {"para_all": total}
    block.update(numbers)
    for name in PARA_BUCKETS:
        block[f"{name}_percent"] = (
            round(numbers[name] / total * 100, 2) if total else 0.0
        )
    return block
