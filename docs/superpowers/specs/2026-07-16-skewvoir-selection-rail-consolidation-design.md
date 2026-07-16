# Skewvoir 분석 선택 레일 통합 설계

## 배경

`skewvoir/analysis` 워크스페이스는 콘텐츠가 늘어나면서 "모든 구성 요소가 스크롤 없이 한 화면에 들어와야 한다"는 규칙을 더 이상 지킬 수 없게 되었습니다. 왼쪽 레일(`LeftRail.vue`)과 뷰 본문은 이미 각각 독립적으로 스크롤되며, 이 설계는 그 전제를 받아들여 상단 컨텍스트 바를 왼쪽 레일로 통합합니다.

현재 레이아웃은 두 영역으로 나뉩니다.

- **왼쪽 레일** (`workspace/LeftRail.vue`, `w-60`): 검색으로 버튼, WORKSPACE 뷰 모드(1–5), CURRENT SELECTION / 비교 세트, ACTIONS.
- **상단 컨텍스트 바** (`workspace/AnalysisContextBar.vue`): `<main>` 상단의 가로 스트립. scope 배지(단일 측정 / 세트 비교), Focus MSR, Parameter, 호환/제외 카운트, 기준(reference) provenance, 세트 편집(`USelectMenu`), 분석 준비 상태 버튼.

두 컴포넌트는 모두 동일한 두 컴포저블(`useSkewvoirWorkspace`, `useSkewvoirAnalysis`) 위에 얹힌 얇은 뷰이므로, 컨트롤을 옮기는 것은 동일한 반응형 소스를 새 위치에서 다시 렌더링하는 것에 불과합니다. 상태 마이그레이션은 없습니다.

## 목표

상단 `AnalysisContextBar`의 표시 내용(단일 측정 & 세트 비교, 세트 편집, 분석 준비 상태)을 왼쪽 레일의 CURRENT SELECTION 영역으로 통합합니다. 좁은 레일에는 핵심만 간결히 노출하고, 전체 상세는 확대 모드(중앙 모달)에서 봅니다.

## 설계

### 레이아웃

- `Workspace.vue`에서 `AnalysisContextBar`를 **제거**합니다. 상단 가로 스트립이 사라지고 뷰 본문(`min-h-0 flex-1 overflow-auto`)이 그 세로 높이를 회수합니다.
- 왼쪽 레일과 뷰 본문의 독립 스크롤을 그대로 활용합니다. "한 화면에 다 들어와야 한다"는 제약은 폐기합니다.

레일의 CURRENT SELECTION / 비교 세트 영역이 컨텍스트 바의 책임을 흡수합니다.

```text
┌ LEFT RAIL (w-60) ─────────────┐
│ [검색으로]                     │
│ WORKSPACE (뷰 모드 1–5)        │  ← 변경 없음
│ ───────────────────────────── │
│ ⬒ 세트 비교 / 단일 측정   [⤢]  │  ← scope 배지 + 확대 버튼
│ Focus  MSR123                 │  ← 간결 메타
│ Param  CD_MEAN                │
│ 호환 8 · 제외 2                │  ← 간결 카운트
│ ── MSR 목록 ──      [선택 해제] │
│ ☑ ▸ lot·eq·ts  (focused)      │  ← ☑ = 세트 포함, 행 클릭 = focus
│ ☑   lot·eq·ts                 │
│ ☑   lot·eq·ts                 │
│ [ 분석 준비 상태 · 제외 2 ]     │  ← ReadinessDrawer 열기 (변경 없음)
│ ───────────────────────────── │
│ ACTIONS (Annotate/Recipe/Share)│ ← 변경 없음
└───────────────────────────────┘
```

### 상호작용 모델

**MSR 목록 (세트 멤버만 표시):**

- **행 본문 클릭** → `analysis.setFocusedMsr(msr)`. 모든 뷰에 걸쳐 동작하는 focus 전환(현재의 비교 세트 칩과 동일). focus된 행을 강조합니다.
- **선행 체크박스** → 해당 MSR의 세트 포함 여부. 목록은 멤버만 표시하므로 모든 행이 체크된 상태이며, 체크 해제 시 즉시 세트에서 제거하고 `ws.setMsrs`로 `?msrs=`를 재작성합니다(행이 사라짐). 로컬 대기 상태 없이 즉시 커밋합니다. 기존의 세트 편집 제거 경로를 대체합니다.
- **선택 해제** → 목록 헤더의 작은 텍스트 버튼. focus된 MSR 하나만 남기고 나머지 멤버를 세트에서 제거합니다(`ws.setMsrs([focusMsr])`). 워크스페이스가 비지 않도록 focus는 항상 남깁니다. (모두 선택은 멤버만 표시하는 목록에서 무의미하므로 제공하지 않습니다.)
- **단일 측정 scope**: 행이 정확히 하나이며 체크박스/선택 해제가 필요 없습니다. focus된 카드처럼 보입니다.

**확대 버튼 (⤢)** → 중앙 모달(`SelectionDetailModal.vue`, `WaferDetailModal` 스타일)을 엽니다. 좁은 레일에 담을 수 없는 전체 상세를 표시합니다.

- 전체 선택 필드 (Lot / Recipe / EQ / MP / Captured)
- 전체 카운트: 호환 / 로드 / 선택 / 제외
- 기준(reference provenance)
- **검색 가능한 세트 편집기** (`USelectMenu multiple`, 전체 후보 풀 대상). 레일 목록은 현재 멤버만 보여주므로, 후보 풀에서 **새 MSR을 추가**하는 곳은 이 모달입니다.

**분석 준비 상태 버튼** → 기존 `ReadinessDrawer`를 변경 없이 엽니다. `LeftRail`이 `open-readiness`를 `Workspace`로 emit합니다(기존 바와 동일).

### 컴포넌트 · 데이터 흐름 · 파일

| 파일 | 변경 |
| --- | --- |
| `workspace/AnalysisContextBar.vue` | **삭제.** 컴퓨티드 로직(`scope`, `counts`, `referenceLabel`, `candidateItems`)은 `LeftRail`과 새 모달로 이전. |
| `workspace/LeftRail.vue` | CURRENT SELECTION 영역 재구성: scope 배지 + 확대 버튼, 간결 메타(Focus / Param / 카운트), 체크 가능한 MSR 목록(행 focus + 모두 선택/선택 해제), 분석 준비 상태 버튼. 새 모달 렌더링, `open-readiness` emit. |
| `workspace/SelectionDetailModal.vue` | **신규.** 중앙 모달(UModal, `WaferDetailModal` 스타일) — 전체 선택 필드, 전체 카운트, 기준, 검색 가능한 세트 편집기(`USelectMenu multiple`). |
| `Workspace.vue` | `AnalysisContextBar` 제거, `LeftRail`의 `@open-readiness` 배선. 뷰 본문이 높이 회수. |

**데이터 흐름:** `LeftRail`은 이미 `ws`, `analysis`, `fab`를 받으므로 바가 계산하던 값 전부를 그 자리에서 도출할 수 있습니다. prop 배선 변경 없음. 멤버십 쓰기는 `ws.setMsrs`, focus는 `analysis.setFocusedMsr` — 모두 기존 API. 모달은 `LeftRail`의 자식으로 `ws` + `analysis`를 받고 로컬 `open` 상태를 가집니다.

**scope 진입 불변:** 세트 vs 단일은 여전히 `?msrs=` 길이로 결정됩니다. 세트 진입 방식은 바꾸지 않고 컨트롤만 통합합니다. 검색 가능한 세트 편집기는 오늘과 동일하게 `scope === 'set'`에서만 노출됩니다.

**백엔드 / 컴포저블 변경 없음** — 기존 상태를 재구성하는 순수 프런트엔드 작업입니다.

## 위험과 완화

- **선택 해제/체크 해제로 세트가 빔** → 선택 해제는 focus된 MSR 하나를 항상 남깁니다. 개별 체크 해제도 마지막 남은 focus 멤버는 제거하지 못하도록 가드합니다.
- **좁은 레일에 목록이 길어짐** → 레일은 이미 `overflow-y-auto`. 스크롤을 허용합니다(no-scroll 규칙 폐기).
- **바 삭제로 상단 컨텍스트 상실** → 핵심(Focus / Param / 카운트)은 레일에, 전체는 확대 모달에 유지됩니다.

## 범위 밖

- scope 진입 로직(단일 ↔ 세트 전환 방식) 변경.
- 백엔드 / 컴포저블 API 변경.
- `ReadinessDrawer` 내부 재설계(열림 배선만 이동).
