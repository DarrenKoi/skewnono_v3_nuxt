# 06. Vite & `nuxt.config.ts` 설정 해설

Nuxt 4는 내부적으로 **Vite**를 번들러로 사용합니다. 별도의 `vite.config.ts`를 쓰지 않고, `nuxt.config.ts`의 `vite:` 키로 Vite 옵션을 전달합니다.

백엔드 관점: Vite는 Flask의 WSGI 서버 + static file server 역할을 합니다 — 소스 코드를 받아 브라우저가 읽을 JS로 변환해 서빙하고, HMR(Hot Module Replacement)로 변경 즉시 반영합니다.

## 1. Vite의 역할 요약

- **ESM 기반 dev server**: 파일을 바꾸면 해당 모듈만 재전송(HMR)
- **프로덕션 번들**: Rollup 기반 트리 셰이킹 + 코드 분할
- **플러그인 생태계**: PostCSS, SVG 로더, Vue SFC 파서 등

Nuxt가 Vite를 감싸기 때문에 직접 Vite 명령을 부를 일은 없습니다. `npm run dev`/`build`가 모두 `nuxt dev`/`nuxt build`를 통해 Vite를 호출합니다.

## 2. `nuxt.config.ts` 한 줄씩 해석

```ts
const portFromEnv = Number.parseInt(import.meta.env.NUXT_PORT || '', 10)
const apiTarget = import.meta.env.NUXT_API_TARGET
const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE || (apiTarget ? '/api' : '/mock-api')
```

**환경 변수 기반 config**. 실행 시점에 다음 env들을 읽습니다.

- `NUXT_PORT` — dev 서버 포트 (기본 3100)
- `NUXT_API_TARGET` — 백엔드 프록시 대상 (있으면 Phase 2/3, 없으면 Phase 1)
- `NUXT_PUBLIC_API_BASE` — 프론트엔드가 `$fetch` 할 때 쓰는 base path

`apiBase`의 기본 로직:
- `NUXT_PUBLIC_API_BASE`가 있으면 그 값 (가장 우선)
- 없으면: `NUXT_API_TARGET`이 있으면 `/api`, 없으면 `/mock-api`

**Phase 스위치**:
- Phase 1 (집): env 없음 → `apiBase = '/mock-api'` → `$fetch('/mock-api/...')` (실제로는 Phase 1 코드에서 mock 데이터를 직접 return하는 쪽으로 넘어감)
- Phase 2 (회사): `NUXT_API_TARGET=http://127.0.0.1:5000 npm run dev` → `apiBase='/api'` + Nitro devProxy가 `/api/*` → Flask로 프록시
- Phase 3 (프로덕션): `NUXT_PUBLIC_API_BASE` 덮어씌우거나 빌드 시 고정

### 2.1 `modules`

```ts
modules: [
  '@nuxt/eslint',
  '@nuxt/ui'
]
```

Nuxt 모듈은 **설치만으로 자동 통합되는 플러그인**. 이 프로젝트는 ESLint 통합과 NuxtUI를 등록.

### 2.2 `devtools`

```ts
devtools: { enabled: true }
```

[Nuxt Devtools](https://devtools.nuxt.com/) — 브라우저 하단에 띄워주는 개발자 도구. 페이지/컴포넌트/상태/성능을 한눈에 볼 수 있습니다.

### 2.3 `css`

```ts
css: ['~/assets/css/main.css']
```

전역 CSS 파일. `~` 또는 `@`는 `app/`(Nuxt 4)를 가리킵니다.

### 2.4 `runtimeConfig`

```ts
runtimeConfig: {
  public: {
    apiBase        // 자바스크립트/클라이언트에서 useRuntimeConfig().public.apiBase로 접근
  }
}
```

환경 변수로 덮여씁니다 (`NUXT_PUBLIC_API_BASE`). `public` 외부에 두면 서버 전용(시크릿 키 등).

### 2.5 `routeRules`

```ts
routeRules: {
  '/': { prerender: true }
}
```

특정 경로에 렌더링 전략을 개별 설정.

- `prerender: true` — 빌드 시 정적 HTML로 미리 생성 (SSG)
- `ssr: false` — 클라이언트 렌더링만 (SPA)
- `cache: { maxAge: 60 }` — 60초 캐싱
- `redirect: '/new'` — 리다이렉트

`/`(홈) 을 prerender해서 초기 로딩을 빠르게 합니다.

### 2.6 `devServer`

```ts
devServer: {
  port: Number.isFinite(portFromEnv) ? portFromEnv : 3100
}
```

dev 서버 포트. 기본 3100 (Nuxt 기본 3000을 피함 — 회사 다른 서비스와 충돌 방지 추정).

### 2.7 `compatibilityDate`

```ts
compatibilityDate: '2025-01-15'
```

Nuxt의 behavior lock-in 날짜. Nuxt가 업데이트되어도 이 날짜 기준의 동작을 유지합니다. 중요한 장치이므로 지우지 마세요.

### 2.8 `nitro.devProxy`

```ts
nitro: apiTarget
  ? {
      devProxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          prependPath: true
        }
      }
    }
  : undefined
```

**Phase 2 핵심**. 개발 중 `/api/*` 요청을 Flask(`NUXT_API_TARGET`)로 투명 프록시합니다.

- `changeOrigin: true` — Host 헤더를 target으로 변경 (CORS 회피)
- `prependPath: true` — 원본 경로를 target 뒤에 붙임

예: `NUXT_API_TARGET=http://127.0.0.1:5000`인 상태에서 브라우저가 `GET /api/ebeam/tools`를 호출하면, Nuxt dev 서버가 받아서 `http://127.0.0.1:5000/api/ebeam/tools`로 포워드.

Phase 1(`apiTarget` 없음)에서는 Nitro 설정이 `undefined`가 되어 프록시가 꺼집니다.

### 2.9 `vite.server.allowedHosts`

```ts
vite: {
  server: {
    allowedHosts: ['.trycloudflare.com']
  }
}
```

Vite dev 서버가 허용하는 Host 헤더. 원격에서 Cloudflare Tunnel(`trycloudflare.com`)로 접속할 때 필요합니다. 로컬에서만 쓰면 건드릴 필요 없음.

### 2.10 `eslint`

```ts
eslint: {
  config: {
    stylistic: {
      commaDangle: 'never',      // 객체/배열 끝 콤마 금지
      braceStyle: '1tbs'         // "one true brace style"
    }
  }
}
```

`@nuxt/eslint` 모듈에게 전달하는 스타일 옵션. 자세한 규칙은 `08-eslint-style/`에서.

## 3. `tsconfig.json`

```json
{
  "files": [],
  "references": [
    { "path": "./.nuxt/tsconfig.app.json" },
    { "path": "./.nuxt/tsconfig.server.json" },
    { "path": "./.nuxt/tsconfig.shared.json" },
    { "path": "./.nuxt/tsconfig.node.json" }
  ]
}
```

**Solution-style tsconfig**. 루트 `tsconfig.json`은 비워두고, 실제 설정은 `.nuxt/`에 Nuxt가 자동 생성합니다. `npm run dev`나 `npm run postinstall`이 이 파일들을 만듭니다.

환경별 분리:
- `tsconfig.app.json` — 클라이언트 사이드 Vue 코드
- `tsconfig.server.json` — `server/` 폴더 (Nitro 코드)
- `tsconfig.shared.json` — 양쪽에서 공유
- `tsconfig.node.json` — `nuxt.config.ts` 같은 Node 스크립트

**실무 팁**: 자체 rule을 추가하고 싶으면 `.nuxt/`가 아닌 루트 `tsconfig.json`에 `compilerOptions`를 넣는 대신 Nuxt가 제공하는 `nuxt.config.ts`의 `typescript` 옵션을 사용하세요. `.nuxt/`는 재생성됩니다.

## 4. `eslint.config.mjs`

```mjs
import withNuxt from './.nuxt/eslint.config.mjs'
export default withNuxt(
  // Your custom configs here
)
```

`@nuxt/eslint` 모듈이 `.nuxt/eslint.config.mjs`를 자동 생성하고, 루트에서 그걸 wrap하는 flat config. 커스텀 룰이 있으면 `withNuxt(...)` 인자로 전달.

## 5. 빌드 출력 (`.output/`)

```bash
npm run build
```

`.output/` 폴더에 생기는 것:

```text
.output/
├── public/     브라우저로 보낼 정적 자원 (bundled JS/CSS, 이미지, HTML)
├── server/     Nitro 서버 코드 (SSR + API)
└── nitro.json  배포 메타데이터
```

Phase 3에서는 이 `.output/public/`을 Flask `static_folder`로 연결하거나 별도 CDN에 올립니다.

## 6. 실행 시나리오 정리

### Phase 1 — 로컬 오프라인

```bash
npm install
npm run dev
```

→ `http://localhost:3100`. `apiBase='/mock-api'`, Nitro 프록시 없음. mock-data 모듈이 데이터 공급.

### Phase 2 — 회사 로컬

Flask가 `http://127.0.0.1:5000`에서 돌고 있을 때:

```bash
NUXT_API_TARGET=http://127.0.0.1:5000 npm run dev
```

→ `apiBase='/api'`. `/api/*` 요청이 Flask로 프록시. HMR은 그대로 작동.

### Phase 3 — 프로덕션

```bash
NUXT_PUBLIC_API_BASE=/api npm run build
```

→ `.output/public/`을 Flask가 정적으로 서빙. Flask 내부에서 `/api/*`는 Blueprint가 처리.

## 7. 환경 변수 요약표

| 변수 | 목적 | Phase 1 | Phase 2 | Phase 3 |
| --- | --- | --- | --- | --- |
| `NUXT_PORT` | dev 서버 포트 | 3100(기본) | 자유 | N/A |
| `NUXT_API_TARGET` | Flask 프록시 대상 | (비움) | `http://127.0.0.1:5000` | N/A |
| `NUXT_PUBLIC_API_BASE` | 프론트 API base path | (자동 `/mock-api`) | (자동 `/api`) | 명시적 `/api` |

## 8. 참고

- Nuxt config 전체 옵션: https://nuxt.com/docs/api/nuxt-config
- Vite docs: https://vitejs.dev/config/
- Nitro (Nuxt 서버): https://nitro.unjs.io
