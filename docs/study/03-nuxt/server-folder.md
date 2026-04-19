# Nuxt `server/` 폴더 정리

## Nuxt에서 `server/` 폴더가 하는 일

Nuxt에서 `server/` 폴더는 Nitro 기반의 Nuxt 서버 런타임에서 실행되는 백엔드 코드를 두는 위치입니다.

이 폴더는 보통 다음 용도로 사용합니다.

- API 엔드포인트
- 서버 미들웨어
- 서버 유틸리티
- 브라우저 번들에 포함되면 안 되는 백엔드 전용 로직

Nuxt는 관례에 따라 이 폴더 안의 파일을 읽고, 자동으로 서버 핸들러로 변환합니다.

예시는 다음과 같습니다.

- `server/routes/users.get.ts` -> `GET /users`
- `server/api/users.ts` -> `/api/users`

파일명 접미사도 중요한 역할을 합니다.

- `.get.ts`는 `GET` 요청을 처리합니다.
- `.post.ts`는 `POST` 요청을 처리합니다.
- `.put.ts`는 `PUT` 요청을 처리합니다.
- `.delete.ts`는 `DELETE` 요청을 처리합니다.

## 이 프로젝트에 현재 들어 있는 것

현재 구조는 다음과 같습니다.

```text
front-dev-home/server/
|-- routes/
|   |-- mock-api/
|   |   `-- sem-list.get.ts
```

즉, 현재 이 프로젝트에는 `server/routes` 아래에 서버 라우트가 하나 있습니다.

## `sem-list.get.ts`가 하는 일

파일: [sem-list.get.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/server/routes/mock-api/sem-list.get.ts:1)

소스는 다음과 같습니다.

```ts
import { mockSemListResponse } from '~/mock-data/sem-list/sem-list'

export default defineEventHandler(() => mockSemListResponse.map(row => ({ ...row })))
```

이 코드는 다음 일을 합니다.

1. `app/mock-data/sem-list/sem-list`에서 mock SEM inventory 데이터를 가져옵니다.
2. `defineEventHandler(...)`로 Nitro 서버 핸들러를 정의합니다.
3. `map(row => ({ ...row }))`로 각 row의 복사본을 반환합니다.

이 파일에서 생성되는 라우트는 다음과 같습니다.

```text
/mock-api/sem-list
```

이유는 다음과 같습니다.

- 파일이 `server/routes` 안에 있습니다.
- 폴더 경로가 `mock-api/sem-list`입니다.
- 파일명이 `.get.ts`로 끝나므로 `GET` 엔드포인트가 됩니다.

## 이 앱에서 어떻게 사용되는가

파일: [nuxt.config.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/nuxt.config.ts:1)

이 프로젝트는 public API base를 다음과 같이 설정합니다.

```ts
const apiTarget = import.meta.env.NUXT_API_TARGET
const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE || (apiTarget ? '/api' : '/mock-api')
```

이 의미는 다음과 같습니다.

- `NUXT_API_TARGET`이 없으면 프론트엔드는 `/mock-api`를 사용합니다.
- `NUXT_API_TARGET`이 있으면 프론트엔드는 `/api`로 전환하고, 요청을 다른 백엔드로 프록시합니다.

파일: [useSemListApi.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/app/composables/useSemListApi.ts:53)

이 composable은 다음 URL을 조합합니다.

```ts
const semListUrl = joinApiPath(config.public.apiBase, '/sem-list')
```

따라서 이 저장소의 일반적인 로컬 개발 환경에서는 요청 경로가 다음처럼 됩니다.

```text
/mock-api/sem-list
```

이 경로는 정확히 `front-dev-home/server/routes/mock-api/sem-list.get.ts`가 제공하는 라우트입니다.

## 이 저장소에서의 실질적 의미

이 코드베이스에서 `front-dev-home/server`는 Nuxt 개발용으로 내장된 작은 mock 백엔드 역할을 하고 있습니다.

현재 맡고 있는 역할은 다음과 같습니다.

- 로컬 API 엔드포인트를 제공합니다.
- mock SEM list 데이터를 반환합니다.
- Flask API가 떠 있지 않아도 프론트엔드가 동작하게 해 줍니다.

## 이 프로젝트에서 알아둘 제한 사항

이 저장소는 [nuxt.config.ts](/C:/Code/skewnono_v3_nuxt/front-dev-home/nuxt.config.ts:10)에 `ssr: false`가 설정되어 있으므로, 앱이 client-rendered SPA로 구성되어 있습니다.

그렇다고 해서 Nuxt 개발 중 `server/` 폴더의 가치가 사라지는 것은 아닙니다. `server/` 라우트는 여전히 Nuxt dev/build 런타임에서 서빙될 수 있습니다. 다만 `nuxt.config.ts`의 주석이 장기 방향을 보여 줍니다.

> Flask serves the built SPA in Phase 2/3, no Node server, no SSR.

즉, 이 `server/` 폴더는 최종 프로덕션 백엔드라기보다, 현재 시점에서는 mock 또는 전환용 API 계층으로 보는 편이 맞습니다.

## 요약

`front-dev-home/server`는 Nitro가 관리하는 Nuxt 서버 측 코드입니다. 이 저장소에서는 현재 `/mock-api/sem-list`라는 mock `GET` 엔드포인트 하나를 가지고 있으며, 프론트엔드가 SEM inventory mock 데이터를 가져올 때 기본적으로 이 경로를 사용합니다. 외부 API target이 설정되면 그때 다른 백엔드로 전환합니다.
