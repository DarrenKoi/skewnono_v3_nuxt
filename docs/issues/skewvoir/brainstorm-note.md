# 스큐보아(Skewvoir) 데이터 뷰어 — 브레인스토밍 중단 노트

- 작성일: 2026-05-31
- 단계: **브레인스토밍 진행 중 (중단)**. 설계 확정 전이며, 다음 세션에서 이어서
  논의합니다.
- 대상: 엔지니어용 측정 결과 분석 뷰어 (`ebeam/{cd-sem,hv-sem}/skewvoir.vue`)
- 관련 메모리: `project_skewvoir_design` (6-view 워크스페이스 셸 슬라이스 계획)
- 사용자 의도: 시계열 추이, wafer-map(wafer-to-wafer·site contour), 통계 분석 등
  CD 데이터 분석 기능을 갖춘 뷰어. 현재 프로토타입을 바탕으로 변경 가능.

## 1. 현재 프로토타입 상태 — 구현이 둘로 갈라져 있음

| 구현 | 위치 | 상태 |
| --- | --- | --- |
| `SkewvoirView.vue` (구버전) | `components/ebeam/SkewvoirView.vue` | **동작함**. MsrPicker → AnalyzePanel. 실제 mock `msr-file` 데이터로 4개 차트 렌더 |
| `Workspace.vue` (IDE 셸) | `components/ebeam/skewvoir/Workspace.vue` | **페이지가 실제 마운트하는 것**. 크롬은 완성, 본문 ~90% 비어 있음 |

- 동작하는 4개 차트(구버전 AnalyzePanel 안): 다중 MSR 시계열(mean + min/max
  band), chip-position wafer map, CD 히스토그램, sequence 추이.
- IDE 셸(Workspace): 상단 탭바 + 좌측 6-view 레일 + Current Selection +
  Pinned Filters + Health + 하단 status bar. 단 `SearchView`만 레이아웃(그것도
  `PanelStub` 자리표시자)이고 나머지 5개 view는 `PlaceholderView` 하나.
  selection/filters/health 값은 모두 **하드코딩된 `useState` 데모값**.
- **핵심 문제: 잘 만든 빈 크롬 + 셸에 연결되지 않은 동작하는 분석 패널**.
  동작하는 4개 차트가 정작 그것을 담아야 할 셸 바깥에 떠 있습니다.

## 2. 사용 가능한 데이터 모델 (`useMsrFileApi`)

- MSR 단위 row: `sequence`, `chip_number`("x,y"), `chip_coordinate`,
  `stage_coordinate`, `dnum_group`, `mp_number`, `parameter`, `cd_value`, images.
- parameter 단위 summary: `count`, `mean`, `std`, `min`, `max`, `unit`.
- 즉 현재 데이터로 가능한 것: chip 위치 scatter(wafer map), sequence별 값,
  히스토그램, 다중 MSR mean±band 시계열 — 정확히 지금 4개 차트가 하는 것.

## 3. 내 의견 (Claude) — 요약

1. **IDE/워크스페이스 메타포는 좋다. 단, 실속보다 크롬을 앞세우고 있다.** 6개 빈
   방을 가진 멋진 셸보다, 실제 분석으로 꽉 찬 방 2개가 낫습니다.
2. **현재 차트는 기술통계(descriptive)지만, CD 엔지니어의 일상 질문은
   의사결정용(decision-grade)이다.** 리서치가 말하는 일상 도구:
   - SPC 한계선 + run rule(Western Electric/Nelson, EWMA 드리프트)이 있는 시계열
     — "이 장비 드리프트 중인가?" (현재는 min/max band만 있음)
   - spec 컨텍스트 + Cpk/Ppk — "spec 안인가, 공정능력 되는가?" (USL/LSL/target
     이 아예 없음)
   - **시그니처로서의 wafer map** — 무지개 scatter가 아니라 ±3σ/outlier 기준 색,
     그리고 **radial(center-vs-edge)** (CD 시그니처 1순위 클래스)
   - 상관 scatter(param vs param, R²) — view #5가 이름만 있고 비어 있음
   - wafer-to-wafer / stacked map — "이 패턴이 systematic인가 random인가?"
3. **가장 큰 레버리지는 UI가 아니라 백엔드 데이터 모델이다.** 모든 레코드에
   **nested `lot › wafer › site` 키 + 공간 좌표(`x, y, radius, field`) +
   `edge_flag` + spec 한계선**을 유지하는 것이 "숫자를 그리는 뷰어"와
   "장비/공정/레시피/계측 중 무엇이 문제인가를 답하는 뷰어"를 가릅니다.

**결론:** 워크스페이스 셸은 유지. 단 view를 더 추가하기 전에 (a) 셸을 홈으로
확정하고 동작하는 분석을 셸 안으로 이주, (b) "엔지니어가 여기서 어떤 의사결정을
하는가"에서 거꾸로 출발해 어떤 분석이 자리를 얻을지 선별 — 레일에 6칸 있으니 6칸
채우는 식이 아니라.

## 4. 리서치 요약 — CD wafer 데이터 분석 기법

(웹 리서치 기반. 각 기법: 답하는 질문 / 시각화 / 필요 데이터.)

| 기법 | 시각화 | 필요 백엔드 필드 |
| --- | --- | --- |
| SPC 시계열 (Xbar-R, EWMA, CUSUM) + run rule | 한계선·σ 밴드 있는 추이선 | subgroup mean/range, timestamp, 베이스라인 한계선, σ zone |
| 분포 + 정규성 | 히스토그램 + normal fit, box plot, Q-Q | raw CD 값 |
| 공정능력 Cpk/Ppk | USL/LSL/target 선 있는 히스토그램 | 값 + USL/LSL/target |
| Wafer heat/parametric map | site별 색 지도 | site `(x,y,CD)`, wafer_id |
| Contour (IDW/kriging) | 보간 등고선 | site + 보간 파라미터 |
| Radial/zonal (center-edge) | 반경별 scatter / 동심원 zone | site `radius`, `angle`, zone |
| Stacked/composite map | 다중 wafer 집계 지도 | 정렬된 multi-wafer site 배열 + 집계법 |
| Golden 대비 차이 지도 | difference map | recipe별 golden site 벡터 |
| 분산 성분(ANOVA) | 분산 기여 stacked bar/pie | nested `lot›wafer›site›tool` 키 |
| 상관 | scatter + R² | 공통 키의 쌍값 |
| Commonality | suspect 장비 Pareto | wafer별 MES genealogy |

권장 우선순위: **Tier 1** CD heat map · SPC 한계선+run rule 시계열 ·
히스토그램+mean/3σ+Cpk · lot/wafer/tool box plot. **Tier 2** radial/zonal ·
composite map · IDW contour · 분산 성분 · 상관 scatter. **Tier 3** kriging ·
golden 차이 · commonality · tool-matching · LER/LWR/PSD.

핵심 설계 노트: 모든 레코드에 **nested 계층(`lot›wafer›site`) + 공간 좌표
(`x,y,radius,field`) + `edge_flag`**를 유지하는 것이 최고 레버리지.

## 5. 다음 세션에서 이어갈 것 (Open)

1. **시각 동반(Visual Companion) 제안에 대한 답** — 브라우저로 목업/레이아웃
   비교를 보여줄지 (미정, 사용자 "나중에 논의").
2. **셸 vs 단순화 결정** — Workspace 셸을 홈으로 확정하고 동작하는 AnalyzePanel을
   그 안으로 이주할 것인가? 구버전 `SkewvoirView.vue`는 정리/폐기할 것인가?
3. **분석 우선순위 선별** — 6개 view를 다 채울지, 아니면 의사결정 기준으로
   Tier 1부터 추릴지.
4. **백엔드 데이터 모델 확장 범위** — 현재 mock에 spec 한계선/공간 좌표/nested
   키를 어디까지 추가할지 (mock 우선 원칙 하에서).
5. 확정 시 → spec(`docs/superpowers/specs/`) + plan으로 승격.
