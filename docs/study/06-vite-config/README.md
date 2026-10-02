# 06. Vite와 Nuxt 설정을 읽는 법

기준일은 2026-10-03입니다. 이 장은 설정의 이름보다 **누가 언제 읽고 어떤 요청에 영향을 주는지**를 먼저 설명합니다. 실제 설정은 [nuxt.config.ts](../../../frontend/nuxt.config.ts), 명령은 [package.json](../../../frontend/package.json), 고정 버전은 [package-lock.json](../../../frontend/package-lock.json)에서 확인합니다.


HMR(Hot Module Replacement)은 전체 재로드 대신 변경 모듈을 교체하는 기능입니다. WSGI(Web Server Gateway Interface)는 Python 서버와 앱의 호출 규약입니다. HTML(Hypertext Markup Language)·JS(JavaScript)·CSS(Cascading Style Sheets)는 브라우저가 받는 구조·동작·스타일 자원입니다. ESM(ECMAScript Modules)은 import/export를 사용하는 JavaScript 모듈 방식입니다.

## 1. 기초: 개발 서버와 배포 서버는 역할이 다릅니다

브라우저는 Vue 파일과 TypeScript를 그대로 실행하지 않습니다. 개발할 때 Nuxt가 Vite를 이용해 소스를 브라우저용 모듈로 변환합니다. HMR은 변경된 코드를 반영하면서 가능한 범위에서 화면 상태를 유지하는 기능입니다. Vite는 Python 코드를 실행하는 WSGI 서버가 아니며 Flask API를 대신하지 않습니다.

이 저장소의 `build` 스크립트는 `nuxt build`가 아니라 **`nuxt generate`**입니다. `ssr: false`이므로 앱 화면은 브라우저에서 렌더링됩니다. 생성된 정적 파일은 사내 배포에서 Flask가 제공하며, Node/Nitro 서버를 배포 런타임으로 요구하지 않습니다.

```text
개발: 브라우저 → Nuxt 개발 서버(:3000)
                   ├─ 화면 모듈: Vite
                   └─ /api/*: Nitro devProxy → Flask(:5050 기본값)
배포: 브라우저 → Flask
                   ├─ 생성한 HTML/JS/CSS
                   └─ /api/* → 기능 Blueprint → data.py → 선택된 provider
```

세 단계 모두 API는 Flask입니다. 프론트에 별도 mock-api 서버가 있는 구조가 아닙니다. 회사용 어댑터는 `providers/office.py`이며 **`data.py`를 회사용으로 교체하지 않습니다.** 단계별 상세 설명은 [백엔드 provider](../10-backend-providers/README.md)에서 이어집니다.

## 2. 용어와 버전의 세 층

| 용어 | 의미 | 이 저장소에서 읽는 곳 |
| --- | --- | --- |
| 번들러 | 모듈을 배포용 파일로 묶는 도구 | Nuxt가 사용하는 Vite |
| Nitro | Nuxt 서버 도구와 정적 생성 기반 | `nitro.devProxy` |
| SPA | 브라우저가 화면을 그리는 앱 | `ssr: false` |
| origin | 프로토콜·호스트·포트 조합 | 브라우저는 `/api`를 화면과 같은 origin에 요청 |
| 선언 | 허용하는 버전 범위 | package.json의 `^` |
| lock | 의존성 해결 결과의 정확한 버전 | package-lock.json |
| 설치 | 지금 디스크에 있는 패키지 버전 | node_modules 안 package.json |

2026-10-03에 lock과 원본 작업 공간의 설치본을 각각 읽었습니다. 아래 둘은 우연히 일치하지만 언제나 같다고 가정하지 않습니다. Vite는 직접 dependency 선언이 아니라 Nuxt의 간접 의존성입니다.

| 패키지 | 직접 선언 | lock | 확인한 설치본 |
| --- | --- | --- | --- |
| Nuxt | `^4.4.2` | 4.5.0 | 4.5.0 |
| Nuxt UI | `^4.6.1` | 4.10.0 | 4.10.0 |
| Vite | 직접 선언 없음 | 8.1.5 | 8.1.5 |
| TypeScript | `^5.9.3` | 5.9.3 | 5.9.3 |

옛 Vite 문서의 Rollup 기반 설명을 현재 Vite 8에 그대로 적용하지 않습니다. Vite 8의 빌드 기반은 Rolldown입니다. 설정을 바꾸기 전에 lock의 실제 주 버전에 맞는 [Vite 8 문서 원본](https://github.com/vitejs/vite/tree/v8.1.5/docs)을 읽습니다.

## 3. 실제 설정을 읽는 순서

### 3.1 모듈, 렌더링, 전역 자원

`modules`에 `@nuxt/eslint`와 `@nuxt/ui`를 **등록**합니다. 패키지를 설치했다는 이유만으로 모든 Nuxt 모듈이 자동 활성화되는 것은 아닙니다. `ssr: false`는 SPA 선택입니다. `devtools.enabled`는 항상 true가 아니라 `isDev`입니다. `css`는 `~/assets/css/main.css`를 전역 로드하며 Nuxt 4에서 `~`는 기본 `app/` 소스 디렉터리를 가리킵니다.

`app.head`는 문서 제목, favicon, theme-color를 설정합니다. 현재 SVG favicon은 data URI로 인라인되어 있고 ICO와 apple-touch 파일 링크도 있습니다. SVG를 파일 URL로 바꾸면 클라이언트 내비게이션 중 favicon 재검증 요청이 증가할 수 있다는 프로젝트 주석이 있습니다.

### 3.2 환경 변수와 포트

```ts
const apiTarget = import.meta.env.NUXT_API_TARGET || 'http://localhost:5050'
const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE || '/api'
```

`devServer.port`는 유한한 `NUXT_PORT` 파싱 결과를 쓰고 아니면 3000입니다. 집 Flask 기본값 5050은 macOS AirPlay의 5000 충돌을 피합니다. 회사에서 Flask가 5000에 있다면 `NUXT_API_TARGET`을 명시합니다. 기본값이 자동으로 회사의 5000으로 바뀌지는 않습니다.

`runtimeConfig.public.apiBase`는 브라우저에 공개됩니다. 비밀 정보를 넣지 않습니다. 이 앱은 정적 생성 산출물을 제공하므로 배포 뒤 Flask 환경 변수만 바꿔서 이미 생성된 브라우저 설정을 갱신한다고 기대하면 안 됩니다. 설정 반영에는 생성 시점도 확인해야 합니다.

### 3.3 개발 프록시

```ts
nitro: {
  devProxy: {
    '/api': {
      target: `${apiTarget.replace(/\/$/, '')}/api`,
      changeOrigin: true
    }
  }
}
```

브라우저의 `/api/sem-list` 요청은 개발 프록시를 거쳐 Flask의 `/api/sem-list`로 전달됩니다. 현재 구성에서 mount 접두사가 제거되는 경로를 보완하려고 target에 `/api`가 포함됩니다. 이 설정은 `vite.server.proxy`가 아니며 다른 프록시 라이브러리의 옵션을 그대로 복사하지 않습니다. `changeOrigin`은 대상에 보내는 Host를 바꾸는 설정이지 브라우저 CORS를 끄는 설정이 아닙니다. 브라우저가 같은 origin의 `/api`를 요청하기 때문에 이 경로에서 교차 origin 요청을 만들지 않습니다.

`devProxy`는 개발 전용입니다. Flask가 정적 SPA와 API를 함께 제공하는 배포에서는 둘이 같은 origin이므로 이 개발 프록시가 필요하지 않습니다.

### 3.4 원격 접속과 Host 허용

`dev:remote`는 `nuxt dev --host 0.0.0.0`입니다. 이것은 서버가 듣는 주소를 바꾸는 설정이고, `vite.server.allowedHosts`는 요청의 Host 허용 여부입니다. 둘은 별개입니다. 현재 목록은 `.ts.net`, `.trycloudflare.com`이며 IP 주소는 Vite에서 기본 허용됩니다. 앞의 점은 해당 도메인과 하위 도메인들을 허용합니다. 편의를 위해 `allowedHosts: true`로 바꾸지 않습니다. [Vite 서버 옵션](https://vite.dev/config/server-options#server-allowedhosts)을 참고합니다.

### 3.5 오프라인 폰트와 아이콘

`ui.fonts: false`로 폰트 자동 해석을 끄고 프로젝트의 자체 자원을 사용합니다. 아이콘은 `fallbackToApi: false`로 외부 Iconify API 폴백을 끕니다. `clientBundle.scan`은 앱 소스와 Nuxt UI 컴파일된 컴포넌트를 함께 스캔합니다. 이름이 동적으로 조립되는 아이콘은 `icons`에 `lucide:x`처럼 등록합니다. template의 `i-lucide-x`와 등록 형식이 다릅니다. `sizeLimitKb: 2048`은 번들 크기 허용 한도이며 모든 아이콘을 자동 포함하는 옵션은 아닙니다.

### 3.6 TypeScript, ESLint, compatibilityDate

`typescript.tsConfig.compilerOptions.allowImportingTsExtensions: true`는 `node --test`용 `.ts` 확장자 import를 허용합니다. **테스트 파일 exclude는 없습니다.** 테스트 fixture도 실제 API 타입과 함께 검사하여 계약 변화가 보이도록 유지합니다. Node 타입은 `@types/node`로 제공합니다.

[tsconfig.json](../../../frontend/tsconfig.json)은 `.nuxt/tsconfig.app.json` 등 네 개 생성 설정을 참조하는 solution 구조입니다. `.nuxt` 파일은 수정하지 않습니다. `postinstall`의 `nuxt prepare` 등이 재생성하기 때문입니다. ESLint 스타일은 trailing comma 금지와 `1tbs`이며 [08장](../08-eslint-style/README.md)에서 검사 범위를 구분합니다.

`compatibilityDate: '2025-01-15'`는 날짜 기반 호환 동작을 선택하는 설정입니다. Nuxt 전체 코드와 의존성 버전을 그 날짜로 고정하는 설정이 아닙니다. 버전 재현은 lock 파일이 담당합니다. 현재 `routeRules` 블록은 없으므로 홈 페이지에만 `prerender: true`를 설정했다는 옛 설명은 적용되지 않습니다.

## 4. 선택 이유와 한계

SPA와 Flask 정적 제공은 배포에 Node 서버를 추가하지 않는 선택입니다. 대신 첫 화면 내용은 브라우저 JS 실행에 의존합니다. `nuxt generate` 산출물 중 배포에 쓰는 위치는 `.output/public/`이며 SSR 서버를 실행하는 것이 아닙니다. 회사 내부 배포 절차는 [deployment.md](../../deployment.md)를 따릅니다. 외부 CDN 배포는 이 프로젝트의 기본 절차가 아닙니다.

자체 폰트와 아이콘은 외부 서비스 의존성을 줄이지만 누락된 아이콘이 자동으로 복구되지는 않습니다. 개발 프록시는 API 주소 차이를 가리지만 회사 DB 연결과 provider 계약까지 검증하지는 않습니다.

## 5. 흔한 실수

- Nuxt의 3000과 Vite 독립 실행 기본 포트 5173을 혼동합니다.
- `NUXT_API_TARGET`만 바꾸면 백엔드 provider까지 바뀐다고 생각합니다. Flask provider 선택은 별도 설정입니다.
- `ssr: false`와 생성 명령을 보고 실제 API 응답까지 빌드 때 고정된다고 생각합니다. API는 브라우저 실행 중 요청합니다.
- `.nuxt` 설정을 직접 편집하거나 테스트를 typecheck에서 빼서 오류를 숨깁니다.
- 회사 5000을 쓰면서 proxy target은 5050 기본값으로 둡니다.

## 6. 안전 실습

아래는 저장소 루트에서 설정을 읽기만 하는 실습입니다. 패키지 설치나 서버 실행은 필요하지 않습니다.

```bash
rg -n '"build"|"dev:remote"|"postinstall"' frontend/package.json
rg -n 'ssr:|devProxy:|allowedHosts:|compatibilityDate:|allowImporting' frontend/nuxt.config.ts
cat frontend/tsconfig.json
```

`build=nuxt generate`, `ssr=false`, `/api` 프록시, 두 Host suffix, `.ts` import 허용을 찾으면 성공입니다. 이어서 종이에 `/api/sem-list` 요청이 개발·배포에서 각각 어느 서버를 거치는지 그립니다. 설정을 읽는 실습은 실제 회사 API 연결 검증과 구분합니다.

공식 자료는 [Nuxt 4 설정](https://nuxt.com/docs/4.x/api/nuxt-config), [Nuxt 4 렌더링](https://nuxt.com/docs/4.x/guide/concepts/rendering), [Vite 8.1.5 서버 옵션 원본](https://github.com/vitejs/vite/blob/v8.1.5/docs/config/server-options.md)입니다. Nuxt 문서 사이트는 4.x 전체 설명이며 패치 버전별 동작은 설치본과 같은 버전 소스로 확인합니다.
