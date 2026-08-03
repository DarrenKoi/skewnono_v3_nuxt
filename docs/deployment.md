# 배포 가이드 (Phase 3 — 사내 클라우드)

사무실에서 번들을 만들어 클라우드 호스트로 옮기는 절차를 정리한 문서입니다.
현재 목표는 **실현 가능성 확인(feasibility) 배포**이므로, mock 데이터를 서빙하는
번들이라도 정상 기동하면 성공으로 간주합니다.

## 1. 전체 흐름

```bash
# 사무실 PC, 저장소 루트에서
npm --prefix front-dev-home run build
.venv/bin/python scripts/deploy/pack.py
```

`dist/skewnono-<타임스탬프>/` 폴더가 생성됩니다. 이 폴더의 **내용**을 클라우드
호스트의 기존 `/project/workSpace/`에 덮어쓴 뒤, 번들 안의 `DEPLOY.md`를 따라
실행합니다. `/project/workSpace` 자체를 삭제하거나 교체하지 않습니다.

| 단계 | 실행 위치 | 명령 |
| --- | --- | --- |
| 1 | 사무실 | `npm --prefix front-dev-home run build` |
| 2 | 사무실 | `.venv/bin/python scripts/deploy/pack.py` |
| 3 | 사무실 → 클라우드 | 번들 내용을 기존 `/project/workSpace/`에 덮어쓰기 |
| 4 | 클라우드 | `python preflight.py` (설치 전) |
| 5 | 클라우드 | `pip install -r back_dev_home/requirements.txt` |
| 6 | 클라우드 | `python preflight.py` (설치 후) |
| 7 | 클라우드 | `uwsgi --ini wsgi.ini` |

`preflight.py` 를 **두 번** 실행하는 이유가 있습니다. 첫 번째 실행은 전송이
올바른 경로에 올바른 구조로 도착했는지 확인합니다. 두 번째 실행은 의존성
설치가 끝났는지 확인합니다.

### 클라우드 이미지에 미리 설치된 패키지

클라우드 호스트는 일부 패키지를 이미 설치한 상태로 제공됩니다. `pip install -r`
은 **이미 설치된 패키지가 명시된 버전 조건을 위반할 때만** 업그레이드하므로,
`requirements.txt` 에 적히지 않은 하위 의존성은 이미지가 주는 낡은 버전 그대로
남습니다. 2026-08-03 클라우드 배포에서 `minio_handler` 의 `pickle.loads` 가
`ModuleNotFoundError: No module named 'numpy._core'` 로 실패한 원인이 이것입니다.
numpy 가 `requirements.txt` 에 선언되어 있지 않아 pandas 를 통해 간접 설치되었고,
이미지의 numpy 1 이 그대로 유지되었습니다.

따라서 **버전이 중요한 패키지는 간접 의존성이라도 `requirements.txt` 에 직접
선언합니다.** 선언하지 않은 조건은 pip 가 강제할 방법이 없습니다.

`preflight.py` 의 `VERSION` 검사는 설치된 버전이 `requirements.txt` 의 조건을
만족하는지 확인합니다. import 성공만으로는 버전을 증명할 수 없고, 오프라인
미러에 해당 릴리스가 없거나 root 소유 `site-packages` 에 권한 오류가 나거나
시스템 사본이 venv 를 가리는 경우 모두 설치가 조용히 실패하기 때문입니다.
실패 줄에는 설치된 버전과 **실제 설치 경로**가 함께 출력되므로, 가려진 사본을
바로 구분할 수 있습니다.

## 2. 경로가 곧 설정입니다

이 배포에서 가장 조심해야 할 부분입니다. `back_dev_home/_runtime/env.py` 의
`is_cloud()` 는 **자기 자신의 파일 경로가 `/project/workSpace` 아래에 있는지**
로 클라우드 여부를 판단합니다. 설정 파일이나 환경 변수가 아닙니다.

따라서 번들을 다른 경로에 풀면 다음이 모두 조용히 꺼집니다.

- SSO 인증 블루프린트가 등록되지 않습니다.
- SPA 가 마운트되지 않아 모든 페이지가 404 를 반환합니다.
- 사이트 판별이 home 으로 떨어져 mock 데이터를 서빙합니다.

그러면서도 애플리케이션은 HTTP 200 을 계속 반환합니다. 즉 **아무것도 실패했다고
알려주지 않습니다.** 이것이 `preflight.py` 가 이 경로 검사를 가장 먼저 수행하는
이유입니다.

같은 이유로 번들 내부의 디렉터리 깊이도 그대로 유지해야 합니다.
`spa_dir()` 이 `parents[2]` 를 거슬러 올라가므로, 번들을 한 겹 더 감싸서 풀면
SPA 경로가 어긋납니다.

## 3. 번들에 무엇이 들어가는가

| 포함 | 이유 |
| --- | --- |
| `back_dev_home/` | Flask 백엔드 전체입니다. |
| `front-dev-home/.output/public/` | 빌드된 SPA 입니다. |
| `ops_store/`, `minio_handler/`, `ftp_handler/` | 앱이 실제로 import 하는 벤더 패키지입니다. |

| 제외 | 이유 |
| --- | --- |
| `index.py`, `wsgi.ini` | 기존 `/project/workSpace`에 영구 보관하는 기동 파일입니다. |
| `ops_index_mgmt/` | 인덱스 생성 도구로, 런타임에 사용되지 않습니다. |
| `docs/`, `openwiki/` | 문서이며 런타임 역할이 없습니다. |
| `__pycache__/`, `tests/`, `conftest.py`, `*.md` | 실행에 불필요합니다. |

클라우드용 `preflight.py`는 오버레이가 끝난 최종 `/project/workSpace`에서
`index.py`와 `wsgi.ini`의 존재 여부를 계속 검사합니다. 두 파일 중 하나라도
유실되면 uWSGI 기동 전에 차단합니다.

빌드된 SPA 출력물은 예외적으로 **가지치기 없이 그대로** 복사합니다. Nuxt 빌드
산출물의 파일명은 우리 규칙이 해석할 수 있는 대상이 아니어서, 만약 `tests` 라는
이름의 디렉터리나 `.md` 로 끝나는 자산이 있으면 조용히 삭제되어 런타임에만
404 가 발생하기 때문입니다.

### 추적되지 않는 파일을 포함하는 이유

`pack.py`는 git이 아니라 **작업 트리**를 읽습니다. 다음 파일들은
의도적으로 gitignore 되어 있지만 반드시 함께 배포되어야 합니다.

- `back_dev_home/<feature>/providers/office.py` — 사내 데이터 어댑터입니다.
- `back_dev_home/.env` — `create_app()` 이 읽는 설정입니다.
- `minio_handler/minio_config.py` — MinIO 접속 정보입니다.

`git archive` 로 번들을 만들면 이 파일들이 빠진 채로 정상 기동하여 운영 환경에서
mock 데이터를 서빙하게 됩니다. 아무 경고도 나오지 않기 때문에 가장 위험한
실패 방식입니다.

> **주의:** 번들에는 자격 증명이 포함됩니다. 출력 폴더는 `chmod 700` 으로
> 생성되며, 공유 스토리지에 두지 않아야 합니다.
>
> 다만 이 권한은 **전송 과정에서 유지되지 않습니다.** `scp -r` 을 `-p` 없이
> 쓰거나 SFTP 클라이언트, tar 압축 해제를 거치면 대상 서버의 umask 로 디렉터리가
> 새로 만들어집니다. 복사 직후 다음을 다시 적용해 주십시오.
>
> ```bash
> chmod 700 /project/workSpace
> chmod 600 /project/workSpace/back_dev_home/.env
> chmod 600 /project/workSpace/minio_handler/minio_config.py
> ```

### `wsgi.ini` 의 두 설정은 스케줄러가 의존합니다

`wsgi.ini` 는 번들에 들어가지 않고 클라우드 호스트에 영구 보관되므로, 아래 두
줄은 **여기에만 기록됩니다.** 지우면 스케줄러가 조용히 멈춥니다.

| 설정 | 지웠을 때 |
| --- | --- |
| `enable-threads = true` | `BackgroundScheduler` 가 요청 스레드 밖에서 돌지 못해 tick 하지 않습니다. 오류는 나지 않고 작업만 영영 실행되지 않습니다. |
| `lazy-apps = true` | 앱이 마스터에서 한 번 만들어지는데 스레드는 `fork()` 를 넘어가지 못하므로, 스케줄러가 **어느 워커에도 존재하지 않게** 됩니다. `uwsgi.worker_id()` 기반 선출도 무의미해집니다. |

`harakiri = 60` 은 스케줄러 작업을 죽이지 않습니다 — harakiri 타이머는 **요청**
단위로 걸립니다. `max-requests = 1000` 은 워커 1 을 주기적으로 재생성하며,
그때마다 스케줄러가 앱 부팅 시간만큼 끊겼다 복구됩니다.

돌고 있는지 확인하려면 `GET /api/health/jobs` (관리자)를 봅니다. 작업 하나가
하루에 여러 줄로 보이면 선출이 실패한 것입니다.

스케줄러를 멈춰야 하면 `SKEWNONO_SCHEDULER_ENABLED=0` 을 설정하고 재기동합니다.
코드 변경은 필요하지 않습니다.

## 4. 클라우드 쪽에서 준비해야 하는 것

| 항목 | 확인 방법 | 담당 |
| --- | --- | --- |
| 기존 `/project/workSpace`에 오버레이 | `python preflight.py`의 PATH 및 영구 파일 검사 | 배포자 |
| `LASTUSER` 쿠키가 브라우저에 전달되는지 | 페이지 접속 후 로그의 `user=` 필드 | 인프라 |
| `back_dev_home/.env` 배치 | `python preflight.py`의 파일 존재 검사 | 배포자 |
| **`SKEWNONO_SECRET_KEY` 설정 (필수)** | 값이 없으면 앱이 **기동을 거부**합니다 | 배포자 |
| **`SKEWNONO_LOG_ENV=production` 설정** | `python preflight.py`의 `SKEWNONO_LOG_ENV` 검사 | 배포자 |
| `skewnono_logging` 롤오버 alias 생성 | `python ops_index_mgmt/skewnono_logging.py` | 배포자 |

### `SKEWNONO_SECRET_KEY` 는 이제 필수입니다

`back_dev_home/.env` 에 반드시 값이 있어야 하며, 없거나 비어 있으면 클라우드에서
앱이 뜨지 않습니다. 집과 사무실 localhost 는 종전대로 기본값으로 동작합니다.

이 키는 자기 신원 입력(`/identify`)이 만든 세션에 서명합니다. 서명이 없으면
"디렉터리로 확인된 신원"이라는 표시를 사용자가 스스로 바꿔 넣을 수 있습니다.
기본값은 **이 저장소에 공개되어 있는 상수**이므로, 값을 두지 않은 채 배포하면
서명이 없는 것과 같으면서 아무 경고도 나오지 않습니다. 그 조용한 상태를 기동
오류로 바꾼 것이 이 규칙입니다.

검사는 **값을 골랐는지**만 봅니다. 강도는 보지 않으므로 임의의 비어 있지 않은
문자열이면 통과합니다.

```bash
# /project/workSpace/back_dev_home/.env
SKEWNONO_SECRET_KEY=<임의의 비어 있지 않은 문자열>
```

### `SKEWNONO_LOG_ENV` 는 어느 인덱스에 기록할지를 정합니다

활동 로그(OpenSearch)의 대상 alias 는 이 값 하나로 결정됩니다.

| 값 | alias | 쓰는 곳 |
| --- | --- | --- |
| `local` | `skewnono_logging_local` | 사무실 PC localhost (Phase 2) |
| `production` | `skewnono_logging` | 사내 클라우드 (Phase 3) |

클라우드에서는 **반드시 `production`** 이어야 합니다. `local` 로 두어도 앱은
정상 기동하고 요청도 빠짐없이 색인됩니다 — 다만 전부 사무실용 alias 로
들어갑니다. `/admin-logs` 도 같은 값을 읽어 같은 alias 를 조회하므로 화면상으로
전혀 이상이 없고, 운영 인덱스만 조용히 비어 있게 됩니다. 두 alias 는 ISM 보존
기간도 다르므로(사무실 진단용 vs. 운영 365일) 잘못 기록된 문서는 예정보다
일찍 삭제됩니다. 2026-08-03 클라우드 배포에서 실제로 발생한 사례입니다.

```bash
# /project/workSpace/back_dev_home/.env
SKEWNONO_LOG_ENV=production
OPENSEARCH_HOST=<사내 OpenSearch 호스트>
OPENSEARCH_USER=<계정>
OPENSEARCH_PASSWORD=<암호>
```

`OPENSEARCH_PASSWORD` 가 없으면 로그 핸들러 자체가 설치되지 않고 stderr 에 한
줄만 남습니다. 반대로 암호만 있고 `SKEWNONO_LOG_ENV` 가 없으면 `create_app()`
이 `LoggingConfigurationError` 로 죽습니다. `preflight.py` 가 이 세 조합을 모두
구분해 보고합니다.

alias 는 미리 만들어 두어야 합니다. 로그 핸들러는 대상이 **번호가 붙은 롤오버
alias** 임을 확인한 뒤에만 색인하며, 아니면 배치를 통째로 버리고
`[opensearch-log]` 한 줄을 남깁니다.

```bash
.venv/bin/python ops_index_mgmt/skewnono_logging.py --dry-run
.venv/bin/python ops_index_mgmt/skewnono_logging.py
```

기동 후 실제 적재 여부는 `GET /api/health/logging` (관리자 전용) 의
`target.alias` 와 `diagnostics.indexed` 로 확인합니다.

### `SKEWNONO_TRUST_PROXY` 는 nginx 뒤로 옮긴 뒤에만 설정합니다

현재 `wsgi.ini` 는 `http-socket` 으로 직접 노출되므로 `request.remote_addr` 이
이미 실제 클라이언트 IP 입니다. 이 상태에서 이 값을 켜면 `X-Forwarded-For`
헤더를 신뢰하게 되어 **누구나 자기 IP 를 위조**할 수 있습니다.

반대로 nginx 뒤로 옮기면서 켜지 않으면 모든 요청이 `127.0.0.1` 로 기록되며,
이때도 오류는 나지 않습니다. 구성 변경과 이 값은 반드시 함께 움직여야 합니다.

### 사용자 식별 방식

사용자 식별은 **사내 인프라가 내려주는 `LASTUSER` 쿠키**만 사용합니다. 기존 AFM
앱이 읽던 것과 같은 쿠키이며, 클라우드 이미지가 제공하는 별도의 SSO 모듈은
필요하지 않습니다. `LAST_USER` 철자도 함께 허용하며 `LASTUSER` 가 우선입니다.

쿠키가 없으면 사용자 ID 를 **`anonymous`** 로 둡니다. AFM 앱이 쓰던 것과 같은
관례입니다. 페이지도 API 도 그대로 동작합니다.

| 요청 | 쿠키 있음 | 쿠키 없음 |
| --- | --- | --- |
| 페이지·정적 자원 | SPA | SPA |
| `/api/*` | `200` (사번으로 기록) | `200` (`anonymous` 로 기록) |
| `/api/admin/*` | allowlist 에 있으면 `200` | `403` |

`anonymous` 는 **공유 ID 이지 신원이 아닙니다.** 관리자가 되어서는 안 되며,
두 가지가 독립적으로 이를 보장합니다 — `_auth/admin.py` 의 두 allowlist 어디에도
없고, `X` 로 시작하지 않아 접근 제어 대상도 아닙니다. `SKEWNONO_ADMIN_USERS` 에
절대 추가하지 마십시오.

> **주의**: 사내망 내부라는 전제 위에 서 있는 설계입니다. 쿠키가 없는 요청도
> 데이터를 받습니다.

### 익명 사용자는 `/identify` 로 유도됩니다

쿠키로 확인되지 않은 사용자는 SPA 가 **`/identify` 화면**으로 보내 사번과 이름을
직접 입력받습니다. 입력된 신원은 `members` 디렉터리로 확인한 뒤 서명된 세션에
기록되며, 활동 로그에는 `identity_source: declared` 로 남아 인프라가 준 신원과
구분됩니다. 이것이 없으면 쿠키를 떨어뜨리는 호스트 설정과 실제 익명 접근이
`anonymous` 한 줄로 합쳐져 구분되지 않습니다.

이 유도는 **Nuxt 라우터 미들웨어**이며 Flask 는 익명 요청을 종전대로 통과시킵니다
(이유는 아래 문단). `curl` 로 API 를 직접 부르면 우회되므로 **보안 경계가
아닙니다.** 서버가 강제하는 규칙은 하나입니다 — 직접 입력한 신원은 사번이
무엇이든 **관리자가 될 수 없습니다.**

디렉터리에 row 가 없는 사번도 통과시키되 "미검증"으로 표시합니다. 협력사·서비스
계정처럼 쿠키는 있으나 등재되지 않은 인원이 실재하기 때문이며, 실제 비율은
사무실에서 확인할 항목으로 `docs/datatables/members.txt` 에 남겨 두었습니다.

페이지를 막지 않는 이유는, 인증 게이트가 애플리케이션의 첫 `before_request`
이기 때문입니다. 여기서 응답을 돌려주면 `index.html` 과 번들까지 함께 막혀
화면에 아무것도 표시되지 않습니다. 실제로 이 자리에서 리다이렉트를 돌려주던
시절에는 브라우저가 앱과 SSO 사이를 무한히 오가다 빈 화면으로 끝났습니다.

로그에서 `path=/ status=302` 또는 `ms=-1` 이 보이면 이 게이트가 요청을
가로챈 것입니다. 라우트나 SPA 마운트가 아니라 `_auth/middleware.py` 를 먼저
확인해 주십시오.

> **주의**: 번들이 `/project/workSpace` 아래에 있지 않으면 `is_cloud()` 가
> False 가 되어 **홈용 identity provider** 가 선택됩니다. 이 경우 쿠키가 없는
> 모든 요청이 관리자 계정 `local-dev` 로 취급되므로, `preflight.py` 의 PATH
> 검사를 반드시 통과시켜야 합니다.

`preflight.py`는 `back_dev_home/.env`의 값 중 **`SKEWNONO_SECRET_KEY`,
`SKEWNONO_LOG_ENV`, `OPENSEARCH_PASSWORD`, `OPENSEARCH_LOGGING_DISABLED`** 만
읽습니다. 앞의 둘은 값이 잘못되면 기동이 실패하거나 로그가 엉뚱한 인덱스로
가기 때문이고, 뒤의 둘은 그 판정에 필요하기 때문입니다. 그 외의 값은 읽지도
검증하지도 않습니다.

## 5. 전환 시 재빌드가 필요하지 않습니다

SPA 는 `/api` 를 **상대 경로**로 호출하고 Flask 가 같은 오리진에서 이를
서빙합니다. 따라서 하나의 번들이 테스트 URL 과 정식 URL 양쪽에서 그대로
동작하며, 전환 시점에 다시 빌드할 필요가 없습니다.

이 구조 때문에 다음 사항을 지켜야 합니다.

- CORS 허용 오리진을 추가하지 않습니다.
- `SESSION_COOKIE_SECURE` 나 HSTS 를 설정하지 않습니다. 두 URL 모두
  http 전용이므로, 이를 켜면 로그인 세션이 끊깁니다.

## 6. 기동 후 확인

```bash
curl -b "LASTUSER=<관리자 사번>" localhost:5000/api/health/providers
```

이 엔드포인트는 관리자 전용입니다. provider 표와 site/mode 를 그대로
드러내므로 일반 사용자에게는 403 을 돌려줍니다. 쿠키 없이 호출하면 확인이
되지 않으니, `SKEWNONO_ADMIN_USERS` 에 등록된 사번을 넣어 호출합니다.

이 엔드포인트는 provider 교체 메커니즘을 **의도적으로 우회**합니다. 교체
가능한 방식으로 만들면 정작 문제가 생긴 상황에서 잘못된 값을 보고할 수 있기
때문입니다. 따라서 어떤 기능이 실제로 office 데이터를 서빙 중인지에 대한
정직한 답을 여기서 얻을 수 있습니다.

번들에 함께 들어 있는 `MANIFEST.txt` 에는 패킹 시점의 git sha, 브랜치,
office 어댑터 목록, 그리고 패킹 당시 발생한 경고가 기록되어 있습니다.
어댑터 존재 여부로 provider 가 결정되는 구조이므로 나중에 읽을 설정 줄이
남지 않습니다. 즉 이 파일이 "지금 저 위에서 무엇이 돌고 있는가"를 알 수 있는
유일한 기록입니다.

## 7. 옵션

| 옵션 | 동작 |
| --- | --- |
| `--build` | 패킹 전에 프런트엔드 빌드를 먼저 실행합니다. |
| `--out <경로>` | 출력 폴더를 지정합니다. 기본값은 `dist/` 입니다. |
| `--strict` | 모든 권고(advisory) 검사를 차단(blocking) 으로 승격합니다. |

`--strict` 는 mock → office 전환이 끝난 뒤에 사용합니다. 지금은 전환이
의도적으로 미완성 상태이므로, office 어댑터가 없다는 사실이 배포를 막아서는
안 됩니다. 기본 동작에서 차단되는 항목은 **확실히 기동에 실패하는 경우**뿐입니다.
