# Chat RAG 매뉴얼 연결 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매뉴얼 1종만 사무실 검색에 연결할 수 있도록, tool 노출을 provider 준비 상태로 구동하고 리랭크 순서·절단을 tracked 계약 절반으로 끌어올린다.

**Architecture:** `knowledge/data.py`에 `available_sources()`를 두어 agent runtime이 준비된 소스의 tool만 조립한다. 사무실 검색은 `office.py`가 사내 embedding/rerank API를 직접 호출하는 C2 방식이므로, `office_example.py`에 `_rerank()` OFFICE-TODO seam을 추가하고 "후보 초과 조회 → 리랭크 → limit 절단"의 순서와 상한은 tracked 계약 절반이 소유한다. `Evidence` 12필드, 네 개 공개 함수 시그니처, 오류 계약은 바뀌지 않는다.

**Tech Stack:** Python 3.14, Flask, pytest, LangChain agent runtime, OpenSearch(사무실), 사내 BGE-M3 / bge-reranker-v2-m3 API.

**Spec:** `docs/superpowers/specs/2026-08-07-chat-rag-manuals-design.md`

## Global Constraints

- `Evidence` 12필드, `AccessScope`, 네 개 `search_*` 공개 시그니처, `KnowledgeDenied`/`KnowledgeTimeout`/`KnowledgeUnavailable` 타입 계약은 **변경 금지**.
- 검색 결과 상한은 소스당 **5행**이며 애플리케이션이 정한다. 모델도 어댑터도 늘릴 수 없다.
- 자동 fallback 금지 — 실패를 mock이나 다른 소스로 대체하지 않는다.
- `knowledge/providers/office.py`는 gitignored이며 **이 계획에서 만들지 않는다.** 사무실에서 `cp office_example.py office.py` 후 seam만 구현한다.
- 접근 필터는 질의 단계에 적용한다. 검색 후 Python 필터링 금지.
- 테스트는 저장소 root에서 `.venv/bin/python -m pytest`로 실행한다(`-m`이 root를 `sys.path`에 올린다).
- 커밋은 **직접 편집한 파일만 명시 경로로** 스테이징한다. `git add -A`, `git add .`, `git commit -a` 금지.
- Markdown을 고치면 root에서 `npm run lint:md`를 돌린다.
- 실제 사내 hostname, index 이름, credential, 원문은 코드·테스트·커밋 어디에도 남기지 않는다.

## File Structure

| 파일 | 책임 | 변경 |
| --- | --- | --- |
| `back_dev_home/chat/config.py` | 환경 변수 → 검증된 설정값 | `get_knowledge_sources()`, `get_knowledge_candidate_pool()` 추가 |
| `back_dev_home/chat/knowledge/data.py` | provider 선택 + 소스 목록 | `available_sources()` 추가 |
| `back_dev_home/chat/runtime/providers/agent.py` | agent 조립 | tool 목록을 `available_sources()`로 구동, 정책 문구의 "four" 제거 |
| `back_dev_home/chat/knowledge/providers/office_example.py` | 사무실 어댑터 tracked 템플릿 | `_rerank()` seam + `_rank_hits()` 계약 절반 + 후보 풀 |
| `back_dev_home/chat/tests/test_knowledge.py` | knowledge 계약 홈 테스트 | `available_sources()` 테스트 추가 |
| `back_dev_home/chat/tests/test_runtime.py` | runtime 홈 테스트 | tool 노출 테스트 추가 |
| `back_dev_home/chat/tests/test_knowledge_office_template.py` | **신규** — 템플릿 계약 절반의 홈 커버리지 | 생성 |
| `back_dev_home/chat/tests/test_knowledge_office.py` | 사무실 copy 대상 fake-client 테스트 | 리랭크 반영해 갱신 |
| `docs/datatables/hitachi/chat_rag_contract.txt` | 인덱스 스키마의 진실 원천 | 갱신 |
| `back_dev_home/chat/MIGRATION.md` | 전환 가이드 | 갱신 |
| `back_dev_home/chat/knowledge/providers/mock.py` | 홈 mock | docstring 갱신 |

**신규 테스트 파일을 만드는 이유:** `test_knowledge_office.py`는 `pytest.importorskip("...providers.office")`로 시작하므로 집에서는 모듈 전체가 skip된다. 그 파일이 검증하는 대상은 `office_example.py`의 tracked 계약 절반인데, 결과적으로 계약 절반은 **집에서 커버리지가 0**이다. `_rank_hits()`를 거기 추가하면 사무실에 갈 때까지 한 번도 실행되지 않는다. 템플릿을 직접 import하는 홈 테스트가 이 구멍을 닫는다.

---

### Task 1: `available_sources()` — 준비된 소스 목록

**Files:**
- Modify: `back_dev_home/chat/config.py` (파일 끝, `get_rag_source_root()` 뒤)
- Modify: `back_dev_home/chat/knowledge/data.py:1-35`
- Test: `back_dev_home/chat/tests/test_knowledge.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: `back_dev_home.chat.config.get_knowledge_provider_name()` (기존)
- Produces:
  - `config.get_knowledge_sources() -> tuple[str, ...]`
  - `knowledge.data.available_sources() -> tuple[str, ...]` — 반환값은 항상 `("manual", "meeting", "email", "report")`의 부분집합이며 **그 정규 순서**를 따른다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`back_dev_home/chat/tests/test_knowledge.py` 끝에 추가한다.

```python
from back_dev_home.chat.knowledge.data import available_sources

_ALL = ("manual", "meeting", "email", "report")


def test_available_sources_is_every_source_at_home(monkeypatch):
    monkeypatch.delenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", raising=False)
    assert available_sources() == _ALL


def test_available_sources_defaults_to_manual_at_the_office(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.delenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", raising=False)
    assert available_sources() == ("manual",)


def test_available_sources_reads_the_office_source_list(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", "email, manual")
    assert available_sources() == ("manual", "email")


def test_available_sources_rejects_an_unknown_source(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", "manual,wiki")
    with pytest.raises(ValueError):
        available_sources()


def test_available_sources_rejects_an_empty_source_list(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", "  ,  ")
    with pytest.raises(ValueError):
        available_sources()


def test_available_sources_does_not_import_the_office_module(monkeypatch):
    """Listing sources must not require the gitignored office.py to exist."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.delenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", raising=False)
    assert available_sources() == ("manual",)
```

`pytest`가 이미 import되어 있지 않다면 파일 상단 import에 추가한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/chat/tests/test_knowledge.py -q`
Expected: FAIL — `ImportError: cannot import name 'available_sources'`

- [ ] **Step 3: config에 소스 목록 파서를 추가한다**

`back_dev_home/chat/config.py` 끝에 추가한다.

```python
KNOWLEDGE_SOURCES: tuple[str, ...] = ("manual", "meeting", "email", "report")


def get_knowledge_sources() -> tuple[str, ...]:
    """Office-side sources whose retrieval path is ready.

    A source is listed only once its index exists. Unlisted sources are not
    exposed to the model at all — returning an empty result instead would read
    as "there is nothing about this in the meeting notes", which is a claim we
    cannot make about a source we never indexed.
    """
    name = "SKEWNONO_CHAT_KNOWLEDGE_SOURCES"
    raw = os.environ.get(name, "manual")
    requested = {part.strip().lower() for part in raw.split(",") if part.strip()}
    if not requested:
        raise ValueError(f"{name} must name at least one knowledge source.")
    unknown = sorted(requested - set(KNOWLEDGE_SOURCES))
    if unknown:
        allowed = ", ".join(KNOWLEDGE_SOURCES)
        raise ValueError(
            f"{name} must be a comma-separated subset of: {allowed}. "
            f"Unknown: {', '.join(unknown)}."
        )
    return tuple(source for source in KNOWLEDGE_SOURCES if source in requested)
```

- [ ] **Step 4: `data.py`에 `available_sources()`를 추가한다**

`back_dev_home/chat/knowledge/data.py`의 import 블록을 수정한다.

```python
from back_dev_home.chat.config import (
    KNOWLEDGE_SOURCES,
    get_knowledge_provider_name,
    get_knowledge_sources,
)
```

`_provider()` 정의 **앞**에 추가한다.

```python
def available_sources() -> tuple[str, ...]:
    """Sources the selected provider can actually answer for.

    Mock answers for all four so the home session exercises the whole tool
    assembly path. Office answers only for the sources whose index exists.
    This never imports the provider module — listing what is ready must not
    depend on the gitignored office copy being present.
    """
    if get_knowledge_provider_name() != "office":
        return KNOWLEDGE_SOURCES
    return get_knowledge_sources()
```

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/chat/tests/test_knowledge.py -q`
Expected: PASS (신규 6건 포함, 기존 테스트도 그대로 통과)

- [ ] **Step 6: 커밋한다**

```bash
git add back_dev_home/chat/config.py back_dev_home/chat/knowledge/data.py back_dev_home/chat/tests/test_knowledge.py
git commit -m "feat(chat): list knowledge sources by provider readiness

available_sources()가 홈에서는 4종 전부를, 사무실에서는
SKEWNONO_CHAT_KNOWLEDGE_SOURCES(기본 manual)를 반환합니다. provider 모듈을
import하지 않으므로 gitignored office.py가 없어도 목록 조회가 됩니다."
```

---

### Task 2: agent runtime이 준비된 tool만 조립하도록

**Files:**
- Modify: `back_dev_home/chat/runtime/providers/agent.py:20-26`(import), `:44-52`(정책 문구), `:223-232`(tool 조립)
- Test: `back_dev_home/chat/tests/test_runtime.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: `knowledge.data.available_sources() -> tuple[str, ...]` (Task 1)
- Produces: `agent._build_tools(request: RuntimeRequest, evidence_budget: EvidenceBudget) -> list` — 준비된 소스의 tool만 정규 순서로 담은 list. 비면 `RuntimeUnavailable`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`back_dev_home/chat/tests/test_runtime.py` 끝에 추가한다. 이 파일은 이미
`make_request()`(무인자 헬퍼), `agent` 모듈, `knowledge_data`, `RuntimeUnavailable`,
`pytest`를 import하고 있으므로 **새로 추가할 import는 `EvidenceBudget` 하나뿐**이다.
기존 import 블록에 넣는다.

```python
from back_dev_home.chat.tools.evidence import EvidenceBudget
```

테스트는 파일 끝에 추가한다.

```python
def test_agent_exposes_every_tool_at_home(monkeypatch):
    monkeypatch.delenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", raising=False)
    tools = agent._build_tools(make_request(), EvidenceBudget.from_config())
    assert [tool.name for tool in tools] == [
        "search_manuals",
        "search_meeting_summaries",
        "search_emails",
        "search_reports",
    ]


def test_agent_hides_tools_for_sources_without_an_index(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", "manual")
    tools = agent._build_tools(make_request(), EvidenceBudget.from_config())
    assert [tool.name for tool in tools] == ["search_manuals"]


def test_agent_refuses_to_run_with_no_available_source(monkeypatch):
    monkeypatch.setattr(agent.knowledge_data, "available_sources", lambda: ())
    with pytest.raises(RuntimeUnavailable):
        agent._build_tools(make_request(), EvidenceBudget.from_config())


def test_application_policy_does_not_hardcode_the_tool_count():
    """The prompt must stay true when only one source is exposed."""
    assert "four" not in agent._APPLICATION_POLICY.lower()
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/chat/tests/test_runtime.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute '_build_tools'`

- [ ] **Step 3: `agent.py`의 import에 knowledge data를 추가한다**

`back_dev_home/chat/runtime/providers/agent.py`의 knowledge import 블록 바로 위에 추가한다.

```python
from back_dev_home.chat.knowledge import data as knowledge_data
```

- [ ] **Step 4: 정책 문구에서 "four"를 뺀다**

`_APPLICATION_POLICY`의 첫 줄을 바꾼다.

```python
_APPLICATION_POLICY = """Application-owned policy (higher priority than thread preferences):
- Use only the provided read-only retrieval tools.
```

나머지 줄은 그대로 둔다. 하드코딩된 "four"는 소스가 하나만 노출될 때 모델에게 거짓을 말하게 된다.

- [ ] **Step 5: `_build_tools()`를 추가한다**

`_build_system_prompt()` 정의 **앞**에 추가한다.

```python
_TOOL_BUILDERS = {
    "manual": build_search_manuals_tool,
    "meeting": build_search_meeting_summaries_tool,
    "email": build_search_emails_tool,
    "report": build_search_reports_tool,
}


def _build_tools(
    request: RuntimeRequest,
    evidence_budget: EvidenceBudget,
) -> list:
    """Expose one tool per source the provider can actually answer for.

    A source without an index is hidden rather than answered with an empty
    list: an empty list reads to the model as "nothing relevant exists in that
    source", which is a different claim from "that source is not searchable".
    """
    tools = [
        _TOOL_BUILDERS[source](request["access_scope"], evidence_budget)
        for source in knowledge_data.available_sources()
        if source in _TOOL_BUILDERS
    ]
    if not tools:
        raise RuntimeUnavailable("No chat knowledge source is available.")
    return tools
```

- [ ] **Step 6: `invoke()`가 그것을 쓰게 한다**

`invoke()` 안의 tool 리터럴 리스트(현재 `tools = [ ... 네 개 ... ]`)를 통째로 바꾼다.

```python
        evidence_budget = EvidenceBudget.from_config()
        tools = _build_tools(request, evidence_budget)
```

- [ ] **Step 7: 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/chat/tests/test_runtime.py -q`
Expected: PASS

- [ ] **Step 8: chat 전체 스위트를 돌린다**

Run: `.venv/bin/python -m pytest back_dev_home/chat -q`
Expected: PASS — 기존 agent 테스트가 tool 4개를 전제하고 있을 수 있으므로 여기서 걸러진다. 실패하면 그 테스트가 홈 기본값(4종)을 쓰도록 환경 변수를 비워 준다.

- [ ] **Step 9: 커밋한다**

```bash
git add back_dev_home/chat/runtime/providers/agent.py back_dev_home/chat/tests/test_runtime.py
git commit -m "feat(chat): build agent tools from available knowledge sources

준비되지 않은 소스는 빈 결과가 아니라 tool 자체를 노출하지 않습니다. 빈
결과는 모델에게 '그 소스에 관련 내용이 없다'로 읽히는데, 색인이 없는 것과
진짜 없는 것은 다른 진술입니다. 정책 프롬프트의 하드코딩된 'four'도 제거해
tool이 하나만 노출될 때 프롬프트가 거짓이 되지 않게 했습니다."
```

---

### Task 3: `_rerank()` seam과 계약 절반의 순서·절단

**Files:**
- Modify: `back_dev_home/chat/config.py` (파일 끝)
- Modify: `back_dev_home/chat/knowledge/providers/office_example.py:6-56`(docstring), `:58-68`(import), `:135-146`(seam 뒤), `:170-192`(`_search`)
- Create: `back_dev_home/chat/tests/test_knowledge_office_template.py`
- Modify: `back_dev_home/chat/tests/test_knowledge_office.py:123-160`

**Interfaces:**
- Consumes: 없음 (Task 1·2와 독립)
- Produces:
  - `config.get_knowledge_candidate_pool() -> int` — 5~50, 기본 24
  - `office_example._rerank(source_type: str, query: str, hits: list[Mapping[str, Any]]) -> list[float]` — OFFICE-TODO seam. 입력 hit과 **같은 길이·같은 순서**의 점수 list를 반환한다.
  - `office_example._rank_hits(source_type: str, query: str, hits: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]` — 계약 절반. 점수 내림차순으로 정렬(동점은 backend 순서 유지)하고 각 hit의 `score`를 리랭크 점수로 대체한다.

- [ ] **Step 1: 실패하는 홈 테스트를 쓴다**

`back_dev_home/chat/tests/test_knowledge_office_template.py`를 새로 만든다.

```python
"""Home coverage for the contract half of the office knowledge template.

``test_knowledge_office.py`` imports the gitignored ``providers.office`` copy
and therefore skips entirely at home — which leaves the tracked contract half
of ``office_example.py`` with no home coverage at all. The contract half is
byte-identical in both files, so exercising the template here pins the
behaviour the office copy inherits: candidate over-fetch, rerank ordering,
and the five-row cap that the application (not the adapter) owns.
"""

from __future__ import annotations

import pytest

from back_dev_home.chat.knowledge.contracts import KnowledgeUnavailable
from back_dev_home.chat.knowledge.providers import office_example as template


_SCOPE = {"user_id": "1234567", "groups": [], "fabs": []}


def _hit(source_id: str, score: float) -> dict:
    return {
        "source_id": source_id,
        "title": f"Manual {source_id}",
        "snippet": f"Synthetic snippet for {source_id}.",
        "revision": "R1",
        "occurred_at": None,
        "section": None,
        "page": 1,
        "region": None,
        "locator": f"manual:{source_id}#page=1",
        "figure_id": None,
        "score": score,
    }


@pytest.fixture
def seams(monkeypatch):
    """Patch the three OFFICE-TODO seams and record what they were given."""
    calls: dict = {}

    def fake_build_request(source_type, query, filters, scope, limit):
        calls["build_request_limit"] = limit
        return {"source_type": source_type, "query": query, "limit": limit}

    def fake_execute(source_type, request):
        return calls["hits"]

    def fake_rerank(source_type, query, hits):
        return calls["scores"]

    monkeypatch.setattr(template, "_build_request", fake_build_request)
    monkeypatch.setattr(template, "_execute", fake_execute)
    monkeypatch.setattr(template, "_rerank", fake_rerank)
    return calls


def test_candidate_pool_over_fetches_beyond_the_row_limit(seams, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES", "24")
    seams["hits"] = [_hit("a", 1.0)]
    seams["scores"] = [1.0]

    template.search_manuals("alarm reset", None, _SCOPE, 5)

    assert seams["build_request_limit"] == 24


def test_rerank_reorders_and_replaces_the_score(seams):
    seams["hits"] = [_hit("a", 9.0), _hit("b", 8.0), _hit("c", 7.0)]
    seams["scores"] = [0.1, 0.9, 0.5]

    rows = template.search_manuals("alarm reset", None, _SCOPE, 5)

    assert [row["source_id"] for row in rows] == ["b", "c", "a"]
    assert [row["score"] for row in rows] == [0.9, 0.5, 0.1]


def test_ties_keep_the_backend_order(seams):
    seams["hits"] = [_hit("a", 1.0), _hit("b", 1.0)]
    seams["scores"] = [0.5, 0.5]

    rows = template.search_manuals("alarm reset", None, _SCOPE, 5)

    assert [row["source_id"] for row in rows] == ["a", "b"]


def test_the_five_row_cap_survives_a_large_candidate_pool(seams):
    seams["hits"] = [_hit(str(index), 1.0) for index in range(24)]
    seams["scores"] = [float(index) for index in range(24)]

    rows = template.search_manuals("alarm reset", None, _SCOPE, 5)

    assert len(rows) == 5
    assert [row["source_id"] for row in rows] == ["23", "22", "21", "20", "19"]


def test_a_rerank_score_count_mismatch_is_unavailable(seams):
    seams["hits"] = [_hit("a", 1.0), _hit("b", 1.0)]
    seams["scores"] = [0.5]

    with pytest.raises(KnowledgeUnavailable):
        template.search_manuals("alarm reset", None, _SCOPE, 5)


def test_a_non_numeric_rerank_score_is_unavailable(seams):
    seams["hits"] = [_hit("a", 1.0)]
    seams["scores"] = ["high"]

    with pytest.raises(KnowledgeUnavailable):
        template.search_manuals("alarm reset", None, _SCOPE, 5)


def test_a_blank_query_never_reaches_the_backend(seams):
    seams["hits"] = [_hit("a", 1.0)]
    seams["scores"] = [1.0]

    assert template.search_manuals("   ", None, _SCOPE, 5) == []
    assert "build_request_limit" not in seams


def test_empty_results_stay_empty(seams):
    seams["hits"] = []
    seams["scores"] = []

    assert template.search_manuals("alarm reset", None, _SCOPE, 5) == []


def test_an_unimplemented_rerank_seam_fails_loudly(monkeypatch):
    """Skipping the rerank silently would degrade quality without an error."""
    monkeypatch.setattr(
        template,
        "_build_request",
        lambda source_type, query, filters, scope, limit: {},
    )
    monkeypatch.setattr(template, "_execute", lambda source_type, request: [_hit("a", 1.0)])

    with pytest.raises(KnowledgeUnavailable):
        template.search_manuals("alarm reset", None, _SCOPE, 5)
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/chat/tests/test_knowledge_office_template.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute '_rerank'`

- [ ] **Step 3: config에 후보 풀을 추가한다**

`back_dev_home/chat/config.py` 끝에 추가한다.

```python
def get_knowledge_candidate_pool() -> int:
    """How many candidates the office retrieval fetches before reranking.

    A cross-encoder reranker costs linearly in candidates, so this stays small.
    The application owns it — the adapter must not widen its own input.
    """
    raw = os.environ.get("SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES", "24")
    return min(max(int(raw), 5), 50)
```

- [ ] **Step 4: 템플릿에 `_rerank()` seam을 추가한다**

`back_dev_home/chat/knowledge/providers/office_example.py`의 import 블록에 config를 추가한다.

```python
from back_dev_home.chat import config
```

`_execute()` 정의 **뒤**, `_translate_error()` **앞**에 추가한다.

```python
def _rerank(
    source_type: str,
    query: str,
    hits: list[Mapping[str, Any]],
) -> list[float]:
    """Score each candidate hit against the query.

    OFFICE-TODO: call the approved in-house reranker and return ONE score per
    hit, in the SAME ORDER as ``hits``. Higher is better. The contract half
    below owns the sort and the row cap, so never reorder or truncate here.

    When reranking happens inside the search backend itself (the C1 path in
    the design spec), return each hit's existing ``score`` — that keeps this
    seam an identity ordering without special-casing the contract half.

    Do not silently skip the rerank when the service is down: raise, and let
    ``_search()`` route it through ``_translate_error()``. Returning the raw
    retrieval order would look like a working answer of measurably worse
    quality, which is the failure mode this contract exists to prevent.
    """
    raise KnowledgeUnavailable(
        "The chat knowledge office provider is not connected: _rerank() is "
        "not implemented."
    )
```

- [ ] **Step 5: 계약 절반에 `_rank_hits()`를 추가한다**

"do not edit below" 구분선 아래, `_search()` 정의 **앞**에 추가한다.

```python
def _rank_hits(
    source_type: str,
    query: str,
    hits: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Order candidates by rerank score. Contract half — the office copy must not edit.

    The sort is stable, so equal scores keep the backend's original order. The
    rerank score replaces the retrieval score in the emitted row because that
    is the number that actually decided the ranking.
    """
    if not hits:
        return []

    scores = _rerank(source_type, query, hits)
    if not isinstance(scores, (list, tuple)) or len(scores) != len(hits):
        raise KnowledgeUnavailable(
            "Office knowledge rerank returned a score count that does not "
            "match the hit count."
        )

    scored: list[tuple[Mapping[str, Any], float]] = []
    for hit, score in zip(hits, scores):
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise KnowledgeUnavailable(
                "Office knowledge rerank returned a non-numeric score."
            )
        scored.append(({**hit, "score": float(score)}, float(score)))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [hit for hit, _ in scored]
```

- [ ] **Step 6: `_search()`가 후보를 넉넉히 뽑고 리랭크하게 한다**

`_search()` 본문을 바꾼다.

```python
def _search(
    source_type: str,
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    if source_type not in _SOURCE_TYPES:
        raise KnowledgeUnavailable(f"Unknown chat knowledge source type: {source_type}")
    bounded = min(max(int(limit), 1), _RESULT_LIMIT)
    trimmed = query.strip()
    if not trimmed:
        return []

    candidates = max(bounded, config.get_knowledge_candidate_pool())
    request = _build_request(source_type, trimmed, filters, scope, candidates)
    try:
        raw_hits = _execute(source_type, request)
        ranked = _rank_hits(source_type, trimmed, raw_hits)
    except (KnowledgeDenied, KnowledgeTimeout, KnowledgeUnavailable):
        raise
    except Exception as error:  # noqa: BLE001 — everything becomes a typed error
        raise _translate_error(error) from error

    return [_to_evidence(source_type, hit) for hit in ranked[:bounded]]
```

- [ ] **Step 7: `_build_request` docstring의 limit 의미를 고친다**

`_build_request()` docstring 첫 줄 아래에 한 문단을 넣는다. `limit`이 최종 행 수가 아니라 후보 수라는 사실이 seam 구현자에게 전달되어야 한다.

```python
    ``limit`` is the CANDIDATE count to retrieve, not the number of rows the
    caller receives. The contract half reranks those candidates and truncates
    to the application's five-row cap afterwards, so fetch all of them.
```

- [ ] **Step 8: 모듈 docstring의 seam 목록을 갱신한다**

파일 상단 docstring에서 "The office implementation fills exactly three seams" 를 four로 고치고, `_execute` 항목 뒤에 추가한다.

```text
* ``_rerank(source_type, query, hits)`` — score the candidates with the
  approved in-house reranker and return one score per hit in the same order.
  The sort, the score substitution and the five-row cap belong to the contract
  half; never reorder or truncate inside this seam.
```

- [ ] **Step 9: 홈 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest back_dev_home/chat/tests/test_knowledge_office_template.py -q`
Expected: PASS (10건)

- [ ] **Step 10: 사무실 fake-client 테스트를 리랭크에 맞춘다**

`back_dev_home/chat/tests/test_knowledge_office.py`의 `test_limit_is_clamped_and_truncates_hits`와 `test_rank_order_is_preserved`는 `_rerank`가 없던 시절을 전제한다. 두 테스트에 `_rerank` monkeypatch를 더해 backend 순서를 그대로 유지하도록 만든다. 각 테스트의 `_execute` monkeypatch 바로 뒤에 추가한다.

```python
    monkeypatch.setattr(
        office,
        "_rerank",
        lambda source_type, query, hits: [
            float(len(hits) - index) for index in range(len(hits))
        ],
    )
```

`test_rank_order_is_preserved`는 이름을 `test_rerank_order_decides_the_final_order`로 바꾸고, docstring에 "backend 순위가 아니라 리랭크 점수가 최종 순서를 정한다"를 명시한다.

이 파일은 집에서 skip되므로 다음 단계에서 통과 여부를 확인할 수 없다. 사무실 검증 시점에 확인한다.

- [ ] **Step 11: chat 전체와 lint를 돌린다**

Run: `.venv/bin/python -m pytest back_dev_home/chat -q`
Expected: PASS

Run: `uv run --no-project ruff check back_dev_home/chat`
Expected: 오류 없음

- [ ] **Step 12: 커밋한다**

```bash
git add back_dev_home/chat/config.py back_dev_home/chat/knowledge/providers/office_example.py back_dev_home/chat/tests/test_knowledge_office_template.py back_dev_home/chat/tests/test_knowledge_office.py
git commit -m "feat(chat): own rerank ordering and the row cap in the contract half

사내 reranker를 쓰는 C2 경로에서 '후보 초과 조회 → 리랭크 → 5행 절단'이
gitignored office.py 안에서 벌어지면, '상한은 애플리케이션이 정한다'는 계약을
집에서 검증할 수 없는 파일이 지키게 됩니다. 순서와 절단을 tracked 계약
절반으로 올리고 office copy에는 _rerank() 호출 seam만 남겼습니다.

test_knowledge_office_template.py를 추가했습니다. 기존
test_knowledge_office.py는 gitignored office 모듈을 importorskip 하므로
집에서 통째로 skip되어, 계약 절반에 홈 커버리지가 없었습니다."
```

---

### Task 4: 문서 정정

**Files:**
- Modify: `docs/datatables/hitachi/chat_rag_contract.txt`
- Modify: `back_dev_home/chat/MIGRATION.md`
- Modify: `back_dev_home/chat/knowledge/providers/mock.py` (모듈 docstring만)

**Interfaces:**
- Consumes: Task 1~3의 실제 동작 (`available_sources()`, `_rerank()`, 후보 풀 환경 변수)
- Produces: 없음 (문서)

사무실 DB 사실은 datatables와 mock 양쪽에 남긴다는 저장소 규칙을 따른다. 출처 표기는 `office 확인 YYYY-MM-DD`, `user-confirmed`, `OFFICE-VERIFY` 중 하나를 반드시 붙인다.

- [ ] **Step 1: `chat_rag_contract.txt`를 갱신한다**

다음을 반영한다. 실제 사내 host·index·credential은 **적지 않는다.**

- "한국어와 영어를 항상 함께" 절: k-NN leg의 multilingual 여부가 `OFFICE-VERIFY`였던 것을 **BGE-M3 dense 사용 (user-confirmed 2026-08-06)** 로 바꾸고, lexical leg는 **Nori analyzer 확보 (user-confirmed 2026-08-06)** 로 확정한다.
- 검색 방식 절을 새로 넣는다: 2-leg hybrid(Nori BM25 ⊕ BGE-M3 dense), BGE-M3 sparse 미사용, `bge-reranker-v2-m3` 크로스인코더, 후보 20~30(`SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES`, 기본 24) → 상한 5행.
- 모델 호출 위치: **C2 — office.py가 사내 embedding/rerank API를 직접 호출 (user-confirmed 2026-08-07)**. ML Commons remote connector(C1)는 `plugins.ml_commons.trusted_connector_endpoints_regex`에 사내 host가 없어 보류 (office 확인 2026-08-07).
- `element_type` 절을 새로 넣는다: 인덱스 내부 전용이며 `Evidence`로 내보내지 않는다. 현재 어휘 11종과, 축이 네 개(형태·기능·안전 등급·도메인 개체) 섞여 있다는 진단, 그리고 `is_generated`·`alarm_codes` 권고를 적는다. `safety_level`은 `OFFICE-VERIFY`.
- 범위: 매뉴얼 1종 우선. 매뉴얼은 개정되지 않음 (user-confirmed 2026-08-06). 회의록·메일·리포트는 authoritative access resolver 선행.
- 관련 문서에 `docs/superpowers/specs/2026-08-07-chat-rag-manuals-design.md`를 추가한다.

- [ ] **Step 2: `MIGRATION.md`를 갱신한다**

- "현재 경계와 선택 matrix" 표에 `SKEWNONO_CHAT_KNOWLEDGE_SOURCES`(기본 `manual`)와 `SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES`(기본 24)를 추가한다.
- "Office knowledge provider 구현 계약" 절에 `_rerank()`를 네 번째 seam으로 추가하고, `limit`이 후보 수라는 점과 정렬·절단이 계약 절반 소유라는 점을 명시한다.
- 같은 절의 "네 개 공개 함수"는 그대로 두되, **소스별 준비 상태**로 전환한다는 문단을 넣는다 — 준비되지 않은 소스는 tool로 노출되지 않으며 빈 list를 반환하지 않는다.
- "Source와 index 준비 checklist"에서 매뉴얼 불변으로 무의미해진 항목(revision 우선순위·superseded 제외)에 "매뉴얼 범위에서는 해당 없음 (user-confirmed 2026-08-06)"를 단다. 항목을 지우지는 않는다 — 회의록·메일·리포트에서 다시 필요해진다.
- "검증 순서"에 `test_knowledge_office_template.py`를 홈 단계로 추가한다.

- [ ] **Step 3: `mock.py` 모듈 docstring을 갱신한다**

무엇을 대신하는지와 의도적으로 다른 지점을 적는다. 생성되는 값 자체는 바꾸지 않는다.

- 사무실은 Nori BM25 ⊕ BGE-M3 dense hybrid 뒤 크로스인코더 리랭크지만, mock은 fixture에 대한 토큰 집합 교집합이라 semantic 매칭이 없다.
- 그래서 `score`가 사무실의 리랭크 점수(float)와 달리 작은 정수다.
- fixture는 한국어와 영어를 의도적으로 섞는다 — 영어 전용 mock이면 사무실이 답하는 한국어 질문에 집에서 빈 결과가 나오고, 모든 홈 세션이 실제와 다른 검색 경로를 상대로 개발하게 된다.
- `figure_id`는 manual fixture 3건에만 있고 뒤에 실제 객체가 없는 불투명 토큰이다. mock은 사무실의 진짜 figure id를 알 수 없으므로 흉내내지 않는다.
- mock은 네 소스를 모두 답한다. 사무실이 `manual` 하나만 노출하더라도 홈에서는 tool 조립 경로 전체를 검증하기 위해서다.

- [ ] **Step 4: lint와 전체 스위트를 돌린다**

Run: `npm run lint:md`
Expected: 0 error(s)

Run: `.venv/bin/python -m pytest tests back_dev_home -q`
Expected: PASS

- [ ] **Step 5: 커밋한다**

```bash
git add docs/datatables/hitachi/chat_rag_contract.txt back_dev_home/chat/MIGRATION.md back_dev_home/chat/knowledge/providers/mock.py
git commit -m "docs(chat): record the confirmed RAG retrieval stack

BGE-M3 dense + Nori BM25 2-leg hybrid, bge-reranker-v2-m3, 그리고 모델을
office.py가 직접 호출하는 C2 경로를 datatables와 MIGRATION.md에 반영했습니다.
multilingual 여부의 OFFICE-VERIFY가 닫혔습니다.

element_type은 인덱스 내부 전용으로 명시했습니다 — Evidence 필드로 착각해
프론트로 끌어올리면 어휘 교정이 5곳 동시 변경이 됩니다.

사무실 사실은 datatables와 mock 양쪽에 남긴다는 규칙에 따라 mock.py
docstring도 함께 갱신했습니다."
```

---

## 검증 (전체 완료 후)

- [ ] `.venv/bin/python -m pytest tests back_dev_home -q` — 전체 스위트
- [ ] `uv run --no-project ruff check back_dev_home/chat`
- [ ] `npm run lint:md`
- [ ] `git diff --check`
- [ ] `front-dev-home/`에서 `npm test && npm run typecheck && npm run lint && npm run build` — 이 계획은 프론트를 건드리지 않지만 `Evidence`가 프론트 타입과 연결되어 있으므로 회귀를 확인한다.

### 홈 agent loop 확인 (OpenRouter, 수동)

Tool을 넷에서 하나로 줄이는 것은 프롬프트 표면을 바꾸는 변화이며, 단위 테스트로는
"tool 목록이 맞다"까지만 확인된다. **실제 tool-calling 모델이 축소된 목록으로도
정상 응답하는지**는 사람이 한 번 봐야 한다. Retrieval은 여전히 mock이므로 이 확인은
검색 품질이 아니라 agent loop의 건전성만 대상으로 한다.

`guard.py`의 egress blocklist는 office mode에서만 작동하므로 집에서는 OpenRouter가
열려 있다. 사무실 데이터는 필요하지 않다.

- [ ] `CHAT_BASE_URL`/`CHAT_API_KEY`를 OpenRouter로, `CHAT_MODELS`에 `supports_tools`가
  `true`인 모델을 하나 둔다. `SKEWNONO_CHAT_RUNTIME=agent`,
  `SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=mock`(4종 노출)으로 Flask를 띄우고 `/chat`에서
  질문 한 건을 보낸다. 답변에 인용이 붙고 tool trace가 남는지 본다.
- [ ] 같은 프로세스에서 `SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office`,
  `SKEWNONO_CHAT_KNOWLEDGE_SOURCES=manual`로 바꾸면 `search_manuals`만 노출되지만
  office adapter가 없어 호출 시 `503`이 된다. Tool **목록**만 보려면
  `available_sources()`를 직접 호출하거나 `_build_tools()` 테스트로 대신한다. 즉 이
  단계에서 모델 행동까지 보려면 사무실이 필요하다 — 집에서는 4종 경로까지가 한계다.
- [ ] 관찰 결과를 `back_dev_home/chat/MIGRATION.md`의 검증 순서에 한 줄로 남긴다.
  Query 본문, 답변, credential은 남기지 않는다.

**OpenRouter가 덮지 못하는 것:** embedding과 rerank. OpenRouter가 구현하는 것은
`/completions`와 `/chat/completions`이며 embedding 엔드포인트가 없다. 따라서 BGE-M3
벡터, 크로스인코더 점수, `_rerank()`의 실제 동작은 사무실에서만 확인된다. 이것이
Task 3의 홈 테스트가 seam을 monkeypatch하는 이유다 — 계약 절반의 순서·절단은 집에서
검증하고, 모델 호출 자체는 사무실 smoke로 미룬다.

## 이 계획의 범위 밖

- `knowledge/providers/office.py` 작성 — 사무실에서 `cp office_example.py office.py` 후 네 seam(`_config`, `_build_request`, `_execute`, `_rerank`)과 `_translate_error()`만 구현한다.
- `test_knowledge_office.py`의 `OFFICE-TODO` skip test 세 건 채우기 — 사무실 작업.
- Figure serving endpoint.
- 회의록·메일·리포트, authoritative access resolver.
- `element_type` 축 분리 확정 (스펙 5.1은 권고 상태 유지).
- 왕복 3회 실측과 그에 따른 deadline 재조정 — 사무실 smoke 이후.
