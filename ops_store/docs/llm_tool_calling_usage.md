# LLM tool calling로 ops_store 쓰기

이 문서는 **LLM 기반 챗봇이 `ops_store`(OpenSearch)를 검색하게 하려면 무엇을
준비해야 하는가**를 정리한다. 코드를 바로 작성하기 전에 개념과 준비물을 먼저
소화하기 위한 참고용 문서다. (구현 예제는 의사코드 수준이며, 실제 모듈은 나중에
`ops_store` 컨벤션에 맞춰 작성한다.)

전제: **로컬/오픈 모델 + in-app tool calling**. 대부분의 로컬 서버(Ollama,
vLLM, llama.cpp)는 OpenAI 호환 `/v1/chat/completions`에 `tools` 파라미터를
지원하므로, 벤더 SDK 없이 loop 하나로 모델을 교체할 수 있다.

---

## 1. 핵심 개념: tool calling은 무엇인가

LLM이 직접 OpenSearch에 접속하는 게 아니다. LLM은 **"어떤 함수를 어떤 인자로
부를지"만 JSON으로 내뱉고**, 실제 실행은 우리 Python 코드가 한다.

```
사용자 질문
   → LLM이 tool_call 방출:  latest_measurement(tool_id="TOOL123")
   → 우리 코드가 OSSearch 실행
   → 결과를 LLM에 다시 전달
   → LLM이 자연어 답변 작성
```

LLM은 **쿼리 DSL을 직접 쓰지 않는다.** 함수 이름과 파라미터만 고른다. 그래서
hallucinated field name이나 비싼 쿼리가 원천적으로 막힌다. tool schema 자체가
guardrail 역할을 한다.

### 3층 구조 — 가장 중요한 그림

```
OpenSearch cluster        ← 모든 걸 할 수 있음
   ↓
ops_store / OSSearch      ← 우리 Python wrapper (이것도 넓음)
   ↓
chatbot tools             ← 사용자가 실제로 묻는 질문 모양만   ← 작게 유지
```

맨 아래 층(모델이 보는 tool 목록)이 셋 중 가장 **작아야** 한다. `OSSearch`의
모든 메서드를 tool로 노출하지 않는다. 자세한 이유는 7장.

---

## 2. 준비물 체크리스트

LLM이 `ops_store`를 쓰게 하려면 아래 6가지가 필요하다.

| # | 준비물 | 무엇 | 이미 있나? |
|---|--------|------|-----------|
| 1 | **tool 정의** | 각 검색 패턴을 JSON schema로 기술 | 새로 작성 |
| 2 | **dispatch 함수** | tool 이름 → `OSSearch` 메서드 연결 | 새로 작성 (glue) |
| 3 | **tool-calling loop** | 모델 호출 ↔ tool 실행 반복 | 새로 작성 |
| 4 | **LLM endpoint** | OpenAI 호환 로컬 서버 | 외부 (Ollama/vLLM/…) |
| 5 | **result projection** | hit을 필요한 필드만 남기고 축소 | 새로 작성 (helper) |
| 6 | **guardrails** | max iteration, result size cap | loop 안에 |

**실제 검색 능력(1~3에서 호출하는 OSSearch 메서드)은 이미 다 있다.** 새로
만드는 건 "자연어 → 어떤 메서드 + 어떤 인자" 번역 층뿐이다.

---

## 3. tool 정의 (준비물 1)

tool은 **API 메서드가 아니라 "질문 모양"** 단위로 만든다. 챗봇이 받을 실제
질문 두 개:

1. "특정 `tool_id`의 최신 measurement" → `latest_measurement`
2. "특정 `tool_id`의 hardware BM/PM history" → `bm_pm_history`

"최신 하나"와 "기간 history"는 OpenSearch에서 정반대를 원한다 — 전자는
`size: 1` + sort desc, 후자는 `size: N` + time-range. 이 차이를 **tool 두 개로
분리**하면 작은 로컬 모델도 헷갈리지 않는다. tool 이름이 의도를 담기 때문이다.
(하나의 tool에 `mode` 플래그를 두는 방식은 피한다.)

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "latest_measurement",
            "description": (
                "주어진 tool_id의 가장 최근 measurement 한 건을 반환한다. "
                "'최신', '마지막', 'latest' 류 질문에 사용."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_id": {"type": "string",
                                "description": "장비 ID, 예: TOOL123"},
                },
                "required": ["tool_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bm_pm_history",
            "description": (
                "주어진 tool_id의 BM/PM 유지보수 이력 전체를 기간 단위로 반환한다. "
                "hardware별 필터는 하지 않고 전체를 돌려주며, 모델이 답변에서 "
                "원하는 hardware만 골라 요약한다. 'history', '이력', '언제 PM' 류 질문에 사용."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_id": {"type": "string"},
                    "days": {"type": "integer", "default": 90,
                             "description": "오늘 기준 며칠 전까지"},
                },
                "required": ["tool_id"],
            },
        },
    },
]
```

`description`은 모델이 tool을 고르는 **유일한 단서**다. "언제 쓰는지"를 한국어
질문 예시와 함께 명확히 적는다.

---

## 4. dispatch 함수 (준비물 2) — 유일한 glue 코드

tool 이름을 받아 실제 `OSSearch` 메서드로 연결한다. 두 tool 모두 이미 있는
one-liner 메서드에 매핑된다.

```python
from ops_store import OSSearch

def run_tool(search: OSSearch, name: str, args: dict) -> dict:
    if name == "latest_measurement":
        df = search.latest_match_dataframe(
            field="tool_id.keyword",          # exact match는 .keyword 필수
            keyword=args["tool_id"],
            time_field="timestamp",
            index="<measurement_index>",
            size=1,
        )
        return _slim(df)

    if name == "bm_pm_history":
        df = search.range_dataframe(
            query={"term": {"tool_id.keyword": args["tool_id"]}},
            time_field="timestamp",
            days=args.get("days", 90),
            index="<maintenance_index>",
            size=500,                          # cap (준비물 6)
        )
        return _slim(df)

    raise ValueError(f"unknown tool: {name}")
```

### `.keyword` 함정 (반드시 기억)

`tool_id`처럼 정확히 일치시켜야 하는 값은 analyzed 필드에 `match`를 쓰면
tokenize되어 오탐이 난다. 반드시 `tool_id.keyword` 서브필드에 `term`/`match`로
정확 매칭한다. (예전에 exact matching이 안 되던 문제의 실제 원인.)

---

## 5. result projection (준비물 5) — 품질의 핵심

검색 결과 전체 `_source`를 모델에 그대로 넘기면 안 된다. context window를
날리고, 필요 없는 필드 토큰까지 비용을 낸다. **필요한 몇 개 필드만 남긴다.**

```python
KEEP = ["tool_id", "timestamp", "recipe", "value", "event_type", "hardware"]

def _slim(df, keep=KEEP, max_rows=50):
    cols = [c for c in keep if c in df.columns]
    rows = df[cols].head(max_rows).to_dict("records")
    return {"rows": rows, "row_count": len(df)}
```

깔끔하고 작은 row를 주면 모델 답변 품질이 올라간다. 챗봇 품질의 대부분이 여기서
결정된다.

---

## 6. tool-calling loop (준비물 3·4·6)

```python
import requests

def chat(user_msg: str, search: OSSearch,
         endpoint="http://localhost:11434/v1/chat/completions",
         model="qwen2.5", max_iters=5) -> str:
    messages = [
        {"role": "system", "content":
            "너는 장비 measurement/유지보수 데이터를 OpenSearch에서 조회해 "
            "답하는 어시스턴트다. 데이터가 필요하면 제공된 tool을 사용해라."},
        {"role": "user", "content": user_msg},
    ]
    for _ in range(max_iters):                 # guardrail: 무한 loop 방지
        resp = requests.post(endpoint, json={
            "model": model, "messages": messages, "tools": TOOLS,
        }).json()
        msg = resp["choices"][0]["message"]
        messages.append(msg)

        calls = msg.get("tool_calls")
        if not calls:
            return msg["content"]              # tool 없음 → 최종 답변

        for call in calls:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"])
            result = run_tool(search, name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })
    return "tool 호출 한도를 초과했습니다."     # guardrail 도달
```

loop는 단순하다: 모델 호출 → tool_calls 있으면 실행 후 결과 append하고 반복,
없으면 그게 최종 답변.

### guardrails — 여기서만 "preemptive" 방어가 정당하다

`ops_store` 컨벤션은 보통 caller를 신뢰하지만, 여기서 caller는 **확률적 모델**
이다. 두 가지 cap은 정당하다:

- **max_iters** (예: 5): 혼란에 빠진 모델이 무한 호출하는 것 방지
- **result size cap** (`_slim`의 `max_rows`, `range_dataframe`의 `size`):
  한 번의 검색이 수천 row를 context에 쏟아붓는 것 방지

---

## 7. "ops 함수를 다 준비해야 하나?" → 아니오

가장 흔한 실수: "챗봇이 뭐든 하게 모든 기능을 노출하자." 작은 로컬 모델에는
**tool이 늘수록 더 멍청해진다.** tool 선택은 분류 문제라서, tool 2개는 거의
명확하지만 15개면 자주 틀린 tool을 고르거나 인자를 hallucinate한다.

원칙: **tool = 메서드가 아니라 use case.**

> 새 tool은 "지금 tool로 답이 안 되는 실제 질문"이 나왔을 때만 추가한다. 미리
> 만들지 않는다. (demand-driven, not capability-driven)

진행 방식:
1. 찾아낸 2개 tool로 출시
2. 사람들이 뭘 묻는지 관찰
3. 처음으로 빈/틀린 답이 나온 질문이 곧 tool #3이 무엇이고 어떤 필드가
   필요한지 정확히 알려준다

### 단 하나의 escape hatch (원하면)

긴 꼬리가 걱정되면 specific tool 2개 + generic fallback 1개:

```
search_ops(index, query_text, days=None, size=5)   # 일반 lexical 검색
```

그래도 총 3개. 단, 2-tool 버전이 실제로 부족함이 보일 때만 추가한다.
`OSSearch`의 나머지 능력(knn, hybrid, aggregate, reindex…)은 Python 코드에
그대로 살아 있다 — 단지 모델에게 버튼을 안 줄 뿐이다.

---

## 8. 빌드 전 확정할 것: 실제 필드 이름

위 코드의 `<measurement_index>`, `tool_id.keyword`, `event_type`, `hardware`,
`timestamp`는 전부 placeholder다. **이름이 틀리면 조용히 빈 결과**가 나오므로
이게 가장 중요하다. 빌드 전 4가지 확정:

1. **인덱스 이름** — measurement 인덱스와 BM/PM 유지보수 인덱스 (보통 별도 2개)
2. **key 필드** — `tool_id`가 맞나? `tool_id.keyword` 서브필드 존재하나?
3. **BM/PM 인덱스 모양** — 이벤트를 기술하는 필드들. `event_type`이 `"BM"`/`"PM"`
   값인가, 아니면 인덱스가 분리돼 있나? hardware 필드 이름은? (`hardware`/`part`/`module`)
4. **timestamp** — 두 인덱스 모두 plain `timestamp`, KST인가? (컨벤션상 yes)

이 4가지가 확정되면 두 tool은 사실상 빈칸 채우기다.

---

## 9. 첫 cut 추천

```
로컬 OpenAI 호환 endpoint
  + tool 2개: latest_measurement, bm_pm_history
  + 필드 이름은 tool description / dispatch에 하드코딩
  + max_iters 5, projection ~6개 필드
  → standalone 모듈 1개 + unittest (client mock + HTTP endpoint mock)
```

embedding 모델 없음, 새 인프라 없음. 먼저 loop가 도는 걸 증명하고, 부족함이
느껴지는 지점에서 kNN이나 `describe_index` tool을 추가한다.

### 나중에 자랄 여지

- **스키마를 모델이 학습**: `describe` tool(`OSIndex.describe()` 활용) 또는
  system prompt에 mapping 주입 → 인덱스가 자주 바뀔 때
- **의미 검색**: `OSSearch.knn` / `hybrid` tool → 단, 데이터가 이미 vector화돼
  있고 embedding 모델이 있을 때만
- **웹 서비스로**: Flask 엔드포인트로 노출 시, blocking LLM 호출은 `ftp_handler`
  의 `BackgroundJobs`처럼 request 스레드 밖으로 빼는 패턴 필요

---

## 관련 문서

- `search_all_usage.md`: `OSSearch` DataFrame 조회 메서드 전체 (dispatch에서 호출)
- `with_dag_usage.md`: OpenSearch 연결(`OPENSEARCH_*`), index/search 기본
