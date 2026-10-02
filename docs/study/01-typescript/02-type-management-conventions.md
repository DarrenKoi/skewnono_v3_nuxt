# 02. 타입 관리 관례: 계약을 누가 소유합니까?

## 1. 기초: 타입의 위치는 책임의 위치입니다

타입은 데이터의 의미와 사용할 수 있는 모양을 설명합니다. 모든 타입을 거대한 전역 파일에 모으는 것보다, 타입을 정의하는 책임이 있는 기능 가까이에 두면 변경 이유와 영향 범위를 읽기 쉽습니다. 한 컴포넌트에서만 필요한 props는 그 컴포넌트 안에, API 응답 계약은 API composable 가까이에 둡니다.

**2026-10-03 기준** [package.json](../../../frontend/package.json)의 TypeScript 선언은 `^5.9.3`이며 [package-lock.json](../../../frontend/package-lock.json)과 원본 node_modules에서 확인한 버전은 5.9.3입니다. 이전 노트가 가리키던 Windows 절대 링크와 프런트 `mock-data/sem-list/`는 현재 구조와 맞지 않습니다. 현재 모든 환경의 화면은 Flask API를 소비합니다.

## 2. 용어: 원본 계약, 파생 타입, 타입 소유자

| 용어 | 의미 |
| --- | --- |
| DTO (Data Transfer Object) / 전송 타입 | API가 전송하는 필드 모양입니다. |
| 도메인 타입 | 앱이 사용하는 업무 개념입니다. |
| 뷰 모델 | 표시를 위해 계산한 값의 모양입니다. |
| owner | 타입의 기준 정의를 관리하는 모듈입니다. |
| re-export | 기존 정의를 다른 경로에서 다시 공개합니다. |
| runtime validation | 실제 들어온 값이 계약에 맞는지 실행 중 확인합니다. |

예를 들어 서버의 `fab_name`과 앱의 “현재 선택한 FAB 목록”은 관련되지만 같은 책임은 아닙니다. 서버 row는 원본 계약이고, 선택 목록은 화면 상태입니다. 두 값이 현재 문자열이라는 이유만으로 하나의 거대한 인터페이스에 합치지 않습니다.

## 3. 실제 구현과 타입 추적

### 3.1 현재 소유자 표

| 종류 | 현재 소유자 | 확인할 계약 |
| --- | --- | --- |
| 장비 계열 값 / 타입 | [utils/toolType.ts](../../../frontend/app/utils/toolType.ts) | `TOOL_TYPES`, `ToolType`, 분류 함수 |
| 내비게이션 상태 | [stores/navigation.ts](../../../frontend/app/stores/navigation.ts) | `Fab = string`, `NavigationState`, ToolType 재수출 |
| SEM API row | [useSemListApi.ts](../../../frontend/app/composables/useSemListApi.ts) | `SemListRow`, `SemListResponse` |
| 저장 상태 옵션 | [usePersistedState.ts](../../../frontend/app/composables/usePersistedState.ts) | `PersistedStateOptions<T>`, unknown normalizer |
| 컴포넌트 이벤트 | [ChatComposer.vue](../../../frontend/app/components/chat/ChatComposer.vue) | `send: [text: string]` |
| 테이블 열 / 상태 | [ToolInventoryView.vue](../../../frontend/app/components/ebeam/ToolInventoryView.vue) | Nuxt UI와 TanStack의 타입 사용 |

`stores/navigation.ts`는 ToolType의 현재 원본 owner가 아닙니다. 원본은 utils/toolType이며 store가 재수출합니다. `Category`, 고정 FAB 유니온과 옛 `FacToolSummary`를 현재 정의처럼 찾으면 안 됩니다. `Fab`는 DB에서 들어오는 이름을 담는 `string`이고, 값의 정규화와 sentinel 처리는 [utils/fab.ts](../../../frontend/app/utils/fab.ts)가 담당합니다.

### 3.2 런타임 목록에서 타입을 파생합니다

현재 utils/toolType.ts의 실제 패턴입니다.

```ts
export const TOOL_TYPES = ['cd-sem', 'hv-sem', 'veritysem', 'provision'] as const
export type ToolType = (typeof TOOL_TYPES)[number]

export const SEM_TOOL_TYPES = ['cd-sem', 'hv-sem'] as const satisfies readonly ToolType[]
```

`as const`는 배열을 readonly tuple과 좁은 문자열 리터럴로 추론하게 합니다. `(typeof TOOL_TYPES)[number]`는 각 요소의 타입을 모아 유니온을 만듭니다. 목록과 유니온을 따로 수정할 필요가 없습니다. `satisfies`는 실제 추론을 유지하면서 값이 주어진 타입을 만족하는지 확인합니다.

`as const`가 JavaScript 객체를 실행 중 `Object.freeze()`한다는 뜻은 아닙니다. readonly 타입을 런타임 불변성이나 입력 검증과 혼동하지 않습니다.

```text
TOOL_TYPES 런타임 상수
  → typeof로 배열 타입 읽기
      → [number]로 요소 타입 읽기
          → ToolType 유니온
              → setter / API 필터 / 컴포넌트 입력에서 사용
```

### 3.3 API 타입은 API 응답 가까이에 둡니다

현재 SemListRow의 `version`은 숫자가 아닌 **string**이며 `1A` 같은 값이나 알 수 없는 빈 문자열을 담을 수 있습니다. `fab_name`도 string입니다. 타입을 단순화해 숫자나 고정 목록으로 좁히면 office 응답을 잘못 표현합니다.

```ts
// 현재 필드 중 일부를 고른 타입 예시입니다.
import type { SemListRow } from '~/composables/useSemListApi'

type ToolLabel = Pick<SemListRow, 'eqp_id' | 'fab_name' | 'version'>
```

백엔드 계약은 [sem_list/contracts.py](../../../backend/sem_list/contracts.py)도 함께 읽습니다. Python과 TypeScript의 타입 선언은 현재 자동 생성으로 동기화되지 않습니다. API row를 사용하는 TypeScript 테스트가 drift를 찾는 데 도움이 되지만 실제 office DB 값까지 증명하지는 않습니다.

### 3.4 파생 타입, props와 라이브러리 타입

화면에서 원본 row를 요약하면 `total`, `online`, `offline` 같은 새 의미가 생깁니다. 실제로 새 데이터 모양이 필요할 때만 계산하는 함수 가까이에 타입을 둡니다. 계산 없이 원본 row를 표시한다면 같은 필드의 UI 인터페이스를 복제할 필요가 없습니다.

컴포넌트의 props/emits는 재사용되기 전까지 SFC 내부에 둡니다. 외부 라이브러리 타입은 직접 가져옵니다.

```ts
import type { TableColumn } from '@nuxt/ui'
import type { SemListRow } from '~/composables/useSemListApi'

const columns: TableColumn<SemListRow>[] = [
  { accessorKey: 'eqp_id', header: '장비 ID' }
]
```

이 예시는 프로젝트의 Nuxt UI 타입이 있는 환경용입니다. Node만으로 Nuxt alias `~`를 해석할 수 있는 예시는 아닙니다. 라이브러리 API를 설명하기 위해 새 인터페이스를 다시 만들지 않습니다.

### 3.5 `interface`, `type`, `import type`

객체 계약에는 interface, 문자열 유니온과 타입 조합에는 type을 쓰는 관례가 있습니다. 객체에 type도 사용할 수 있으므로 Nuxt가 강제하는 규칙은 아닙니다. 기존 소유자의 스타일을 따르는 편이 더 일관됩니다.

`import type`은 실행 코드가 아닌 타입만 필요함을 표시하며 JavaScript 결과에서 제거됩니다. API 함수 호출에 필요한 import는 일반 import입니다. 타입 import를 썼다고 구조적 의존성과 모든 순환 의존성 문제가 해결되는 것은 아닙니다.

### 3.6 TypeScript와 런타임 경계를 구분합니다

`$fetch<SemListResponse>`의 제네릭은 컴파일러에게 기대하는 타입을 알려 줍니다. 응답 JSON에 모든 필드가 실제로 있는지 검사하는 코드가 생성되는 것은 아닙니다. `as SemListRow`도 검증이 아닙니다.

[usePersistedState.ts](../../../frontend/app/composables/usePersistedState.ts)는 JSON 파싱 결과를 `unknown`으로 받아 `normalize`로 확인합니다. 이것은 이미 존재하는 런타임 경계 검증의 예시입니다. 현재 저장소가 real API를 아직 쓰지 않는다는 옛 전제는 틀렸습니다. 모든 단계에서 Flask API를 사용합니다.

Zod/Valibot은 lock에 있는 의존성입니다. 설치 사실과 실제 특정 API에 적용된 사실은 다르므로, 도구 이름을 나열하는 대신 현재 경계에 어떤 확인이 필요한지 먼저 설명합니다. OpenAPI에서 생성된 타입도 별도 런타임 검증이 없으면 응답 값을 자동 검증하지 않습니다.

## 4. 선택 이유와 한계

소유자 가까이 두면 한 기능의 변경을 따라갈 파일 수가 줄어듭니다. 여러 기능이 실제로 공유하는 안정된 어휘만 재수출합니다. 공유 pagination 같은 계약이 실제로 생기면 작은 공통 모듈을 만들 수 있지만 미래를 위해 빈 `types/` 체계를 먼저 만들지 않습니다.

순수 타입 import는 실행 의존성을 만들지 않으므로 “큰 타입 파일은 항상 런타임 순환 import를 만든다”도 과한 주장입니다. 핵심 문제는 서로 무관한 계약을 찾고 변경하기 어려워지는 것입니다. 위치 규칙만으로 타입 품질과 런타임 안전성이 보장되지는 않습니다.

## 5. 흔한 실수

1. ToolType 문자열 목록을 여러 곳에 다시 선언합니다. 현재 owner에서 가져옵니다.
2. Fab를 옛 고정 유니온으로 복원합니다. 실제 서버 FAB 범위와 정규화 함수를 확인합니다.
3. API row version을 숫자로 가정합니다. 실제 계약은 string입니다.
4. 값이 한 번 쓰였다고 바로 공통 types 폴더로 옮깁니다. 실제 공유 요구를 기다립니다.
5. `as`, `$fetch<T>`, 생성 타입을 검증기로 오해합니다. 입력 경계의 실행 코드를 확인합니다.
6. optional과 null을 섞고 모든 값 없음 상태를 같은 의미로 사용합니다. [값 없음 문서](03-null-undefined-false-none-empty-string.md)로 이어집니다.

## 6. 안전 실습

저장소 루트에서 읽기만 합니다.

```bash
rg -n 'TOOL_TYPES|type ToolType|satisfies' frontend/app/utils/toolType.ts
rg -n 'type Fab|type.*ToolType|interface NavigationState' frontend/app/stores/navigation.ts
rg -n 'interface SemListRow|version:|SemListResponse' frontend/app/composables/useSemListApi.ts
rg -n 'unknown|normalize' frontend/app/composables/usePersistedState.ts
```

완료 기준은 ToolType의 선언, 재수출, 소비자를 구분하고 SemListRow의 현재 소유자와 version 타입을 답하는 것입니다. 임의 타입 이동이나 패키지 설치를 하지 않습니다.

개인 TypeScript Playground에서 `SEM_TOOL_TYPES`에 `'unknown-tool'`을 추가하면 satisfies 검사에 오류가 생겨야 합니다. 그러나 `JSON.parse`로 읽은 입력에 타입 단언만 추가하면 잘못된 문자열이 런타임에서 거부되지 않는다는 차이를 확인합니다.

## 7. 공식 근거

- [TypeScript 객체 타입](https://www.typescriptlang.org/docs/handbook/2/objects.html)
- [TypeScript typeof와 indexed access](https://www.typescriptlang.org/docs/handbook/2/indexed-access-types.html)
- [TypeScript satisfies](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html)
- [Vue props와 emits 타입](https://vuejs.org/guide/typescript/composition-api.html)
