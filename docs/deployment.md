# 배포 가이드 (Phase 3 — 사내 클라우드)

사무실에서 번들을 만들어 클라우드 호스트로 옮기는 절차를 정리한 문서입니다.
현재 목표는 **실현 가능성 확인(feasibility) 배포**이므로, mock 데이터를 서빙하는
번들이라도 정상 기동하면 성공으로 간주합니다.

## 1. 전체 흐름

```bash
# 사무실 PC, 저장소 루트에서
npm --prefix front-dev-home run build
.venv/bin/python -m scripts.pack_deploy
```

`dist/skewnono-<타임스탬프>/` 폴더가 생성됩니다. 이 폴더를 통째로 클라우드
호스트의 `/project/workSpace/` 아래에 복사한 뒤, 번들 안의 `DEPLOY.md` 를
따라 실행합니다.

| 단계 | 실행 위치 | 명령 |
| --- | --- | --- |
| 1 | 사무실 | `npm --prefix front-dev-home run build` |
| 2 | 사무실 | `.venv/bin/python -m scripts.pack_deploy` |
| 3 | 사무실 → 클라우드 | 번들 폴더를 `/project/workSpace/` 로 복사 |
| 4 | 클라우드 | `python preflight.py` (설치 전) |
| 5 | 클라우드 | `pip install -r back_dev_home/requirements.txt` |
| 6 | 클라우드 | `python preflight.py` (설치 후) |
| 7 | 클라우드 | `uwsgi --ini wsgi.ini` |

`preflight.py` 를 **두 번** 실행하는 이유가 있습니다. 첫 번째 실행은 전송이
올바른 경로에 올바른 구조로 도착했는지 확인합니다. 두 번째 실행은 의존성
설치가 끝났는지 확인합니다.

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
| `index.py`, `wsgi.ini` | WSGI 진입점입니다. |
| `back_dev_home/` | Flask 백엔드 전체입니다. |
| `front-dev-home/.output/public/` | 빌드된 SPA 입니다. |
| `ops_store/`, `minio_handler/`, `ftp_handler/` | 앱이 실제로 import 하는 벤더 패키지입니다. |

| 제외 | 이유 |
| --- | --- |
| `ops_index_mgmt/` | 인덱스 생성 도구로, 런타임에 사용되지 않습니다. |
| `docs/`, `openwiki/` | 문서이며 런타임 역할이 없습니다. |
| `__pycache__/`, `tests/`, `conftest.py`, `*.md` | 실행에 불필요합니다. |

빌드된 SPA 출력물은 예외적으로 **가지치기 없이 그대로** 복사합니다. Nuxt 빌드
산출물의 파일명은 우리 규칙이 해석할 수 있는 대상이 아니어서, 만약 `tests` 라는
이름의 디렉터리나 `.md` 로 끝나는 자산이 있으면 조용히 삭제되어 런타임에만
404 가 발생하기 때문입니다.

### 추적되지 않는 파일을 포함하는 이유

`pack_deploy` 는 git 이 아니라 **작업 트리**를 읽습니다. 다음 파일들은
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

## 4. 클라우드 쪽에서 준비해야 하는 것

| 항목 | 확인 방법 | 담당 |
| --- | --- | --- |
| `/project/workSpace` 에 압축 해제 | `python preflight.py` 의 PATH 검사 | 배포자 |
| 이미지에 `hcputil` 이 있는지 | `preflight.py` 가 어떤 철자로 해석되었는지 보고합니다 | 인프라 |
| SSO 에 호스트명 등록 | 로그인 리다이렉트가 동작하는지 | SSO 담당 |
| 실제 `SKEWNONO_SECRET_KEY` 설정 | `preflight.py` 의 경고가 사라지는지 | 배포자 |

`hcputil` 은 requirements.txt 가 아니라 **클라우드 이미지가 제공**합니다.
사내 요구사항 문서(`docs/afm/개발요구.txt:31`)에는 `auto` 로,
라이브러리 실제 철자는 `auth` 로 적혀 있어 양쪽 모두를 시도하도록 되어 있습니다.
어느 쪽이 실제로 존재하는지는 `preflight.py` 가 첫 실행에서 알려줍니다.

SSO 호스트명 등록은 테스트 URL 과 정식 URL 각각에 대해 필요합니다.

- `skewnono-v3-webapp.aipp01.skhynix.com` (feasibility 테스트)
- `skewnono.skhynix.com` (정식 전환 시)

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
curl localhost:5000/api/health/providers
```

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
