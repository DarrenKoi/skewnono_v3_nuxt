# 13. 테스트 전략 (`node:test` 순수 함수 규율)

예전 학습 노트(`07-code-patterns/`)는 "단위 테스트 기반 마련"을 *다음에 해볼 일*로 적어 두었습니다. 그 일이 **현실이 되어** 지금 프론트엔드에는 77개의 `*.test.ts` 파일이 있습니다. 이 문서는 그 테스트 규율을 다룹니다.

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
3. **부수효과는 순수 조각으로 쪼갠다.** 표 내보내기는 칸을 눕히는 순수 `toSheetRows`(`tableExport.ts`, 테스트 가능)와, 워크북을 만들어 다운로드를 트리거하는 `downloadTable`(`xlsx.ts` — DOM 필요, 테스트 안 함)로 **나뉩니다**. 테스트할 수 없는 부분을 최소화하는 전형적 기법입니다. `xlsx.ts`는 아예 "여기에 행을 만드는 로직을 두지 않는다"를 파일 주석으로 못박습니다 — 실행할 수 없는 파일에 판단이 들어가면 그 판단은 영영 검증되지 않기 때문입니다.

```ts
// 순수 — 테스트됨
export const toSheetRows = (
  headers: string[],
  rows: unknown[][]
): (string | number)[][] => [
  headers,
  ...rows.map(row => row.map(v => (v == null ? '' : v) as string | number))
]

// 부수효과 — exceljs 동적 import + DOM Blob/anchor, 테스트 대상 아님.
export async function downloadTable(filename, headers, rows): Promise<void> {
  if (rows.length === 0) return
  await downloadWorkbook(filename, [{ name: 'Sheet1', rows: toSheetRows(headers, rows) }])
}
```

## 4. 백엔드 테스트 — `pytest`

프론트가 `node --test`라면, 백엔드(`back_dev_home/`)는 `pytest`입니다. Provider 아키텍처(`10-backend-providers/`)의 완료 기준이 곧 테스트 green입니다. 테스트 러너는 `back_dev_home/requirements-dev.txt`로만 설치합니다 — Phase 3 운영 설치(`requirements.txt`)에는 테스트 러너가 들어가지 않도록 분리해 둔 것입니다.

```bash
# 백엔드 전체 (레포 루트에서, 약 990개)
.venv/bin/python -m pytest tests back_dev_home -q

# 위와 완전히 같은 수집 범위. 루트 pyproject.toml의 testpaths 설정 덕분입니다
.venv/bin/python -m pytest -q

# 기능 하나만 (집에서는 mock provider로 해석됩니다)
.venv/bin/python -m pytest back_dev_home/sem_list -q
```

명령 형태에서 세 가지가 중요합니다.

1. **경로 두 개를 모두 적어야 합니다.** `tests/`만 돌리면 `back_dev_home/<feature>/tests/`에 있는 provider 계약 스위트가 전부 빠집니다. 그쪽이 오히려 더 큰 절반이고, mock↔office 교체를 지키는 부분도 그쪽입니다.
2. **`python -m pytest` 형태를 씁니다.** `-m`이 레포 루트를 `sys.path`에 올려 주기 때문에 테스트가 `back_dev_home.*`를 import할 수 있습니다. 항상 레포 루트에서 실행합니다.
3. **`tests/` 디렉토리가 28개 있습니다.** 기능 폴더 23개(`sem_list/`, `msr_image/`, `ebeam/hitachi/*/` 등)와 공용 인프라 5개(`_auth/`, `_core/`, `_logging/`, `_runtime/`, `_spa/`)입니다. 각 기능의 `tests/`와 `__fixtures__/`가 계약(`contracts.py`) 준수를 강제합니다. 예: `msr_file/tests/test_contract.py`는 mock이 특정 메타데이터 필드를 **지어내지 못하게** 막습니다. 한편 `_runtime/tests/`는 provider 해석 규칙 자체(어느 어댑터가 왜 선택됐는지)를 검증하므로, Phase 2 작업 중에 가장 자주 깨지는 곳입니다.

### Phase 2(office) 게이트

회사에서 실제 소스 연결을 검증할 때는 기능 단위로 provider를 강제합니다.

```bash
SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/python -m pytest back_dev_home/sem_list -q
```

이 명령은 `back_dev_home/sem_list/providers/office.py`가 **있을 때만** 의미가 있습니다. `office.py`는 gitignore 대상이라 회사에서 직접 만들어야 합니다.

```bash
cp back_dev_home/sem_list/providers/office_example.py back_dev_home/sem_list/providers/office.py
```

어댑터가 없는 상태에서 위 게이트를 돌리면 조용히 mock으로 돌아가지 않고, 위 `cp` 명령을 그대로 알려 주는 `RuntimeError`로 **실패**합니다. 이 설계 덕분에 "green이면 진짜로 office 어댑터를 통과한 것"이라고 믿을 수 있습니다.

## 5. 브라우저 확인 — Playwright MCP (자동화 스위트가 아닙니다)

여기서 오해가 자주 생기므로 분명히 해 둡니다. **이 레포에는 자동화된 E2E 스위트가 없습니다.**

- `playwright.config.ts`가 없고, `*.spec.ts` 파일도 0개입니다.
- `npx playwright test`를 실행하면 `Error: No tests found`로 끝납니다. (설정이 없어 기본 `testMatch`가 `app/**/*.test.ts`를 주워 오는 바람에, 수집 과정에서 `node:test` 파일들이 부수효과로 실행된 뒤 "테스트 없음"이 뜹니다. 실행 로그만 보면 E2E가 도는 것처럼 보이지만 아닙니다.)
- `package.json`에 `@playwright/test`가 devDependency로 들어 있는 것은 **Playwright MCP 서버**를 위해서입니다.

즉 Playwright는 이 프로젝트에서 **개발자나 에이전트가 손으로 조종하는 대화형 도구**이지, CI가 돌릴 수 있는 스위트가 아닙니다. 실제 브라우저로 UI 흐름을 확인하는 일(예: `useSemList()` 통합 후 네트워크 요청이 3건→1건으로 줄었는지 측정 — `07-code-patterns/sem-list-caching.md` 4.3절)은 지금도 이 방식으로 **수동 검증**합니다.

- 스크린샷은 `.playwright-mcp/screenshots/`에 저장합니다(루트 `CLAUDE.md` 규칙).
- 원격 개발 환경에서는 Tailscale IP로 접속해 스크린샷을 찍습니다.
- 브라우저 검증 절차 전체는 `verify` 스킬(`.claude/skills/verify/SKILL.md`)에 정리돼 있습니다.

E2E를 진짜 자동화하려면 `playwright.config.ts`와 `*.spec.ts`를 새로 만들어야 하며, 그건 아직 하지 않은 일입니다.

## 6. 테스트 계층 정리 (자동화 여부 포함)

| 계층 | 도구 | 대상 | 명령 | 자동화 |
| --- | --- | --- | --- | --- |
| 순수 단위 (프론트) | `node --test` | `app/**/*.ts` 순수 함수 | `npm test` | CI 게이트 |
| 단위/통합 (백엔드) | `pytest` | provider 어댑터, 계약 준수, 라우트 | `.venv/bin/python -m pytest tests back_dev_home -q` | CI 게이트 |
| Phase 2 office 게이트 | `pytest` | 실제 사내 소스 연결 | `SKEWNONO_<FEATURE>_PROVIDER=office .venv/bin/python -m pytest back_dev_home/<feature> -q` | 회사에서 수동 |
| 컴포넌트 (`.vue`) | 없음 | — | — | 없음 |
| E2E (브라우저) | Playwright MCP | 실제 UI 흐름·네트워크 | 에이전트/개발자가 대화형으로 조종 | 없음 (수동) |

`.vue` 컴포넌트 계층이 비어 있는 것은 사고가 아니라 선택입니다. 마운트 하네스(jsdom, `@vue/test-utils`)를 들이지 않는 대신, 검증할 가치가 있는 로직을 컴포넌트 밖 순수 함수로 밀어내는 3절의 규율로 대신하고 있습니다.

CI(`.github/workflows/ci.yml`)는 두 잡을 돌립니다 — 백엔드 `pytest`와 프론트 `typecheck + test`입니다. `npm run lint`는 아직 게이트가 아닙니다(손대지 않은 파일들에 기존 lint 부채가 남아 있어서 의도적으로 빼 둔 상태입니다).

## 7. 커밋 전 체크리스트 (갱신판)

프론트엔드를 건드렸다면 `front-dev-home/`에서:

```bash
npm run lint        # ESLint (스타일 + 정적 분석)
npm run typecheck   # vue-tsc 타입 체크 (테스트 파일은 제외됨)
npm test            # node --test 순수 단위 테스트
npm run build       # 빌드 통과 확인 (nuxt generate)
```

백엔드를 건드렸다면 레포 루트에서:

```bash
.venv/bin/python -m pytest tests back_dev_home -q
```

문서만 고쳤다면 레포 루트에서:

```bash
npm run lint:md
```

## 8. 이 챕터의 큰 교훈

- **테스트 러너도 의존성입니다.** 순수 함수만 테스트하면 Vitest의 무게 없이 Node 내장 러너로 충분합니다.
- **테스트 가능성 = 좋은 경계.** "이걸 어떻게 테스트하지?"가 안 풀리면, 보통 계산과 부수효과가 안 갈라진 것입니다.
- **엣지 케이스는 테스트에 박제합니다.** `>` vs `>=`, 빈 배열, `NaN`/`null` — 코드는 잊지만 테스트는 기억합니다.
- **부수효과(DOM/fetch)는 얇게, 순수 로직은 두껍게.** 테스트 못 하는 부분을 최소 표면적으로.
