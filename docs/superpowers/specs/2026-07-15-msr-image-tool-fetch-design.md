# MSR 이미지 tool FTP 수집 Design

- Date: 2026-07-15
- Status: **결정 완료 — 디스크 캐시 + 비동기 전체 다운로드(job + poll) + APScheduler 야간 정리. 구현 대기.**
- Scope: `back_dev_home/msr_image/` (신규 feature), `ftp_handler/` (수정 없이 사용), `front-dev-home/app/` (이미지 소비 경로)
- 선행/기준 문서:
  - 오피스 전환 규약: [`docs/superpowers/plans/2026-07-15-office-data-connection.md`](../plans/2026-07-15-office-data-connection.md)
  - 공통 adapter 규칙: [`docs/back-end/office-data-adapters.md`](../../back-end/office-data-adapters.md)
  - provider 선택: `back_dev_home/_runtime/data_provider.py`

## 1. 배경

스큐보아(Skewvoir)는 MSR의 SEM 이미지를 갤러리와 대시보드에서 보여 줍니다. 현재
프런트엔드는 `<img :src="msrImageUrl(name)">` 형태로 이미지당 GET 하나를
브라우저가 팬아웃합니다(`useMsrFileApi.ts` → `/api/msr-image?name=<name>`). 홈(Phase 1)
에서는 `get_msr_image(name)`이 결정적 SVG placeholder를 반환하고, 그 docstring은
사무실 빌드가 이 함수를 **"같은 파일명으로 tool에서 실제 이미지를 가져오는 fetch"**
로 교체한다고 이미 명시하고 있습니다.

이번 작업은 그 사무실 fetch를 실제로 구현하기 위한 것입니다. MSR 측정 데이터는
MinIO에 저장하지만 **이미지는 저장하지 않고 tool에서 직접 가져옵니다.** 흐름은
`tool FTP → Flask → 프런트엔드`이며, 다수 이미지를 빠르게 relay 하는 것이 목표입니다.

수집 엔진으로는 `flask_modules`에서 가져온 `ftp_handler`를 사용합니다.

## 2. 목표와 비목표

### 목표

- MSR 이미지를 tool FTP 서버에서 가져와 프런트엔드로 relay 합니다.
- 한 번 받은 이미지는 Flask 서버 디스크에 **약 1일** 남겨 다음 요청을 빠르게 relay 합니다.
- MSR 한 건의 이미지(보통 수백 장)를 한 번에 받는 **"전체 다운로드"** 액션을 제공합니다.
- 오래된 캐시 이미지는 **야간에 스케줄러가 정리**합니다.
- 홈↔사무실 전환은 **바이트 출처(SVG 생성 ↔ FTP fetch)** 한 곳만 바뀌고 나머지
  기계(캐시·serve·전체 다운로드·정리)는 두 환경에서 동일하게 동작합니다.

### 비목표

- 이미지를 MinIO 등 영구 저장소에 적재하지 않습니다(캐시는 임시입니다).
- 이미지당 병렬 RETR(한 host에 다중 연결)은 하지 않습니다. `ftp_handler`는 host 간
  동시성 + host 내 연결 재사용만 제공하며, tool FTP 세션 수 보호를 위해 그대로 둡니다.
- 자동 프리페치(MSR 열자마자 전체 수집)는 하지 않습니다. 수백 장이 무겁기 때문에
  **명시적 버튼**으로만 전체 수집합니다.
- 사무실 `providers/office.py`의 실제 경로 템플릿·자격 증명·IP 필드 확정은 이 문서의
  범위가 아니라 사무실 연결 노트에서 확정합니다(§8).

## 3. 고정 결정

| 항목 | 결정 |
| --- | --- |
| 수집 엔진 | `ftp_handler.FtpFleetDownloader` (vendored, 수정 금지) |
| 캐시 매체 | Flask 서버 로컬 디스크 |
| 캐시 보존 | 약 1일(`IMAGE_CACHE_TTL_HOURS`, 기본 24) |
| 캐시 위치 | `IMAGE_CACHE_DIR` 환경 변수, 기본 `<project>/var/image_cache`, Git 제외 |
| 정리 방식 | APScheduler `BackgroundScheduler` cron(기본 03:00) |
| 전체 다운로드 | **비동기** — `POST /api/msr-images` → `202 {job_id}`, `GET /api/msr-images/<job_id>` 폴링 |
| job 상태 저장 | 홈/단일 worker: 프로세스 내 메모리. 사무실 다중 worker: Redis 키(우리 측 관리) |
| 이미지당 serve | `GET /api/msr-image` — 캐시 hit → sendfile, miss → fetch → 캐시 write → serve |
| provider 선택 | `get_data_provider("msr_image")` (`SKEWNONO_MSR_IMAGE_PROVIDER`) |
| mock 구현 | `providers/mock.py` — 기존 SVG 생성기(오프라인 흐름 유지) |
| office 구현 | `providers/office.py` — `ftp_handler` fetch(사무실에서 실제 경로 확정) |
| 경로 구성 | **백엔드 측**에서 조립. 프런트엔드는 검색 row의 의미 필드만 전송 |
| 오류 정책 | 자동 mock fallback 금지. 사무실 source 실패는 JSON 오류로 노출(§7) |
| ftp_handler 수정 | 금지. 필요 시 이 저장소와 `flask_modules` **양쪽** 동일 수정 |

## 4. 아키텍처

### 4.1 단일 seam — `ImageSource`

홈↔사무실에서 바뀌는 유일한 지점은 "바이트를 어디서 얻는가"입니다.

| provider | 단건 fetch | 다건 fetch(전체 다운로드) |
| --- | --- | --- |
| `mock` | 이름 seed로 SVG 바이트 생성 | 요청한 이름마다 SVG 생성 후 캐시에 기록 |
| `office` | `FtpFleetDownloader.download` 단일 파일 | `FtpFleetDownloader.download` fleet + `save_to_dir` 싱크 |

선택은 skew feature와 동일하게 `data.py` dispatcher에서 `get_data_provider("msr_image")`
로 결정하고 provider 모듈을 lazy import 합니다(사무실 전용 의존성을 홈 기동 경로에서 제외).

### 4.2 Phase 무관 기계(두 환경 공통)

- **`ImageCache`** — `IMAGE_CACHE_DIR` 아래 디스크 캐시. `(host, remote_path)`를
  `ftp_handler.local_target`으로 로컬 경로에 결정적으로 매핑해 캐시 키로 사용합니다.
  `get_or_serve(locator)`는 디스크에 있으면 그대로, 없으면 `source.fetch` → write → serve.
- **엔드포인트**(신규 blueprint `msr_image`)
  - `GET /api/msr-image` — 이미지당 serve. rate-limit 예외 유지.
  - `POST /api/msr-images` — 전체 다운로드 시작(비동기). fleet download를 백그라운드로
    kick off하고 `202 {job_id}` 반환.
  - `GET /api/msr-images/<job_id>` — 진행/결과 폴링. `{status, done, total, ok, ng, failures}`.
- **야간 정리** — APScheduler cron이 `IMAGE_CACHE_TTL_HOURS`보다 오래된 파일 삭제.
  `create_app`에서 기동(단일 프로세스 가정, `BackgroundJobs`와 동일한 주의).

`ftp_handler`가 이 기계의 세 조각을 그대로 제공합니다.

| 필요 | ftp_handler 제공물 | 이유 |
| --- | --- | --- |
| 수백 장을 RAM 폭증 없이 디스크로 | `save_to_dir(dest, ...)` (streaming `on_file`) | 파일당 write 후 바이트 폐기 |
| 캐시 키(로컬 경로) 재계산 | `local_target(dest, host, remote_path, ...)` | download 없이 순수 매핑 |
| host 간 동시성 + host별 연결 재사용 | `FtpFleetDownloader.download` | 로그인 1회/host, 부분 실패 격리 |
| 요청 스레드 밖 실행 | `BackgroundJobs.submit/get` (또는 bare 스레드) | `202` 즉시 반환, work는 백그라운드 |
| 파일당 진행 표시 | `save_to_dir(..., then=cb)` hook | 우리 카운터를 원자적으로 증가 |

## 5. 컴포넌트와 파일

신규 feature `back_dev_home/msr_image/` (feature-sliced 규약, app factory가 `routes.py`
자동 등록):

| 파일 | 역할 |
| --- | --- |
| `routes.py` | blueprint `msr_image`. `GET /msr-image`, `POST /msr-images`, `GET /msr-images/<job_id>` |
| `contracts.py` | `ImageLocator`, `DownloadAllRequest`, `DownloadJobStatus` TypedDict |
| `data.py` | seam. `get_data_provider("msr_image")`로 provider dispatch |
| `providers/__init__.py` | provider lazy import 안 함(홈 기동 보호) |
| `providers/mock.py` | 기존 `get_msr_image` SVG 생성기 이전 |
| `providers/office.py` | `ftp_handler` 기반 단건/다건 fetch(사무실 확정 항목 포함) |
| `cache.py` | `ImageCache` — 경로 매핑, get/write/serve, purge |
| `jobs.py` | 전체 다운로드 job 실행/상태. `ftp_handler.BackgroundJobs`는 executor로만, 상태는 우리 측(메모리/Redis) |
| `scheduler.py` | APScheduler cron 등록 헬퍼 |
| `__fixtures__/` | 대표 응답(job status) fixture |

기타 수정(phase 무관 인프라, vendored 아님):

- `back_dev_home/__init__.py` — rate-limit 예외 엔드포인트 이름을 `msr_image.msr_image`로
  이동, `create_app`에서 정리 스케줄러 기동.
- `back_dev_home/msr_file/{routes,data}.py` — 이미지 관련 코드 제거(`msr_image`로 이전).
  `/msr-file`, `/msr-files`(측정 데이터)는 그대로 둡니다.
- `back_dev_home/requirements.txt` — `apscheduler>=3.10` 추가.
- `.gitignore` — `var/` 및 캐시 경로 추가.
- 프런트엔드 `useMsrFileApi.ts`(또는 신규 `useMsrImageApi.ts`), 갤러리/대시보드
  이미지 컴포넌트, MSR 뷰의 "전체 다운로드" 버튼.

## 6. 데이터 흐름

### 6.1 이미지당 serve (`GET /api/msr-image`)

1. 프런트엔드 `<img>`가 locator 필드(host + 경로 구성 필드 + name)로 요청.
2. 백엔드가 locator로 캐시 경로 계산(`local_target`).
3. 캐시 hit → `send_file`(디스크에서 즉시 relay).
4. 캐시 miss → `source.fetch(locator)`:
   - mock: SVG 바이트 생성.
   - office: 단일 파일 FTP fetch.
   그 후 캐시에 write, 그리고 serve. 실패 시 §7 오류.

첫 열람자가 fetch 비용을 지불하고, 이후 열람자는 하루 동안 디스크에서 relay 됩니다.

### 6.2 전체 다운로드 (`POST /api/msr-images`, 비동기)

1. MSR 뷰의 "전체 다운로드" 버튼 → body `{ host, images: [locator...] }`(또는 MSR 단위
   필드 + 백엔드 경로 조립).
2. 백엔드가 `job_id`를 발급하고 상태 `{status: running, done: 0, total: N}`를 우리 측
   저장소(홈: 메모리, 사무실 다중 worker: Redis)에 기록한 뒤, fleet download를 백그라운드로
   `submit`하고 **즉시 `202 {job_id}` 반환**.
3. 백그라운드 work: host별로 묶어 `HostSpec` 구성 후
   `download(specs, on_file=save_to_dir(CACHE_DIR, then=progress.increment))`.
   - host 내: 연결 1회 재사용, 파일 순차 RETR.
   - host 간: `max_concurrency`까지 동시.
   - `then` hook이 파일당 진행 카운터를 원자적으로 증가(락 또는 Redis `HINCRBY`).
   - 종료 시 최종 `{status: done, ok, ng, failures}` 기록. **바이트는 상태에 넣지 않음.**
4. 프런트엔드는 `GET /api/msr-images/<job_id>`를 폴링해 진행률·결과를 표시.
5. 완료 후 갤러리 `<img>` GET은 모두 캐시 hit.

각 HTTP 요청이 짧게 끝나므로 gateway/브라우저 timeout과 worker 점유 문제가 사라집니다.
다운로드 소요 시간 자체는 동일합니다(연결 재사용·캐시가 속도를 결정). 비동기는 속도가
아니라 **견고성과 진행 표시**를 위한 것입니다.

원칙: `ftp_handler`는 **바이트**를 옮기고, SKEWNONO는 **상태**(job 상태·캐시 디렉터리·
라우트)를 소유합니다. 그래서 `BackgroundJobs`의 프로세스-로컬 레지스트리를 수정할 필요가
없습니다(vendored 규약 준수, §10).

## 7. 오류 계약 (mock fallback 금지)

오피스 전환 규약(office-data-connection §Task 0.3)을 따릅니다. source 실패를 mock
이미지로 위장하지 않습니다.

| 상황 | HTTP | 의미 |
| --- | --- | --- |
| 필수 환경 변수 누락(FTP 자격 등) | 500 | `office_configuration_error`, 내부 값 은닉 |
| tool FTP 연결 실패/timeout | 503 | `office_source_unavailable`, 자격 정보 미노출 |
| tool에 파일 없음 | 404 | 실제 부재. 프런트엔드는 실패 이미지 상태 표시 |
| 전체 다운로드 시작 | 202 | `{job_id}` 반환, 실제 수집은 백그라운드 |
| 전체 다운로드 부분 실패 | 폴링 결과 | 성공분은 캐시, 실패는 최종 상태의 `failures[]`로 보고(은닉 금지) |
| 알 수 없는 job_id 폴링 | 404 | 만료·오타. 프런트엔드는 재시도 안내 |

프런트엔드는 실패한 `<img>`를 조작된 SVG가 아니라 명시적 실패 상태로 렌더링합니다.

## 8. 경로 구성과 사무실 확정 항목

이미지의 tool 위치는 사무실 `meas_hist_cdsem` OpenSearch index에서 옵니다(tool IP +
이미지 경로 구성 요소). 검색 섹션이 이미 그 row를 프런트엔드에 노출하므로, 프런트엔드는
**의미 필드**를 백엔드로 전달하고 백엔드가 최종 FTP 경로를 조립합니다(폴더 레이아웃을
한 곳에 고정).

사무실 연결 노트(`docs/back-end/office-sources/msr-image.md`)에서 확정할 항목:

| 항목 | 상태 |
| --- | --- |
| `meas_hist_cdsem`의 tool IP 필드명과 반환 권한 | 확인 필요 |
| 이미지 폴더/파일 경로 템플릿("경로 조금 조립") | 확인 필요 |
| 이미지 + 사이드카(`cond.txt`) 레이아웃 필요 여부 | 확인 필요(§11) |
| FTP 자격 증명·포트·passive 모드 | 환경 변수 이름만 기록 |
| 이미지 포맷/확장자(예: `.jpeg`)와 content-type | 확인 필요 |

실제 IP·경로·자격·row는 연결 노트에 기록하지 않습니다(규약 준수).

## 9. 설정(환경 변수)

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `SKEWNONO_MSR_IMAGE_PROVIDER` | `mock` | provider 선택(전역 `SKEWNONO_DATA_PROVIDER` override) |
| `IMAGE_CACHE_DIR` | `<project>/var/image_cache` | 디스크 캐시 루트(Git 제외) |
| `IMAGE_CACHE_TTL_HOURS` | `24` | 정리 기준 나이 |
| `IMAGE_CACHE_PURGE_HOUR` | `3` | 야간 정리 cron 시각 |
| `SKEWNONO_TOOL_FTP_USER` / `_PASSWORD` | — | tool FTP 자격(사무실, Git 미커밋) |
| `SKEWNONO_TOOL_FTP_PORT` | `21` | tool FTP 포트 |
| `SKEWNONO_MSR_IMAGE_MAX_JOBS` | `2` | 동시 전체 다운로드 job 수(`BackgroundJobs(max_workers)`) |
| `SKEWNONO_MSR_IMAGE_JOB_TTL` | `3600` | job 상태 보존(초). Redis 키 만료에도 사용 |
| `REDIS_*`(기존) | — | 사무실 다중 worker의 job 상태 저장(홈/단일 worker는 불필요) |

자격 증명은 환경 변수/사내 secret manager로만 주입하며 Git에 커밋하지 않습니다.

## 10. 홈/사무실 동작

- **홈(Phase 1)**: `mock` provider. `providers/mock.py`가 SVG를 생성해 실제 캐시에 기록하고
  serve 하므로, 버튼·진행 표시·갤러리-from-캐시·야간 정리까지 **오프라인에서 전 흐름
  검증 가능**합니다. tool·OpenSearch는 필요 없습니다.
- **사무실(Phase 2/3)**: `SKEWNONO_MSR_IMAGE_PROVIDER=office`. `providers/office.py`가
  `ftp_handler`로 실제 tool에서 fetch. 실제 경로·자격은 연결 노트에서 확정.
- 다중 worker(`gunicorn -w N`) 주의:
  - **job 상태**: `BackgroundJobs`의 레지스트리는 프로세스 로컬이라(vendored, 수정 금지)
    폴링이 다른 worker에 닿으면 못 봅니다. 그래서 관측 상태는 우리 측에서 관리합니다 —
    홈/단일 worker는 메모리, 다중 worker는 **Redis 키**. `BackgroundJobs`(또는 bare 스레드)는
    해당 worker 안에서 work를 실행하는 executor로만 씁니다.
  - **캐시 디스크**: worker가 공유 파일시스템의 같은 `IMAGE_CACHE_DIR`를 보면 문제 없습니다.
  - **정리 cron**: worker마다 뜨지만 중복 삭제는 무해합니다. 원하면 전용 프로세스로 한정합니다.

## 11. 범위 밖 / 후속

- 이미지 + `cond.txt` 사이드카(측정 조건) 표시 — `ftp_handler.save_image_with_sidecar`로
  지원 가능하나 이번 범위 밖.
- 전체 다운로드 취소/재개 — 이번 범위 밖(실패 시 재클릭으로 재수집).
- 이미지당 병렬 RETR(한 host 다중 연결).

## 12. 테스트

| 층 | 방법 | 확인 |
| --- | --- | --- |
| mock 흐름 | 홈에서 serve/miss/write/purge 단위 테스트 | SVG 캐시 생성·재serve·만료 삭제 |
| office adapter | fake downloader 주입 단위 테스트 | tool 없이 fetch·저장·부분 실패 보고 |
| 캐시 매핑 | `local_target` 기반 경로 결정성 테스트 | 같은 locator → 같은 경로 |
| 전체 다운로드 job | submit→`202`, 폴링 상태 전이, 진행 카운터, 최종 counts | 비동기 흐름 검증 |
| 진행 카운터 동시성 | 다중 host 콜백 동시 증가 | 원자적, 최종 done == total |
| 정리 | mtime 조작 후 purge 테스트 | TTL 초과분만 삭제, 최신 보존 |
| 오류 계약 | 연결 실패 강제 시 503, 설정 누락 시 500 | mock 위장 없음 |
| 라우팅 | provider dispatch 테스트(mock/office/override/invalid) | env로만 전환 |
| frontend | Nuxt 수동 smoke | 갤러리/대시보드 렌더, 전체 다운로드 버튼 동작 |
| 문서 | `npm run lint:md` | 변경 문서 오류 0 |

## 13. 인수 기준

- 홈에서 `<img>` 요청이 캐시 miss 시 SVG를 생성·캐시하고, 재요청은 디스크에서 relay 됩니다.
- 홈에서 "전체 다운로드"가 `202 {job_id}`를 즉시 반환하고, 폴링이 진행률과 최종
  `{ok, ng, failures}`를 보고하며, 완료 후 갤러리가 캐시에서 relay 됩니다.
- 야간 정리 cron이 TTL 초과 파일만 삭제하고 최신 파일은 남깁니다.
- provider 전환이 **config-only**이며 코드 변경 없이 rollback 됩니다.
- 사무실 source 실패가 mock 이미지로 위장되지 않고 §7 오류로 노출됩니다.
- `ftp_handler`는 수정되지 않습니다(vendored 규약 준수).
- `routes.py`/`contracts.py`는 phase를 모릅니다. 사무실 지식은 `providers/office.py`에만 있습니다.
