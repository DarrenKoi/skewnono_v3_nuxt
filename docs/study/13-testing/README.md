# 13. 테스트 전략 (`node:test` 순수 함수 규율)

예전 학습 노트(`07-code-patterns/`)는 "단위 테스트 기반 마련"을 *다음에 해볼 일*로 적어 두었습니다. 그 일이 **현실이 되어** 지금 프론트엔드에는 57개의 `*.test.ts` 파일이 있습니다. 이 문서는 그 테스트 규율을 다룹니다.

핵심 결정 하나: **Vitest도 Jest도 쓰지 않습니다. Node 내장 테스트 러너(`node --test`)만 씁니다.**

## 1. 왜 Vitest가 아니라 `node --test`인가

```json
// package.json
"scripts": {
  "test": "node --test \"app/**/*.test.ts\""
}
```

- `node:test` + `node:assert/strict`는 **Node에 기본 내장**되어 별도 의존성이 없습니다. 오프라인/폐쇄망 정책과 잘 맞습니다(설치할 게 없음).
- 최신 Node는 `.ts`를 **네이티브 type-stripping**으로 실행하므로 트랜스파일 설정이 필요 없습니다.
- 테스트 대상이 **순수 함수**뿐이라 브라우저 DOM·jsdom·Vue 렌더링을 쓸 일이 없습니다. Vitest의 강점(컴포넌트 마운트, jsdom)을 살릴 데가 없으니 도입 비용만 떠안는 셈입니다.

테스트 파일 예:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { detectDeviceOutliers } from './outlierDetect.ts'   // ← 명시적 .ts 확장자!

test('value exactly at threshold is not flagged', () => {
  const result = detectDeviceOutliers([...])
  assert.equal(result.outlier_count, 0)
})
```

## 2. `.ts` 확장자를 명시하는 이유

`node --test`는 sibling 모듈을 import할 때 **확장자를 생략할 수 없습니다** — `./outlierDetect`가 아니라 `./outlierDetect.ts`로 써야 합니다. 그런데 이건 보통의 TS/Vue 규칙과 충돌하므로 `nuxt.config.ts`에서 두 가지를 조정합니다(자세히는 `06-vite-config/` 2.12절).

```ts
typescript: {
  tsConfig: {
    exclude: ['../app/**/*.test.ts'],           // vue-tsc가 node:test 파일을 타입체크 안 하게
    compilerOptions: {
      allowImportingTsExtensions: true           // .ts 확장자 import 허용
    }
  }
}
```

- `exclude` — 앱 타입체크(`vue-tsc`)가 `import { test } from 'node:test'`나 `.ts` 확장자를 보고 에러 내지 않도록 테스트 파일을 앱 컴파일에서 제외.
- `allowImportingTsExtensions` — 명시적 `.ts` import를 TS 컴파일러가 허용.

## 3. "순수 함수 + 콜로케이트 테스트"가 무엇을 강제하나

패턴: **로직을 프레임워크에서 떼어내 순수 함수로 만들고, 바로 옆에 `X.test.ts`를 둔다.**

```text
utils/outlierDetect.ts        ← 순수 함수 (DOM/Nuxt/Vue import 0)
utils/outlierDetect.test.ts   ← 바로 옆 테스트
utils/waferGeometry.ts
utils/waferGeometry.test.ts
utils/csvDownload.ts
utils/csvDownload.test.ts
...
```

이 규율이 아키텍처에 주는 압력이 중요합니다.

1. **테스트 가능성이 곧 좋은 경계.** 함수가 DOM이나 `useRuntimeConfig()`에 의존하면 `node --test`로 못 돌립니다. 그래서 자연스럽게 **계산(순수)과 부수효과(fetch/DOM)를 분리**하게 됩니다. `11-echarts-dataviz/`의 "계산은 순수 TS, 그리기만 ECharts"가 정확히 이 압력의 결과입니다.
2. **엣지 케이스가 명세가 된다.** 예: `outlierDetect.test.ts`는 "빈 배열 → median 0", "임계값과 정확히 같으면 이상치 아님(`>`이지 `>=`아님)"을 못박습니다. 이런 미묘한 경계는 코드만 봐선 잊히지만, 테스트가 살아있는 명세로 지켜 줍니다.
3. **부수효과는 순수 조각으로 쪼갠다.** `csvDownload.ts`는 CSV 문자열을 만드는 순수 `buildCsvContent`(테스트 가능)와, 실제 다운로드를 트리거하는 `downloadCsvRaw`(DOM 필요, 테스트 안 함)를 **분리**합니다. 테스트할 수 없는 부분을 최소화하는 전형적 기법입니다.

```ts
// 순수 — 테스트됨
export const buildCsvContent = (headers: string[], rows: unknown[][]): string => {
  const headerRow = headers.map(escapeCsvValue).join(',')
  const bodyRows = rows.map(row => row.map(escapeCsvValue).join(','))
  return [headerRow, ...bodyRows].join('\r\n')
}

// 부수효과 — DOM Blob/anchor, 테스트 대상 아님. import.meta.client 가드.
export const downloadCsvRaw = (filename: string, content: string): void => {
  if (!import.meta.client || content.length === 0) return
  const blob = new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8;' })
  ...
}
```

## 4. 백엔드 테스트 — `pytest`

프론트가 `node --test`라면, 백엔드(`back_dev_home/`)는 `pytest`입니다. Provider 아키텍처(`10-backend-providers/`)의 완료 기준이 곧 테스트 green입니다.

```bash
# mock provider로 테스트 (집에서 기본)
.venv/bin/pytest back_dev_home/sem_list

# office provider로 테스트 (회사에서 실제 소스 연결 검증)
SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/pytest back_dev_home/sem_list
```

각 기능의 `tests/`와 `__fixtures__/`가 계약(`contracts.py`) 준수를 강제합니다. 예: `msr_file/tests/test_contract.py`는 mock이 특정 메타데이터 필드를 **지어내지 못하게** 막습니다.

## 5. E2E — Playwright (별도 계층)

`@playwright/test`는 devDependency로, 순수 단위 테스트와는 **다른 계층**입니다. 실제 브라우저에서 앱을 띄워 UI 흐름을 검증합니다(예: `useSemList()` 통합 후 네트워크 요청이 3건→1건으로 줄었는지 측정 — `07-code-patterns/sem-list-caching.md` 4.3절).

- 스크린샷은 `.playwright-mcp/screenshots/`에 저장(루트 `CLAUDE.md` 규칙).
- 원격 개발 환경에서는 Tailscale IP로 접속해 스크린샷을 찍습니다.

## 6. 테스트 3계층 정리

| 계층 | 도구 | 대상 | 명령 |
| --- | --- | --- | --- |
| 순수 단위 (프론트) | `node --test` | `utils/*.ts` 순수 함수 | `npm test` |
| 단위/통합 (백엔드) | `pytest` | provider 어댑터, 계약 준수 | `pytest back_dev_home/<feature>` |
| E2E (브라우저) | Playwright | 실제 UI 흐름·네트워크 | `npx playwright test` |

## 7. 커밋 전 체크리스트 (갱신판)

```bash
npm run lint        # ESLint (스타일 + 정적 분석)
npm run typecheck   # vue-tsc 타입 체크 (테스트 파일은 제외됨)
npm test            # node --test 순수 단위 테스트
npm run build       # 빌드 통과 확인
```

## 8. 이 챕터의 큰 교훈

- **테스트 러너도 의존성입니다.** 순수 함수만 테스트하면 Vitest의 무게 없이 Node 내장 러너로 충분합니다.
- **테스트 가능성 = 좋은 경계.** "이걸 어떻게 테스트하지?"가 안 풀리면, 보통 계산과 부수효과가 안 갈라진 것입니다.
- **엣지 케이스는 테스트에 박제합니다.** `>` vs `>=`, 빈 배열, `NaN`/`null` — 코드는 잊지만 테스트는 기억합니다.
- **부수효과(DOM/fetch)는 얇게, 순수 로직은 두껍게.** 테스트 못 하는 부분을 최소 표면적으로.
