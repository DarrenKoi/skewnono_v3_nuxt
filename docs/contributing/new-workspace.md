# 동료가 작업 공간을 추가하는 방법

SKEWNONO 는 장비별 작업 공간의 **허브**입니다. 사용자는 장비를 고르고 그 장비의
작업 공간에 들어갑니다. 그 작업 공간이 같은 앱 안에 있는지, 별도 URL 에 있는지는
구현 세부이고 만든 사람이 소유합니다. 이 문서는 동료가 자기 작업 공간을 붙일 때
**SKEWNONO 쪽에서 손대야 하는 것이 무엇인지**만 적습니다. 나머지는 자기 폴더 안의
일이고, 최종 반영은 저장소 소유자가 결정합니다.

이 문서는 사람과 사내 LLM 이 같이 읽도록 썼습니다. 작업을 시작할 때 이 문서와 저장소
루트의 `AGENTS.md` 를 LLM 컨텍스트에 넣습니다. 1단계 프런트엔드를 만들 때는 `DESIGN.md`
도 넣습니다. 그 밖의 파일은 필요할 때 본보기로 지목한 것만 읽게 합니다. LLM 이 공유
코드를 고치자고 제안하는 것을 막는 방법은 문서를 늘리는 것이 아니라 **읽는 범위를
자기 폴더와 이 세 파일로 좁히는 것**입니다.

## 원칙 네 가지

- **동료 폴더가 깨져도 SKEWNONO 는 뜹니다.** 백엔드는 `backend/contrib/<slug>/` 아래만
  fail-soft 로 로드합니다. import 가 실패하면 그 패키지만 건너뛰고 부팅 로그와
  `SKEWNONO_CONTRIB_FAILED` 에 이름이 남습니다. 프런트엔드는 같은 Nuxt 빌드에 들어간
  코드가 빌드를 막을 수 있으므로, 검증 전 작업 공간은 **자기 빌드를 따로 가지는
  2단계나 3단계**로 시작하고 1단계는 승격 뒤에 씁니다.

- **폴더가 곧 기능입니다.** 백엔드는 `routes.py` 가 있는 폴더를 자동 등록하고,
  프런트엔드는 `components/<slug>/` 에 접두어를 자동으로 붙입니다. 아래 표의 "손대는
  줄" 밖으로 나오는 공유 파일 변경에는 이유가 있어야 합니다.
- **주소는 SKEWNONO 쪽에 고정합니다.** 작업 공간의 진입 주소는 항상 `/<slug>` 입니다.
  뒤에 무엇이 있든 사용자가 북마크하는 주소는 변하지 않고, 나중에 위치를 옮겨도
  링크가 깨지지 않습니다.
- **mock/office 이중화는 선택입니다.** `providers/mock.py` 와 `office.py` 는 집에서
  개발하는 소유자의 제약을 푸는 장치이지 기능의 자격 요건이 아닙니다. 레지스트리는
  `routes.py` 를 기능의 표식으로 보고 `providers/` 는 별개 질문으로 다룹니다
  (`backend/_runtime/office_registry.py` 의 docstring). 사무실에서만 개발한다면
  `providers/` 폴더를 만들지 않습니다. 만들 거면 `mock.py` 와 `office_example.py` 를
  모두 갖춰야 합니다. `office.py` 만 있는 seam 은 부팅을 거부합니다.

## 슬러그 규칙

슬러그 하나가 백엔드 폴더, API 경로, 페이지 경로, 활동 로그 키를 모두 정합니다.

- 백엔드 폴더와 API 접두어는 **snake_case** 입니다: `backend/contrib/my_tool/`, `/api/my_tool/...`.
- 페이지 경로는 **kebab-case** 입니다: `/my-tool`. 활동 로그가 페이지 경로의 `-` 를
  `_` 로 바꾸고 API 경로는 첫 세그먼트를 그대로 쓰므로, 이렇게 해야 둘이 같은
  `my_tool` 로 모입니다. API 경로를 kebab 으로 쓰면 `backend/_logging/feature_map.py`
  에 규칙 한 줄을 더해야 하고, 한 번 기록된 슬러그는 되돌릴 수 없습니다.
- `_` 로 시작하는 폴더는 공유 plumbing 으로 취급되어 등록되지 않습니다.
- 백엔드 슬러그가 겹치면 부팅이 실패합니다. 페이지 경로가 겹치면 Nuxt 가 조용히
  하나만 남기므로, `frontend/app/pages/` 의 기존 이름과 겹치지 않는지 먼저 봅니다.

## 백엔드

```text
backend/contrib/<slug>/
├── __init__.py            # from .routes import bp  (앱 팩토리는 이 패키지에서 bp 를 찾습니다)
├── routes.py              # bp = Blueprint("<slug>", __name__), 경로는 /<slug>/... 로 시작
├── data.py                # 사내 OpenSearch/Redis 를 직접 읽습니다
├── tests/test_routes.py   # 정상 응답 shape 하나, 소스 없을 때 503 하나
└── MIGRATION.md           # 아래 세 항목
```

`MIGRATION.md` 에는 세 가지를 적습니다. 소유자와 목적 한 줄, 읽는 사내 소스와 부르는
SKEWNONO API, 그리고 자기 폴더 밖 공유 파일을 건드렸다면 어느 줄을 왜 건드렸는지.

- 앱 팩토리가 `routes.py` 를 찾아 `backend.contrib.<slug>` 패키지를 import 하고 그
  `bp` 를 `/api` 아래에 등록합니다. `contrib/` 아래에서는 import 실패나 `bp` 누락이
  부팅을 막지 않고 그 패키지만 빠집니다. 자기 엔드포인트가 404 면 부팅 로그에서
  `contrib feature ... failed to load` 를 찾습니다. 등록 코드는 고치지 않습니다.
- 신원(LASTUSER 쿠키), 요청 제한, 에러 JSON, 활동 로그는 자동으로 상속됩니다.
- `data.py` 는 **import 시점에 사내 자원을 만지지 않습니다.** 연결은 첫 호출에서
  엽니다. import 시점에 실패하면 앱 전체가 부팅되지 않습니다.
- 사내 소스를 못 읽을 때는 `raise RuntimeError("...")` 를 그대로 던집니다. 전역
  핸들러가 **정확히 `RuntimeError` 인 예외**만 JSON 503 으로 바꾸고, 서브클래스는
  500 으로 남깁니다. 다른 기능의 예외 클래스를 import 하지 않습니다. 집에서는 이
  기능이 늘 503 인데, 그것이 정상입니다.
- 요청 제한은 사용자당 `/api/*` 전체 공유 예산(50 req / 5 s)입니다. 갤러리나 폴링처럼
  한 화면이 그 예산을 넘는 작업 공간은 소유자가 `backend/__init__.py` 의
  `_EXEMPT_BLUEPRINTS` 에 넣어야 합니다. 먼저 요청 수를 줄이는 쪽을 검토합니다.
- 주기 작업은 기능 폴더 안에서 스레드나 타이머로 띄우지 않습니다. 실행 프로세스가
  하나로 정해져 있기 때문입니다. `backend/_scheduler/tasks/<slug>.py` 에 두고
  `backend/_scheduler/registry.py` 에 등록하는데, 이 등록은 공유 파일 편집이므로
  소유자와 상의합니다.
- 게이트: `.venv/bin/python -m pytest backend/contrib/<slug> -q`, `.venv/bin/python -m ruff check .`

## 프런트엔드: 세 단계 중 하나를 고릅니다

독립성이 낮은 쪽부터 높은 쪽 순서입니다. **검증 전 작업 공간은 2단계나 3단계로
시작합니다.** 1단계는 SKEWNONO 와 같은 빌드에 들어가므로 문법 오류 하나가 전체 빌드를
막고, 그래서 승격된 기능만 씁니다. SKEWNONO 의 데이터와 화면을 많이 쓰면 2단계,
자기 데이터로 자기 도구를 만들면 3단계가 맞습니다.

| 단계 | 형태 | 공유되는 것 | SKEWNONO 쪽에 손대는 줄 |
| --- | --- | --- | --- |
| 1 | 같은 Nuxt 안의 폴더 | 신원, API, 헤더, 디자인 토큰, NuxtUI | `headerNav.ts` 1 줄 |
| 2 | 같은 origin 의 별도 Vite 앱 | 신원, API | `headerNav.ts` 1 줄 + 빌드 순서 |
| 3 | 별도 URL 로 이동 | 없음 | `headerNav.ts` 1 줄 + 페이지 1 개, API 를 쓰면 CORS |

### 1단계: 같은 Nuxt 안의 폴더 (승격 뒤)

```text
frontend/app/
├── pages/<slug>/index.vue          # 하위 페이지도 이 폴더 안에 둡니다
├── components/<slug>/*.vue         # <Slug…> 접두어가 자동으로 붙습니다
└── composables/use<Slug>Api.ts     # useSemListApi.ts 를 복사해서 시작합니다
```

Nuxt 를 몰라도 됩니다. 페이지는 그냥 Vue SFC 이고 `import { ref } from 'vue'` 로
써도 됩니다. 본보기는 `components/magpixel/` 과 `pages/thickness/` 입니다.

- API 주소는 `/api` 를 문자열로 박지 않고 기존 composable 처럼
  `joinApiPath(useRuntimeConfig().public.apiBase, '/<slug>/...')` 로 만듭니다.
  `NUXT_PUBLIC_API_BASE` 로 바뀔 수 있는 값입니다.
- 유틸은 `utils/<slug>/` 아래 두고 명시적으로 import 합니다. 최상위 `utils/` 와
  `composables/` 는 자동 import 라, 기존 이름과 겹치면 빌드 경고 한 줄만 남기고
  조용히 버려집니다.
- 색상은 `--sk-*` 토큰만 씁니다. `DESIGN.md` 를 먼저 읽습니다.
- `/ebeam/<tool>/[fab]/` 탭 계열로는 넣지 않습니다. 공유 파일이 넷으로 늘고 fab 과
  툴 타입 라우팅 의미까지 따라야 합니다. 탭 승격은 소유자가 합니다.

손대는 한 줄은 `utils/headerNav.ts` 의 `HEADER_LINKS` 에 `group: 'lab'` 항목입니다.
실험실 메뉴 노출과 기능 탭 표시가 여기서 함께 파생됩니다. 활동 랭킹은 `/<slug>` 경로
하나면 자동으로 잡힙니다. 하위 페이지 여러 개를 한 슬러그로 묶고 싶을 때만
`utils/pageIdentity.ts` 의 `IDENTITY_RULES` 와 그 fixture 를 소유자와 함께 고칩니다.

### 2단계: 같은 origin 의 별도 Vite 앱

Nuxt 는 `frontend/public/` 을 빌드 결과에 그대로 복사하고, 클라우드의 Flask 는 요청
경로와 **정확히 일치하는 파일**이 있으면 그 파일을, 없으면 루트 `index.html` 을
돌려줍니다. 그래서 정적 빌드를 던져 넣기만 하면 두 번째 SPA 가 같은 origin 에서
돕니다. 단, 디렉터리 index 는 찾지 않으므로 진입 주소는 파일명까지 적습니다.

- `frontend/apps/<slug>/` 에 Vite + Vue 프로젝트. `base: '/<slug>/'`,
  `outDir: '../../public/<slug>'`, **해시 라우터**. `/<slug>/foo` 같은 깊은 경로는
  파일이 없어 루트 `index.html` 로 떨어지기 때문입니다.
- 진입 주소는 `/<slug>/index.html`. `utils/headerNav.ts` 에 그 주소로 항목 한 줄.
- 같은 origin 이므로 LASTUSER 쿠키와 `/api/*` 호출이 그대로 동작합니다.
- 개발 중에는 Nuxt dev 서버가 `public/` 을 서빙하므로 `vite build` 후 `/<slug>/index.html`
  로 확인합니다. Flask 의 SPA 서빙은 클라우드에서만 켜집니다.
- 사무실 빌드 순서에 이 앱의 `vite build` 를 Nuxt 빌드 **앞에** 한 줄 추가합니다.
  이것도 공유 파일(`frontend/package.json`)이므로 소유자와 상의합니다.
- 헤더, 툴/fab 컨텍스트, 디자인 토큰, 활동 랭킹은 없습니다. 토큰과 폰트는 CSS 를
  따로 가져옵니다.

### 3단계: 별도 URL 로 이동

동료가 자기 클라우드 공간에 자기 저장소, 자기 서버, 자기 배포로 올립니다.

- SKEWNONO 에는 `pages/<slug>.vue` 하나를 두고 `navigateTo(url, { external: true })`
  로 보내고, `utils/headerNav.ts` 에 `/<slug>` 항목 한 줄을 둡니다. 메뉴에 외부
  링크를 직접 넣지 않는 이유는 퍼지는 주소를 `/<slug>` 로 고정하기 위해서입니다.
- 신원이 끊깁니다. LASTUSER 쿠키는 호스트 단위라 다른 URL 에서는 보이지 않습니다.
  상대 앱이 자기 게이트를 두거나, 같은 상위 도메인의 서브도메인으로 두고 쿠키
  도메인을 맞춰야 합니다.
- SKEWNONO 의 `/api/*` 를 부르려면 CORS 허용 origin 이 `backend/__init__.py` 에 하나로
  박혀 있으므로 소유자가 그 줄을 고쳐야 합니다. 요청 제한과 활동 로그는 상대 앱
  기준으로 남습니다.

## 반입 경로

사무실에서는 GitHub 로그인이 되지 않으므로 PR 흐름이 성립하지 않습니다.

1. 동료는 `main` 에서 브랜치를 만들어 자기 폴더 안에서 작업하고 **commit 합니다.**
   `git status` 가 깨끗해야 합니다. `format-patch` 와 `bundle` 은 commit 된 변경만
   담고, 작업 트리의 변경은 조용히 빠집니다.
2. `git format-patch main` 또는 `git bundle create <slug>.bundle main..HEAD` 로
   묶어 소유자에게 넘깁니다. 사내 공유 경로에 bare 저장소를 두고 그곳에 push 해도
   됩니다. `git diff --stat main...HEAD` 를 같이 넘기면 수신 쪽이 완전성을 맞춰볼 수
   있습니다.
3. 소유자가 사무실에서 받아 검토하고, 집에서 `main` 에 올립니다.

소유자는 **patch 전체**를 봅니다. 기능 폴더도 부팅 때 import 되므로 검토 밖이
아닙니다. 다만 자기 폴더 안은 동작과 게이트 통과 여부만 보고, 위 표의 "손대는 줄"
밖으로 나온 공유 파일 변경은 줄마다 이유를 확인합니다.

## 승격

작업 공간이 검증되어 정식 기능이 되면 소유자가 옮깁니다. 컴포넌트가 순수 Vue 이면
복사로 끝나고, 라우팅과 데이터 호출만 Nuxt 식으로 바꿉니다. 3단계에서 1단계로 오는
경우도 `/<slug>` 주소는 그대로이므로 사용자 링크는 바뀌지 않습니다.

## 게이트 요약

```bash
.venv/bin/python -m pytest backend/contrib/<slug> -q   # 저장소 루트
.venv/bin/python -m ruff check .
npm run typecheck && npm run lint && npm test   # frontend/
npm run lint:md                                 # Markdown 을 고쳤다면, 저장소 루트
```
