# 하드웨어 MDC 시계열 개편 + BM/PM 오버레이 · 설계

- 작성일: 2026-07-13
- 대상 페이지: H/W 관리 (CD-SEM / HV-SEM)
- 구성: Part A — MDC 탭 개편(시계열 + 박스플롯 비교), Part B — 시계열 차트
  BM/PM 오버레이. 두 파트는 함께 배포합니다 (Part B가 Part A의 신규 차트를
  오버레이 대상으로 포함).

## Part A. MDC 탭 개편

### A1. 목적

현재 MDC 탭은 as-of 스냅샷 기준의 tool 간 비교 매트릭스(테이블)만 제공합니다.
선택 장비의 MDC **이력(시계열)** 을 1차 뷰로 추가하여 보정값의 시간적 변화를
추적할 수 있게 하고, 비교 뷰는 값 차이를 읽기 어려운 테이블 대신
**박스플롯**으로 개선합니다.

### A2. 하위 뷰 구조

- MDC 탭 내부에 pill 하위 탭 2개를 둡니다: **시계열**(기본) | **비교**.
- `FdcPanel`의 `fdc_key` 하위 탭과 같은 패턴이며, 상태는 패널 로컬 `ref`로
  관리합니다.

### A3. 백엔드 — mock + 응답 계약

- `mdc` 서비스 payload에 `docs` 배열을 추가합니다. 기존 `settings`
  (fleet 스냅샷 dict-of-dict)는 그대로 유지하며 비교 뷰가 계속 사용합니다.
- `docs`: **선택 장비**의 timestamped long-format 레코드이며, 요청된
  `start`/`end` 윈도우 안에서 시간 오름차순으로 정렬합니다.

```python
# docs 레코드 (DataFrame.to_dict(orient="records") 형식)
{"timestamp": "2026-05-01 09:00", "beam_condition": "800V_HR_0Deg", "mdc_value": 1.001234}
```

- mock (`mdc_mock.py`): `build_mdc_history()`를 추가합니다.
  - 장비별 3~10일 간격의 재교정(recalibration) 이벤트를 생성합니다. 이벤트
    시점마다 해당 장비가 가진 모든 beam_condition의 값이 한 번에 갱신됩니다.
  - 값은 기존과 같은 0.995~1.006 밴드 안에서 condition별 random walk로
    드리프트합니다.
  - 기존 seed-from-eqp_id 방식으로 결정적으로 생성하여, 같은 장비는 항상 같은
    이력을 반환합니다.
- normalizer: mdc payload에 `docs`와 `settings`를 함께 실어 반환합니다.
- office provider는 이후 동일한 레코드 shape으로 OpenSearch 조회를 구현합니다
  (3단계 배포 전략 — 계약 고정, provider만 교체).

### A4. 시계열 하위 뷰

- 상단에 **condition family 칩**을 둡니다: `800V_HR`, `500V_HR`, 그리고 장비가
  보유한 extras(`3000V_HR`, `Valley`). 기본 선택은 `800V_HR`입니다.
- 0°/90° 쌍이 있는 family (`800V_HR`, `500V_HR`):
  - **x/y trajectory 차트** — x = 0Deg 값, y = 90Deg 값. 각 점은 한 재교정
    시점의 스냅샷입니다. 오래된 점일수록 투명하게 fade 처리하고 최신 점을
    강조하여 드리프트 경로를 보여줍니다. `(1.0, 1.0)`(무보정 기준점)에 참조
    십자선을 표시합니다.
  - **축별 시계열 차트 2개** — 0Deg 추이, 90Deg 추이. 기존 하드웨어 추이
    차트 관례(dataZoom, 시간축 포맷)를 따르되, y축은 **tight 스케일**
    (`scale: true`)을 사용합니다. MDC 값은 1.0 ±0.55% 밴드의 드리프트 자체가
    신호이므로, `stableYRange`의 magnitude-relative 최소 스팬(크기의 25%)을
    적용하면 전부 평평한 선으로 뭉개집니다 (`chartRange.ts` 주석의 "shape
    차트는 tight 유지" 원칙에 해당).
- 쌍이 없는 family (`3000V_HR_0Deg`, `Valley`): x/y 차트 없이 단일 시계열만
  표시합니다.
- `docs` → 차트 시리즈 매핑(0°/90° 쌍 구성, family 분류 포함)은 순수 util
  (`utils/mdcHistory.ts`)로 분리하여 단위 테스트합니다.

### A5. 비교 하위 뷰 (박스플롯)

- 기존 매트릭스 테이블을 제거하고 ECharts **boxplot**으로 대체합니다.
- beam_condition별로 box 1개 — fab 내 tool들의 값 분포(`settings` 기반)를
  나타냅니다. 그 위에 **선택 장비의 값**을 강조 마커(scatter overlay)로 겹쳐,
  fleet 대비 위치를 한눈에 보여줍니다.
- 사분위(quartile) 계산은 순수 util(`utils/boxplotStats.ts`)로 작성하고 단위
  테스트합니다.
- 테이블 제거로 dead code가 되는 `utils/mdcMatrix.ts`(`buildMdcMatrix`,
  `cellDeviation`)와 `mdcMatrix.test.ts`는 함께 삭제합니다.

## Part B. 시계열 차트 BM/PM 오버레이

### B1. 목적

BM/PM 이력 탭에만 있던 유지보수 일시 정보를 다른 탭의 시계열 차트 위에
수직 점선으로 함께 표시합니다. 유지보수(BM/PM) 시점과 장비 상태 지표의
변화(회복·악화)를 같은 시간축에서 바로 대조할 수 있게 하는 것이 목적입니다.

### B2. 범위 (Scope)

- 대상: 시간축(`xAxis.type: 'time'`) 차트 6곳, 탭 기준 5개.
  - BSM 탭 · Sharpness 탭 — 공용 `BsmTrendChart` 1곳 수정으로 함께 적용됩니다.
  - Reso Center 탭 — best-reso 추이 차트.
  - MDC 탭 — 시계열 하위 뷰의 0°/90° 추이 차트 2개 (Part A 신규).
  - FDC 탭 — 시계열 차트 2종.
- 비대상: MDC x/y trajectory·박스플롯, SCE 계수 곡선, BSM 레이더, drift
  scatter(CenterX 축), focus sweep(category 축), FDC index 차트. 시간축이
  아니므로 수직선의 의미가 없습니다.
- 이벤트 범위: **과거(완료) 작업만** 표시합니다. future(예정) 작업은 시간축을
  데이터 범위 밖으로 늘려 추세를 압축시키므로 제외합니다.
- 토글: 페이지 전역 스위치 1개, 기본 **ON** 입니다.

### B3. 데이터 흐름

- `HardwareView`가 기존 서비스 fetch와 별도로 두 번째 `useAsyncData`를
  추가합니다. 캐시 키는 `hardware:bmpm-events:<toolType>:<fab>`이며 선택 장비
  (`selectedTool.eqp_id`) 변경 시 재조회합니다.
- 조회는 기존 엔드포인트 재사용입니다: `fetchService({ service: 'bm-pm', ... })`.
- 백엔드 mock 정합성 수정 1건: `bm_pm_mock.py`는 고정 앵커(`NOW = 2026-05-24`)
  기준으로 날짜를 생성하지만, 추이 차트 mock들(beam_shape 등)은 요청된
  `start`/`end` 윈도우 안에서 데이터를 생성합니다. 이대로면 BM/PM 마커가 전부
  차트 범위 밖으로 잘려 보이지 않으므로, `build_bm_pm_data`가 요청 `end`를
  앵커로 받도록 수정합니다 (같은 `(eqp_id, end)`에 대해 결정적 — 다른 mock들과
  동일한 원칙, 응답 shape 불변).
- 응답 `tables` 중 key `past_work` 섹션의 행을 다음 이벤트 타입으로 매핑합니다.

```ts
export interface BmPmEvent {
  ts: string        // job_starts ("YYYY-MM-DD HH:MM")
  category: 'BM' | 'PM'
  jobEnd: string    // job_end
  note: string      // engr_note
}
```

- fetch 실패 또는 빈 데이터이면 이벤트 배열은 빈 배열이 됩니다. 오버레이만
  조용히 생략되고 차트 본체는 영향을 받지 않습니다.

### B4. 구성 단위

#### B4.1 `front-dev-home/app/utils/bmPmMarkers.ts` (신규, 순수 함수)

Vue 의존성 없는 순수 모듈입니다. `BmPmEvent` 타입과 `bmPmMarkLine(events)`
빌더를 export 합니다. 반환값은 ECharts 시리즈에 spread 할 `markLine` 조각입니다.

- 각 이벤트의 `job_starts`를 epoch(ms)로 변환해 `{ xAxis: epoch }` 엔트리를
  만듭니다.
- 스타일: 수직 **점선**(dashed), BM은 rose(bad) 톤 / PM은 emerald(ok) 톤으로
  BM/PM 이력 탭의 카테고리 칩 색과 대응시킵니다. 라이트/다크 모드별 색 쌍을
  사용합니다.
- 선 상단에 `BM` / `PM` 라벨을 표시하고, hover 시 카테고리 · 작업 시간
  (`job_starts` ~ `job_end`) · 엔지니어 노트를 tooltip으로 보여줍니다.
- 빈 배열 입력이면 `undefined`를 반환해 시리즈에 markLine이 아예 붙지 않게
  합니다.

#### B4.2 `HardwareView.vue`

- BM/PM 이벤트 fetch(§B3)와 토글 상태를 소유합니다:
  `useState('hw-bmpm-overlay', () => true)`.
- 서비스 상세 헤더 행에 `USwitch` "BM/PM 표시"를 배치하되, 시간축 차트가 있는
  5개 탭(BSM · Reso Center · MDC · FDC · Sharpness)에서만 노출합니다.
- 각 차트 패널에 `maintenance-events` prop을 전달합니다. 토글 OFF이면 빈
  배열을 전달해 computed 옵션이 markLine 없이 재계산되게 합니다.
- MDC 패널에는 Part A의 `docs`도 함께 전달합니다.

#### B4.3 차트 패널 배선

| 컴포넌트          | 변경 내용                                                        |
| ----------------- | ---------------------------------------------------------------- |
| `BsmTrendChart`   | `events` prop 추가, 시리즈에 markLine spread                      |
| `BsmPanel`        | prop pass-through (BSM 탭)                                        |
| `SharpnessPanel`  | prop pass-through (Sharpness 탭)                                  |
| `ResoCenterPanel` | best-reso 추이 차트에만 markLine 적용                             |
| `MdcPanel`        | Part A 개편 + 0°/90° 추이 차트 2개에 markLine 적용                |
| `FdcPanel`        | 시계열 차트 2종에 markLine 적용 (index 차트는 제외)               |

### B5. 엣지 케이스

- 가시 범위 밖 이벤트: ECharts가 grid 기준으로 자동 clip 하므로 별도 필터가
  필요 없습니다.
- dataZoom 팬/줌: markLine이 time 좌표에 고정되어 자동으로 따라 움직입니다.
- BM/PM 탭 활성 중에도 이벤트 fetch는 별도 캐시 키로 동작합니다. 가벼운 GET
  1회 중복은 허용합니다 (멱등, mock/office 동일).
- 장비 미선택 상태: 이벤트 fetch를 건너뛰고 빈 배열을 유지합니다.
- MDC 비교(박스플롯) 하위 뷰에는 시간축이 없으므로 토글이 영향을 주지
  않습니다. 토글은 탭 단위로 노출을 유지합니다 (하위 뷰 전환 시 숨기지 않음).

### B6. 테스트

- `node --test` 단위 테스트 (모두 `app/utils/` colocated,
  `npm --prefix front-dev-home test`로 실행):
  - `bmPmMarkers.test.ts` — `past_work` 행 → `BmPmEvent` 매핑,
    `"YYYY-MM-DD HH:MM"` → epoch 변환, BM/PM별 색·라벨 선택, 빈 입력 →
    `undefined` 반환.
  - `mdcHistory.test.ts` — `docs` → family 분류, 0°/90° 쌍 구성, 시계열
    시리즈 매핑, 쌍 없는 condition 처리.
  - `boxplotStats.test.ts` — 사분위 계산 (홀/짝 표본, 소표본, 동일값).
  - `mdcMatrix.test.ts` 삭제 (util 제거에 따라).
- 브라우저 검증: 라이트/다크 모드, MDC 하위 탭 전환, condition family 전환,
  토글 ON/OFF, dataZoom 조작 시 마커 추종, tooltip 내용 확인 후 커밋합니다.
