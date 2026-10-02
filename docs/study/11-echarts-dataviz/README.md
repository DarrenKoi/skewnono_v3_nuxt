# 11. ECharts: 데이터에서 차트와 선택 좌표까지

차트는 숫자를 화면의 위치·색·모양으로 바꿉니다. 이 문서는 Vue 반응성과 명령형 차트 라이브러리가 만나는 지점을 설명합니다. [02-vue-basics](../02-vue-basics/README.md)에서 `ref`·`computed`·생명주기를 먼저 익히고, 계산 자체는 [12-statistics-wafer](../12-statistics-wafer/README.md)에서 이어집니다.

2026-10-03 기준 `frontend/package.json`의 허용 범위는 `echarts@^6.1.0`, `package-lock.json`의 해석 버전은 **6.1.0**입니다. `useEchart.ts`, `useEchartsTheme.ts`, `echartsThemes.ts`, `chartNearest.ts`, AFM `detail/HeatmapChart.vue`를 확인했습니다. 공식 설명은 [ECharts 6 업그레이드 안내](https://echarts.apache.org/handbook/en/basics/release-note/v6-upgrade-guide/)와 [차트 컨테이너 크기·정리](https://echarts.apache.org/handbook/en/concepts/chart-size/)를 참고합니다. 공식 handbook은 공용 문서이고, 프로젝트의 정확한 옵션은 현재 코드를 기준으로 확인합니다.


DOM(Document Object Model)은 브라우저 문서 객체 구조, API(Application Programming Interface)는 라이브러리를 호출하는 약속입니다. TS는 TypeScript이며 순수 계산과 차트 생명주기를 분리해서 읽습니다.

## 1. 기초: Vue의 값과 캔버스의 그림은 별개입니다

Vue는 템플릿과 반응형 값을 연결합니다. ECharts는 DOM 컨테이너에 인스턴스를 만든 뒤 메서드를 호출하는 라이브러리입니다. `computed` 값이 바뀐 사실만으로 ECharts 화면이 알아서 갱신되지는 않습니다. 둘 사이에서 변경을 감지하고 `setOption()`을 호출해야 합니다.

```text
API rows -> 순수 계산 함수 -> computed<EChartsOption>
                                    |
                              useEchart의 watch
                                    |
                                setOption()
                                    |
                             canvas 화면의 차트
```

이 저장소는 계산을 `utils/*.ts`에, 옵션 조립을 Vue 컴포넌트에, 인스턴스 생명주기를 `useEchart()`에 둡니다. “계산은 순수 TS, 그리기는 ECharts”라는 기존 원칙입니다. 모든 컴포넌트가 통계 공식을 되풀이하지 않으면서, 계산은 브라우저 없이 테스트할 수 있습니다.

## 2. 용어: 옵션을 읽는 최소 어휘

| 용어 | 뜻 | 예 |
| --- | --- | --- |
| Instance | 한 컨테이너에 연결한 살아 있는 차트 객체 | `echarts.init(el, themeId)` |
| Option | 그림의 축·계열·설명을 지정하는 설정 객체 | `EChartsOption` |
| Series | 함께 그릴 데이터 한 묶음 | 장비별 line, 측정점 scatter |
| Axis | 데이터 값을 화면 위치로 바꾸는 기준 | `category`, `value`, `time` |
| Grid | Cartesian 차트가 들어가는 플롯 영역 | 상하 두 패널 각각의 grid |
| Tooltip | 포인터 위치의 데이터를 설명하는 상자 | `trigger: 'axis'` 또는 `'item'` |
| DataZoom | 화면에서 볼 데이터 범위 | 확대된 구간 |
| ZRender | ECharts 아래에서 실제 캔버스 입력·그리기를 처리하는 계층 | `chart.getZr()` |
| Dispose | 인스턴스의 자원과 연결을 정리하는 메서드 | `chart.dispose()` |

`category` 축은 장비 이름·lot 이름 같은 순서 목록입니다. 좌표 2는 목록의 세 번째 칸입니다. `value` 축의 2는 실제 수치 2이고, `time` 축은 시간 좌표입니다. 세 축의 숫자가 같은 타입이어도 의미가 같지 않습니다.

## 3. 현재 구현: 생성·갱신·입력·정리

### 3.1 공통 래퍼가 생명주기를 소유합니다

`useEchart(elRef, optionRef, options)`의 입력은 DOM ref, computed 옵션, 클릭·hover·다운로드 설정입니다. 아래는 API를 설명하는 짧은 사용 예시이며 특정 컴포넌트의 전체 소스는 아닙니다.

```ts
const chartEl = ref<HTMLDivElement | null>(null)
const option = computed<EChartsOption>(() => ({
  xAxis: { type: 'category', data: labels.value },
  yAxis: { type: 'value' },
  series: [{ type: 'line', data: values.value }]
}))
useEchart(chartEl, option, { exportName: 'measurement-trend' })
```

실제 공통 래퍼의 순서는 다음과 같습니다.

1. 테마를 등록하고, DOM이 생긴 `onMounted`에서 `init()`·최초 `setOption()`을 수행합니다.
2. series 클릭, index 클릭, grid 클릭·hover를 필요한 경우 연결합니다.
3. 컨테이너를 `ResizeObserver`로 관찰해 `chart.resize()`를 호출합니다.
4. 옵션이 바뀌면 현재 zoom을 읽고 `withPreservedZoom(next, live)`로 이어 붙여 갱신합니다.
5. 컨테이너가 바뀌거나 테마 ID가 바뀌면 이전 인스턴스를 dispose하고 새로 만듭니다.
6. unmount에서 hover 예약 프레임, observer, 다운로드 버튼, 차트 자원을 정리합니다.

**현재 크기 관찰 대상은 window가 아니라 컨테이너입니다.** 창 크기가 같아도 행 숨기기·패널 높이 변경으로 카드 크기는 변합니다. window resize만 감지하면 캔버스가 이전 높이를 유지할 수 있습니다. 컨테이너에는 초기 크기가 있어야 하며, 숨겨진 상태의 0 크기도 브라우저에서 확인해야 합니다.

옵션 갱신의 `setOption(..., true)`는 `notMerge`입니다. 이전 계열과 병합하지 않으므로 장비가 3대에서 2대로 줄었을 때 남은 가짜 세 번째 선을 방지합니다. 대신 모든 옵션을 다시 주므로 확대 구간이 초기화될 수 있습니다. 프로젝트는 `chartZoom.ts`로 live `dataZoom`을 보존합니다. 테마 재생성과 옵션 갱신은 다른 경로이므로, 모든 종류의 갱신에서 모든 상호작용 상태가 보존된다고 확대 해석하지 않습니다.

### 3.2 클릭에는 두 종류의 대상이 있습니다

series 클릭은 그려진 선·점·막대 요소를 맞혀야 합니다. 빈 플롯을 눌러 가까운 측정점을 선택하는 기능은 `onGridClick`을 사용합니다. `showSymbol: false`인 선에서 작은 표식만 클릭하도록 기대하면 사용자가 쉽게 선택을 놓칩니다.

- `onClick(name)`은 표시 이름을 줍니다. 표시 문자열은 고유 ID가 아닐 수 있습니다.
- `onDataIndex(dataIndex, seriesIndex)`는 해당 series 안의 위치를 줍니다. 호출부가 자신의 데이터 배열로 되돌립니다.
- `onGridClick(detail)`은 포인터의 축 좌표, grid 번호, 축별 한 픽셀의 데이터 크기를 줍니다.
- `onGridHover(detail)`은 호출부가 고른 `{ seriesIndex, dataIndex }`로 tooltip을 보여 줍니다. `null`이면 자신의 hover tooltip을 숨깁니다.

multi-grid에서는 같은 x 값이라도 어느 패널인지에 따라 데이터가 다릅니다. `gridIndex`를 버리고 첫 번째 패널의 배열로만 찾으면 아래 패널 클릭이 위 데이터로 연결됩니다.

### 3.3 category 좌표의 소수를 보존하는 이유

ECharts의 `convertFromPixel()`은 category 축에서 칸의 정수 위치로 snap할 수 있습니다. 프로젝트의 `gridDetail()`은 `convertToPixel()`의 한 단위 기울기를 사용해 **그 칸 안에서 포인터가 어디에 있는지** 소수 좌표를 복원합니다.

```text
칸 중심의 화면 x       100px                 180px
category index          1                     2
포인터 x                           132px
복원한 축 x              1 + (132 - 100) / 80 = 1.4
```

클릭이 1.4인 사실은 최근접 거리를 재는 동안 필요합니다. 곧바로 1로 둥글리면 32px 떨어진 포인터가 칸 중심에 있었다고 계산되어 잘못된 점을 고를 수 있습니다. `gridDetail()`은 signed 기울기로 역방향 축과 화면 y가 아래로 증가하는 방향도 처리합니다.

배열의 한 칸을 고르는 소비자만 `nearestIndex(x, length)`에서 반올림합니다. `nearestIndex(1.4, 3)`은 1, `nearestIndex(1.6, 3)`은 2입니다. 범위 밖·비유한 값은 `null`입니다. **value/time 축에서 x를 배열 인덱스로 반올림하지 않습니다.** 연속 축은 후보들의 실제 x 값과 비교합니다.

`nearestPoint()`는 축별 차이를 `dataPerPixelX/Y`로 나눠 화면 픽셀 거리를 계산합니다. nm와 초처럼 다른 단위를 그냥 더하면 숫자가 큰 축이 선택을 지배합니다. 기본 반경은 44px이고, 그보다 멀면 `null`입니다. 시간 추세처럼 세로 위치가 선택 의도가 아닌 경우에는 `xOnly`가 가능합니다. hover와 클릭에 같은 후보·규칙을 사용해야 설명한 점과 선택한 점이 맞습니다.

hover는 마우스 이동마다 전체 후보를 찾는 대신 animation frame당 최신 위치 한 번을 처리합니다. 옵션 재구성 때 기존 tooltip이 지워지므로 hover의 “이미 표시한 index” 기억도 초기화합니다. dispose 전에 예약 frame을 취소해야 예전 좌표가 새 인스턴스에 dispatch되지 않습니다.

### 3.4 한 점만 남아도 보여야 합니다

선은 적어도 두 점을 이어야 길이가 생깁니다. 필터 결과가 한 점이고 `showSymbol: false`이면 데이터가 있어도 화면이 빈 것처럼 보입니다. AFM `components/afm/detail/HeatmapChart.vue`는 profile line에 다음 규칙을 사용합니다.

```ts
// 현재 profile line의 핵심 옵션을 발췌한 것입니다.
tooltip: { trigger: 'axis', formatter: formatTooltip }
// series 안의 설정입니다.
showSymbol: filtered.value.kept.length === 1
```

한 점이면 표식을 보여 주고, 여러 점에서는 표식을 줄여 복잡도를 낮춥니다. axis tooltip은 선 위의 작은 표식 직접 hit에만 의존하지 않습니다. `HeatmapChart`라는 파일명만 보고 모든 모드가 heatmap이라고 생각하지 않고 현재 선택한 series 종류를 읽습니다. 이 규칙은 해당 컴포넌트에 구현되어 있으며 공통 래퍼가 모든 차트의 single-point 표시를 자동 고쳐 주지는 않습니다.

### 3.5 테마와 색: 데이터 의미와 장식의 경계

`useEchartsTheme()`는 `usePersistedState`로 선택값을 저장하고, 선택·color mode에서 `themeId`, palette, surface를 계산합니다. 기본 선택은 light에서 `matlab`, dark에서 `dark`입니다. 테마 이름만 보는 대신 테마와 light/dark를 조합한 ID를 관찰하므로 둘 중 하나가 바뀌어도 재생성됩니다.

등록 테마의 canvas 배경은 투명하며 카드 표면색이 보입니다. 명시적으로 선택한 테마와 color mode가 다르면 축·글자색도 실제 표면에 맞아야 합니다. PNG는 투명 캔버스 그대로가 아니라 `surface.value.surface`를 배경으로 사용합니다.

`chartPalette.ts`는 의미가 고정된 `SK_SCALE`·`SK_STATE`와 테마에 따라 변하는 series 색을 나눕니다. low→high 램프나 경고 의미는 테마를 바꾸어도 유지해야 합니다. 장비 A·B 계열 색은 활성 palette를 사용할 수 있습니다. DOM 뱃지가 차트 색을 따라야 할 때도 같은 TS 값을 바인딩해 사본을 만들지 않습니다.

canvas 색 설정에 `var(--sk-...)` 문자열을 그대로 주면 DOM의 CSS 계산처럼 해결되지 않습니다. 필요하면 계산한 실제 색을 넘겨야 합니다. 이 프로젝트 차트의 색 경계는 `chartPalette.ts`·`echartsThemes.ts`이고 일반 UI 토큰 규칙은 `DESIGN.md`를 따릅니다.

### 3.6 PNG 저장도 부수효과입니다

`getDataURL({ type: 'png', pixelRatio: 2, backgroundColor })`로 이미지를 만들고 임시 `<a download>`를 클릭합니다. 파일명은 순수 `chartExportFilename()`이 만듭니다. 옵션의 `exportName`, 차트 제목, 기본 이름 순서로 결정합니다.

이 앱의 공통 다운로드는 PNG입니다. ECharts 자체의 SVG renderer 지원이 곧 이 다운로드 기능의 SVG 지원을 뜻하지는 않습니다. 표 저장은 별도 `xlsx.ts` 경로이고 그림 데이터와 표의 원본 수치도 구분합니다.

## 4. 선택 이유와 한계

인스턴스 생명주기를 한곳에 모으면 크기·테마·정리 버그를 개별 차트마다 고칠 필요가 줄어듭니다. ECharts full build를 사용하므로 각 컴포넌트마다 renderer를 등록하는 절차는 없습니다. 새 래퍼·별도 tooltip 선택 엔진을 만들기 전에 기존 함수와 callback을 찾습니다.

순수 좌표 테스트는 실제 canvas hit, 브라우저 크기, tooltip 배치·겹침을 증명하지 못합니다. 한 점·빈 배열·다중 grid·역방향 축·zoom·테마 변경을 실제 화면에서 확인해야 합니다. resize observer가 있어도 의도한 카드 CSS 높이를 만들어 주는 것은 아닙니다.

## 5. 흔한 실수

- category index와 value/time 숫자를 같은 방식으로 배열 접근하면 다른 측정점이 선택됩니다.
- 소수 category 좌표를 너무 일찍 반올림하면 픽셀 거리 계산이 틀어집니다.
- tooltip과 클릭이 별도 반경을 쓰면 “누르면 선택되지만 hover 설명은 없는” 영역이 생깁니다.
- `notMerge`만 보고 zoom 보존을 생략하면 점을 선택할 때 화면이 전체 범위로 돌아갑니다.
- 한 점 profile에서 표식을 숨기면 측정값이 없는 것처럼 보입니다.
- 테마 이름만 저장하고 color mode 대비를 확인하지 않으면 dark 카드에서 축이 안 보일 수 있습니다.
- unmount 정리를 빠뜨리면 observer·frame·인스턴스가 남을 수 있습니다.

## 6. 안전한 실습

먼저 브라우저나 API 없이 순수 함수를 확인합니다. `frontend/`에서 실행합니다.

```bash
node --test app/utils/chartNearest.test.ts app/utils/chartZoom.test.ts \
  app/utils/chartExport.test.ts app/utils/echartsThemes.test.ts
```

Node 24를 사용합니다. Node 실행 파일이 깨져 있다면 정상 설치의 Node 경로를 사용하며 의존성을 새로 설치할 필요는 없습니다. 이어서 작은 값으로 인덱스를 확인합니다.

```bash
node --input-type=module -e 'import { nearestIndex } from "./app/utils/chartNearest.ts"; console.log(nearestIndex(1.4, 3), nearestIndex(1.6, 3), nearestIndex(3, 3))'
```

기대 출력은 `1 2 null`입니다. 출력의 마지막 `null`을 2로 강제하면 플롯 밖을 클릭해도 마지막 점을 선택하는 버그가 됩니다.

브라우저 확인은 이미 실행 중인 집 mock 앱에서 수행할 수 있습니다. 서버를 새로 켜기 전 실행 위치·포트를 확인합니다. 앱은 보통 frontend `:3000`, backend `:5050`이며, 검증 도구 선택은 `.claude/skills/browser-verify/SKILL.md`를 따릅니다.

1. 데이터 여러 점과 한 점만 남기는 필터를 각각 확인합니다. 한 점이 실제로 보이는지 봅니다.
2. 점 주변 빈 영역에서 hover와 클릭이 같은 점을 설명·선택하는지 확인합니다.
3. multi-grid가 있으면 위·아래 패널에서 선택한 데이터를 각각 비교합니다.
4. zoom 후 선택으로 옵션을 다시 만들 때 확대 구간이 유지되는지 확인합니다.
5. light/dark·테마 변경 뒤 축·tooltip·PNG 배경 대비를 확인합니다.

학습 완료 기준은 “차트가 그려졌다”가 아닙니다. category x=1.4를 왜 보존하며, 어느 소비자에서 정수로 바꾸고, 한 점 profile에는 왜 표식이 필요한지를 설명할 수 있어야 합니다.
