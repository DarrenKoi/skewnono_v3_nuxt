# 13. 테스트: 무엇을 증명하고 무엇이 남는가

테스트는 입력을 주고 결과가 약속과 같은지 자동으로 비교하는 프로그램입니다. 이 문서는 처음 테스트를 읽는 사람을 위해 단위 검증·타입 검사·브라우저 확인·회사 연결의 경계를 설명합니다. [10-backend-providers](../10-backend-providers/README.md)의 반환 계약, [11-echarts-dataviz](../11-echarts-dataviz/README.md)의 입력 좌표, [12-statistics-wafer](../12-statistics-wafer/README.md)의 수학을 어떻게 검증하는지 연결합니다.

2026-10-03 기준 `frontend/package.json`, `nuxt.config.ts`, `pyproject.toml`, `.github/workflows/ci.yml`, frontend `*.test.ts`와 backend 계약 테스트를 확인했습니다. 파일·테스트 개수는 계속 바뀌므로 과거의 77개·990개 같은 숫자를 현재 보장으로 유지하지 않습니다. CI frontend는 Node **24**, backend는 Python **3.14**입니다. 원본 환경의 pytest는 **9.1.1**입니다. 개발·회사 interpreter는 Python **3.11**이므로 CI 통과가 3.11 실행 증거를 대신하지 않습니다.

## 1. 기초: 기대값과 실제값을 비교합니다

예를 들어 category 좌표 1.4에서 가장 가까운 배열 위치는 1입니다. 이 약속을 테스트에 쓰면 반올림 규칙이 바뀌었을 때 바로 알 수 있습니다. 문장으로만 적으면 고친 사람이 설명과 구현의 차이를 놓칠 수 있습니다.

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { nearestIndex } from './chartNearest.ts'

test('fractional category position rounds to its nearest index', () => {
  assert.equal(nearestIndex(1.4, 3), 1)
  assert.equal(nearestIndex(3, 3), null)
})
```

이 코드는 규칙을 설명하는 예시입니다. 기존 `chartNearest.test.ts`에 이미 해당 경계가 있으므로 같은 테스트 파일을 또 만들 필요는 없습니다. 실패할 때는 **입력, 기대값, 실제값, 왜 그 기대가 도메인 약속인지**를 읽습니다. 테스트 기대값도 틀릴 수 있으므로 테스트를 무조건 통과시키기 위한 수정은 피합니다.

## 2. 용어: 서로 다른 검증 도구를 구분합니다

| 용어 | 뜻 | 이 저장소에서의 경계 |
| --- | --- | --- |
| Assertion | 기대 결과가 맞는지 확인하는 문장 | `assert.equal`, Python `assert` |
| Unit test | 작은 계산·행동을 좁게 검증합니다. | 순수 TS 계산, Python 함수 |
| Integration test | 여러 경계가 함께 동작하는지 확인합니다. | Flask test client와 라우트·provider |
| Fixture | 테스트 입력·임시 환경을 준비하는 자료입니다. | 가짜 row, pytest fixture |
| Mock / test double | 외부 의존성의 응답을 대신합니다. | 실제 Redis 대신 가짜 client |
| Contract test | 반환 shape·의미·허용 결측을 확인합니다. | mock·office 어댑터의 공통 계약 |
| Typecheck | 타입이 어긋나는 코드를 실행 전에 찾습니다. | `nuxt typecheck` |
| Lint | 정적 코드 규칙 위반을 찾습니다. | Ruff·ESLint·markdownlint |
| Component test | 컴포넌트를 mount하고 렌더·이벤트를 검사합니다. | 현재 자동 mount suite 없음 |
| E2E | 브라우저부터 서버까지 실제 흐름을 확인합니다. | 현재 자동 E2E suite 없음 |
| CI | push마다 같은 명령을 새 환경에서 실행합니다. | GitHub Actions |

단위·통합이라는 이름보다 **어떤 의존성이 진짜로 실행됐는지**가 중요합니다. 테스트 이름이 office여도 DB client를 monkeypatch했다면 사내 네트워크 연결을 증명하지 않습니다. 테스트가 통과한 조건을 결과와 함께 적습니다.

## 3. 현재 구현: frontend·backend·CI

### 3.1 프론트엔드는 Node 내장 runner입니다

`frontend/package.json`의 명령은 다음과 같습니다.

```json
{
  "test": "node --test \"app/**/*.test.ts\""
}
```

`node:test`는 테스트 실행, `node:assert/strict`는 엄격한 비교를 제공합니다. 별도 Vitest·Jest를 도입하지 않았습니다. 테스트할 가치가 있는 계산을 Nuxt·DOM 바깥의 순수 함수로 분리하면 Node만으로 실행할 수 있습니다. 컴포넌트 디렉토리나 composable 이름의 파일에도 테스트가 있지만, 이름만으로 Vue mount 테스트라고 해석하지 않습니다. 어떤 import와 대체 환경을 사용하는지 읽습니다.

Node 24는 지울 수 있는 TypeScript 타입 문법을 제거하고 실행합니다. **타입이 맞는지는 검사하지 않습니다.** `tsconfig.json`의 paths alias도 실행 시 자동 적용하지 않으며, `.vue` 템플릿을 mount해 주지도 않습니다. 실행 값이 있는 enum 등의 변환이 필요한 문법은 기본 type stripping과 다른 문제입니다. [Node 24.13.0 TypeScript 문서](https://nodejs.org/download/release/v24.13.0/docs/api/typescript.html)와 [test runner 문서](https://nodejs.org/download/release/v24.13.0/docs/api/test.html)를 기준으로 읽습니다.

### 3.2 실행과 타입 검사를 둘 다 수행합니다

실행되는 상대 import는 `./outlierDetect.ts`처럼 확장자를 씁니다. Node가 sibling 경로를 실제 파일로 찾아야 하기 때문입니다. 타입만 필요한 import는 `import type`으로 쓰면 실행 시 지울 수 있습니다. Nuxt alias를 실행 값 import에 쓰면 Node에서 별도 처리 없이 해결되지 않습니다.

현재 `nuxt.config.ts`에는 `allowImportingTsExtensions: true`가 있고, **테스트 파일을 typecheck에서 제외하는 설정은 없습니다.** 예전 설명의 `exclude: ['../app/**/*.test.ts']`는 현재 구조와 반대입니다. 많은 fixture가 실제 API row 타입으로 작성되므로 테스트도 타입 검사에 포함해 office 계약과 frontend shape의 어긋남을 잡습니다. `@types/node`는 devDependency이고 Nuxt 생성 타입과 함께 자동 포함됩니다.

따라서 두 명령은 보완 관계입니다.

```bash
# frontend/에서
npm run typecheck
npm test
```

첫 명령은 실행하지 않은 경로의 타입도 볼 수 있고, 둘째는 실행 결과를 확인합니다. TypeScript 숫자 타입만으로 평균·단위·필터·경계값의 의미가 맞는지는 확인할 수 없습니다.

### 3.3 순수 계산과 부수효과를 나눕니다

`X.ts` 옆에 `X.test.ts`를 두는 colocated 패턴을 사용합니다.

```text
app/utils/stats.ts            -> stats.test.ts
app/utils/waferGeometry.ts    -> waferGeometry.test.ts
app/utils/chartNearest.ts     -> chartNearest.test.ts
app/utils/tableExport.ts      -> tableExport.test.ts
```

순수 함수는 같은 입력에서 같은 값을 반환하고 DOM·DB·시간 같은 외부 상태를 직접 읽지 않습니다. 계산과 부수효과를 분리하면 다음을 검증하기 쉽습니다.

- 임계값과 같을 때 `>`인지 `>=`인지 확인합니다.
- 빈 배열·한 점·null·비유한 수를 확인합니다.
- nm→mm, map_offset, 배열 범위 밖 좌표를 확인합니다.
- 원본 배열을 정렬 과정에서 의도치 않게 바꾸지 않는지 확인합니다.
- 실제 API shape로 만든 fixture가 타입과 계약을 유지하는지 확인합니다.

표 내보내기는 `tableExport.ts`의 행 만들기와 `xlsx.ts`의 workbook·Blob·download 부수효과를 나눕니다. Node에서 행이 맞다는 결과가 브라우저 다운로드 정상이라는 뜻은 아닙니다. PNG도 파일명·좌표 계산 테스트와 실제 canvas·download 확인을 구분합니다. 단순 코드 한 줄을 그대로 따라 쓰는 테스트보다 실패 시 중요한 계약 위반을 드러내는 경계 입력이 유용합니다.

### 3.4 백엔드는 pytest와 Ruff입니다

`backend/requirements-dev.txt`는 운영 requirements를 포함하고 pytest·Ruff를 추가합니다. 운영 설치에 테스트 runner를 별도로 싣지 않는 경계입니다. Python 의존성은 `>=` 등 범위이며 모든 설치 버전을 고정한 lock은 아닙니다.

명령은 레포 루트에서 실행합니다.

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
```

`pyproject.toml`의 `testpaths = ["tests", "backend"]` 덕분에 아래 명령은 같은 수집 범위입니다.

```bash
.venv/bin/python -m pytest tests backend -q
```

`tests/`만 지정하면 `backend/**/tests/`의 provider 계약 suite가 빠집니다. 루트에서 `python -m pytest`를 사용하는 이유는 repo root를 import 경로에 포함하기 위해서입니다. 현재 설정의 `prepend` import mode와 각 테스트 패키지 `__init__.py`도 import 해석에 영향을 줍니다. 테스트 파일을 디렉토리 밖으로 이동하거나 import mode를 바꿀 때 이 조건을 함께 확인합니다. [pytest 9.1.1 공식 호출 문서 원본](https://github.com/pytest-dev/pytest/blob/9.1.1/doc/en/how-to/usage.rst)는 명령·수집 옵션을 설명하며, 저장소의 실제 수집 root는 `pyproject.toml`이 정합니다.

기능 단위 확인은 다음과 같습니다.

```bash
.venv/bin/python -m pytest backend/sem_list -q
```

계약 테스트는 반환 키·타입뿐 아니라 의미를 봅니다. 예를 들어 mock이 알 수 없는 회사 메타데이터를 지어내지 않는지, LEFT 조인에서 장비가 중복·누락되지 않는지 확인합니다. provider 선택 테스트는 잘못된 override·어댑터 누락·사이트 기본값을 확인합니다. 회사 전용 `office.py`는 gitignore이므로 깨끗한 checkout에는 없습니다. 테스트가 모듈 최상단에서 무조건 import하면 수집 전체가 깨질 수 있습니다. 회사 파일이 필요한 테스트는 guard·skip을 구분하고 skip을 실행 성공으로 세지 않습니다.

### 3.5 Office gate가 증명하는 범위

회사에서 기능별 선택을 강제하는 명령은 다음과 같습니다.

```bash
SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/python -m pytest backend/sem_list -q
```

복사본이 없으면 selector가 `cp office_example.py office.py`를 안내하는 `RuntimeError`를 냅니다. 명시적 office 요청을 mock으로 바꾸어 green을 만들지 않습니다. **office adapter가 선택됐다는 증거와 실제 DB를 읽었다는 증거는 다릅니다.** fixture나 가짜 client가 실제 접속을 대체하는 테스트는 어댑터 코드·반환 계약을 검증합니다. 실제 연결은 회사 인프라에서 실행한 요청·로그·데이터 확인이 필요합니다.

아직 복사본이 없는 회사 기능의 준비 절차는 해당 `MIGRATION.md`를 읽습니다. 학습을 위해 집에서 `office.py`를 만들거나 기존 회사 파일을 덮어쓸 필요는 없습니다. 템플릿 업데이트가 회사 복사본에 반영됐는지도 따로 확인합니다.

### 3.6 CI는 두 잡이며 backend lint가 먼저입니다

| CI job | 환경 | 실행 순서 | 포함하지 않는 검증 |
| --- | --- | --- | --- |
| `typecheck + test` | Ubuntu, Node 24 | `npm ci` → `npm run typecheck` → `npm test` | Vue mount·브라우저 E2E·frontend ESLint |
| `lint + pytest` | Ubuntu, Python 3.14 | dev requirements → `ruff check .` → `python -m pytest tests backend -q` | Python 3.11·실제 회사 DB·office 복사본 |

Ruff 실패면 pytest는 실행되지 않습니다. “pytest job 실패”라고 뭉뚱그리면 실제 실패 단계가 가려집니다. frontend의 `npm ci` 후 `nuxt prepare`는 typecheck에 필요한 Nuxt 타입을 생성합니다. frontend ESLint는 손대지 않은 파일의 기존 lint 문제가 있어 현재 CI gate에서 제외되어 있습니다. 따라서 `npm run lint`를 별도로 실행해 확인한 파일의 범위와 기존 오류를 구분해야 합니다.

### 3.7 브라우저 검증 도구와 자동 suite는 다릅니다

현재 Playwright config·E2E spec·Vue mounting harness가 없습니다. `@playwright/test`는 devDependency에 있지만 package가 있다는 사실만으로 E2E coverage가 생기지 않습니다. `npx playwright test`를 표준 검증 명령처럼 사용하지 않습니다.

브라우저 확인은 개발자·에이전트가 실제 UI를 조작하는 별도 작업입니다. 도구 선택은 `.claude/skills/browser-verify/SKILL.md`에서 확인합니다. 특정 MCP·스크린샷 경로를 현재 유일한 방법으로 외우지 않습니다. repo guide의 기본 경로를 따르고 실제 실행 도구·URL·상태를 기록합니다.

| 확인 계층 | 현재 도구 | 통과가 말하는 것 | 남은 확인 |
| --- | --- | --- | --- |
| TS 계산 | Node test | 입력에 대한 함수 결과 | canvas·DOM·network |
| TS 타입 | Nuxt typecheck | 앱·fixture 타입 관계 | 수학·실제 runtime 값 |
| Python 계약·route | pytest | 실행된 mock/adapter/route 조건 | 회사 접속·실제 스키마 |
| 정적 규칙 | Ruff·ESLint | 검사 범위의 규칙 준수 | 사용자 흐름 |
| 실제 화면 | 대화형 브라우저 | 확인한 URL·데이터·상호작용 | 미확인 상태·다른 환경 |
| 사내 실제 소스 | 회사 실행·로그 | 확인한 연결과 실제 반환 | 다른 장비·기간·권한 |

`.vue` 자동 mount 계층이 없는 대신 판단 로직을 순수 함수로 꺼냅니다. 그래도 CSS 높이·focus·tooltip·download·fetch 순서는 브라우저에서 확인해야 합니다.

## 4. 선택 이유와 한계

Node 내장 runner는 현재 순수 함수 범위에 필요한 실행 도구를 이미 제공합니다. 별도 프레임워크를 추가할 이유가 실제 DOM·컴포넌트 격리 검증으로 생기면 그때 비교할 수 있습니다. 현재 도구를 작게 유지하는 것과 중요한 검증을 생략하는 것은 다릅니다.

passing은 “실행한 테스트의 조건에서 기대와 같았다”는 증거입니다. fixture가 한 데이터 블록만 가진다면 순서가 뒤집힌 두 블록을 잡지 못합니다. null 허용 row만 고르면 populated metadata의 모양을 확인하지 못합니다. 동시성·타이밍·브라우저 hit·회사 스키마는 해당 실패를 구분하는 입력과 환경이 필요합니다. 테스트 수가 늘었다는 것만으로 coverage가 충분해지지는 않습니다.

## 5. 흔한 실수

- `npm test`가 타입 검사도 한다고 생각하면 잘못된 fixture 타입이 남을 수 있습니다.
- 테스트를 앱 typecheck에서 제외하라는 옛 설정을 복원하면 계약 shape 검증이 약해집니다.
- Node가 Nuxt paths alias·Vue DOM을 자동 지원한다고 생각하면 import 단계에서 실패합니다.
- backend `tests/`만 실행하면 더 큰 기능별 계약 영역을 누락합니다.
- `skip`·office 강제 선택·실제 DB 실행을 모두 같은 green으로 읽으면 연결 증거가 과장됩니다.
- UI 변경 후 순수 테스트만 통과시키면 한 점 차트·tooltip·실제 다운로드 버그가 남습니다.
- CI 3.14 성공을 회사 3.11 성공으로 쓰면 interpreter 경계를 놓칩니다.
- 테스트 로그의 마지막 숫자만 보고 Ruff·수집 오류·빠진 경로를 확인하지 않으면 실패를 오해합니다.

## 6. 안전한 실습과 변경별 확인

처음에는 전체 suite보다 작은 테스트 하나를 읽고 실행합니다. `frontend/`에서 다음을 수행합니다.

```bash
node --test app/utils/chartNearest.test.ts
node --test app/utils/stats.test.ts app/utils/waferGeometry.test.ts
```

각 파일에서 하나씩 입력·기대값을 손으로 계산합니다. category 범위 밖은 null인지, 표준편차의 분모는 무엇인지, map_offset이 stage와 die 중 어디에 적용되는지 설명합니다. 실패를 일부러 만들고 싶다면 기존 파일을 바꾸기보다 앞의 `node --input-type=module` 예시에 임시 `assert.equal`을 적어 실행합니다. 버전 관리 파일을 손상시키지 않고 실패 메시지를 볼 수 있습니다.

backend는 레포 루트에서 실행합니다.

```bash
.venv/bin/python -m pytest backend/_runtime/tests/test_site_provider.py -q
.venv/bin/python -m pytest backend/sem_list -q
```

출력의 passed·skipped를 읽고 어느 테스트가 외부 client를 대체했는지 확인합니다. DB 값·환경변수를 출력하는 실습은 필요하지 않습니다. `.venv`가 없는 worktree라면 원본 환경의 interpreter 경로를 사용하되 실행 cwd는 이 checkout 루트인지 확인합니다.

변경 범위에 따라 확인을 고릅니다.

| 변경 | 기본 확인 | 필요하면 추가하는 확인 |
| --- | --- | --- |
| 문서만 | 루트 `npm run lint:md`·링크·예제 값 확인 | 생성 HTML의 읽기·코드 블록 확인 |
| 순수 TS 함수 | 해당 `.test.ts`·typecheck | 영향 있는 전체 Node suite |
| UI·차트 | 순수 계산 테스트·typecheck·수정 파일 lint | 실제 앱 흐름·테마·크기·한 점·download |
| backend 함수·provider | Ruff·해당 기능 pytest | 전체 수집 범위·회사 실제 소스 |
| 앱 부팅·공통 경계 | Ruff·runtime/root 관련 테스트 | 전체 backend suite·해당 Phase 실행 |

문서 편집의 표준 명령은 루트 `npm run lint:md`입니다. frontend를 고칠 때는 `npm run lint`, `npm run typecheck`, `npm test`, 필요한 빌드를 실행하며 실제 UI 변경은 브라우저 확인을 완료합니다. 실행하지 않은 검증은 완료라고 적지 않습니다.

학습 완료 기준은 다음 질문에 구체적으로 답하는 것입니다. 어떤 함수·입력이 검증됐습니까? 어떤 의존성을 대체했습니까? 타입 검사와 실행 검증이 각각 무엇을 잡습니까? 같은 변경을 회사에서 적용할 때 남은 게이트는 무엇입니까?
