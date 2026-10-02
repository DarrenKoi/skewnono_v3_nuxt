# 14. 실행 환경과 HTTP 요청의 여행

> **기준: 2026-10-03.** 이 문서의 ‘구현’은 현재 추적된 코드와 로컬 설치를 확인한 사실입니다. 사내 호스트의 실제 설정·버전·응답은 미확인입니다. 먼저 [학습 홈](../README.md)의 버전 표를 읽습니다.

## 1. 기초 개념: 파일이 실행되는 곳을 구분합니다

웹 화면을 만드는 프로그램과 데이터를 계산하는 프로그램은 서로 다른 곳에서 실행됩니다. 브라우저는 내려받은 JavaScript를 실행해 화면을 만들고, Python 프로세스는 데이터 요청을 받아 JSON을 돌려줍니다. 개발 중 Node.js는 화면 코드를 변환하고 개발 서버를 실행합니다. 운영에서도 Node 서버가 꼭 필요한 것은 아닙니다. 이 저장소는 Nuxt를 정적 파일로 생성하고 Flask가 그 파일과 API를 함께 제공합니다.

파일을 수정했다는 사실과 실행 중인 프로세스가 새 파일을 읽었다는 사실은 다릅니다. 서버 재시작, 프런트엔드 재빌드, 브라우저 새로고침 중 무엇이 필요한지 구분해야 ‘코드를 고쳤는데 그대로’인 문제를 설명할 수 있습니다.

## 2. 전문 용어: 요청과 실행 환경

| 용어 | 뜻과 작은 예시 |
| --- | --- |
| HTTP (Hypertext Transfer Protocol) | 클라이언트가 요청하고 서버가 응답하는 규약입니다. `GET /api/sem-list`는 목록을 읽는 요청입니다. |
| URL (Uniform Resource Locator) | 자원 위치입니다. `http://localhost:3000/api/sem-list`는 스킴·호스트·포트·경로로 나뉩니다. |
| origin, 오리진 | 스킴·호스트·포트의 조합입니다. 3000과 5050은 서로 다른 오리진입니다. |
| API (Application Programming Interface) | 다른 프로그램이 사용하는 입출력 약속입니다. HTTP 상태와 JSON 필드도 약속에 포함됩니다. |
| JSON (JavaScript Object Notation) | 문자열·수·불리언·배열·객체·null로 표현하는 교환 형식입니다. Python DataFrame 자체는 JSON이 아닙니다. |
| 프록시 | 요청을 대신 전달합니다. 브라우저가 3000으로 보낸 요청을 개발 서버가 5050으로 전달할 수 있습니다. |
| CORS (Cross-Origin Resource Sharing) | 브라우저가 다른 오리진의 응답을 읽어도 되는지 정하는 HTTP 헤더 규칙입니다. 서버의 권한 검사를 대체하지 않습니다. |
| WSGI (Web Server Gateway Interface) | Python 웹 서버와 애플리케이션 사이의 호출 규약입니다. 네트워크 프로토콜 이름이 아닙니다. |
| uWSGI | WSGI 애플리케이션을 실행하는 서버 제품입니다. `uwsgi` 프로토콜과 HTTP 중 어느 것을 듣는지는 설정으로 결정합니다. |
| venv (virtual environment) | 특정 Python 실행 파일과 패키지를 분리하는 가상 환경입니다. 가상 머신이나 컨테이너는 아닙니다. |
| PATH | 명령어 실행 파일을 찾는 디렉터리 순서입니다. `python`이 `.venv/bin/python`과 같은 실행 파일인지 확인해야 합니다. |
| 잠금 파일 | 의존성을 실제 선택 버전으로 기록합니다. 설치 허용 범위와 의미가 다릅니다. |

`localhost`는 그 명령이나 브라우저가 실행되는 컴퓨터입니다. 태블릿에서 `localhost:3000`을 입력하면 개발 PC가 아니라 태블릿 자신을 찾습니다. `0.0.0.0`은 서버가 모든 인터페이스에서 수신하도록 하는 주소이며 브라우저 접속 주소로 쓰는 값이 아닙니다.

## 3. 이 저장소의 구현: 화면에서 provider까지

![개발과 운영 요청 흐름: 브라우저, Nuxt 개발 서버, Flask, provider의 경계](../assets/request-flow.svg)

### 3.1 개발 요청을 끝까지 추적합니다

1. `frontend`에서 `npm run dev`를 실행하면 Nuxt 개발 서버가 기본 3000 포트를 사용합니다.
2. 브라우저의 Vue 화면은 composable을 통해 `$fetch`로 `/api/…`를 호출합니다.
3. [nuxt.config.ts](../../../frontend/nuxt.config.ts)의 Nitro `devProxy`가 `/api`를 Flask로 전달합니다. 기본 대상은 `http://localhost:5050`입니다.
4. 프록시 내부에서 `/api` 접두사가 제거되므로 대상 URL에도 `/api`를 넣는 설정이 있습니다. 이를 제거하면 Flask가 기대한 경로와 달라집니다.
5. [Flask factory](../../../backend/__init__.py)가 신원·활동 로그·제한 정책을 적용하고 기능 Blueprint의 route를 호출합니다.
6. route는 기능의 `data.py`를 거쳐 선택된 provider를 호출합니다. [10장](../10-backend-providers/README.md)에서 선택 조건을 다룹니다.
7. provider의 Python 데이터가 응답 계약에 맞는 dict로 정규화되고 JSON 응답이 브라우저로 돌아옵니다. Vue가 받은 상태를 읽어 화면을 갱신합니다.

`/api` 상대 경로를 쓰면 브라우저는 3000과만 통신합니다. 따라서 이 개발 경로에는 다른 오리진으로 직접 요청할 때와 같은 CORS 설정이 필요하지 않습니다. 현재 Flask CORS 허용 값 `http://localhost:3100`을 보고 Nuxt 기본 포트가 3100이라고 결론 내리면 안 됩니다.

### 3.2 운영 요청과 SPA fallback

[package.json](../../../frontend/package.json)의 `build`는 `nuxt generate`입니다. 결과는 `frontend/.output/public`에 있는 HTML·JavaScript·CSS 등입니다. `ssr: false`이므로 서버가 각 페이지의 업무 데이터까지 Vue로 렌더링하지 않습니다. 브라우저가 JavaScript 실행 후 데이터를 요청합니다. SPA (Single Page Application)는 이러한 클라이언트 라우팅 방식입니다.

[SPA serving](../../../backend/_spa/serving.py)은 실제 정적 파일이 있으면 파일을 보내고, 페이지 경로면 `index.html`을 보냅니다. `/api/…`의 누락 route는 JSON 오류로 남겨야 하므로 SPA 화면으로 대체하지 않습니다. 내용 해시가 붙은 `/_nuxt/` 파일에는 긴 캐시 수명을 주고 `index.html`은 같은 방식으로 영구 캐시하지 않습니다. HTML이 새 파일 이름을 가리키도록 갱신되어야 하기 때문입니다.

**구현상 중요한 조건:** SPA mount는 `is_cloud()`가 참일 때만 등록됩니다. [env.py](../../../backend/_runtime/env.py)는 자신의 파일이 `/project/workSpace` 아래인지 확인합니다. 따라서 사무실 localhost도 무조건 Flask가 SPA를 제공한다고 말할 수 없습니다. Nuxt 개발 서버·preview·실제 uWSGI 설정 중 어떤 것으로 화면을 제공하는지 사내에서 확인해야 합니다.

### 3.3 WSGI 진입점과 포트

[index.py](../../../index.py)는 `create_app()`을 호출한 뒤 `app`과 `application`을 같은 Flask 객체로 노출합니다. 직접 실행하면 Flask/Werkzeug 개발 서버이고, [wsgi.ini](../../../wsgi.ini)의 `module = index`, `callable = application`은 uWSGI가 이 객체를 가져오도록 합니다.

현재 추적된 uWSGI 설정은 `http-socket = 0.0.0.0:5000`입니다. nginx와 Unix socket 설정은 주석으로 제시된 대안입니다. nginx가 실제 앞에 있다고 단정하지 않습니다. 회사의 ingress·도메인·TLS (Transport Layer Security) 종료 위치와 영구 `wsgi.ini`는 별도 확인 대상입니다.

직접 `index.py` 실행의 기본 포트는 5050입니다. 저장소 안내의 ‘사무실 5000’은 환경 설정 또는 uWSGI 경로와 함께 읽어야 하며, 실행 파일 자체의 기본값은 5050이라는 점을 구분합니다.

### 3.4 실행 버전과 설치 규칙

Python은 집·사무실 기준 3.11이고 CI (Continuous Integration, 지속적 통합)는 3.14입니다. 로컬 `.venv`의 현재 확인 버전은 3.11.14입니다. Python 패키지 선언에는 `>=` 하한이 많으며 재설치 시 같은 버전을 보장하는 Python 잠금 파일은 발견되지 않았습니다. NumPy `>=2`는 MSR pickle 생산자의 `numpy._core` 경로를 읽기 위한 실제 호환성 조건입니다.

Node는 CI에서 24를 선택하고 로컬 확인은 24.13.0입니다. Node 24의 TypeScript type stripping은 실행 전에 타입 구문을 지우는 기능이며 타입 검사기가 아닙니다. `npm test`가 통과해도 `npm run typecheck`가 별도로 필요합니다. 프런트엔드 `packageManager`는 `npm@11.9.0`을 선언하지만 실행한 npm 버전은 별도 확인해야 합니다.

## 4. 선택 이유와 한계

상대 `/api` 경로와 provider 경계는 화면을 집·사무실·사내 운영에서 재사용하게 합니다. 정적 생성은 운영 Node 서버 관리 부담을 줄입니다. 하지만 업무 API 장애가 없어지는 것은 아니며, 브라우저는 JavaScript가 실행되어야 실제 업무 화면을 만듭니다.

개발 프록시는 개발 서버 기능입니다. 정적 빌드에 `NUXT_API_TARGET` 값을 넣었다고 운영 프록시 서버가 생기지 않습니다. 다른 오리진으로 배포 구조를 바꾼다면 쿠키·CORS·API 주소·권한을 함께 검토해야 합니다.

## 5. 흔한 실수와 수정의 영향

- 포트가 안 맞으면 provider보다 먼저 직접 Flask 요청과 Nuxt 경유 요청을 비교합니다. 오래된 서버 프로세스가 응답할 수도 있습니다.
- `data.py`에 사내 연결 코드를 넣으면 안정된 교체 경계가 깨집니다. 사내 데이터 접근은 provider에 둡니다.
- `ssr: false`를 제거하면 인증 쿠키 전달·서버 렌더링·브라우저 전용 API·배포 산출물까지 영향이 있습니다. 단순 성능 옵션이 아닙니다.
- `/project/workSpace`를 다른 경로로 옮기면 SPA 등록뿐 아니라 신원 fallback도 바뀝니다. 실제 경로 확인은 배포의 필수 단계입니다.
- `.venv` 폴더를 다른 운영체제로 복사하면 실행 파일과 바이너리 패키지가 맞지 않습니다. 대상 환경에서 다시 설치합니다.

## 6. 안전한 실습과 확인 방법

아래 명령은 **저장소 루트**, 이미 준비된 환경에서 실행합니다. 설치·재기동·배포는 하지 않습니다. 버전 확인은 서비스 상태를 바꾸지 않습니다.

```bash
.venv/bin/python -c "import sys; print(sys.executable); print(sys.version)"
.venv/bin/python -c "import importlib.metadata as m; print(m.version('Flask'))"
node --version
npm --version
node -e "const p=require('./frontend/package-lock.json'); console.log(p.packages['node_modules/nuxt'].version)"
```

집에서 **이미 실행 중인 mock 개발 서버**를 확인할 때만 다음 두 요청을 한 번씩 보냅니다. 기대 결과는 상태 200과 같은 provider 선택 정보입니다. 연결 거부는 서버 미기동·포트 오류를, 403은 관리자 신원 문제를 의미합니다. 실제 사번·토큰을 학습 문서에 저장하지 않습니다.

```bash
curl -i http://localhost:5050/api/health/providers
curl -i http://localhost:3000/api/health/providers
```

종이에 `브라우저 → Nitro → Flask → route → data → provider`를 그린 뒤 ‘프록시 대상만 바꾸면 되는 문제’와 ‘응답 계약을 바꿔야 하는 문제’를 하나씩 설명합니다. 전자는 포트 변경, 후자는 응답 필드 이름 변경입니다. 상세 검사 경계는 [13장](../13-testing/README.md), 배포는 [16장](../16-storage-deployment/README.md)으로 이어집니다.

## 근거와 공식 문서

- [Flask 3.1 요청 lifecycle](https://flask.palletsprojects.com/en/stable/lifecycle/) — 현재 stable 문서의 3.1 계열 표시를 확인했습니다. hook 동작은 이 문서와 factory 코드를 함께 대조합니다.
- [Node 24.13.0 TypeScript 실행](https://nodejs.org/download/release/v24.13.0/docs/api/typescript.html)
- [Python 3.11 venv](https://docs.python.org/3.11/library/venv.html)
- [uWSGI 2.0 설정 옵션](https://uwsgi-docs.readthedocs.io/en/latest/Options.html) — 서버 버전은 사내 미확인입니다. 설정 의미의 일반 근거로 사용합니다.
