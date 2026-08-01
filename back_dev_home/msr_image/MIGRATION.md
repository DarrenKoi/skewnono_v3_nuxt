# msr_image — office 마이그레이션

## 개요

`msr_image`는 OpenSearch 문서를 읽는 다른 기능들과 달리 **순수 FTP** 소스입니다.
office 어댑터는 계측 장비(HITACHI SEM) FTP 서버에 직접 접속해 이미지/cond 파일을
가져오는 relay 역할만 수행하며, 어떤 OpenSearch 인덱스도 조회하지 않습니다.
캐시 계층만 MinIO를 사용합니다.

## 규칙

- 먼저 추적 스켈레톤을 복사한 뒤 그 복사본에서만 작업합니다:
  `cp providers/office_example.py providers/office.py`. `office.py`는
  `.gitignore`에 등록되어 있어 office 현장에만 존재하므로 `git pull` 시
  충돌하지 않습니다.
- `providers/office.py`만 수정합니다. `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`,
  `tests/`는 건드리지 않습니다.
- `ftp_handler`(vendored)는 절대 수정하지 않고 `FtpFleetDownloader`를
  인스턴스화만 합니다. 코드 안에서 모듈 수준 이름 `FtpFleetDownloader`로
  참조해야 테스트가 monkeypatch로 대체할 수 있습니다.
- 전송 계층은 import 시점에 플랫폼으로 선택됩니다. office 로컬 PC(Windows)는
  장비로의 직접 FTP가 차단되어 있으므로 `ftp_handler.proxy`(HTTP 프록시 경유)를,
  그 외(Phase 3 클라우드 등 직접 접속 가능한 호스트)는
  `ftp_handler.direct_downloader`를 import합니다. 두 클래스는 생성자·메서드
  표면이 동일하고 dataclass(`HostSpec`/`ListDir`/report류)도 공유하므로 import
  한 줄만 다릅니다. 프록시의 위치와 인증(`PROXY_URL`/`PROXY_TOKEN`)은
  `ftp_handler/proxy/proxy_downloader.py` 상단의 모듈 상수이며 배포마다 한 번만
  수정합니다.
- 완료 기준: 아래 확인 명령이 모두 초록색으로 통과하는 것입니다.

## 엔드포인트별 동작

| 함수 | 시그니처 | 동작 |
| --- | --- | --- |
| `list_images` | `(eqp_ip, class_name, msr, _config=None) -> list[str]` | FTP로 디렉터리를 리스팅하고 `.jpeg`/`.jpg`/`.tif`/`.tiff`만 필터링합니다 (tool 은 JPEG 프리뷰와 TIFF 원본을 함께 저장 — 2026-07-24 office 확인) |
| `fetch_image` | `(locator, _config=None) -> FetchedImage` | 이미지 바이트를 내려받아 확장자 기준 content-type(`image/jpeg` 또는 `image/tiff`)으로 반환하고, cond 사이드카는 best-effort로 붙입니다. 브라우저는 TIFF 를 `<img>` 로 렌더링하지 못하므로 frontend 는 TIFF 에 다운로드 fallback 을 보여줍니다 |
| `download_all` | `(eqp_ip, class_name, msr, names, on_file, concurrency=6, _config=None)` | 같은 장비를 가리키는 `HostSpec` n개를 한 번의 fleet 호출로 넘겨 연결 n개로 분산하고, 파일별 진행 상황을 `on_file` 콜백에 스트리밍으로 보고합니다 |

- 경로 조립은 `paths.py`(`image_dir`/`image_path`/`cond_path`)가 전담하며,
  office 어댑터는 이를 그대로 재사용합니다. `_ROOT`(`/HITACHI/DEVICE/HD`)가
  실제 장비 경로와 다르면 `paths.py`를 함께 확인해야 합니다.
- 에러 매핑: 디렉터리 리스팅 실패는 `SourceUnavailable`, 이미지 파일이 없으면
  `ImageNotFound`, 그 외 fetch 실패는 `SourceUnavailable`로 변환합니다. cond
  파일 다운로드 실패는 에러로 취급하지 않고 `cond=None`으로 넘어갑니다.

## 환경 변수

| 키 | 의미 | 기본값 |
| --- | --- | --- |
| `SKEWNONO_TOOL_FTP_USER` | 장비 FTP 계정 | `hitachi` |
| `SKEWNONO_TOOL_FTP_PASSWORD` | 장비 FTP 비밀번호 | `hid` |
| `SKEWNONO_TOOL_FTP_PORT` | FTP 포트 | `21` |
| `SKEWNONO_TOOL_FTP_CONCURRENCY` | `download_all`의 최대 동시 연결 수 | `6` |
| `SKEWNONO_TOOL_FTP_TIMEOUT` | 연결/응답 타임아웃(초) | `8.0` |
| `SKEWNONO_TOOL_SUBNETS` | 허용 서브넷 CIDR 목록(쉼표 구분); SSRF 가드용 IP 검증에 사용 | 빈 값(제한 없음) |
| `SKEWNONO_IMAGE_CACHE_BUCKET` | MinIO 캐시 버킷 | 없음(office에서 필수 설정) |
| `SKEWNONO_IMAGE_CACHE_PREFIX` | MinIO 캐시 오브젝트 키 prefix | `image_cache/` |
| `IMAGE_CACHE_DIR` | 홈/mock 디스크 캐시 루트(office에서는 사용하지 않음) | `var/image_cache` |
| `IMAGE_CACHE_TTL_HOURS` | 캐시 보존 시간; 이보다 오래된 항목을 purge가 삭제 | `72`(3일) |
| `IMAGE_CACHE_PURGE_HOUR` | 야간 purge cron 실행 시각(0–23) | `3` |
| `SKEWNONO_MSR_IMAGE_MAX_JOBS` | 동시 실행 가능한 다운로드 job 수 | `2` |
| `SKEWNONO_MSR_IMAGE_JOB_TTL` | job 상태 보존 시간(초); Redis 키 TTL로도 사용 | `3600` |
| `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD` | multi-worker job 상태 저장소; 설정 시에만 Redis 레지스트리 선택 | 없음 |

## MinIO 캐시 prefix 주의사항

- `SKEWNONO_IMAGE_CACHE_BUCKET`/`SKEWNONO_IMAGE_CACHE_PREFIX`는 측정 데이터가
  저장되는 버킷·prefix(`minio_handler/minio_config.py`가 가리키는 것)와
  **반드시 분리**해야 합니다. 캐시는 TTL 경과 시 통째로 삭제(`purge`)되므로,
  측정 원본 데이터와 같은 prefix를 공유하면 원본이 함께 지워질 수 있습니다.
- `minio_cache.py`의 `MinioImageCache`는 클라이언트를 `use_prefix(None)`로
  passthrough 상태로 두고 `_key()`만을 유일한 prefix 소스로 사용합니다.
  따라서 `minio_config.py`의 기본 PREFIX(`2067928/`)는 적용되지 않으며,
  `SKEWNONO_IMAGE_CACHE_PREFIX`에 사용자 네임스페이스를 포함한 **전체
  prefix**를 넣어야 합니다. office 레이아웃(bucket=`user`,
  네임스페이스=`2067928/` — `minio_config.py`와 동일, 2026-07-24 확인)
  기준 설정:

  ```text
  SKEWNONO_IMAGE_CACHE_BUCKET=user
  SKEWNONO_IMAGE_CACHE_PREFIX=2067928/image_cache/
  ```

  측정 데이터는 `2067928/hitachi_sem/...` 아래에 있으므로 두 prefix 는
  겹치지 않고, purge 는 `2067928/image_cache/` 아래만 지웁니다.

  클라이언트에 별도 default prefix까지 설정하면 `_resolve_key()`가 prefix를
  두 번 붙이게 되어 `put`/`get`/`exists`/`stat` 모두 어긋나고, `purge`가
  넘겨받는 오브젝트 이름도 이미 이중 prefix가 붙은 상태라 `delete_many`가
  재차 잘못 resolve해 아무것도 지우지 못하는(에러 없이 조용히 실패하는)
  상황이 생깁니다. `msr_file` MIGRATION.md에 기록된 동일 함정을 참고하십시오.

## job 상태 저장소 (multi-worker)

`POST /api/msr-images`가 만든 job의 상태를 어디에 두는지는 `jobs.py`의
`make_registry(cfg, provider)`가 결정합니다. 선택 조건은 **두 가지가 모두**
참일 때만 Redis입니다.

| 조건 | 저장소 | 이유 |
| --- | --- | --- |
| provider가 `office`이고 `REDIS_HOST`가 설정됨 | `RedisJobRegistry` | 요청이 다른 프로세스에 도달할 수 있음 |
| 그 외 전부 | `MemoryJobRegistry` | 단일 프로세스이므로 외부 의존성이 불필요함 |

office라는 사실만으로는 부족합니다. Redis 없이 단일 워커로 띄운 office
인스턴스도 그대로 동작해야 하기 때문입니다. 반대로 `REDIS_HOST`만 있는 것도
근거가 되지 못합니다. home에서도 다른 기능 때문에 `REDIS_*`가 설정되어 있을 수
있기 때문입니다.

`gunicorn -w N`으로 띄우면 `POST`를 받은 워커와 폴링을 받는 워커가 서로 다른
프로세스일 수 있습니다. 이때 job 상태가 프로세스 메모리에 있으면 옆 워커에서
정상 실행 중인 job을 폴링이 404로 응답하게 됩니다. `RedisJobRegistry`는 그
상태를 모든 워커가 이미 공유하는 Redis로 옮깁니다.

### 키 레이아웃

```text
skewnono:msr_image:job:<job_id>    HASH   job_id status total done ok ng
skewnono:msr_image:fail:<job_id>   LIST   실패 건당 JSON {name, error}
```

- 실패 목록은 `:failures` 접미사가 아니라 **별도 prefix**를 씁니다.
  `running_count()`의 job 스캔이 리스트 키를 집어 들면 `HGET`이 WRONGTYPE
  오류를 내기 때문입니다.
- 카운터는 read-modify-write가 아니라 `HINCRBY`로 증가시킵니다. bounded
  다운로드 풀의 여러 스레드가 같은 job을 동시에 갱신하므로, get/put 경합이
  생기면 진행 카운트가 조용히 유실됩니다.
- 모든 키에 `SKEWNONO_MSR_IMAGE_JOB_TTL`(기본 3600초)을 걸고 갱신할 때마다
  다시 설정합니다. 따라서 완료된 job은 스스로 사라지고, 다운로드 도중 죽은
  워커가 `max_jobs` 슬롯을 영구히 점유하지 못합니다.

### 주의: `create_bounded`는 원자적이지 않습니다

메모리 구현과 달리 Redis 쪽 `create_bounded`는 "개수 확인 → 생성"이 한 번의
원자적 연산이 아닙니다. 두 워커가 같은 순간에 `POST`를 받으면 둘 다 통과할 수
있습니다. 이는 soft 자원 가드로서 **허용된 초과**입니다. 최악의 경우 동시
다운로드가 몇 개 늘어날 뿐이고, job 키가 TTL로 만료되므로 슬롯이 새지 않고
스스로 복구됩니다. 엄밀한 원자성은 Lua 스크립트가 필요한데, 얻는 것에 비해
home에서 검증할 수 없다는 비용이 큽니다.

home/mock은 단일 프로세스이므로 `MemoryJobRegistry`를 그대로 유지합니다.

## 비동기 다운로드 시작 (202)

`POST /api/msr-images`는 디렉터리 리스팅을 **기다리지 않고** 즉시
`202 {job_id}`를 반환합니다. 리스팅은 장비 FTP 왕복이라 요청 경로에서 가장
느린 단계이기 때문입니다. office 어댑터를 만들 때 다음을 유의하십시오.

- `list_images`는 요청 스레드가 아니라 백그라운드 워커에서 호출됩니다.
- job은 리스팅 **전에** 생성되므로 `total`이 `0`(미확정)으로 시작하고,
  리스팅이 끝난 뒤 워커가 실제 개수로 채웁니다.
- 따라서 `list_images`가 `SourceUnavailable`을 던져도 `POST`가 503을 주지
  않습니다. 클라이언트는 이미 `job_id`를 받았기 때문에, 그 실패는 폴링
  응답의 `status: "error"`로 드러납니다. 절대 `done`으로 끝나서는 안 됩니다.
  `done`은 클라이언트가 "이미지가 0장인 성공"으로 읽기 때문입니다.
- IP 검증·경로 세그먼트 검증은 그대로 요청 경로에 남아 동기 400을 반환합니다.

## 후속 과제 2 (종결): 태그 기반 native lifecycle — office에서 불가

- 현재 `purge()`는 애플리케이션 레벨에서 `last_modified`를 스캔해 TTL이
  지난 오브젝트를 `delete_many`로 지우는 방식입니다(스케줄러가 주기 호출).
- MinIO/S3의 native lifecycle 규칙(태그 기반 만료)으로 대체하는 안은
  **office에서 불가함이 확인되어 종결**되었습니다(2026-07-24). office
  계정은 `user/<사번>/...` prefix 아래 오브젝트 접근만 허용되며, lifecycle
  설정 등 버킷 수준 작업 권한이 없습니다. prefix 밖 키에 대한 조회는
  `NotFound`가 아니라 `AccessDenied`로 응답됩니다(msr_file 스모크 테스트의
  raw exists 프로브가 이렇게 실패하는 것이 정상입니다).
- 따라서 애플리케이션 레벨 purge가 유일한 정리 수단이며, 계속 유지합니다.
- office 기준 정리 주체는 **둘**입니다. (1) 이 앱의 APScheduler purge가 매일
  `IMAGE_CACHE_PURGE_HOUR`시에 돌고, (2) Airflow DAG `minio_purge_image_cache`
  (`flask_modules` 저장소의 `airflow_mgmt/`, 매일 03:35 KST)가 같은 prefix를
  `last_modified` 기준으로 훑습니다. 둘 다 **3일**로 맞춰져 있습니다
  (2026-08-02에 7일에서 함께 줄였습니다, user-confirmed). DAG는 앱이
  내려가 있는 동안 쌓인 오브젝트를 잡는 안전망이므로, 이 앱의 보존 기간만 더
  짧게 바꾸면 DAG는 영구히 아무것도 찾지 못합니다. 한쪽을 조정하면 반드시 다른
  쪽도 함께 맞추십시오.
- 혼동 주의: `IMAGE_CACHE_TTL_HOURS`/`IMAGE_CACHE_PURGE_HOUR`는 **MinIO 설정이
  아니라 Flask 프로세스가 읽는 앱 환경 변수**입니다. MinIO 권한과 무관하므로
  `.env`만 고치면 보존 기간을 조정할 수 있습니다. 저장 시각을 우리가 따로
  기록할 필요도 없습니다 — `last_modified`는 PUT 시점에 MinIO 서버가 찍어
  주고 일반 `list_objects` 응답으로 돌아오며, 이는 prefix 범위의 오브젝트
  읽기 권한만 있으면 되는 작업입니다.

## 확인

```bash
SKEWNONO_MSR_IMAGE_PROVIDER=office .venv/bin/pytest back_dev_home/msr_image/tests/test_office_template.py
.venv/bin/python -m back_dev_home.msr_image.providers.office
```

두 명령 모두 저장소 루트에서 실행해야 합니다. 첫 번째는 템플릿 로직(경로
조립 + fleet downloader 사용법)이 fake `FtpFleetDownloader`로 검증되는지 확인하는
회귀 테스트입니다. 두 번째는 self-contained 스모크 테스트로, meas_hist에서
최신 문서(msr/class_name/eqp_ip/minio_pkl)를 찾아 pickle의
`mp_image_name NN` 컬럼(정답 목록)과 `list_images()`의 FTP 리스팅을 대조하고
이미지 1장을 `fetch_image()`로 실제로 내려받습니다. 요청 경로는 순수 FTP
그대로이며 OpenSearch/MinIO 는 `__main__` 진단 블록에서만 import 됩니다.
pickle 이름이 tool FTP 에 없으면 `MISSING`, tool 에만 있는 파일은 `extra`
(대개 정상)로 출력됩니다.
