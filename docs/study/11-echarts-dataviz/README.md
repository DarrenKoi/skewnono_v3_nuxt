# 11. ECharts 데이터 시각화

이 프로젝트는 계측(metrology) 데이터 분석 도구라서 **차트가 UI의 절반**입니다. 시계열, 박스플롯, 웨이퍼 맵, 히트맵, 히스토그램, 산점도 등을 [Apache ECharts](https://echarts.apache.org)로 그립니다.

- 버전: `echarts@^6.1.0` (`import * as echarts from 'echarts'` — full build)
- 래퍼 컴포저블: `composables/useEchart.ts`
- 테마: `composables/useEchartsTheme.ts` + `utils/echartsThemes.ts`
- 팔레트: `utils/chartPalette.ts`

핵심 철학 하나만 기억하세요: **"계산은 순수 TS 유틸에서, 그리기만 ECharts에서."** 통계·좌표 변환은 전부 `utils/*.ts`의 순수 함수가 하고(→ `12-statistics-wafer/`, `13-testing/`), ECharts는 이미 계산된 데이터를 받아 렌더만 합니다. 이렇게 나눠 둬야 테스트와 유지보수가 쉬워집니다.

## 1. 왜 래퍼 컴포저블이 필요한가

ECharts는 Vue 컴포넌트가 아니라 **명령형(imperative) 라이브러리**입니다. `echarts.init(dom)`으로 인스턴스를 만들고, `setOption()`으로 갱신하고, 다 쓰면 `dispose()`로 정리해야 합니다. 이걸 매 차트마다 손으로 하면 다음 버그가 생깁니다.

- resize 리스너를 안 떼서 메모리 누수
- 컴포넌트 unmount 시 `dispose()` 안 해서 유령 인스턴스
- 다크모드 전환 시 테마가 안 바뀜

`useEchart.ts`가 이 라이프사이클 전체를 소유합니다.

## 2. `useEchart.ts` 라이프사이클

```ts
const ensureChart = () => {
  if (chart || !elRef.value) return
  chart = echarts.init(elRef.value, resolvedThemeName.value)
  chart.setOption(optionRef.value)
  bindClick()
  mountDownloadButton()
  if (!resizeHandler) {
    resizeHandler = () => chart?.resize()
    window.addEventListener('resize', resizeHandler)
  }
}

onMounted(() => { ensureChart() })

// 컨테이너가 v-if 안에 있어 토글될 수 있음. 이전 엘리먼트가 unmount되면
// 그 엘리먼트에 묶인 인스턴스를 dispose하고, 새 엘리먼트에 다시 init.
watch(elRef, (next, prev) => {
  if (prev && prev !== next) {
    chart?.dispose()
    chart = null
    unmountDownloadButton()
  }
  if (next) ensureChart()
})

watch(optionRef, (next) => {
  chart?.setOption(next, true)   // 두 번째 인자 true = notMerge
})

// ECharts는 테마를 init 시점에 바인딩. 테마 교체 = 같은 DOM 노드에 dispose + re-init.
watch(resolvedThemeName, () => {
  if (!elRef.value) return
  chart?.dispose()
  chart = null
  unmountDownloadButton()
  ensureChart()
})

onBeforeUnmount(() => {
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
  unmountDownloadButton()
  chart?.dispose()
  chart = null
})
```

읽을 때 주목할 점:

1. **입력은 `elRef`(엘리먼트 ref) + `optionRef`(`ComputedRef<EChartsOption>`).** 옵션이 computed이므로, 소스 데이터가 바뀌면 자동으로 `setOption`이 다시 불립니다. Vue 반응성과 ECharts 명령형 API를 잇는 다리입니다.
2. **`setOption(next, true)`의 `true`는 `notMerge`.** 기본 `setOption`은 이전 옵션과 **병합**하는데, 시리즈 개수가 줄어드는 경우(예: 장비 3대 → 2대) 병합하면 유령 시리즈가 남습니다. `notMerge: true`로 매번 옵션을 통째로 갈아끼웁니다.
3. **테마는 init 시점에 고정된다.** ECharts는 `registerTheme`한 테마를 `init(dom, themeName)`에서만 받습니다. 그래서 다크↔라이트 전환은 옵션 갱신이 아니라 **dispose + 재init**입니다. 위 `watch(resolvedThemeName)`가 정확히 그걸 합니다.
4. **`v-if` 토글 대응.** 차트 컨테이너가 `v-if`로 붙었다 떨어졌다 하면 `elRef`가 바뀝니다. 이전 노드의 인스턴스를 dispose하고 새 노드에 init해야 합니다.
5. **PNG 다운로드 버튼은 raw DOM으로 주입**됩니다(Vue 컴포넌트 아님). 그래서 `dispose()`(호스트 div를 비움)마다 버튼을 다시 mount해야 합니다.

## 3. 테마 — `echartsThemes.ts`

테마는 앱 시작 시 한 번만 등록됩니다(모듈 레벨 `registered` 플래그로 가드).

```ts
export const resolveEchartThemeName = (
  selection: EchartThemeSelection,
  colorMode: string
): EchartThemeName => {
  if (selection !== 'default') return selection
  return colorMode === 'dark' ? 'dark' : 'vintage'
}

export const registerEchartsThemes = (echarts: EchartsModule) => {
  if (registered) return
  Object.entries(themes).forEach(([name, theme]) => {
    echarts.registerTheme(name, theme)
  })
  registered = true
}
```

- 사용자가 고른 테마 + Nuxt `useColorMode()`를 조합해 최종 테마 이름을 결정합니다. 선택이 `'default'`면 다크모드에서 `dark`, 아니면 `matlab`입니다.
- 선택값은 `localStorage`의 `skewnono:echarts-theme`에 저장(이것도 `usePersistedState` 패턴군 — `07-code-patterns/persisted-state.md`).

**투명 배경 트릭**: 등록된 테마는 `backgroundColor: 'transparent'`라서 차트가 자기 카드 표면색을 그대로 투과합니다. 하지만 PNG로 export할 땐 투명 배경이 곤란하므로, `getEchartThemeBackground(name)`이 테마별 불투명 색(`vintage → #fef8ef`, `dark → #100C2A`, 그 외 `#ffffff`)을 제공해 export 시에만 깔아 줍니다.

## 4. 팔레트 — 색이 CSS가 아니라 TS에 있는 이유

`utils/chartPalette.ts`는 색을 **존재 이유** 기준으로 둘로 나눠 둡니다. 이 구분이 이 파일의 핵심입니다.

```ts
// 뜻이 고정된 색 — 테마가 바뀌어도 절대 따라 움직이면 안 됩니다.
export const SK_SCALE = ['#5C86AE', '#9BB6CD', '#E4D9C4', '#DB9A6B', '#C75A3C']
export const SK_STATE = { ok: '#3E8E5E', warn: '#C98A2E', bad: '#C4453B' }

// 보여 주기용 색 — 활성 테마를 따라갑니다.
const sk = useChartPalette()
sk.value.series      // 주 계열
sk.value.brand       // 대비가 필요한 오버레이(회귀선 등)
sk.value.muted       // 축 라벨, 보조선 같은 부속 요소
```

**왜 이렇게 나누나?** low→high 램프와 "spec 위반" 색은 **데이터를 인코딩**합니다. 테마를 바꿨다고 웨이퍼 맵의 색 의미가 달라지면 어제 캡처한 이미지와 비교할 수 없고, `bad`는 어떤 테마에서든 빨강이어야 합니다. 반면 계열 색은 "이건 1번, 저건 2번"이라는 뜻밖에 없으므로 테마를 따라가는 편이 자연스럽습니다.

**왜 CSS 토큰이 아니라 TS 리터럴인가?** ECharts는 `<canvas>`에 그리는데, 캔버스 렌더링 컨텍스트는 CSS custom property(`var(--sk-chart-1)`)를 **해석하지 못합니다.** DOM/SVG는 CSS 변수를 읽지만 캔버스는 실제 색 리터럴이 필요합니다. 그래서 차트 색의 단일 출처는 `chartPalette.ts`이고, `main.css`에는 대응하는 `--sk-chart-*` 토큰을 두지 않습니다. DOM 조각(뱃지, 범례 dot 등)이 차트와 색을 맞춰야 한다면 CSS에 값을 복사하지 말고 `chartPalette.ts`에서 바인딩하십시오. 사본을 두면 반드시 어긋납니다.

이건 캔버스 기반 시각화에서 자주 만나는 함정이니 기억해 두세요.

## 5. 클라이언트 export — 백엔드 없이 PNG 다운로드

이 앱은 SPA라서 "차트를 이미지로 저장"도 브라우저에서 끝냅니다. 서버 왕복이 없습니다.

```ts
const downloadChartImage = () => {
  if (!chart) return
  const url = chart.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: getEchartThemeBackground(resolvedThemeName.value)
  })
  const filename = chartExportFilename(options.exportName, title, new Date())
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
```

- `chart.getDataURL({ type: 'png', pixelRatio: 2 })` → base64 data URL. `pixelRatio: 2`로 레티나 화질.
- `<a download>` 엘리먼트를 만들고 `.click()`을 프로그램적으로 호출 → 브라우저 다운로드 발생.
- 파일명은 **순수 함수** `chartExportFilename`이 생성(제목 slugify + `YYYY-MM-DD` + `.png`). DOM에 의존하지 않아 `node --test`로 테스트됩니다.

> **SVG는 지원하지 않습니다.** ECharts 6은 SVG 렌더러도 있지만, 이 앱의 export 경로는 **PNG 래스터 전용**입니다. (표 export 는 별도 — `12-statistics-wafer/`와 `utils/xlsx.ts` 참고. 2026-09-02 부터 표 내보내기는 전부 `.xlsx` 입니다.)

## 6. 차트를 추가할 때의 표준 절차

1. **데이터 변환 로직을 `utils/`에 순수 함수로 작성** (+ `.test.ts`). 예: `boxplotStats.ts`, `mdcHistory.ts`, `waferPoints.ts`.
2. 컴포넌트에서 그 함수 결과를 `computed<EChartsOption>`으로 조립.
3. `useEchart(elRef, optionRef, { exportName })` 호출.
4. 색은 되도록 지정하지 마십시오 — 계열 색은 ECharts가 테마 팔레트에서 자동으로 배정합니다. 꼭 직접 써야 할 때만 뜻이 고정된 색은 `SK_SCALE`/`SK_STATE`, 테마를 따라갈 색은 `useChartPalette()`를 사용합니다.
5. 다크/라이트 대비를 두 모드에서 모두 확인.

## 7. 참고

- ECharts 옵션 레퍼런스: https://echarts.apache.org/en/option.html
- `useEchart.ts` — 이 프로젝트의 모든 차트가 통과하는 단일 관문
- 통계 유틸의 상세: `12-statistics-wafer/`
- 순수 함수 테스트 규율: `13-testing/`
