# Radius Analysis 팝업 리노베이션 — 계획 (Claude → Codex 토론용)

대상: `frontend/app/components/ebeam/skewvoir/dashboard/RadiusAnalysisDialog.vue`
(측정 개요 → Radius Plot 패널의 ⤢ 아이콘으로 열리는 확대 팝업).
호출부: `dashboard/RadiusPlot.vue`, 차트: `skewvoir/RadiusChart.vue`,
수학: `utils/radialAnalysis.ts` (수정 안 함).

## 사용자 요구
1. 한국어 위주로, 지표(Residual MAD, CV RMSE 등)의 **의미를 설명**할 것.
2. 페이지가 어지럽지 않게 설명은 **(i) 아이콘**(툴팁)으로.
3. **Sector 색상은 기본 ON**.
4. 차수 1~3 은 드롭다운 대신 **버튼**. 현재 드롭다운(모델, 밴드 "Observed IQR")이 **반응 없음** → 반드시 동작하게.

## 버그 원인 가설 (드롭다운 무반응)
USelect 의 팝오버는 body 로 portal 되는데 NuxtUI 오버레이는 z-index 를 안 실어 준다
(앱 chrome / 이 다이얼로그의 `z-50` 백드롭 아래로 깔림). 항목 클릭이 백드롭에 떨어져
`@click="close"` 만 실행되거나 아예 안 보임. → 드롭다운을 없애고 세그먼트 버튼으로 바꾸면
근본적으로 사라진다. (별도 z-index 패치는 안 함 — 이 팝업 안에서만 쓰는 컨트롤이라.)

## 변경안
### A. 세그먼트 토글 컴포넌트 추출 (재사용, 새 스타일 없음)
`PanelFrame.vue` 안의 인라인 토글 마크업(`bg-(--sk-chip-bg) p-0.5` + 활성 `bg-(--sk-surface) shadow-sm`)을
`ebeam/skewvoir/SegmentedToggle.vue` 로 뽑아 `PanelFrame` 과 다이얼로그 둘 다 사용.
props: `items: {label, value}[]`, `modelValue`. PanelFrame 은 string[] 그대로 받아 감싼다.

### B. 다이얼로그 헤더
- 제목 `반경 분석 · {parameter}`, 메타 `관측 반경 a–b mm · 측정점 n개 · 서로 다른 반경 k개`
- 모델 토글: `원본만 | 1차 | 2차 | 3차` (SegmentedToggle)
- 밴드 토글: `IQR | 95% 신뢰 | 95% 예측 | 없음` + 옆에 (i): 현재 밴드 의미 설명 (기존 "Band meaning" 섹션 흡수)
- `섹터 색` 토글 버튼 (기본 ON)

### C. 우측 사이드
- **적합 품질**: 6개 지표, 각 라벨 옆 (i) UTooltip 한국어 설명
  - 조정 R² — 추세가 값 변동을 설명하는 비율(0~1). 차수를 올려도 공짜로 오르지 않게 보정.
  - RMSE — 추세선과 실측의 평균 거리. 단위 그대로.
  - CV RMSE — 각 점을 하나씩 빼고 예측했을 때 오차(교차검증). RMSE 보다 크게 벌어지면 과적합 신호.
  - 잔차 σ — 잔차의 표준편차(자유도 보정). 이상점에 민감.
  - 잔차 MAD — 중앙값 기반 산포(σ 스케일로 환산). 이상점에 둔감 → σ 와 크게 다르면 소수 점이 튀는 것.
  - Δ 추세 폭 — 추세선의 최외곽-최내곽 값 차. 중심→가장자리 기울기 크기.
- **가장 큰 잔차**: 값 + `측정점 seq` + 한 줄 주의(진단용, 사이트 판정 대체 아님)
- **모델 식**: 기존 그대로 + (i) 로 "t 는 관측 반경 범위로 정규화, 미측정 구간으로 연장 안 함"
- **섹터 범례**: 현재 하드코딩 hex(#5C86AE 등) → DESIGN.md 위반. RadiusChart 와 같은 소스
  (`useChartPalette().series/brand`, `SK_STATE.warn/ok`)로 맞춤. E/N/W/S 한국어 병기(동/북/서/남).
- 경고 배너 문구 한국어화.

### D. RadiusPlot.vue
변경 최소: 패널 토글 `1° 2° 3°` 는 이미 버튼. `initial-model` 전달 그대로.

## 하지 않는 것
- radialAnalysis 수학/지표 변경 없음.
- 툴팁 라이브러리 추가 없음 (NuxtUI `UTooltip` 이미 있음, BsmPanel 선례).
- 새 CSS 토큰 없음.

## 검증
- `npm run typecheck`, `npm run lint`, `npm test` (frontend)
- 브라우저: 팝업 열기 → 4개 모델 버튼 / 4개 밴드 버튼 각각 클릭 시 차트·지표 변동, 섹터 기본 채색, (i) hover.

Codex 에게: 위 계획에서 빠진 것 / 틀린 가정(특히 무반응 원인) / 더 단순한 방법을 지적해 주세요.
구현은 Claude 가 하고, 끝나면 리뷰를 다시 요청합니다.
