# Spec 2: 튜닝할 장비 위치 이동 + 튜닝 목표에 장비 정보 표시

Status: approved (manager, 2026-09-01). Follow-up to spec-lab-single-route.md.
Worktree: `../skewnono-lab2` (branch `work/lab-picker-targets`)

## 요구 (사용자)

1. PM 튜닝 칩을 켜면 **튜닝할 장비 바가 분석 조건 바로 아래에** 나타나야 한다
   (지금은 데이터 요청 바와 분석 조건 사이, 즉 분석 조건 **위**에 뜬다).
2. 튜닝할 장비를 고르면 **튜닝 목표 카드가 그 장비의 정보(eqp_id, 모델명)를
   표시**해야 한다.

## 변경

### 1. `components/ebeam/LabView.vue` — ToolPicker 블록 이동

`EbeamPmPlanningToolPicker` 블록(v-if="has('pm')" 포함)을 `EbeamAnalysisBar`
**바로 아래**로 옮긴다. 새 순서: MetaBar → ScopeBar → ToolGroupBar →
RequestBar → AnalysisBar → **ToolPicker** → empty states → 결과.

블록 주석 갱신: "비교 대상·장비 모델 그룹 다음" 논리는 그대로 참이고, 이제
"이 바를 부르는 PM 튜닝 칩(분석 조건 안)이 바로 위에 있다"는 문장을 추가 —
칩 클릭 → 바로 아래에 바가 나타나는 배치가 의도임을 남긴다.
`ToolPicker.vue:3` 의 위치 서술 주석("그 두 바 다음에 옵니다")도 사실에 맞게
손본다. 로직·props 변경 없음.

### 2. `components/ebeam/pmPlanning/Targets.vue` — 고른 장비 정보 표시

- 카드 머리(제목 줄)에 고른 장비의 **eqp_id 와 모델명(eqp_model_cd)** 을
  표시한다. 제목은 "튜닝 목표 — 그룹 중심" 유지, 그 옆(또는 배지 반대편)에
  ToolPicker trigger 와 같은 정체성 표기 스타일(`sk-card-id` + 모델은
  `sk-field-label` 급)로. 예: `EQP123` + `CG6300`.
- 장비를 아직 고르지 않았으면(기존 `!target` 분기) 정체성 표기는 그리지
  않는다 — 기존 안내 문장이 그 상태를 이미 말한다.
- 데이터 경로: payload `ToolRef` 는 이미 `eqp_model_cd` 를 갖고 있다
  (`useTttmApi.ts:10`). LabView 의 `labelRefs` 가 eqp_id/label 만 추리므로,
  eqp_model_cd 를 함께 넘기거나 picked tool 하나를 `{ eqp_id, label,
  eqp_model_cd }` prop 으로 내려주는 것 중 구현자가 택일. payload 에 없는
  장비(요청 전 pick)는 roster(`useTttmScope`의 roster, 같은 필드 보유)로
  보강해도 되고, 그 경우가 아니면 payload 기준으로 충분.
- DESIGN.md: 값은 full ink, 라벨은 muted — 기존 카드 규칙 그대로. `--sk-*`
  토큰만.

### 하지 말 것

- Up gate 카드(GateCard)는 이미 `:eqp-id="picked"` 를 받는다 — 건드리지 않음.
- 백엔드·contracts 변경 없음. pageIdentity 변경 없음.

## 게이트

worktree 준비(node_modules symlink + `npx nuxi prepare`) 후:
1. `npm run typecheck` 2. `npm test` 3. `npm run lint`
4. 커밋(명시 pathspec), `type(scope): 요약` 형식.
