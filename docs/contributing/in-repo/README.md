# 저장소 안에서 기여하기

동료의 코드가 SKEWNONO 저장소에 들어오고, SKEWNONO 와 함께 배포되고, 신원과 API 를
그대로 씁니다. 공통 규칙(진입 주소, 슬러그, 반입, 검토)은 [상위 안내](../README.md)에
있고, 여기에는 이 방향에만 해당하는 것을 적습니다.

## 격리 원칙

- **백엔드**: `backend/contrib/<slug>/` 아래만 fail-soft 로 로드합니다. import 가
  실패하거나 `bp` 가 없으면 그 패키지만 빠지고 부팅 로그에
  `contrib feature ... failed to load` 가 남습니다. 핵심 기능은 지금처럼 부팅 시
  즉시 실패합니다.
- **프런트엔드**: 검증 전 작업 공간은 **자기 빌드를 따로 가지는 Vite 앱**으로
  만듭니다. SKEWNONO 의 Nuxt 빌드에 들어간 코드는 문법 오류 하나로 전체 빌드를 막기
  때문에, 같은 Nuxt 안의 폴더는 승격 뒤에만 씁니다.

## SKEWNONO 쪽에 손대는 줄

| 무엇 | 어디 | 비고 |
| --- | --- | --- |
| 진입 페이지 | `frontend/app/pages/<slug>.vue` | 상위 안내의 redirect 한 장 |
| 메뉴 항목 | `frontend/app/utils/headerNav.ts` 한 줄 | `to: '/<slug>'`, `group: 'lab'` |
| 빌드 순서 | `frontend/package.json` 의 `build` 앞에 Vite 빌드 한 줄 | **소유자가 편집.** 동료는 `MIGRATION.md` 에 요청만 적습니다 |

이 밖의 공유 파일은 건드리지 않습니다. 필요해 보이면 `MIGRATION.md` 에 이유를 적고
소유자에게 맡깁니다. 자주 나오는 경우는 아래 백엔드 절에 있습니다.

## 백엔드

```text
backend/contrib/<slug>/
├── __init__.py            # from .routes import bp  (앱 팩토리는 이 패키지에서 bp 를 찾습니다)
├── AGENTS.md              # 이 폴더의 AGENTS.md 템플릿을 복사해 채웁니다
├── routes.py              # bp = Blueprint("<slug>", __name__), 경로는 /<slug>/... 로 시작
├── data.py                # 사내 OpenSearch/Redis 를 직접 읽습니다
├── tests/
│   ├── __init__.py        # 없으면 다른 기능의 test_routes.py 와 이름이 충돌합니다
│   └── test_routes.py     # 정상 응답 shape 하나, 소스 없을 때 503 하나
└── MIGRATION.md           # 소유자와 목적, 읽는 사내 소스와 부르는 API, 공유 파일을 건드린 이유
```

- 앱 팩토리가 `routes.py` 를 찾아 `backend.contrib.<slug>` 패키지를 import 하고 그
  `bp` 를 `/api` 아래에 등록합니다. 등록 코드는 고치지 않습니다.
- 신원(LASTUSER 쿠키와 API 토큰), 요청 제한, 에러 JSON, 활동 로그는 자동으로
  상속됩니다. 요청한 사용자는 `flask.g.user_id` 입니다.
- 공유 코드 중 import 해도 되는 것은 `backend._core` (예: `request_args.resolve_fab_name`)
  뿐입니다. 다른 기능 패키지나 `_runtime`, `_auth`, `_logging` 은 import 하지 않습니다.
- `data.py` 는 **import 시점에 사내 자원을 만지지 않습니다.** 연결은 첫 호출에서
  엽니다. import 시점에 실패하면 자기 패키지가 통째로 빠져 모든 엔드포인트가 404 가
  됩니다.
- 사내 소스를 못 읽을 때는 `raise RuntimeError("...")` 를 그대로 던집니다. 전역
  핸들러가 **정확히 `RuntimeError` 인 예외**만 JSON 503 으로 바꾸고, 서브클래스는
  500 으로 남깁니다. 잘못된 요청은 `flask.abort(400)` 입니다. 집에서는 이 기능이 늘
  503 인데, 그것이 정상입니다.
- `providers/` 폴더는 만들지 않습니다. mock/office 이중화는 집에서 개발하는 소유자의
  장치이지 기능의 자격 요건이 아닙니다. 만들 거면 `mock.py` 와 `office_example.py`
  를 모두 갖춰야 하고, `office.py` 만 있는 seam 은 부팅을 거부합니다.
- 새 pip 의존성은 `backend/requirements.txt` 편집이므로 소유자와 상의합니다.
- 요청 제한은 사용자당 `/api/*` 전체 공유 예산(50 req / 5 s)입니다. 한 화면이 그
  예산을 넘는 작업 공간은 먼저 요청 수를 줄이고, 그래도 안 되면 소유자가
  `backend/__init__.py` 의 `_EXEMPT_BLUEPRINTS` 에 넣습니다.
- 주기 작업은 기능 폴더 안에서 스레드나 타이머로 띄우지 않습니다. 실행 프로세스가
  하나로 정해져 있기 때문입니다. `backend/_scheduler/tasks/<slug>.py` 에 두고
  `backend/_scheduler/registry.py` 에 등록하는데, 이 등록은 공유 파일 편집이므로
  소유자와 상의합니다.
- `home-to-office` 감사는 `backend/contrib/**` 를 건너뜁니다. 이 아래는 처음부터
  사무실 전용이기 때문입니다.

## 프런트엔드

### 기본: 별도 Vite 앱

```text
apps/<slug>/                          # 저장소 루트. frontend/ 밖이라 SKEWNONO 의 lint/typecheck 가 보지 않습니다
├── AGENTS.md
├── package.json
├── vite.config.ts                    # base: '/ws/<slug>/', build.outDir: '../../frontend/public/ws/<slug>'
└── src/...
```

- 빌드 결과가 `frontend/public/ws/<slug>/` 에 놓이고, Nuxt 는 `public/` 을 빌드 결과에
  그대로 복사합니다. 이 경로는 gitignore 되어 있으므로 산출물은 commit 하지 않고,
  사무실 빌드 때 Vite 빌드가 다시 만듭니다. 클라우드의 Flask 는 요청 경로와 정확히 일치하는 파일이 있으면
  그 파일을, 없으면 SPA 의 `index.html` 을 돌려주므로 `/ws/<slug>/index.html` 이 그대로
  열립니다. 진입 페이지 `pages/<slug>.vue` 는 이 주소로 보냅니다.
- `/ws/` 접두어는 SKEWNONO 페이지가 아닌 경로여야 합니다. `nuxt generate` 가 페이지마다
  `<경로>/index.html` 을 만들기 때문에, Vite 앱을 `public/<slug>/` 에 두면 진입
  페이지의 출력물과 같은 자리에서 충돌합니다.
- **해시 라우터**를 씁니다. `/ws/<slug>/foo` 같은 깊은 경로는 파일이 없어 SKEWNONO 의
  404 화면이 뜨고, 페이지 조회 비콘까지 `ws` 슬러그로 찍힙니다. 디렉터리 index 도
  찾지 않으므로 링크는 항상 `/ws/<slug>/index.html#/...` 형태입니다.
- 같은 origin 이므로 LASTUSER 쿠키와 `/api/*` 호출이 그대로 동작합니다. API 주소는
  `/api/<slug>/...` 상대 경로입니다.
- 개발 중에는 `vite build` 뒤 SKEWNONO 의 Nuxt dev 서버(`public/` 을 서빙)에서
  `/ws/<slug>/index.html` 로 확인합니다. Vite dev 서버를 쓰려면 자기 `vite.config.ts`
  에 `/api` 프록시를 `http://localhost:5050` 으로 둡니다.
- 사무실 빌드 순서에 이 앱의 `vite build` 를 Nuxt 빌드 **앞에** 둡니다.
- 헤더, 툴/fab 컨텍스트, 디자인 토큰, NuxtUI 는 없습니다. 토큰과 폰트는 CSS 를 따로
  가져옵니다. 활동 랭킹은 `/<slug>` 진입만 세고 안에서의 사용은 세지 않습니다.

### 승격 뒤: 같은 Nuxt 안의 폴더

```text
frontend/app/
├── pages/<slug>/index.vue          # redirect 페이지를 진짜 구현으로 바꿉니다. 하위 페이지도 이 폴더 안에
├── components/<slug>/*.vue         # <Slug…> 접두어가 자동으로 붙습니다
└── composables/use<Slug>Api.ts     # useSemListApi.ts 를 복사해서 시작합니다
```

Nuxt 를 몰라도 됩니다. 페이지는 그냥 Vue SFC 입니다. 본보기는 `components/magpixel/`
과 `pages/thickness/` 입니다.

- API 주소는 `/api` 를 문자열로 박지 않고 기존 composable 처럼
  `joinApiPath(useRuntimeConfig().public.apiBase, '/<slug>/...')` 로 만듭니다.
- 유틸은 `utils/<slug>/` 아래 두고 명시적으로 import 합니다. 최상위 `utils/` 와
  `composables/` 는 자동 import 라, 기존 이름과 겹치면 빌드 경고 한 줄만 남기고
  조용히 버려집니다.
- 색상은 `--sk-*` 토큰만 씁니다. `DESIGN.md` 를 먼저 읽습니다.
- `/ebeam/<tool>/[fab]/` 탭 계열로 옮기는 것은 공유 파일이 넷으로 늘고 fab 과 툴 타입
  라우팅 의미까지 따라야 하므로 소유자가 합니다.
- 활동 랭킹은 `/<slug>` 경로 하나면 자동으로 잡힙니다. 하위 페이지 여러 개를 한
  슬러그로 묶고 싶을 때만 `utils/pageIdentity.ts` 의 `IDENTITY_RULES` 와 그 fixture
  를 소유자와 함께 고칩니다.

## 게이트

```bash
.venv/bin/python -m pytest backend/contrib/<slug> -q   # 저장소 루트
.venv/bin/python -m ruff check .
npm run lint:md                                        # Markdown 을 고쳤다면, 저장소 루트
npm run typecheck && npm run lint && npm test          # frontend/. 진입 페이지나 headerNav.ts 를 포함해 frontend/app/ 을 만졌다면
```

Vite 앱의 게이트는 자기 `package.json` 에 둡니다. SKEWNONO 의 게이트는 그 앱을 보지
않습니다.
