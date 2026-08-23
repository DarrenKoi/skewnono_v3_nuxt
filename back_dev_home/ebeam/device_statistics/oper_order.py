"""M-fab 공정 스텝(oper_det_desc) 정렬 순서.

M 계열 양산 fab 의 스텝은 OpenSearch ``ebeam_tas_lot_hist`` 에서 오는데, 이 index
에는 **공정 순서 field 가 없습니다** (R3 의 sknn-planstep-r3 는 oper_seq / samp_seq
를 가짐 — docs/datatables/hitachi/ebeam_tas_lot_hist.txt). 대신 oper_det_desc 가 관례적인
공정 접두사로 시작하므로, 그 접두사의 순서로 정렬합니다.

    "CBL ETCH CD"    -> 접두사 "CBL"
    "ISO PTN CD(E)"  -> 접두사 "ISO"

스텝명은 접두사로 시작해 띄어쓰기로 이어지는 문자열이고 "/" 는 쓰이지 않습니다
(user-confirmed 2026-08-09).

**중요 — 이 순서는 근사입니다.** 실제 공정 순서는 tool 마다 다릅니다(user-confirmed
2026-07-30). 따라서 이 정렬은 "화면에 안정적이고 대체로 공정 흐름에 가까운 순서로
보여주기" 위한 것이고, 공정 순서를 주장하지 않습니다. **이 목록을 쓰는 화면은
"운영 공정 순서를 반영하지 않는다"는 것을 명시해야 합니다** — 사용자가 이 정렬을
공정 순서로 신뢰하면 안 되기 때문입니다.

접두사 매칭은 반드시 **longest-prefix** 여야 합니다. 목록에 SNC, SNC2, SN 이 함께
있고 M2, M2C 도 함께 있어서, 앞에서부터 훑으며 startswith 로 처음 맞는 것을 고르면
"SNC2..." 가 SNC 나 SN 으로 잡혀 엉뚱한 자리에 놓입니다. 프론트엔드의 파라미터 타입
파생(EDGE_EX > EDGE)과 똑같은 함정입니다.
"""

from __future__ import annotations


# user-confirmed 2026-07-30. 순서가 곧 값이므로 알파벳순으로 정리하거나 중복처럼
# 보이는 항목(SNC/SNC2, M2/M2C)을 합치지 마십시오 — 각각 다른 공정입니다.
OPER_PREFIX_ORDER: tuple[str, ...] = (
    "ISO",
    "CW",
    "BG",
    "MBO",
    "BLC",
    "POM",
    "PRW",
    "NW",
    "GT",
    "CBL",
    "SNC",
    "M0C",
    "SNC2",
    "SN",
    "ILD",
    "M2",
    "M2C",
    "M3",
    "M4",
    "RDL",
)

# 긴 접두사부터 검사하기 위한 사본. 원본 tuple 의 순서가 rank 이므로 그것을 건드리지
# 않고 별도로 둡니다.
_BY_LENGTH_DESC: tuple[str, ...] = tuple(
    sorted(OPER_PREFIX_ORDER, key=len, reverse=True)
)

# 목록에 없는 접두사를 만났을 때의 rank. 알려진 스텝 뒤로 보내되 버리지는 않습니다 —
# 새 공정이 추가되었을 때 화면에서 사라지는 것이 가장 나쁜 실패이기 때문입니다.
UNKNOWN_RANK: int = len(OPER_PREFIX_ORDER)


def oper_prefix(desc: str) -> str | None:
    """``oper_det_desc`` 앞머리의 공정 접두사. 못 찾으면 None.

    longest-prefix 로 찾습니다 — "SNC2 CELL OPEN ETCH CLN CD" 는 SNC2 이고
    SNC 나 SN 이 아닙니다.
    """
    if not desc:
        return None
    text = desc.strip().upper()
    for prefix in _BY_LENGTH_DESC:
        if text.startswith(prefix):
            return prefix
    return None


def oper_rank(desc: str) -> int:
    """공정 접두사의 순서. 알 수 없으면 :data:`UNKNOWN_RANK`."""
    prefix = oper_prefix(desc)
    if prefix is None:
        return UNKNOWN_RANK
    return OPER_PREFIX_ORDER.index(prefix)


def sort_key(desc: str) -> tuple[int, str]:
    """정렬 키. 같은 접두사 안에서는 문자열순 — 같은 입력이면 같은 순서입니다.

    두 번째 요소가 있어야 rank 동률(같은 접두사, 알 수 없는 접두사끼리)이 입력
    순서에 좌우되지 않습니다.
    """
    return (oper_rank(desc), (desc or "").strip().upper())


def sort_oper_descs(descs: list[str]) -> list[str]:
    """스텝 이름을 공정 접두사 순서로 정렬합니다(중복 제거하지 않음)."""
    return sorted(descs, key=sort_key)


def unknown_prefixes(descs: list[str]) -> list[str]:
    """접두사를 못 찾은 스텝 이름들 — 목록 갱신이 필요한지 알려 줍니다.

    조용히 뒤로 밀어 두면 목록이 낡아도 아무도 모르므로, 어댑터/probe 가 이것을
    보고할 수 있게 별도 함수로 둡니다.
    """
    return sorted({d for d in descs if d and oper_prefix(d) is None})
