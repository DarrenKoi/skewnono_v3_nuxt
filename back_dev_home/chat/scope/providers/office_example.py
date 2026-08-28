# TEMPLATE — copy to office.py at the office (`cp office_example.py office.py`).
# office.py is gitignored; this file is the tracked implementation, COMPLETE as
# of 2026-08-28 — the copy needs no edits. Selected by
# SKEWNONO_CHAT_SCOPE_PROVIDER=office; copying alone changes nothing.
"""Office scope classifier: the RAG side's domain markers, Korean and English.

A marker policy rather than a model call, as specified in the RAG handoff
(``docs/datatables/chat/chat_office_adapter_handoff.txt``, 2026-08-27): the
domain is narrow and the cost of a false refusal is higher than the cost of
letting a borderline question reach retrieval, where empty evidence already
produces an honest "no evidence found". The engine is shared with the mock
(``scope/keyword_policy.py``); only the vocabulary differs.

Every English marker has its Korean counterpart because users mix the two in
one question ("얼라인 alarm 리셋") — an English-only list would refuse Korean
questions the index answers fine.

``unsafe`` covers instructions to ignore access control, reveal credentials
or bypass permissions; the decision is ``unsafe`` regardless of any in-scope
marker beside it.
"""

from __future__ import annotations

from back_dev_home.chat.scope import keyword_policy
from back_dev_home.chat.scope.contracts import ScopeDecision


_UNSAFE_MARKERS = (
    "ignore access", "reveal api key", "reveal the api key", "bypass permission",
    "권한 우회", "권한을 우회", "접근 제어 무시", "접근 권한 무시", "api 키 보여",
    "api 키 알려", "비밀번호 알려", "인증 우회",
)

# The handoff's marker list (EN) plus the mock's source words, each paired
# with its Korean counterpart. Keep the handoff set intact —
# test_office_vocabulary_covers_every_handoff_marker pins it.
_IN_SCOPE_MARKERS = (
    # equipment / domain
    "ebeam", "e-beam", "이빔", "전자빔", "metrology", "계측", "measurement", "측정",
    "tool", "장비", "alarm", "알람", "manual", "매뉴얼", "recipe", "레시피",
    "error", "에러", "오류", "cd-sem", "cdsem", "sem", "calibration", "캘리브레이션",
    "교정", "optics", "광학", "vacuum", "진공", "stage", "스테이지", "wafer", "웨이퍼",
    "idp", "amp", "hitachi", "히타치", "gt2000", "cg6300", "align", "얼라인", "정렬",
    "beam", "빔", "focus", "초점", "포커스", "magnification", "배율",
    # the other knowledge sources
    "meeting", "회의", "email", "메일", "report", "보고서", "리포트", "tat",
)

_OUT_OF_SCOPE_MARKERS = (
    "movie", "영화", "shopping", "쇼핑", "dating", "데이트", "game", "게임",
    "주식", "stock tip", "날씨", "weather", "맛집", "restaurant", "여행", "travel",
    "로또", "lottery",
)


def classify(query: str) -> ScopeDecision:
    return keyword_policy.classify(
        query,
        in_scope=_IN_SCOPE_MARKERS,
        out_of_scope=_OUT_OF_SCOPE_MARKERS,
        unsafe=_UNSAFE_MARKERS,
    )
