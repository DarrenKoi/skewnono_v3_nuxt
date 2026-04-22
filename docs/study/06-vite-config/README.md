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
const apiTarget = import.meta.env.NUXT_API_TARGET || 'http://localhost:5000'
const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE || '/api'
const isDev = import.meta.dev
```

**환경 변수 기반 config**. 실행 시점에 다음 env들을 읽습니다.

- `NUXT_PORT` — dev 서버 포트 (기본 3100)
- `NUXT_API_TARGET` — 백엔드 프록시 대상 (기본 `http://localhost:5000`, 즉 Flask)
- `NUXT_PUBLIC_API_BASE` — 프론트엔드가 `$fetch` 할 때 쓰는 base path (기본 `/api`)
- `isDev` — `import.meta.dev` (dev 서버일 때 `true`, build 산출물에서는 `false`)

**현재 설계 — 단일 백엔드(Flask)**:

이전 설계는 Phase 1에서 Nitro의 `server/routes/mock-api/sem-list.get.ts`가 mock 데이터를 서빙하고 Phase 2/3에서만 Flask를 붙이는 방식이었습니다. 지금은 **세 Phase 모두 Flask가 백엔드**이며, 바뀌는 것은 Flask 내부의 데이터 소스(mock dict → OpenSearch/Redis)뿐입니다. 이렇게 하면 `/api/*` 응답 형태가 Phase 간 100% 동일해지고, 프론트엔드는 설정 변경만으로 Phase를 바꿀 수 있습니다.

**Phase 스위치**:
- Phase 1 (집): `npm run dev` → Flask `back_dev_home/`를 `localhost:5000`에서 별도로 띄움 → Nitro devProxy가 `/api/*` → Flask로 프록시
- Phase 2 (회사): `NUXT_API_TARGET=http://company-host:5000 npm run dev` 또는 기본값 사용 → 같은 프록시 경로
- Phase 3 (프로덕션): `npm run build` 후 `.output/public/`을 Flask가 직접 정적 서빙 → 같은 origin이라 프록시 불필요

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
nitro: {
  devProxy: {
    // h3 strips the '/api' mount prefix before the proxy runs, so the /api
    // segment must live inside the target URL for Flask to receive it.
    '/api': {
      target: `${apiTarget.replace(/\/$/, '')}/api`,
      changeOrigin: true
    }
  }
}
```

**모든 Phase의 dev 서버에서 핵심**. Nuxt dev 서버(`:3100`)가 받는 `/api/*` 요청을 Flask(`:5000`)로 투명 프록시합니다. 브라우저 입장에서는 same-origin fetch이므로 CORS preflight가 발생하지 않습니다.

- `changeOrigin: true` — Host 헤더를 target으로 변경 (대상 서버가 vhost 기반이면 필요)
- **target에 `/api`를 folding** — 이 부분이 직관적이지 않습니다. h3(Nitro의 HTTP 레이어)는 매칭된 mount prefix(`/api`)를 target으로 포워드하기 전에 **제거**합니다. 그래서 target이 그냥 `http://localhost:5000`이면 Flask는 `/api`가 사라진 `GET /sem-list`를 받게 됩니다. Flask의 Blueprint가 `/api` 하위에 마운트돼 있기 때문에 404가 납니다. 해결: target URL 자체에 `/api`를 붙여서 잘린 prefix를 복원합니다.
- `prependPath`는 의도적으로 쓰지 않았습니다. `prependPath: true`는 "matched prefix도 보존"이라는 Nitro/h3 옵션이지만 버전 간 동작이 흔들리는 영역이라, target에 직접 박는 쪽이 더 예측 가능합니다.

**중요 — Phase 1부터 이미 필요**: 이전 설계에서는 Phase 1이 Nitro `/mock-api` 라우트로 동작해서 프록시가 필요 없었습니다. 현재 설계는 Phase 1부터 Flask를 쓰기 때문에, dev 모드에서 `:3100`과 `:5000`을 잇는 이 프록시가 **Phase 1에서도 반드시 필요**합니다.

**Phase 3에서는 프록시가 필요 없음**: Phase 3은 Flask가 빌드된 SPA(`.output/public/`)를 직접 서빙하므로 HTML과 `/api/*`가 같은 origin입니다. `devProxy` 키는 이름 그대로 dev 전용 — prod에는 영향 없습니다.

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

터미널 두 개를 엽니다.

```bash
# 터미널 1 — Flask mock 백엔드
python index.py            # back_dev_home/__init__.py::create_app을 띄움, :5000

# 터미널 2 — Nuxt dev 서버
npm run dev                # :3100
```

→ 브라우저: `http://localhost:3100`. `apiBase='/api'`, devProxy가 `/api/*`를 `:5000`으로 포워드. 데이터는 `back_dev_home/<feature>/data.py`의 in-memory Python dict.

### Phase 2 — 회사 로컬

Flask가 회사 네트워크의 `http://company-host:5000`에 떠 있을 때:

```bash
NUXT_API_TARGET=http://company-host:5000 npm run dev
```

→ Phase 1과 동일 구조. Flask 내부에서 `data.py`만 OpenSearch/Redis를 쳐다보는 실제 구현으로 교체됨. 프론트엔드 코드는 변화 없음.

### Phase 3 — 프로덕션

```bash
npm run build              # .output/public/ 생성
```

→ Flask가 `.output/public/`을 `static_folder`로 삼아 HTML/JS/CSS를 직접 서빙. `/api/*`는 같은 Flask의 Blueprint가 처리. 한 origin, 한 서버 — Nitro dev 서버도 devProxy도 런타임에 없음.

## 7. 환경 변수 요약표

| 변수 | 목적 | Phase 1 | Phase 2 | Phase 3 |
| --- | --- | --- | --- | --- |
| `NUXT_PORT` | Nuxt dev 서버 포트 | 3100(기본) | 자유 | N/A (build) |
| `NUXT_API_TARGET` | devProxy 대상 Flask URL | (기본 `http://localhost:5000`) | `http://company-host:5000` | N/A |
| `NUXT_PUBLIC_API_BASE` | 프론트 `$fetch` base path | `/api`(기본) | `/api`(기본) | `/api`(기본) |

**관찰**: 세 Phase 모두 `apiBase='/api'`로 고정. 바뀌는 것은 `NUXT_API_TARGET`(dev 때 proxy가 어디로 쏘는지) 하나뿐이고, Phase 3에서는 그마저도 dev가 아니라 의미 없음. 즉 **프론트엔드가 Phase를 구별할 방법이 없음** — 이게 의도된 설계입니다.

## 8. 참고

- Nuxt config 전체 옵션: https://nuxt.com/docs/api/nuxt-config
- Vite docs: https://vitejs.dev/config/
- Nitro (Nuxt 서버): https://nitro.unjs.io
