# activity Sparkline ECharts 전환 설계

작성일: 2026-08-07
대상: `front-dev-home/app/components/activity/Sparkline.vue`

## 변경 이력

**2026-08-08 — 줌 기능 철회.** 실제로 붙여 본 뒤 슬라이더가 64px 호스트의 3분의 1을
차지하면서 컨트롤이 아니라 장식처럼 읽힌다고 판단해 걷어냈습니다. 이 문서에서 줌 관련
설계(`zoomable` prop, `dataZoom`, `h-24` 호스트, 줌일 때 날짜 줄 숨김)는 모두
철회되었으며 아래 본문은 그 결과로 수정되었습니다. **툴팁은 그대로 남습니다.**

ECharts 전환의 근거가 툴팁 하나로 좁아졌지만 전환 자체는 유지합니다. 툴팁만으로도 히트
영역 계산·커서 위치 역산을 직접 쓰지 않아도 되고, 하드코딩 hex를 `chartPalette` 정책 아래로
가져온 것은 줌과 무관하게 남는 이득이기 때문입니다.

## 배경

`/activity` 페이지의 "30일 활동" 막대는 손으로 작성한 SVG입니다. 하루당 `<rect>` 하나를
`viewBox="0 0 300 60"` 안에 배치하고, `preserveAspectRatio="none"`으로 컨테이너 폭에
늘리는 방식입니다. 축도 툴팁도 없기 때문에 차트 라이브러리 없이도 충분했습니다.

이제 날짜별 툴팁이 필요해졌습니다.

| 요구 | 손코딩 SVG로 구현할 경우 |
| --- | --- |
| 날짜별 툴팁 / hover | 히트 영역 계산, 커서 위치→인덱스 역산, 툴팁 위치 보정을 직접 작성해야 합니다 |

`composables/useEchart.ts`가 이미 제공하는 것이므로, 이 컴포넌트를 ECharts로 전환합니다.

## 범위

전환 대상은 `Sparkline.vue` **하나뿐입니다.**

`FeatureBarList.vue`는 전환하지 않습니다. 그것은 차트가 아니라 "비율 막대가 붙은 목록"이고,
ECharts로 옮기면 `truncate` + `title` 툴팁, 스크린리더 접근성, 항목 수에 따른 가변 높이를
모두 캔버스 위에서 다시 구현해야 합니다. 얻는 기능은 없고 코드만 늘어납니다.

## 소비처와 차이

`Sparkline`은 두 곳에서 쓰입니다.

| 위치 | 맥락 | 색 역할 |
| --- | --- | --- |
| `activity.vue:128` | "30일 활동" 단독 카드 | `series` |
| `activity.vue:576` | 사용자 상세 확장 행, `lg:grid-cols-3`의 1/3 폭 | `brand` |

두 소비처는 색만 다르고 동작은 같습니다. 처음에는 단독 카드에만 줌을 주려 했으나
(확장 행은 폭이 3분의 1이라 슬라이더가 막대를 삼킴), 실제로는 단독 카드에서도 64px 중
20px를 슬라이더가 가져가 같은 문제가 났습니다. 그래서 줌 자체를 걷어냈습니다.

확장 행은 사용자마다 인스턴스가 하나씩 생기지만 누수는 없습니다. `useEchart.ts:237-273`이
`elRef` 변경 시와 `onBeforeUnmount`에서 `dispose()`를 호출하고 `ResizeObserver`도
해제하므로, 행을 접으면 인스턴스가 함께 사라집니다.

## 컴포넌트 경계

두 파일로 나눕니다.

### `app/utils/activitySparkline.ts` (신규)

ECharts option을 만드는 순수 함수입니다. `echarts`를 import하지 않습니다.

```ts
export const buildSparklineOption = (
  series: DailyCount[],
  barColor: string
): EChartsOption
```

색은 문자열 하나만 받습니다. 이 모듈은 `echarts`를 import하지 않으므로 `npm test`(node
--test)가 그대로 실행할 수 있습니다.

날짜 포맷(`MM.DD`)과 합계 계산도 여기로 옮깁니다.

### `app/components/activity/Sparkline.vue` (재작성)

차트 호스트와 주변 HTML만 담당합니다.

```ts
props: {
  series: DailyCount[]
  tone?: 'series' | 'brand'   // 기본 'series'
}
```

`color` prop(`'from-sky-400 to-violet-500'` 같은 Tailwind 클래스 문자열)은 `tone`으로
교체합니다. 색 값 자체는 `useChartPalette()`가 돌려주는 `series` / `brand` 역할에서
읽습니다.

## 색

기존 `GRADIENT_MAP`의 하드코딩 hex(`#38bdf8`, `#8b5cf6`, ...)는 삭제합니다.

`app/assets/css/main.css:175-177`이 정책을 명시하고 있습니다.

> No `--sk-chart-*` here: ECharts draws to canvas and can't read custom
> properties, so chart color lives in `utils/chartPalette.ts`. Bind from there
> rather than add a second copy that drifts.

따라서 전환 후 색은 `useChartPalette()` → `ChartPalette`의 역할 토큰에서 옵니다.

| 소비처 | `tone` | 막대 색 |
| --- | --- | --- |
| 메인 카드 | `series` | `palette.series` |
| 확장 행 | `brand` | `palette.brand` |

두 인스턴스가 서로 다른 색을 갖는다는 기존 성질은 유지되며, 이제 테마를 바꾸면 함께
따라옵니다. 하드코딩 hex일 때는 따라오지 않았습니다.

시각적으로 달라지는 점을 분명히 적어둡니다. **그라디언트를 버리고 단색으로 갑니다.**
기존 가로 그라디언트는 왼쪽(오래된 날짜)에서 오른쪽(최근)으로 색상이 이동했는데, 이는
데이터에 없는 의미를 암시합니다. 날짜에 따라 색이 달라질 이유가 없기 때문입니다.

`ChartPalette`에 `brand`의 연한 짝(`brandSoft`)이 없다는 실무적 이유도 있습니다.
`seriesSoft`는 `series`에서 파생된 색이므로 `brand`와 짝지으면 서로 다른 색상 간
이동이 되어, 없애려던 성질이 그대로 돌아옵니다.

## 차트 구성

캔버스는 막대만 그립니다. 축 선, 축 라벨, 눈금은 모두 끕니다.

- `grid`: `{ left: 0, right: 0, top: 2, bottom: 2, containLabel: false }`
- `xAxis`: `type: 'category'`, `data` = ISO 날짜, `axisLine`/`axisTick`/`axisLabel` 비표시
- `yAxis`: `type: 'value'`, 전부 비표시, `min: 0`
- `series`: `type: 'bar'`, `barCategoryGap: '20%'`, `itemStyle.borderRadius: [1.5, 1.5, 0, 0]`
- `tooltip`: `trigger: 'axis'`, `axisPointer.type: 'shadow'`, formatter는 `MM.DD · N건`

합계 라벨(차트 위)과 양끝 날짜(차트 아래)는 **HTML로 그대로 유지합니다.** 캔버스 안에
축을 그리면 64px 중 상당 부분을 축이 가져가 막대가 뭉개집니다. 기존 레이아웃 계약을
지키는 쪽이 안전합니다.

`dataZoom`은 넣지 않습니다. 호스트 높이는 두 소비처 모두 `h-16`이고, 양끝 날짜 HTML도
항상 표시합니다. 줌을 붙였다가 걷어낸 경위는 맨 위 "변경 이력"에 있습니다.

## 빈 상태

`maxCount === 0`이면 지금처럼 "30일간 활동이 없습니다." 문구를 렌더하고 **차트를 만들지
않습니다.** `v-if`로 호스트 div 자체를 걸러내므로 빈 데이터에서는 ECharts 인스턴스가
생성되지 않습니다. 사용자 목록에 활동 없는 사용자가 많을 때 이 조건이 실질적인 비용
차이를 만듭니다.

## 테스트

두 갈래로 유지합니다.

### `app/utils/activitySparkline.test.ts` (신규)

`buildSparklineOption`에 대한 순수 함수 테스트입니다.

- 시리즈 길이와 `series[0].data` 길이가 일치할 것
- 막대 값이 입력 `count`와 순서대로 1:1 대응할 것
- `dataZoom`이 존재하지 않을 것 (줌 철회를 테스트로 못박아, 나중에 다시 넣으려면
  테스트와 먼저 다퉈야 하도록)
- `grid.bottom`이 2일 것 — 막대 아래에 아무것도 놓이지 않음
- 넘긴 `barColor`가 `series[0].itemStyle.color`에 반영될 것
- 빈 시리즈에서 예외 없이 빈 `data`를 돌려줄 것
- 날짜 포맷이 `MM.DD`일 것

### `app/components/activity/Sparkline.test.ts` (개작, 삭제하지 않음)

기존 테스트는 SFC의 **템플릿만** 컴파일해 가짜 `data`로 SSR 렌더한 뒤 "합계는 위, 날짜는
아래"라는 DOM 순서를 검증합니다. 스크립트를 실행하지 않으므로 ECharts도 Nuxt 런타임도
필요하지 않습니다. 즉 이 테스트는 전환 후에도 유효합니다.

바꿀 것은 앵커 하나뿐입니다. `<svg>`를 찾던 자리를 차트 호스트 `div`(`data-testid="sparkline-canvas"`)로
교체합니다. 커버리지 성격은 그대로 "주변 HTML의 배치"입니다.

## 변경 파일

| 파일 | 성격 |
| --- | --- |
| `app/utils/activitySparkline.ts` | 신규 |
| `app/utils/activitySparkline.test.ts` | 신규 |
| `app/components/activity/Sparkline.vue` | 재작성 |
| `app/components/activity/Sparkline.test.ts` | 앵커 교체 |
| `app/pages/activity.vue` | 호출부 2곳의 prop 교체 |

## 검증

- `npm test` — 신규 util 테스트와 개작한 컴포넌트 테스트가 모두 통과할 것
- `npm run typecheck`
- `npm run lint`
- `npm run lint:md` (이 문서)
- 브라우저 확인: `/activity`에서 (1) 막대 hover 시 툴팁, (2) 두 sparkline 어디에도 줌
  슬라이더가 없을 것, (3) 사용자 행을 펼쳤을 때 확장 행 sparkline이 다른 색으로 뜰 것,
  (4) 활동 없는 사용자에서 빈 상태 문구, (5) 다크 모드에서 막대가 보일 것

## 하지 않는 것

- `FeatureBarList.vue` 전환
- 범용 미니 차트 컴포넌트(`components/chart/MiniBar.vue`) 신설 — 소비처가 둘뿐이라
  추상화를 지탱할 근거가 없습니다. 세 번째 소비처가 생기면 그때 승격합니다.
- `ChartFrame.vue` 재사용 — `h-80` 고정 높이와 "측정을 선택하세요" 빈 상태가 박혀 있어
  activity에 맞지 않습니다. 이름만 재사용이고 실익이 없습니다.
