# Device Statistics v2 Prototype — 핸드오프

## 이 세션이 한 일

이전 grilling 세션 ([`device-statistics-grilling-handoff.md`](./device-statistics-grilling-handoff.md)) 의 결정을 기반으로 다음을 진행했습니다.

1. 후보 2 (Bucket 라디오) 의 push-back 4개를 모두 닫음 — top sticky · focus 유지 정책 · hint chip · Sample chip 시각 구분. CONTEXT.md 의 [[bucket]] 정의가 "page-wide interpretive frame" 4-속성 + 한국어 명칭 "기준 보기" + default `mother_normal` 로 강화됨.
2. 후보 3 (신호등 카드 시각) 의 push-back 4개를 닫음 — soft tint / inline muted avail_recipe / inline stage chip with `[?]` fallback / 행 sparkline 안 함. CONTEXT.md 의 [[lot]] 정의에 "lot_cd 가 팀 정체성을 인코딩" 사실이 추가됨.
3. 세 개 ADR 작성: [`0001-lot-as-primary-axis.md`](../adr/0001-lot-as-primary-axis.md) · [`0002-shared-url-across-audiences.md`](../adr/0002-shared-url-across-audiences.md) · [`0003-admin-only-rule-editor.md`](../adr/0003-admin-only-rule-editor.md).
4. `/prototype` UI sub-shape 변종 + `/frontend-design` 으로 별도 페이지 prototype 구현 완료. v1 그대로, v2 가 별도 route 에 살고, v2 내부에서 `?variant=A|B|C` 로 3가지 시각 분기.

## 현재 상태

- `npx nuxi typecheck` 통과 (EXIT=0).
- 코드 변경은 작업 디렉터리에 있고 미커밋. `git status` 의 새 파일/수정 파일이 이 prototype 의 산물.
- 사용자가 dev server (Flask :5050, Nuxt :3000) 를 PyCharm 에서 직접 띄움 — 이 세션은 시작하지 않음.

## 작성/수정 파일

대부분 `front-dev-home/app/` 아래입니다.

| 파일 | 역할 |
| --- | --- |
| `components/cdsem-stats-v2/healthTokens.ts` | red/yellow/green soft tint + para_16~5 색 + classifyHealth |
| `components/cdsem-stats-v2/StageChip.vue` | EV/TV/PV/Pool 칩, `?` fallback |
| `components/cdsem-stats-v2/StackedBarV2.vue` | para_16/13/9/5 horizontal bar, cap-breach 행 강조 |
| `components/cdsem-stats-v2/BucketSelector.vue` | top sticky · only_sample divider · URL `?bucket=` 동기화 |
| `components/cdsem-stats-v2/TrendChart.vue` | T-A health trajectory + T-B composition stacked area, SVG |
| `components/cdsem-stats-v2/VariantA.vue` | Dense rows ledger · 인라인 expand · 페이지 하단 trend zone |
| `components/cdsem-stats-v2/VariantB.vue` | Wide card grid atlas · 카드 footer mini-trend · expand-in-place |
| `components/cdsem-stats-v2/VariantC.vue` | Sidebar rail + detail pane inspector · cascade 한 pane |
| `components/cdsem-stats-v2/PrototypeSwitcher.vue` | floating ink pill · ← / → keys · `import.meta.dev` gating |
| `composables/useLotHealthMock.ts` | SummaryRow → HealthAugmentedRow (stage 추출 + cap 적용 + violation_ratio) |
| `pages/ebeam/cd-sem/device-statistics2/index.vue` | host · cart 재사용 · 샘플 20 lot preview · URL query sync |
| `pages/ebeam/cd-sem/device-statistics/index.vue` | banner 추가 (terracotta gradient · localStorage dismiss) |

## URL · 동작 확인 경로

```
http://localhost:3000/ebeam/cd-sem/device-statistics2?variant=A&bucket=mother_normal_summary
```

- ← / → 키로 A → B → C 순회 (input/textarea focus 시 가로채지 않음).
- cart 가 비어 있으면 "샘플 20개 lot 으로 미리 보기" 한 번 누름 → `useDeviceCart` 에 lot 적재 (v1 cart 와 공유, 사용자가 일부러 채운 게 아니라는 점 유의).
- v1 페이지 상단 banner → v2 로 이동. banner 우측 × 로 dismiss, `localStorage` 에 기억.

## 세 variant 의 분기축 (요약)

| Variant | Layout | 1차 affordance | Trend 자리 |
| --- | --- | --- | --- |
| A — Dense rows | CSS grid, 1 lot = 1 row | 행 클릭 → 인라인 expand (recipe table) | 페이지 하단 고정 zone (TZ-2chart) |
| B — Wide cards | flex-wrap, ~280px 카드 | 카드 클릭 → expand-in-place full row | 카드 footer mini-sparkline |
| C — Sidebar+detail | left rail + right pane | rail 클릭 → pane 갱신 | pane 안 (cascade 묶음) |

## 알려진 caveats

- **데이터 출처 = v1 endpoint 만**. `useLotHealthMock` 가 client-side 로 stage/cap/violation 을 *추가* — 룰은 in-file 상수 (`CAPS_BY_STAGE` 등). 실제 룰 편집기 (`/admin/measurement-rules`) 와 백엔드 룰 API 는 아직 없음 (ADR 0003 결정 이후 미구현).
- **bucket-aware trend 불완전**. T-A health trajectory 는 `recipe-trend` endpoint 의 weekly summary 를 client-side 로 augment 해 계산 — 정확하지만 매 변경마다 4 bucket 분량 계산이 클라이언트에서 일어남. 실제 dataset 이 커지면 v2 endpoint 신설 검토.
- **Sample preview 가 cart 를 mutate**. v2 페이지의 "샘플 20 lot" 버튼이 `useDeviceCart.addDeviceLots` 를 호출 → v1 의 cart 에도 그 lot 들이 박힘. 사용자가 의도 안 한 cart 채움이 일어날 수 있음. 정 거슬리면 별도 "preview-only" state 분리.
- **CONTEXT.md 의 only_sample bucket 의 universal rule** 은 mock 에서 `CAPS_SAMPLE` 한 벌로 표현. M-fab 룰 (`CAPS_MFAB`) 도 단일 값으로 잡혀 있음 — 실제 운영 룰 정의에 맞춰 조정 필요.
- **stage 추출 패턴**: `STAGE_PATTERNS` 가 `ctn_desc` 에서 `PV / EV / TV / Pool` 단어 경계만 봄. 케이스 변종이 더 있을 수 있어 mock 서버 generator 와 대조 권장.

## 남은 분기

| 단계 | 상태 |
| --- | --- |
| Variant 승자 결정 | **여기서 멈춤** — 다음 세션이 picking |
| 승자 → ADR 0004 로 기록 | 미시작 |
| 패자 + switcher 삭제, 승자 안을 `device-statistics2/index.vue` 안으로 흡수 | 미시작 |
| 룰 편집기 페이지 (`/admin/measurement-rules`) | 미시작 (ADR 0003 결정만) |
| v2 전용 endpoint 신설 여부 | 데이터 분기점 도달 후 결정 — 현재까진 v1 endpoint 만으로 충분 |
| v1 → v2 swap (route rename) | v2 안정화 + 사용자 합의 후 |

## 다음 세션 운영 팁

- 시작 시 본인이 (또는 임원 forward 받은 사람) 세 variant 를 forward 받아 화면에서 좌우 키로 본 뒤, "B의 헤더 + C의 detail pane" 같은 *조합* 의견이 나오는 게 자연스러움 — `/prototype` skill 의 "interesting feedback" 패턴 (handoff 문서 본문 외에서 자주 일어남).
- 승자 결정 후 *바로* `/prototype` skill 의 cleanup step 적용: 패자 두 variant + `PrototypeSwitcher` 삭제, 승자 안을 host 안으로 흡수. 그 결과를 ADR 0004 로 1-2단락 박아 두기 (LotHealthCard layout 선택 이유).
- 룰 편집기 + 백엔드 룰 API 신설은 별도 plan/PRD 으로 분리 권장 — prototype 의 mock 룰을 production 으로 쓰면 안 됨.

## 추천 skills · 다음 세션

- `/frontend-design` — 승자 variant 의 미세 결 (typography · spacing · 트랜지션) 다듬기.
- `grill-with-docs` 의 ADR 작성 흐름 — 0004 박을 때.
- `/prototype` (cleanup phase) — 패자 / switcher 제거.
- `feature-dev` — 룰 편집기 신설처럼 *진짜 features* 로 넘어갈 때.

## 참고 자료

- 도메인 글로서리: [`CONTEXT.md`](../../CONTEXT.md)
- ADR 들: [`docs/adr/`](../adr/)
- 이전 grilling 핸드오프: [`device-statistics-grilling-handoff.md`](./device-statistics-grilling-handoff.md)
- API 계약: [`docs/api-contracts/cdsem-device-statistics.yaml`](../api-contracts/cdsem-device-statistics.yaml)
- 원본 사용자 문제: [`device-statistics.txt`](./device-statistics.txt)
- 페이지 구현 계획 (오래된 버전): [`docs/device-statistics-plan.md`](../device-statistics-plan.md)
