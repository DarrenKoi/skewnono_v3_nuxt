# 02. 타입 관리 관례

이 문서는 이 저장소를 기준으로, Nuxt + TypeScript 코드베이스에서 타입을 일반적으로 어떻게 관리하는지 정리한 학습 노트입니다.

## 핵심 아이디어

일반적인 목표는 모든 타입을 거대한 `types/` 폴더 하나에 몰아넣는 것이 아닙니다.

보다 관례적인 접근은 다음과 같습니다.

- 타입을 소유하는 도메인이나 기능 가까이에 둡니다.
- 여러 기능이 실제로 함께 쓰는 소수의 타입만 재수출합니다.
- UI 전용 타입이나 일회성 타입은 해당 컴포넌트나 컴포저블 내부에 둡니다.
- 같은 리터럴 값을 여러 곳에 중복해서 선언하지 않습니다.

실무에서는 보통 "모든 타입이 여기 산다"는 방식보다, 누가 이 타입을 소유하는지를 기준으로 타입을 관리합니다.

## 실전에서 자주 쓰는 분리 방식

이와 같은 프론트엔드 앱에서는 보통 다음과 같이 나누는 편입니다.

| 종류 | 보통 두는 위치 | 이 저장소의 예시 |
| --- | --- | --- |
| 앱 전역 도메인 유니온 | 해당 도메인을 소유한 store/모듈 근처 | [front-dev-home/app/stores/navigation.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/stores/navigation.ts:4) |
| 기능별 데이터 모델 및 DTO | 해당 기능 또는 API 소스 옆 | [front-dev-home/app/mock-data/sem-list/sem-list.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/mock-data/sem-list/sem-list.ts:3) |
| 파생 요약 타입 또는 뷰 모델 | 그것을 계산하는 composable/service 내부 | [front-dev-home/app/composables/useSemListApi.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/composables/useSemListApi.ts:4) |
| 컴포넌트 props / emits | 재사용 전까지는 컴포넌트 내부 | Vue SFC의 `defineProps<{ ... }>()` 패턴 |
| 외부 라이브러리 보조 타입 | 사용하는 곳에서 직접 import | `TableColumn`, `SortingState`, `ColumnFiltersState` |

## 이 저장소가 이미 잘하고 있는 점

이 저장소는 이미 전반적으로 관례에 맞는 구조를 따르고 있습니다.

### 1. 공유 도메인 타입은 필요한 곳에서만 중앙화합니다

`Category`, `ToolType`, `Fab`는 [front-dev-home/app/stores/navigation.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/stores/navigation.ts:4)에 정의되어 있습니다.

이 방식이 좋은 이유는 이 값들이 다음 성격을 가지기 때문입니다.

- 안정적인 도메인 개념입니다.
- 페이지, composable, plugin, mock data에서 재사용됩니다.
- 한곳에 모아두어도 충분히 작고 이해하기 쉽습니다.

`NavigationState`도 store가 소유하는 상태 모양이므로 같은 파일에 두는 것이 자연스럽습니다.

### 2. 기능 전용 row 타입은 해당 기능 가까이에 둡니다

`SemListRow`, `SemListResponse`는 [front-dev-home/app/mock-data/sem-list/sem-list.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/mock-data/sem-list/sem-list.ts:3)에 있습니다.

이것도 관례적입니다. 이 타입은 SEM list 데이터 자체를 설명하는 타입이지, 앱 전역에서 쓰는 범용 개념은 아니기 때문입니다.

나중에 백엔드 API가 진짜 기준(source of truth)이 되더라도, 이 타입은 임의의 전역 파일보다 API 클라이언트나 생성된 스키마 근처에 두는 편이 더 자연스럽습니다.

### 3. 파생 타입은 그것을 계산하는 로직과 함께 둡니다

`FacToolSummary`는 [front-dev-home/app/composables/useSemListApi.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/composables/useSemListApi.ts:4)에 있습니다.

이 역시 관례적입니다. 이것은 백엔드의 원본 엔티티가 아니라, UI나 리포팅 용도로 composable이 만들어 내는 파생 결과이기 때문입니다.

### 4. 좁은 리터럴 값은 필요한 곳에서 그대로 유지합니다

[front-dev-home/app/components/nav/AppHeader.vue](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/components/nav/AppHeader.vue:4)에서는 category 목록에 `as const`를 사용합니다.

이 방식은 `'ebeam'`, `'thickness'` 같은 값이 단순 `string`으로 넓어지는 것을 막는 일반적인 패턴입니다.

## 자주 쓰는 관례 규칙

### 규칙 1. 거대한 전역 `types.ts`를 만들지 않습니다

이것은 규모가 커지는 TypeScript 프로젝트에서 가장 흔한 실수 중 하나입니다.

거대한 중앙 파일은 다음 문제를 만들기 쉽습니다.

- 탐색하기 어렵습니다.
- 서로 관계없는 타입이 뒤섞입니다.
- 순환 import의 원인이 되기 쉽습니다.
- 오래된 정의가 쌓이는 잡동사니 파일이 되기 쉽습니다.

하나의 기능에서만 쓰는 타입이라면 그 기능 안에 두는 편이 낫습니다.

### 규칙 2. 안정적인 공유 용어만 중앙화합니다

다음과 같은 것들은 중앙화할 가치가 있습니다.

- 라우트 식별자
- category 또는 status 유니온
- 공유 엔티티 ID
- store 상태 계약
- 여러 기능이 함께 쓰는 API 계약

이 저장소에서는 `ToolType`, `Fab`가 공유 어휘의 좋은 예시입니다.

### 규칙 3. 전송 타입과 UI 타입을 분리합니다

백엔드 row 모양과 화면에 렌더링할 row 모양은 종종 같지 않습니다.

예를 들면 다음과 같습니다.

- API 타입: 서버가 반환한 원본 응답 필드입니다.
- 도메인 타입: 앱이 해석한 정규화된 의미입니다.
- 뷰 모델: 화면 표시용으로 가공된 필드입니다.

의미가 갈라지기 시작하면, 하나의 인터페이스에 모든 역할을 억지로 몰아넣기보다 타입을 분리하는 편이 낫습니다.

### 규칙 4. 하나의 기준(source of truth)에서 타입을 파생합니다

이미 상수 값이 있다면, 유니온 타입을 수동으로 중복 선언하기보다 상수에서 파생하는 편이 좋습니다.

예시는 다음과 같습니다.

```ts
export const TOOL_TYPES = ['cd-sem', 'hv-sem', 'verity-sem', 'provision'] as const

export type ToolType = typeof TOOL_TYPES[number]
```

이 방식은 런타임 값과 컴파일 타임 타입이 어긋나는 문제를 줄여줍니다.

현재 저장소처럼 짧고 안정적인 목록은 유니온을 직접 선언해도 충분히 괜찮습니다. 다만 같은 목록을 런타임에서도 반복해서 쓴다면 상수 기반 파생 방식이 더 유용해집니다.

### 규칙 5. 객체 모양에는 `interface`, 유니온과 조합에는 `type`을 우선합니다

이것은 절대 규칙이 아니라 널리 쓰이는 관례입니다.

- 확장 가능한 객체 계약에는 `interface`를 사용합니다.
- 문자열 유니온, 유틸리티 타입 조합, mapped type, 별칭에는 `type`을 사용합니다.

이 저장소도 이 패턴을 잘 따르고 있습니다.

- `type ToolType = ...`
- `interface NavigationState { ... }`
- `interface SemListRow { ... }`

### 규칙 6. 타입 import는 타입으로 import합니다

타입 전용 import에는 `import type`을 사용합니다.

이렇게 하면 의도가 분명해지고, 불필요한 런타임 import를 피하는 데도 도움이 됩니다.

이 저장소도 다음과 같은 위치에서 이미 일관되게 사용하고 있습니다.

- [front-dev-home/app/composables/useNavigation.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/composables/useNavigation.ts:1)
- [front-dev-home/app/composables/useSemListApi.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/composables/useSemListApi.ts:1)
- [front-dev-home/app/mock-data/sem-list/sem-list.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/mock-data/sem-list/sem-list.ts:1)

### 규칙 7. 런타임 경계 검증은 TypeScript와 분리해서 생각합니다

TypeScript는 컴파일 타임 가정만 검사합니다. 실제 API 응답이 올바른지는 런타임에 검증하지 않습니다.

보통은 다음처럼 역할을 나눕니다.

- TypeScript는 기대하는 형태를 설명합니다.
- 런타임 검증은 신뢰할 수 없는 입력을 처리합니다.

이 프로젝트가 나중에 실제 백엔드 응답을 소비하게 되면, `zod`, `valibot`, 생성된 OpenAPI 타입 같은 도구를 도입하는 것이 관례적인 다음 단계가 됩니다.

## 이 저장소에 권장할 수 있는 구조

이 코드베이스가 더 커진다면 다음과 같은 관례가 무난합니다.

- `stores/navigation.ts`는 계속 공유 네비게이션 도메인 타입의 소유자로 둡니다.
- SEM 데이터 계약은 `mock-data/sem-list/`에 두거나, 실제 엔드포인트가 중심이 되면 API 모듈로 옮깁니다.
- composable 전용 파생 타입은 다른 기능이 재사용하기 전까지 composable 내부에 둡니다.
- 정말로 여러 도메인에서 함께 쓰는 계약만 `app/types/` 같은 공유 디렉토리에 둡니다.

만약 `app/types/`를 도입한다면, 그 디렉토리는 작게 유지하는 것이 좋습니다. 좋은 후보는 다음과 같습니다.

- 범용 API envelope 타입
- 공유 pagination 계약
- 재사용 가능한 identifier 또는 option-item 모양

반대로 새 인터페이스가 생길 때마다 기본 목적지처럼 쓰면 안 됩니다.

## 짧은 답

관례적인 타입 관리는 보통 다음 원칙을 따릅니다.

1. 공유 도메인 어휘는 소수의 owner 모듈에 둡니다.
2. 기능 전용 데이터 타입은 기능 가까이에 둡니다.
3. 컴포넌트 전용 타입은 컴포넌트 안에 둡니다.
4. 런타임 값과 타입 유니온은 하나의 기준에서 동기화합니다.
5. 모든 타입을 모으는 거대한 전역 파일은 만들지 않습니다.

이 저장소는 이미 대체로 올바른 방향으로 가고 있습니다. 가장 중요한 것은 너무 이른 시점에 모든 것을 중앙화하지 말고, 타입 소유권 기준의 구조를 유지하는 것입니다.
