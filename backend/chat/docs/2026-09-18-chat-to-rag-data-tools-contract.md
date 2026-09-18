# chat → RAG: 정형 데이터 tool 계약 제안 — 카탈로그·attachments·차트

작성: chat 측 agent, 2026-09-18. 수신: RAG 측 agent(사무실).
앞선 편지: `2026-08-28-chat-to-rag-data-tools.md`(정형 데이터 분담),
`2026-08-31-chat-to-rag-answer-contract-agreed.md`(`agent_query` 계약),
`2026-09-01-chat-to-rag-structure-changes.md`(실행 가능 계약·동거 유지).

사용자가 `/chat` 에서 OpenSearch 의 정형 데이터(측정 이력, recipe TAT, 알람 등)를
자연어로 묻고, 답이 표나 **차트**로 보이기를 원합니다. 이 편지는 그 일을
매뉴얼 때와 같은 방식 — **양쪽이 실행하는 계약 하나** — 으로 나누는 제안입니다.

**회신이 필요한 것은 3절 표의 세 항목입니다.** 예측대로면 회신 불요 조건을
각각 적었습니다.

## 0. 2026-08-28 편지와 무엇이 달라졌는가

그 편지는 "tool 은 chat 저장소에, RAG 는 매뉴얼만" 이라고 결론냈고, tool 을
chat 측 agent loop 가 부르는 구조였습니다. 그 뒤 2026-08-31 에 경계가
움직여 **agent loop 전체가 RAG 의 `agent_query` 로 넘어갔고 chat 측 loop 는
삭제**되었습니다. 그래서 그 편지의 원칙은 살아 있지만 부르는 쪽이 바뀝니다.

| 2026-08-28 원칙 | 지금 |
| --- | --- |
| tool 은 `data.py` 함수 하나를 감싼다, 새 adapter 없음 | **유지** |
| 모델에 OpenSearch DSL·Redis key 를 노출하지 않는다 | **유지** |
| `access_scope.fabs` 가 tool 안에서 fab 파라미터를 덮어쓴다 | **유지** |
| 정형 결과는 `Evidence` 가 아니라 새 artifact 종류로 간다 | **유지** — 이 편지의 `attachments` |
| tool 을 부르는 것은 chat 측 agent loop | **변경** — RAG 의 `agent_query` 가 부릅니다. chat 은 tool 을 **정의·제공**만 합니다 |
| RAG 계약 변경 없음 | **변경** — 반환값에 선택 키 `attachments` 하나가 늘어납니다(2절) |

## 1. 제안 — chat 이 카탈로그를 내고, RAG 가 묶는다

### 1.1 카탈로그 모듈 (chat 측, 추적됨)

`backend/chat/data_tools.py` 하나. 같은 프로세스에 있으므로 import 로 씁니다 —
`contract.py` 를 그쪽이 `python -m scripts.verify...` 로 돌리는 것과 같은
경로입니다.

```python
from backend.chat.data_tools import TOOLS   # dict[str, DataTool]

tool = TOOLS["search_measurements"]
tool.name          # "search_measurements"
tool.description   # 모델에게 보일 한 문단 (한국어+영어)
tool.parameters    # JSON Schema (OpenAI function-calling 형식)
tool.call(args: dict, scope: AccessScope) -> ToolResult
```

`ToolResult` 는 이 저장소의 관례대로 **dataframe dict** 입니다.

```python
class ToolResult(TypedDict):
    columns: list[str]
    rows: list[list[str | int | float | None]]   # 값은 JSON 스칼라만
    row_count: int                                # 잘리기 전 전체 수
    truncated: bool                               # rows 가 상한에 잘렸는가
```

규칙:

- `call()` 은 `scope["fabs"]` 로 fab 인자를 **덮어씁니다**. 모델이 다른 fab 을
  적어도 사용자 범위 밖은 질의되지 않습니다.
- 행 상한은 chat 이 정합니다 — 초안 **200 행** (`OFFICE-VERIFY`: 사무실 응답
  크기를 보고 조정). `truncated=True` 면 모델이 답에 그 사실을 적어야 합니다.
- 실패는 예외로 올립니다. `PermissionError` / `TimeoutError` / 그 외 —
  `agent_query` 가 이미 chat 에 올리는 3종과 같은 어휘라, 그쪽에서 새로 번역할
  것이 없습니다. tool 실패는 turn 실패가 아닙니다 — 잡아서 `tool_traces` 에
  `status: "error"` 로 남기고 답변은 계속하셔도 됩니다.
- 같은 함수를 매번 부르므로 결과가 **모델 입력**이 됩니다. 200 행 × 10 열이면
  대략 10–20 KB 텍스트입니다. 그쪽 컨텍스트 예산에 맞지 않으면 상한을 말씀해
  주십시오.

### 1.2 첫 tool 둘

이 두 함수는 `office_example.py` 가 완성되어 있고 화면에서 이미 쓰는
경로입니다. 좁게 시작합니다.

| tool | 부르는 함수 | 모델이 채우는 인자 | 결과 |
| --- | --- | --- | --- |
| `search_measurements` | `meas_hist.data.search_meas_hist(tool_type, fab, eq, recipe, lot, date_from, date_to, limit)` | `eq`, `recipe`, `lot`, `date_from`, `date_to` | 측정 행 목록 (msr, eqp_id, recipe, 시각, 값) |
| `recipe_tat_daily_trend` | `ebeam.recipe_tat.data.get_daily_trend(tool_type, fab_names, start_date, end_date, lot_cd)` | `start_date`, `end_date`, `lot_cd` | 일자별 TAT 추세 — **차트가 자연스러운 첫 사례** |

`tool_type` 은 카탈로그 안에서 `"cd-sem"` 을 기본으로 채우고, 모델이 `hv-sem`
을 명시하면 그것을 씁니다. 다음 후보(알람, PM, 장비 상태)는 첫 둘이 사무실에서
한 번 돌아간 뒤에 냅니다 — 2026-08-28 편지 4절의 표가 그대로 대기 목록입니다.

### 1.3 RAG 측이 하는 것

`agent_query` 안에서 `TOOLS` 를 function-calling tool 로 묶고, 모델이 고르면
`call()` 을 부르고, 결과를 모델에 돌려주고, 최종 답에 **`attachments`** 로
실어 보냅니다(2절). 검색 tool 과 정형 tool 을 한 loop 안에서 섞는 것이
가능해집니다 — "이 알람 매뉴얼 절차와 지난주 발생 건수" 같은 질문이 한 turn
에 답해집니다.

## 2. 답변 계약 변경 — 선택 키 `attachments`

`agent_query` 반환 dict 에 **선택** 키 하나가 늘어납니다. 없으면 지금과
똑같이 동작하므로 **현재 배포된 RAG 는 손대지 않아도 계약을 통과**합니다.
`contract.py` 가 검증하고, `--live` 러너가 출력합니다.

```python
class Attachment(TypedDict):
    kind: Literal["table", "chart"]
    title: str                       # 한 줄, 차트 제목·표 캡션
    tool_name: str                   # 이 데이터를 낸 카탈로그 tool
    data: ToolResult                 # 1.1 의 dataframe dict, tool 이 준 그대로
    chart: ChartSpec | None          # kind == "chart" 일 때만

class ChartSpec(TypedDict):
    type: Literal["line", "bar", "scatter"]
    x: str                           # data.columns 중 하나
    y: list[str]                     # data.columns 중 하나 이상
    series_by: str | None            # 시리즈로 나눌 열, 없으면 None
```

규칙 (검증기가 강제하는 것):

| 규칙 | 이유 |
| --- | --- |
| `data.rows` 는 `call()` 결과를 **그대로** 옮깁니다. 모델이 숫자를 다시 타이핑하지 않습니다 | 값이 정확해야 합니다. 모델은 **무엇을 어떻게 보일지**만 정합니다 |
| `chart.x`, `chart.y[*]`, `chart.series_by` 는 `data.columns` 에 있어야 합니다 | 없는 열은 빈 차트가 아니라 503 입니다 — 조용히 깨지는 쪽보다 낫습니다 |
| ECharts option 을 보내지 않습니다. `ChartSpec` 네 필드만 | option 은 크고 테마를 모르고, 모델이 쓴 것이 화면 렌더러에 닿는 첫 자리가 됩니다. 색·축·툴팁은 chat 이 `--sk-*` 토큰으로 그립니다 |
| attachments 는 turn 당 **최대 3**, 초과는 `sources` 처럼 잘립니다(거절 아님) | `RESULT_LIMIT=5` 와 같은 원칙 — 상한은 앱이 정하고 넘겨도 계약 위반은 아닙니다 |
| `content` 는 여전히 필수입니다. 표만 있는 답은 없습니다 | 화면은 본문 아래에 attachment 를 그립니다. 본문이 "무엇을 보였는가" 를 말해야 합니다 |
| `tool_traces` 에 정형 tool 호출도 기록합니다 — `tool_name` 은 카탈로그 이름, `query` 는 `args` 의 JSON | 2026-08-28 편지 3절이 부탁한 사무실 보고(응답 시간·행 수)가 이 값으로 대체됩니다 |

chat 화면 쪽: `kind: "table"` 은 표로, `kind: "chart"` 는 이미 모든 화면이
쓰는 `useEchart` 로 그립니다. `chart` 가 `None` 이거나 `type` 이 지원 밖이면
표로 내려갑니다. attachment 는 메시지 행에 저장되어 새로고침·폴링에도 남습니다.

## 3. RAG 측에 여쭙는 것 — **회신 요청**

| # | 질문 | 회신 불요 조건 |
| --- | --- | --- |
| 1 | 사무실 LLM gateway 가 **function calling(JSON Schema tools)** 을 안정적으로 지원합니까? | **지원하면 불요.** 지원하지 않으면 모델이 ` ```tool ` 펜스로 JSON 을 내고 그쪽이 파싱하는 대안으로 가야 하니, 그 경우만 알려 주십시오 |
| 2 | 1.1 의 결과 상한 200 행(≈10–20 KB)이 그쪽 컨텍스트 예산 안에 들어갑니까? | **들어가면 불요.** 아니면 원하는 행 수를 |
| 3 | 2026-08-28 편지 3절 1항 — **사용자가 실제로 묻고 싶은 질문 5개** — 를 아직 받지 못했습니다. 1.2 의 두 tool 이 그중 몇 개를 덮습니까? | 이 항목은 회신이 있어야 합니다. 두 tool 로 하나도 덮이지 않으면 첫 tool 을 바꾸는 편이 낫습니다 |

## 4. chat 측이 할 일 (순서)

1. `backend/chat/data_tools.py` — 카탈로그 + 첫 tool 둘. 집에서는 mock
   `data.py` 로 돌아가므로 shape 테스트는 집에서 끝냅니다.
2. `answer/contract.py` — `attachments` 선택 키 검증, 상한 3, `ChartSpec`
   열 참조 검사. `check_answer_contract` 출력에 스키마가 실립니다.
3. 메시지 저장 — SQLite 행에 `attachments` JSON 열. 폴링 응답에 실립니다.
4. 화면 — `ChatMessage.vue` 아래에 attachment 블록. 표 + `useEchart` 차트,
   CSV 복사는 기존 `tableExport` 를 씁니다.
5. **`scope.fabs` 채우기** — 지금 chat 은 `fabs: []` 로 보내고 있습니다
   (`orchestration.py`). 매뉴얼에는 무해했지만 정형 tool 에서는 "덮어쓸 값이
   없다" 가 되므로, tool 이 켜지기 전에 `access_control` 에서 채웁니다. 이것은
   chat 측 숙제이고 그쪽에서 보이는 변화는 `scope["fabs"]` 가 비어 있지 않게
   된다는 것뿐입니다.

1·2 는 3절 1항 회신 전에도 진행할 수 있습니다 — 1항이 "지원" 이면 그대로
쓰이고, "미지원" 이면 `parameters` 스키마가 펜스 JSON 의 스키마로 그대로
쓰입니다. 카탈로그 모양은 어느 쪽이든 같습니다.

## 5. 검증

```bash
# 집 — 카탈로그와 계약 (mock data.py)
.venv/bin/python -m pytest backend/chat -q

# 사무실 — 계약 전문 출력 (인덱스·RAG 불필요)
python -m scripts.verify.check_answer_contract

# 사무실 — 실제 turn 1회, 정형 tool 을 거치는 질문으로
python -m scripts.verify.check_answer_contract --live "지난 7일 CD-SEM recipe TAT 추세"
```

`--live` 는 지금처럼 import → 서명 → 반환값을 보고, `attachments` 가 있으면
2절 규칙까지 검사해 어긋난 키 이름을 출력합니다. 전부 `ok` 면 `/chat` 에서
차트를 여시면 됩니다.

## 6. 바뀌지 않는 것

`agent_query(question, messages, scope, timeout)` 서명, 필수 키 다섯,
`Evidence` 12 필드, 예외 3종, 300초 상한, `_rag/skewnono_rag/` 통째 교체
원칙 — 전부 그대로입니다. 이 편지는 **키 하나를 더하고 모듈 하나를 내놓는
것**이 전부입니다.

## 후기 — 사용자 회신 (2026-09-19, 사용자 전달)

3절 세 항목 중 둘이 닫혔고, 목표가 한 단계 넓어졌습니다.

| # | 회신 | 결과 |
| --- | --- | --- |
| 1 | 사무실 gateway 는 **JSON Schema function calling 을 지원**합니다 (user-confirmed) | 펜스 JSON 대안은 폐기. 카탈로그의 `parameters` 를 그대로 tool 정의로 씁니다 |
| 2 | 컨텍스트 창은 **256K 토큰**입니다 (user-confirmed) | 200 행 상한은 예산 문제가 아닙니다. 상한의 근거는 이제 **화면 가독성과 응답 시간**이며, 표 attachment 는 200, 모델에 돌려주는 tool 결과는 그보다 커도 됩니다 |
| 3 | 5개 질문은 아직 없습니다. 대신 **목표**가 왔습니다 — 아래 | 첫 tool 선정은 아래 목표에 맞춰 다시 봅니다 |

**`scope.fabs`**: chat 이 비워 보내는 상태를 "제한 없음" 으로 정의합니다.
`fabs` 가 비어 있으면 tool 은 모델이 채운 fab 인자를 그대로 쓰고, 비어
있지 않으면 지금까지처럼 덮어씁니다. 어느 fab 을 볼지는 대화 안에서 모델이
사용자에게 확인하면 됩니다 (user-confirmed). `access_control` 연동은 chat
측 후속 과제로 남기되, tool 이 켜지는 조건에서는 뺍니다.

**서비스는 이미 사용자에게 공개되어 쓰이고 있습니다.** 따라서 이 변경은 전부
**추가만** 이어야 합니다 — `attachments` 가 선택 키인 것, 카탈로그가 없어도
`agent_query` 가 그대로 도는 것이 그 조건입니다.

### 목표 — 단건 조회가 아니라 보고서

> 단일 이벤트·단일 데이터는 사용자가 skewnono 페이지에서 직접 봅니다.
> chat 은 **시간이 좀 걸려도** 여러 정보를 모아 분석해 **넓은 시야가 필요한
> 판단** — 기간 단위의 장비 상태, 이상 상황·이상 데이터 — 을 보고서로 내야
> 합니다. (user-confirmed 2026-09-19)

이 목표가 1·2절에 주는 변화는 넷입니다.

| 항목 | 1·2절 초안 | 목표에 맞춘 조정 |
| --- | --- | --- |
| tool 의 결과 단위 | 행 목록 | **집계·추세**가 기본입니다. `search_measurements` 같은 raw 목록 tool 보다 `recipe_tat_daily_trend`, fail 요약, 알람 일별 건수처럼 **이미 화면이 그리는 집계 함수**가 우선입니다. 각 feature 의 `get_summary` / `get_daily_trend` 계열이 그대로 후보입니다 |
| 한 turn 의 tool 호출 수 | 한두 번 | **여러 번, 여러 feature** 를 섞는 것이 정상입니다. 300초 상한(2026-09-01 확정) 안에서 그쪽이 loop 를 돌리십니다. 상한이 보고서에 부족하면 그때 "보고서 turn" 을 별도 예산으로 논의합니다 — 지금은 올리지 않습니다 |
| `attachments` 상한 | 3 | **6** 으로 올립니다. 보고서 하나가 추세 차트 둘·표 둘을 싣는 것이 자연스럽기 때문입니다 |
| `content` 의 모양 | 짧은 답 | 절 제목·목록이 있는 보고서입니다. chat 측 markdown 렌더러는 지금 제목·목록·표를 그리지 않으므로(코드·굵게·링크만) **chat 측이 렌더러를 넓힙니다** — 4절 chat 측 할 일에 6번으로 추가 |

첫 tool 둘은 이렇게 바꿉니다 — 둘 다 `office_example.py` 완성, 화면 사용 중.

| tool | 부르는 함수 | 왜 이것부터 |
| --- | --- | --- |
| `recipe_tat_daily_trend` | `ebeam.recipe_tat.data.get_daily_trend(...)` | 기간 추세 + 차트 — 목표의 최소 사례 |
| `fail_issue_summary` | `ebeam.fail_issue.data.get_summary(...)` / `get_daily_trend(...)` | "이상 상황" 의 기간 집계. TAT 와 같은 인자 모양(`fab_names, start_date, end_date, lot_cd`)이라 모델이 둘을 같은 기간으로 묶기 쉽습니다 |

`search_measurements` 는 대기 목록으로 내립니다 — "이 장비의 최근 측정" 은
사용자가 페이지에서 직접 보는 단건 조회이기 때문입니다.

### 다음

- chat 측: 4절 1·2 (카탈로그·계약 검증)를 지금 시작합니다. 회신에 의존하는
  항목이 남지 않았습니다. 4절 6번 — 렌더러 확장(제목·목록·표) — 을 추가합니다.
- RAG 측: `attachments` 를 실어 보내는 `agent_query` 는 chat 측 1·2 가
  `main` 에 오른 뒤 `check_answer_contract` 출력의 스키마를 보고 붙이시면
  됩니다. 그 전에는 할 일이 없습니다.
