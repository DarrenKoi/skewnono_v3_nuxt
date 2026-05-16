# Device Statistics — 이슈 · 구현 요청 · 결정 (v2까지)

세 개의 분리된 핸드오프 문서를 하나로 통합한 요약본입니다. 원문은 [`device-statistics.txt`](./device-statistics.txt), [`device-statistics-grilling-handoff.md`](./device-statistics-grilling-handoff.md), [`device-statistics-v2-prototype-handoff.md`](./device-statistics-v2-prototype-handoff.md) 에 그대로 보존되어 있습니다.

---

## 1. 원본 이슈 — 페이지의 존재 이유

### 페이지 서비스 목적

팹별로 개발 중인 디바이스들을 통계적으로 비교 분석해 팹 운영에 도움을 주는 것이 주 목적입니다.

- 너무 많은 파라미터와 너무 잦은 측정을 하는 `recipe_id` 를 찾아내 최적화를 진행합니다.
- 시간 추이에 따라 어떻게 변하는지 모니터링하여 팹 운영 최적화를 지속적으로 유지합니다.

### 사용자가 궁금해 하는 것

- Recipe 별 파라미터 측정 포인트 수가 어떻게 구성되어 있는지.
- Recipe 안에 구체적으로 어떤 파라미터가 들어 있는지.
- 선택된 디바이스가 다른 디바이스 대비 어떤 상태인지.

### 도메인 사실

- 각 개발 디바이스는 측정 스텝(`oper_id`)을 가지며 `recipe_id` 와 쌍을 이루는 경향이 있습니다.
- `bucket` 을 나눈 이유는 디바이스별로 전체를 비교할지 부분(Only Normal, Only Sample)만 비교할지 선택할 수 있게 하기 위함입니다.
- Mother 파라미터는 측정 시간(TAT)에 영향을 줍니다. Son(자식 파라)은 Mother 안에서 측정되므로 TAT 에 영향이 없습니다.

### 좁혀진 통점

원문의 5 개 user job 중 grilling 세션에서 가장 큰 통점으로 좁혀진 것:

- **(A) 비대한 `recipe_id` 발굴**
- **(D) Recipe 내부 파라미터 드릴다운**

---

## 2. 합의된 결정 (Grilling 세션 산출물)

도메인 용어로 정리된 사항은 [`CONTEXT.md`](../../CONTEXT.md) 에, hard-to-reverse 결정은 [`docs/adr/`](../adr/) 에 박혀 있습니다. 본 절은 인덱스 역할만 합니다.

### 축 · 사용자

| 결정 | 근거 |
| --- | --- |
| Lot 이 primary axis | 팀 · 담당자 할당이 lot 단위 (조직적 ownership boundary). [ADR 0001](../adr/0001-lot-as-primary-axis.md) |
| 담당자 + 임원 두 audience 가 같은 URL 공유 | Evidence forwarding 때문에 hide-by-tab 불가. [ADR 0002](../adr/0002-shared-url-across-audiences.md) |
| Rule editor 는 관리자(daeyoung) 전용 별도 페이지 | Single source of truth 가 cross-team coordination 매체. [ADR 0003](../adr/0003-admin-only-rule-editor.md) |

### IA · 인터랙션

| 결정 | 내용 |
| --- | --- |
| Page IA | 1-page 통합. `comparison.vue` → `index.vue` 로 흡수 |
| Cascade | 신호등 → recipe table(process walkthrough) → U1 인라인 행 확장. Slideover 폐기 |
| Cart layer | Last-session state 로만 유지 (UI 없음). Preset 은 명시적 저장 묶음으로 별도 유지 |
| Focus 정책 | Single focus 기본(F1). Multi-lot focus(F2) 는 향후 U4 pinning 으로 검토 |

### Bucket — “기준 보기”

- 한국어 명칭 **기준 보기**, default `mother_normal`.
- Page-wide interpretive frame (4 속성 정의는 [`CONTEXT.md`](../../CONTEXT.md) 의 `[[bucket]]` 항목).
- Top sticky bar 위치, URL `?bucket=` 동기화, 전환 시 lot focus 유지 · recipe row 부재 시 conditional collapse.

### Rule 형태

- Per-recipe cap: `para_16_max`, `para_13_max`, `para_9_max`, `para_5_max`.
- 매트릭스: R3 = `(stage × bucket)`, M-fab = `bucket`, Sample = 1 universal cell.
- Seed 위치: `back_dev_home/ebeam/cdsem/device_statistics/rules.py`.

### Lot Health 지표

- `violation_ratio = 위반 recipe / 총 recipe`, 10/20 threshold.
- Severity 는 cell-level σ 시각 표현(구체 식은 미정 — open 항목).
- Device Stage: R3 에만 존재, 백엔드가 `ctn_desc` 에서 PV/EV/Pool 추출.

### 시각화

- **Zone ②**: V2 horizontal stacked bar + 행 색이 신호등 (soft tint).
- **Trend zone (TZ-2chart)**: T-A health trajectory line + zone 배경 색 / T-B composition shift stacked area + `avail_recipe` 보조 line + cap 점선.
- 신호등 카드: inline muted `avail_recipe`, inline stage chip + `[?]` fallback, 행 sparkline 은 도입하지 않음.

---

## 3. 구현 요청 (v2 Prototype 으로 답한 것)

### 별도 route 에 prototype 분기

| 항목 | 값 |
| --- | --- |
| Host route | `/ebeam/cd-sem/device-statistics2` |
| Variant 분기 | `?variant=A \| B \| C` |
| Bucket 동기화 | `?bucket=mother_normal_summary` 등 |
| v1 → v2 진입 | v1 페이지 상단 terracotta gradient banner, `localStorage` dismiss |

### 세 variant 의 분기축

| Variant | Layout | 1차 affordance | Trend 자리 |
| --- | --- | --- | --- |
| A — Dense rows | CSS grid, 1 lot = 1 row | 행 클릭 → 인라인 expand (recipe table) | 페이지 하단 고정 zone (TZ-2chart) |
| B — Wide cards | flex-wrap, ~280px 카드 | 카드 클릭 → expand-in-place full row | 카드 footer mini-sparkline |
| C — Sidebar+detail | left rail + right pane | rail 클릭 → pane 갱신 | pane 안 (cascade 묶음) |

### 작성/수정 파일

| 파일 | 역할 |
| --- | --- |
| `components/cdsem-stats-v2/healthTokens.ts` | red/yellow/green soft tint + para_16~5 색 + `classifyHealth` |
| `components/cdsem-stats-v2/StageChip.vue` | EV/TV/PV/Pool 칩, `?` fallback |
| `components/cdsem-stats-v2/StackedBarV2.vue` | para_16/13/9/5 horizontal bar, cap-breach 행 강조 |
| `components/cdsem-stats-v2/BucketSelector.vue` | top sticky · `only_sample` divider · URL `?bucket=` 동기화 |
| `components/cdsem-stats-v2/TrendChart.vue` | T-A health trajectory + T-B composition stacked area, SVG |
| `components/cdsem-stats-v2/VariantA.vue` | Dense rows ledger · 인라인 expand · 페이지 하단 trend zone |
| `components/cdsem-stats-v2/VariantB.vue` | Wide card grid atlas · 카드 footer mini-trend · expand-in-place |
| `components/cdsem-stats-v2/VariantC.vue` | Sidebar rail + detail pane inspector · cascade 한 pane |
| `components/cdsem-stats-v2/PrototypeSwitcher.vue` | floating ink pill · `← / →` keys · `import.meta.dev` gating |
| `composables/useLotHealthMock.ts` | SummaryRow → HealthAugmentedRow (stage 추출 + cap 적용 + `violation_ratio`) |
| `pages/ebeam/cd-sem/device-statistics2/index.vue` | host · cart 재사용 · 샘플 20 lot preview · URL query sync |
| `pages/ebeam/cd-sem/device-statistics/index.vue` | banner 추가 (terracotta gradient · `localStorage` dismiss) |

### 동작 확인 경로

```text
http://localhost:3000/ebeam/cd-sem/device-statistics2?variant=A&bucket=mother_normal_summary
```

- `← / →` 키로 A → B → C 순회 (input/textarea focus 시 가로채지 않음).
- cart 가 비어 있으면 “샘플 20개 lot 으로 미리 보기” 클릭 → `useDeviceCart` 에 lot 적재 (v1 cart 와 공유).

### 현재 상태

- `npx nuxi typecheck` 통과 (EXIT=0).
- 변경 사항은 작업 디렉터리에 있고 미커밋.
- Dev server (Flask :5050, Nuxt :3000) 는 사용자가 PyCharm 에서 직접 기동.

---

## 4. 알려진 caveats (v2 한정)

- **데이터 출처 = v1 endpoint 만.** `useLotHealthMock` 가 client-side 로 stage/cap/violation 을 *추가*. 룰은 in-file 상수 (`CAPS_BY_STAGE` 등). 실제 룰 편집기(`/admin/measurement-rules`) 와 백엔드 룰 API 는 미구현 (ADR 0003 결정 이후).
- **Bucket-aware trend 불완전.** T-A health trajectory 가 `recipe-trend` endpoint 의 weekly summary 를 client-side 로 augment 하여 4 bucket 분량 재계산. 데이터셋이 커지면 v2 전용 endpoint 신설 검토.
- **Sample preview 가 cart 를 mutate.** “샘플 20 lot” 버튼이 `useDeviceCart.addDeviceLots` 를 호출 → v1 cart 에도 박힘. 정 거슬리면 preview-only state 분리 필요.
- **`only_sample` universal rule** 은 mock 에서 `CAPS_SAMPLE` 한 벌, M-fab 룰(`CAPS_MFAB`) 도 단일 값. 실제 운영 룰에 맞춰 조정 필요.
- **Stage 추출 패턴**: `STAGE_PATTERNS` 가 `ctn_desc` 의 `PV / EV / TV / Pool` 단어 경계만 봄. 케이스 변종은 mock 서버 generator 와 대조 권장.

---

## 5. 남은 분기 · Open 항목

### 다음 단계 (순서대로)

| 단계 | 상태 |
| --- | --- |
| Variant 승자 결정 | **여기서 멈춤** — 다음 세션이 picking |
| 승자 → ADR 0004 로 기록 | 미시작 |
| 패자 + switcher 삭제, 승자 안을 `device-statistics2/index.vue` 안으로 흡수 | 미시작 |
| 룰 편집기 페이지 (`/admin/measurement-rules`) | 미시작 (ADR 0003 결정만) |
| v2 전용 endpoint 신설 여부 | 데이터 분기점 도달 후 결정 |
| v1 → v2 swap (route rename) | v2 안정화 + 사용자 합의 후 |

### 지연된(open) 결정

- Severity weighting 의 구체 식 (σ 기준 *방향* 만 합의).
- F2 multi-lot focus — U4 (recipe pinning) 후보로 향후 검토.
- 사용자 → 관리자 룰 변경 요청 채널 — 첫 버전 없음 (구두/Slack 처리).
- Server-side user tracking 부재 — 현재 cart layer 가 임시로 그 자리를 채움.

### 다음 세션 운영 팁

- 세 variant 를 화면에서 좌우 키로 본 뒤 “B 의 헤더 + C 의 detail pane” 같은 *조합* 의견이 자연스럽게 나옴 — `/prototype` skill 의 “interesting feedback” 패턴.
- 승자 결정 직후 `/prototype` cleanup 적용 → 패자 두 variant + `PrototypeSwitcher` 삭제, 승자 안을 host 로 흡수. 결과를 ADR 0004 (1~2 단락) 로 기록.
- 룰 편집기 + 백엔드 룰 API 는 별도 plan/PRD 로 분리. Prototype 의 mock 룰을 production 으로 쓰지 말 것.

---

## 참고 자료

- 도메인 글로서리: [`CONTEXT.md`](../../CONTEXT.md)
- ADR 들: [`docs/adr/`](../adr/)
- 원본 사용자 문제: [`device-statistics.txt`](./device-statistics.txt)
- Grilling 핸드오프: [`device-statistics-grilling-handoff.md`](./device-statistics-grilling-handoff.md)
- v2 prototype 핸드오프: [`device-statistics-v2-prototype-handoff.md`](./device-statistics-v2-prototype-handoff.md)
- API 계약: [`docs/api-contracts/cdsem-device-statistics.yaml`](../api-contracts/cdsem-device-statistics.yaml)
- 페이지 구현 계획(오래된 버전): [`docs/device-statistics-plan.md`](../device-statistics-plan.md)
