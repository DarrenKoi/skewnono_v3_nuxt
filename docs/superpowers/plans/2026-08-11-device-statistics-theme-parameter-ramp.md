# Device Statistics Theme Parameter Ramp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Device Statistics 비교 화면의 파라미터 구간을 선택한 ECharts theme의 차가운 색에서 따뜻한 색으로 이어지는 5단계 램프로 표시합니다.

**Architecture:** 새 순수 유틸리티가 실제 ECharts theme 이름을 받아 테마별 low/high anchor를 RGB로 5단계 보간합니다. 모든 파라미터 차트와 DOM 막대는 `useEchartsTheme().resolvedThemeName`에서 이 유틸리티를 호출하며, 기존 color-mode 전용 고정 램프는 제거합니다.

**Tech Stack:** Nuxt 4, Vue 3 Composition API, TypeScript, ECharts 6, Node test runner

## Global Constraints

- 설계 문서는 `docs/superpowers/specs/2026-08-11-device-statistics-theme-parameter-ramp-design.md`입니다.
- `para_5`는 low anchor, `para_over_16`은 high anchor이며 중간 세 구간은 각각 25%, 50%, 75% RGB 보간값입니다.
- 테마별 anchor는 기존 ECharts series palette에서 선택한 설계 문서의 정확한 색을 사용합니다.
- Settings의 기존 ECharts theme 저장값과 `resolvedThemeName`을 사용합니다. 새 저장소, 설정 UI, 의존성을 추가하지 않습니다.
- 비교 차트, 카드 헤더 범례, Lot 테이블, 상세 모달 막대, 상세 모달 파라미터 추이가 모두 같은 램프를 사용합니다.
- health, violation, outlier 색상과 `운용 레시피수` 차트의 기본 theme 색상은 변경하지 않습니다.
- API, bucket 정의, 합계, 정렬, 문구, 레이아웃은 변경하지 않습니다.
- `.vue` component mounting harness가 없는 저장소이므로 색상 계산은 순수 함수로 자동 검증하고 reactive UI 연결은 실행 중인 앱에서 검증합니다.
- 여러 파일을 수정하므로 실행 시작 시 `superpowers:using-git-worktrees`로 격리된 worktree를 만듭니다.
- 커밋은 이 계획에 적힌 파일만 정확한 path로 지정합니다. `git add -A`, `git add .`, `git commit -a`를 사용하지 않습니다.

## File Structure

| File | Responsibility |
| --- | --- |
| `front-dev-home/app/utils/parameterRamp.ts` | 테마별 anchor와 5단계 RGB 보간 순수 함수 |
| `front-dev-home/app/utils/parameterRamp.test.ts` | anchor 소속, bucket 매핑, 보간, Default 해석 회귀 테스트 |
| `front-dev-home/app/utils/paraTrendSeries.test.ts` | 제거되는 고정 단색 램프 테스트 정리 |
| `front-dev-home/app/components/cdsem/comparison/healthTokens.ts` | health 의미 색상만 유지하고 고정 para 램프 제거 |
| `front-dev-home/app/components/cdsem/comparison/StackedBar.vue` | 표와 모달에서 재사용하는 DOM 막대의 theme 반응형 색상 |
| `front-dev-home/app/components/cdsem/comparison/LotTable.vue` | Lot 카드 범례의 theme 반응형 색상 |
| `front-dev-home/app/components/cdsem/comparison/LotDetailModal.vue` | 상세 모달 범례의 theme 반응형 색상 |
| `front-dev-home/app/components/cdsem/comparison/TrendChart.vue` | 상세 모달 파라미터 추이의 theme 반응형 색상 |
| `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/comparison.vue` | 주 스택 차트와 카드 헤더 범례의 theme 반응형 색상 |

---

### Task 1: Theme-native parameter ramp를 만들고 모든 소비자를 연결합니다

**Files:**

- Create: `front-dev-home/app/utils/parameterRamp.ts`
- Create: `front-dev-home/app/utils/parameterRamp.test.ts`
- Modify: `front-dev-home/app/utils/paraTrendSeries.test.ts`
- Modify: `front-dev-home/app/components/cdsem/comparison/healthTokens.ts`
- Modify: `front-dev-home/app/components/cdsem/comparison/StackedBar.vue`
- Modify: `front-dev-home/app/components/cdsem/comparison/LotTable.vue`
- Modify: `front-dev-home/app/components/cdsem/comparison/LotDetailModal.vue`
- Modify: `front-dev-home/app/components/cdsem/comparison/TrendChart.vue`
- Modify: `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/comparison.vue`

**Interfaces:**

- Consumes: `EchartThemeName`, `getEchartThemePalette()`, `resolveEchartThemeName()`, `PARA_KEYS`, `ParaKey`, `useEchartsTheme().resolvedThemeName`.
- Produces: `PARAMETER_RAMP_ANCHORS`와 `buildParameterRamp(themeName): Record<ParaKey, string>`.

- [ ] **Step 1: 순수 함수의 실패 테스트를 작성합니다**

`front-dev-home/app/utils/parameterRamp.test.ts`를 다음 내용으로 생성합니다.

```ts
import assert from 'node:assert/strict'
import test from 'node:test'
import {
  ECHART_THEME_OPTIONS,
  getEchartThemePalette,
  resolveEchartThemeName,
  type EchartThemeName
} from './echartsThemes.ts'
import { PARA_KEYS } from './paraTrendSeries.ts'

const themeNames = ECHART_THEME_OPTIONS
  .map(option => option.value)
  .filter((value): value is EchartThemeName => value !== 'default')

const parameterRamp = async () => {
  const loaded = await import('./parameterRamp.ts').catch(() => null)
  assert.ok(loaded, 'parameter ramp module must exist')
  return loaded
}

test('every real theme has anchors taken from its own series palette', async () => {
  const { PARAMETER_RAMP_ANCHORS } = await parameterRamp()
  for (const name of themeNames) {
    const palette = getEchartThemePalette(name).map(color => color.toLowerCase())
    const [low, high] = PARAMETER_RAMP_ANCHORS[name]
    assert.ok(palette.includes(low.toLowerCase()), `${name} low anchor is outside its palette`)
    assert.ok(palette.includes(high.toLowerCase()), `${name} high anchor is outside its palette`)
  }
})

test('every ramp maps the cool end to para_5 and the warm end to para_over_16', async () => {
  const { buildParameterRamp, PARAMETER_RAMP_ANCHORS } = await parameterRamp()
  for (const name of themeNames) {
    const ramp = buildParameterRamp(name)
    const [low, high] = PARAMETER_RAMP_ANCHORS[name]
    assert.deepEqual(Object.keys(ramp).sort(), [...PARA_KEYS].sort())
    assert.equal(ramp.para_5, low.toLowerCase())
    assert.equal(ramp.para_over_16, high.toLowerCase())
    assert.equal(new Set(Object.values(ramp)).size, PARA_KEYS.length)
  }
})

test('MATLAB ramp uses deterministic 25 percent RGB steps', async () => {
  const { buildParameterRamp } = await parameterRamp()
  assert.deepEqual(buildParameterRamp('matlab'), {
    para_over_16: '#a2142f',
    para_16: '#7a2c53',
    para_13: '#514376',
    para_9: '#295b9a',
    para_5: '#0072bd'
  })
})

test('Default follows MATLAB in light mode and Dark in dark mode', async () => {
  const { buildParameterRamp } = await parameterRamp()
  assert.deepEqual(
    buildParameterRamp(resolveEchartThemeName('default', 'light')),
    buildParameterRamp('matlab')
  )
  assert.deepEqual(
    buildParameterRamp(resolveEchartThemeName('default', 'dark')),
    buildParameterRamp('dark')
  )
})
```

- [ ] **Step 2: 새 테스트가 올바른 이유로 실패하는지 확인합니다**

Run: `cd front-dev-home && node --test app/utils/parameterRamp.test.ts`

Expected: FAIL with `AssertionError: parameter ramp module must exist`. RED는 module
loader error가 아니라 아직 없는 동작을 명시한 assertion으로 실패해야 합니다.

- [ ] **Step 3: 테마별 anchor와 RGB 보간 함수를 구현합니다**

`front-dev-home/app/utils/parameterRamp.ts`를 다음 내용으로 생성합니다.

```ts
import type { EchartThemeName } from './echartsThemes.ts'
import type { ParaKey } from './paraTrendSeries.ts'

export const PARAMETER_RAMP_ANCHORS = {
  vintage: ['#61a0a8', '#d87c7c'],
  dark: ['#4992ff', '#ff6e76'],
  macarons: ['#5ab1ef', '#c05050'],
  infographic: ['#60C0DD', '#C1232B'],
  shine: ['#0098d9', '#c12e34'],
  roma: ['#6699FF', '#E01F54'],
  matlab: ['#0072BD', '#A2142F']
} as const satisfies Record<EchartThemeName, readonly [string, string]>

const parseHex = (value: string): [number, number, number] => {
  const hex = value.slice(1)
  return [
    Number.parseInt(hex.slice(0, 2), 16),
    Number.parseInt(hex.slice(2, 4), 16),
    Number.parseInt(hex.slice(4, 6), 16)
  ]
}

const mixHex = (low: string, high: string, position: number): string => {
  const from = parseHex(low)
  const to = parseHex(high)
  const channels = from.map((value, index) =>
    Math.round(value + (to[index]! - value) * position)
      .toString(16)
      .padStart(2, '0')
  )
  return `#${channels.join('')}`
}

export const buildParameterRamp = (themeName: EchartThemeName): Record<ParaKey, string> => {
  const [low, high] = PARAMETER_RAMP_ANCHORS[themeName]
  return {
    para_over_16: mixHex(low, high, 1),
    para_16: mixHex(low, high, 0.75),
    para_13: mixHex(low, high, 0.5),
    para_9: mixHex(low, high, 0.25),
    para_5: mixHex(low, high, 0)
  }
}
```

- [ ] **Step 4: 순수 함수 테스트를 통과시킵니다**

Run: `cd front-dev-home && node --test app/utils/parameterRamp.test.ts`

Expected: 4 tests PASS.

- [ ] **Step 5: `StackedBar.vue`를 theme 반응형 램프로 전환합니다**

`useColorMode`, `paraColors`, `paraColorsDark`, `paraOrder` import를 제거하고 다음 import와 computed를 사용합니다.

```ts
import { buildParameterRamp } from '~/utils/parameterRamp'
import { PARA_KEYS } from '~/utils/paraTrendSeries'

const paraOrder = PARA_KEYS
const { resolvedThemeName } = useEchartsTheme()
const palette = computed(() => buildParameterRamp(resolvedThemeName.value))
```

기존 `segments`, `visibleSegments`, `emptyFlex`, `ariaLabel`은 `paraOrder`와 `palette.value`를 계속 사용하므로 계산 로직을 변경하지 않습니다.

- [ ] **Step 6: `LotTable.vue`와 `LotDetailModal.vue`의 범례를 같은 램프로 전환합니다**

두 파일 모두 `healthTokens`에서는 health 관련 export만 import합니다. 각각 다음 import와 선언을 추가합니다.

```ts
import { buildParameterRamp } from '~/utils/parameterRamp'
import { PARA_KEYS } from '~/utils/paraTrendSeries'

const paraOrder = PARA_KEYS
const { resolvedThemeName } = useEchartsTheme()
const paraPalette = computed(() => buildParameterRamp(resolvedThemeName.value))
```

`LotTable.vue`와 `LotDetailModal.vue`의 기존 `colorMode`와 `isDark`는 health badge 색상을 위해 유지합니다. 기존 `isDark ? paraColorsDark : paraColors` computed만 제거합니다.

- [ ] **Step 7: 상세 모달의 `TrendChart.vue`를 같은 램프로 전환합니다**

`useColorMode`와 고정 palette import를 제거하고 다음 import와 선언으로 교체합니다.

```ts
import { buildParameterRamp } from '~/utils/parameterRamp'

const { resolvedThemeName, surface } = useEchartsTheme()
const palette = computed(() => buildParameterRamp(resolvedThemeName.value))
```

`itemStyle`, `lineStyle`, `areaStyle`, `endLabel`은 모두 기존 `pal[s.key]`를 그대로 사용합니다. `SYMBOLS`도 유지하여 색상 외 식별 수단을 보존합니다. “single hue”라고 설명하는 기존 주석은 “theme-derived cool-to-warm ramp”로 고쳐 실제 동작과 맞춥니다.

- [ ] **Step 8: comparison page의 주 차트와 카드 범례를 같은 램프로 전환합니다**

고정 palette import를 제거하고 다음 import와 선언을 사용합니다.

```ts
import { buildParameterRamp } from '~/utils/parameterRamp'
import { PARA_KEYS } from '~/utils/paraTrendSeries'

const paraOrder = PARA_KEYS
const { resolvedThemeName } = useEchartsTheme()
const paraPalette = computed(() => buildParameterRamp(resolvedThemeName.value))
```

기존 `colorMode`는 `chartInk`가 카드의 Light/Dark mode와 대비하도록 계속 사용합니다. `stackedOption`의 series 색과 header legend가 동일한 `paraPalette`를 읽게 하고, `availRecipeOption`은 수정하지 않습니다.

- [ ] **Step 9: 고정 램프와 낡은 테스트를 제거합니다**

`healthTokens.ts`에서 parameter category palette 설명, `paraColors`, `paraColorsDark`, `paraOrder`를 제거하고 health token만 남깁니다.

`paraTrendSeries.test.ts`에서는 다음 항목만 제거합니다.

- `healthTokens.ts`의 `paraColors`, `paraColorsDark`, `paraOrder` import
- `PARA_KEYS matches the token module paraOrder` 테스트
- `// --- palette ramp ---` 아래의 단일 hue, lightness, key-set 테스트 전체

`series come back in PARA_KEYS order` 테스트는 bucket 순서 회귀를 계속 지키므로 유지합니다.

- [ ] **Step 10: focused 자동 검증을 실행합니다**

Run:

```bash
cd front-dev-home
node --test app/utils/parameterRamp.test.ts app/utils/paraTrendSeries.test.ts
rg -n "paraColors|paraColorsDark" app
rg -l "buildParameterRamp" \
  app/components/cdsem/comparison/StackedBar.vue \
  app/components/cdsem/comparison/LotTable.vue \
  app/components/cdsem/comparison/LotDetailModal.vue \
  app/components/cdsem/comparison/TrendChart.vue \
  app/pages/ebeam/cd-sem/device-statistics/comparison.vue
```

Expected:

- 두 test 파일이 모두 PASS합니다.
- 첫 `rg`는 exit 1이며 결과가 없습니다.
- 두 번째 `rg`는 지정한 5개 consumer 파일을 모두 출력합니다.

- [ ] **Step 11: 프런트엔드 전체 gate를 실행합니다**

Run:

```bash
cd front-dev-home
npm test
npm run typecheck
npm run lint
```

Expected: 세 명령 모두 exit 0입니다.

- [ ] **Step 12: 실행 중인 앱에서 theme와 surface를 검증합니다**

worktree의 repo root에서 main checkout의 virtualenv를 사용해 backend를
`/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python index.py`로 실행하고,
`front-dev-home/`에서 `npm run dev`를 실행합니다. Browser 도구로 다음을 확인합니다.

1. `/settings`에서 Light mode + MATLAB을 선택합니다.
2. `/ebeam/cd-sem/device-statistics`에서 Lot을 2개 이상 선택하고 comparison으로 이동합니다.
3. `파라미터 분포 (스택)`에서 `para_5`가 MATLAB blue, `para_over_16`이 MATLAB dark red이며 중간 bucket이 연속된 색인지 확인합니다.
4. 카드 header legend, ECharts stack, Lot table bar가 같은 bucket 색을 쓰는지 확인합니다.
5. Lot 상세 modal을 열어 modal bar, legend, `파라미터 추이`의 line/stack 색이 같은지 확인합니다.
6. `/settings`에서 Dark theme와 Dark mode를 선택한 뒤 같은 화면으로 돌아와 모든 surface가 blue-to-red Dark palette로 즉시 바뀌고 label/axis가 읽히는지 확인합니다.
7. 0인 segment가 나타나지 않고, tooltip/title/aria-label과 숫자 표시가 기존대로인지 확인합니다.

Expected: 두 theme와 두 color mode에서 색상 연결과 가독성이 유지되며 layout 변화가 없습니다.

- [ ] **Step 13: 직접 수정한 파일만 커밋합니다**

```bash
git add \
  front-dev-home/app/utils/parameterRamp.ts \
  front-dev-home/app/utils/parameterRamp.test.ts \
  front-dev-home/app/utils/paraTrendSeries.test.ts \
  front-dev-home/app/components/cdsem/comparison/healthTokens.ts \
  front-dev-home/app/components/cdsem/comparison/StackedBar.vue \
  front-dev-home/app/components/cdsem/comparison/LotTable.vue \
  front-dev-home/app/components/cdsem/comparison/LotDetailModal.vue \
  front-dev-home/app/components/cdsem/comparison/TrendChart.vue \
  front-dev-home/app/pages/ebeam/cd-sem/device-statistics/comparison.vue
git diff --cached --check
git commit -m "feat(device-statistics): follow chart theme in parameter ramps"
```

Expected: 커밋에는 위 9개 파일만 포함됩니다. push는 사용자가 별도로 요청할 때만 수행합니다.
