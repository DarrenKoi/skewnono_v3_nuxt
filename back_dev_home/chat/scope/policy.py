"""Which questions this chat answers — one marker policy, everywhere.

**Deny-list, not allow-list (2026-09-01).** A query is in scope unless it
carries an explicitly off-topic marker. The earlier rule was the inverse — a
domain marker was REQUIRED — and it refused every question phrased in terms
the list had never heard of: "MDC에 대해서 알려줘" was turned away because
``mdc`` is not in the vocabulary, which is precisely the question the manuals
can answer and the user cannot rephrase without already knowing the answer.
An allow-list of domain words can only contain the jargon we thought of first,
so it fails hardest on exactly the unfamiliar term someone is asking about.

The real filter is retrieval, not this function: a genuinely off-domain
question finds no evidence and gets an honest "no evidence found", which costs
one search. A false refusal costs the user the answer. So the in-scope markers
below no longer gate anything — they survive to salvage the supported clause
out of a MIXED query, and as the record of what the RAG side listed.

**No ``mixed`` state (2026-09-01).** A query that carried both a work topic
and an off-topic one used to be split: a regex cut it at punctuation or a
conjunction, the supported clauses were rejoined, and THAT was sent to the
RAG. When the query had no splittable boundary the fallback forwarded the
matched marker words alone — ``"계측 알람"`` — which is not a question anyone
asked, and it went out under a notice telling the user we had answered them.
Such a query is now just ``in_scope``: the work part gets answered from
evidence and the off-topic part finds none. The markers below survive for the
one thing they still decide — whether an off-topic query has any work in it
at all.

The vocabulary is the RAG side's domain markers in Korean and English
(handoff ``docs/datatables/chat/chat_office_adapter_handoff.txt``, 2026-08-27),
and it is the same at home and at the office: scope is a product decision
about what SKEWNONO chat is for, not a fact about which machine is running.
There was a mock/office split here; it only ever meant "home refuses Korean
questions the office accepts", which is a difference no test wanted.

A marker policy rather than a model call, per the same handoff: the domain is
narrow and a false refusal costs more than letting a borderline question reach
retrieval, where empty evidence already produces an honest "no evidence found".

Every English marker has its Korean counterpart because users mix the two in
one question ("얼라인 alarm 리셋") — an English-only list would refuse Korean
questions the index answers fine. ``unsafe`` covers instructions to ignore
access control, reveal credentials or bypass permissions; that decision wins
over any in-scope marker beside it.

Substring matching on the lowercased query, deliberately: it errs toward
``in_scope``, and answering a borderline work question beats refusing it.
"""

from __future__ import annotations


from back_dev_home.chat.scope.contracts import ScopeDecision

def _contains_any(query: str, markers: tuple[str, ...]) -> bool:
    return any(marker in query for marker in markers)


def _decide(
    query: str,
    *,
    in_scope: tuple[str, ...],
    out_of_scope: tuple[str, ...],
    unsafe: tuple[str, ...],
) -> ScopeDecision:
    normalized = query.lower()
    if _contains_any(normalized, unsafe):
        return {"status": "unsafe", "reason_code": "unsafe_instruction"}

    has_in_scope = _contains_any(normalized, in_scope)
    has_out_of_scope = _contains_any(normalized, out_of_scope)
    if not has_out_of_scope:
        # Nothing off-topic in it — pass, whether or not a domain marker
        # matched. The two reason codes keep that distinction visible in the
        # messages table, so how often the permissive default carries a turn
        # is a query rather than a guess.
        return {
            "status": "in_scope",
            "reason_code": (
                "supported_domain" if has_in_scope else "no_marker_default_allow"
            ),
        }
    if has_in_scope:
        # Both topics in one query. Ask it as the user wrote it: retrieval
        # answers the work half and finds nothing for the rest, which is the
        # honest outcome. Its own reason code, so "how often does this happen"
        # stays a query against the messages table rather than a guess.
        return {"status": "in_scope", "reason_code": "off_topic_clause_ignored"}
    return {"status": "out_of_scope", "reason_code": "unsupported_domain"}


_UNSAFE_MARKERS = (
    "ignore access", "reveal api key", "reveal the api key", "bypass permission",
    "권한 우회", "권한을 우회", "접근 제어 무시", "접근 권한 무시", "api 키 보여",
    "api 키 알려", "비밀번호 알려", "인증 우회",
)

# The handoff's marker list (EN), each paired with its Korean counterpart.
# Keep the handoff set intact — test_vocabulary_covers_every_handoff_marker
# pins it.
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
    """Classify one chat query against the domain vocabulary."""
    return _decide(
        query,
        in_scope=_IN_SCOPE_MARKERS,
        out_of_scope=_OUT_OF_SCOPE_MARKERS,
        unsafe=_UNSAFE_MARKERS,
    )
