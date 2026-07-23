# MSR 이미지 tool FTP 수집 Design (사무실 확정판)

- Date: 2026-07-23
- Status: **결정 완료 — 신규 `msr_image` feature slice + 프런트 전송 `eqp_ip` +
  cond 헤더 번들 + 유계 병렬 풀 다운로드. 구현 대기.**
- Supersedes: `docs/superpowers/specs/2026-07-15-msr-image-tool-fetch-design.md`
  (git 히스토리 `eaf4d2b`; 트리에서는 정리됨). 이 문서는 그 설계에 **사무실
  확정 사항**(실제 경로 템플릿·jpeg·cond.txt 사이드카·자격 증명·IP 출처·속도
  요구)을 반영해 갱신한 판본입니다.
- Scope: `back_dev_home/msr_image/` (신규 feature), `back_dev_home/meas_hist/`
  (`eqp_ip` row 추가), `back_dev_home/msr_file/` (이미지 코드 제거),
  `ftp_handler/`·`minio_handler/` (수정 없이 사용), `front-dev-home/app/` (이미지
  소비 경로)

## 1. 배경과 이번 판본의 변경점

스큐보아(Skewvoir)는 MSR의 SEM 이미지를 갤러리·증거 드로어·정렬 대시보드에서
보여 줍니다. 현재 프런트엔드는 `<img :src="msrImageUrl(name)">`로 이미지당 GET
하나를 팬아웃하고(`useMsrFileApi.ts` → `/api/msr-image?name=<name>`), 홈(Phase 1)
에서는 `get_msr_image(name)`이 결정적 SVG placeholder를 반환합니다.

측정 데이터는 MinIO에 저장하지만 **이미지는 저장하지 않고 tool에서 직접
가져옵니다.** 흐름은 `tool FTP → Flask → 프런트엔드`입니다. 2026-07-15 설계에서
"확인 필요"로 남겼던 항목이 사무실에서 확정되어 이번 판본에 반영됩니다.

2026-07-15 대비 확정·변경 사항:

| 항목 | 2026-07-15 | 2026-07-23 (이번 판본) |
| --- | --- | --- |
| 이미지 dir 템플릿 | 확인 필요 | `/HITACHI/DEVICE/HD/{class_name}/images/{msr}` |
| 이미지 포맷 | 확인 필요 | `.jpeg` |
| cond.txt 사이드카 | 범위 밖(§11) | **범위 안** — 이미지당 조건을 함께 전달 |
| tool IP 출처 | 백엔드가 index에서 조회 | **프런트가 전송**(`eqp_ip`), 백엔드는 IP 검증만 |
| 이미지 집합 출처 | 프런트가 파일명 목록 전송 | **백엔드가 tool dir를 나열** |
| host 내 동시성 | 병렬 RETR 금지(비목표) | **유계 병렬 풀**(속도 요구 반영) |
| 자격 증명 | 환경 변수 이름만 기록 | 환경 변수 + 기본값 `hitachi`/`hid`(비기밀) |
| 캐시 매체 | 서버 로컬 디스크(전 phase) | 홈=로컬 디스크, **사무실=MinIO 공유 캐시**(만료 있는 임시 저장) |
| 캐시 만료 | 로컬 디스크 야간 정리 | 홈=디스크 정리, 사무실=**MinIO 나이 기반 sweep**(약 3일) |

## 2. 목표와 비목표

### 목표

- MSR 이미지를 tool FTP 서버에서 가져와 프런트엔드로 relay 합니다.
- 이미지 갤러리가 한 MSR의 **모든** 이미지를 보여 줄 수 있도록 tool 디렉터리를
  나열해 이미지 집합을 확정합니다.
- 한 번 받은 이미지는 캐시에 **약 3일** 남겨 다음 요청을 빠르게 relay 합니다.
  사무실 캐시는 **MinIO 공유 저장**이라 첫 사용자가 채우면 이후 모든 worker·모든
  사용자가 tool을 다시 거치지 않고 빠르게 받습니다.
- MSR 한 건의 이미지(보통 수백 장)를 **최대한 빠르게** 받는 "전체 다운로드"
  액션을 제공합니다(유계 병렬 풀).
- 각 이미지의 측정 조건(`cond.txt`)을 이미지와 함께 전달합니다.
- 홈↔사무실 전환은 **바이트 출처(SVG 생성 ↔ FTP fetch)** 한 곳만 바뀌고 나머지
  기계(나열·캐시·serve·전체 다운로드·정리)는 두 환경에서 동일하게 동작합니다.

### 비목표

- 이미지를 **영구** 저장소로 적재하지 않습니다. 사무실 MinIO 캐시는 나이 기반
  sweep으로 약 3일 후 삭제되는 **임시** 저장입니다(측정 데이터 버킷과 분리된 캐시
  prefix). 캐시가 사라져도 tool에서 다시 받으면 되므로 source of truth는 tool입니다.
- **무제한** 병렬 RETR은 하지 않습니다. tool FTP 세션 한도 보호를 위해 host당
  동시 연결 수를 환경 변수로 **유계**로 둡니다(§4.4).
- 자동 프리페치(MSR 열자마자 전체 수집)는 하지 않습니다. 수백 장이 무겁기 때문에
  **명시적 버튼**으로만 전체 수집합니다.
- 전체 다운로드 취소/재개는 이번 범위 밖입니다(실패 시 재클릭 재수집).

## 3. 고정 결정

| 항목 | 결정 |
| --- | --- |
| feature slice | 신규 `back_dev_home/msr_image/` (feature-sliced 규약) |
| 수집 엔진 | `ftp_handler` `FtpClient` (vendored, 수정 금지) |
| IP 출처 | 프런트가 `eqp_ip` 전송. 백엔드는 IPv4 형식(+선택적 서브넷) 검증만 |
| 이미지 dir | `/HITACHI/DEVICE/HD/{class_name}/images/{msr}` (백엔드 조립) |
| 이미지 포맷 | `.jpeg` (content-type `image/jpeg`) |
| cond 경로 | `{image_dir}/.{name}/cond.txt` (이미지별 숨김 dir 사이드카) |
| cond 전달 | serve 응답의 `X-Msr-Cond` 헤더(URL-encoded) |
| 이미지 집합 | 백엔드가 tool dir를 FTP 나열(`list_dir`) |
| 전체 다운로드 속도 | 유계 병렬 풀 `SKEWNONO_TOOL_FTP_CONCURRENCY`(기본 6) |
| 자격 증명 | `SKEWNONO_TOOL_FTP_USER`/`_PASSWORD`, 기본 `hitachi`/`hid`(비기밀) |
| 캐시 인터페이스 | `ImageCache` — 백엔드 2종을 provider가 선택 |
| 캐시(홈/mock) | `DiskImageCache` — 로컬 디스크(`IMAGE_CACHE_DIR`, Git 제외) |
| 캐시(사무실) | `MinioImageCache` — MinIO 공유 캐시 prefix. **모든 worker·사용자 공유** |
| 캐시 보존 | 약 3일(`IMAGE_CACHE_TTL_HOURS`, 기본 72) |
| cond 저장 | 홈=`<image>.cond` 사이드카, 사무실=MinIO **object metadata** |
| 정리 방식 | APScheduler cron(기본 03:00). 홈=디스크 삭제, 사무실=`list`+`delete_many`(last_modified) |
| MinIO 캐시 만료 | 나이 기반 app-side sweep(vendored 미수정·admin 불필요). native lifecycle은 §4.6 |
| 전체 다운로드 | 비동기 — `POST /api/msr-images` → `202 {job_id}`, `GET .../<job_id>` 폴링 |
| job 상태 저장 | 홈/단일 worker: 프로세스 메모리. 사무실 다중 worker: Redis 키(우리 관리) |
| provider 선택 | `get_data_provider("msr_image")`(`SKEWNONO_MSR_IMAGE_PROVIDER`) |
| mock 구현 | SVG 생성 + 합성 목록 + 합성 cond(오프라인 전 흐름 검증) |
| office 구현 | `ftp_handler` fetch. **OpenSearch 의존 없음**(순수 FTP feature) |
| 오류 정책 | 자동 mock fallback 금지. source 실패는 JSON 오류로 노출(§7) |
| ftp_handler 수정 | 금지. 필요 시 이 저장소와 `flask_modules` **양쪽** 동일 수정 |

## 4. 아키텍처

### 4.1 단일 seam — `ImageSource`

홈↔사무실에서 바뀌는 유일한 지점은 "바이트를 어디서 얻는가"입니다.

| provider | 목록(list) | 단건 fetch(image + cond) | 다건 fetch(전체 다운로드) |
| --- | --- | --- | --- |
| `mock` | 이름 seed로 N개 합성 목록 | SVG 바이트 + 합성 cond 생성 | 목록 전부 SVG 생성 후 캐시 기록 |
| `office` | tool dir `list_dir`(`.jpeg` 필터) | 단일 파일 + cond FTP fetch | 유계 병렬 풀로 fleet fetch → 캐시 싱크 |

선택은 skew feature와 동일하게 `data.py` dispatcher가 `get_data_provider("msr_image")`
로 결정하고 provider 모듈을 lazy import 합니다(사무실 전용 의존성을 홈 기동 경로에서
제외). 홈 기동 경로가 `ftp_handler`를 import 하지 않는 것이 규약입니다.

### 4.2 경로 조립과 IP 검증 (office)

프런트가 보내는 **의미 필드**로 백엔드가 최종 FTP 경로를 한 곳에서 조립합니다.

- **host** = `eqp_ip` (프런트 전송; §4.3에서 검증)
- **dir** = `/HITACHI/DEVICE/HD/{class_name}/images/{msr}`
- **image** = `{dir}/{name}`
- **cond** = `str(PurePosixPath(image).with_name(f".{name}") / "cond.txt")`
  = `{dir}/.{name}/cond.txt`
- **credentials** = `SKEWNONO_TOOL_FTP_USER`/`_PASSWORD` (기본 `hitachi`/`hid`)

이미지·cond 경로 조립은 office 어댑터의 순수 헬퍼로 두어 테스트에서 tool 없이
경로 결정성을 검증합니다.

### 4.3 IP guard

백엔드는 프런트가 보낸 `eqp_ip`로 FTP 세션을 엽니다. 클라이언트가 임의 호스트를
지정하는 SSRF-형 표면이므로, 연결 **전에** 검증합니다.

- **필수**: `ipaddress.ip_address()`로 정규 IPv4인지 검증. 실패 시 400
  `invalid_tool_ip`(값 은닉).
- **선택(권장, 사무실 확정)**: `SKEWNONO_TOOL_SUBNETS`(콤마 구분 CIDR)가 설정되면
  그 서브넷에 속하는 IP만 허용. 미설정 시 형식 검증만 수행.
- 내부망 전용 앱이라 위험은 낮지만, 형식 검증은 malformed/적대적 값이 서버를
  임의 호스트로 향하게 하는 것을 막는 값싼 방어입니다.

### 4.4 전체 다운로드 — 유계 병렬 풀

한 MSR의 모든 이미지는 **하나의 tool(host)** 에 있습니다. `FtpFleetDownloader`는
host **간** 동시성만 제공하므로, host **내** 속도를 위해 SKEWNONO 층에서 tool로
가는 `FtpClient` 연결을 **유계 풀**로 여러 개 열어 RETR을 팬아웃합니다.

- 연결 수 = `SKEWNONO_TOOL_FTP_CONCURRENCY`(기본 6). tool FTP 세션 한도 보호를 위해
  상한을 둡니다.
- `ThreadPoolExecutor(max_workers=N)`가 파일(이미지 + cond)을 풀에 분배합니다.
- 각 연결은 자기 `FtpClient` 인스턴스(1 로그인)를 재사용하며 여러 파일을 순차 RETR.
- 진행 카운터는 원자적으로 증가(락 또는 Redis `HINCRBY`), 최종 `{ok, ng, failures}`
  기록. **바이트는 상태에 넣지 않습니다.**
- `ftp_handler`는 **수정하지 않습니다** — vendored `FtpClient`를 인스턴스로만 사용.

### 4.5 캐시 인터페이스와 백엔드 2종

`ImageCache`(`cache.py`)는 "바이트 + cond를 어디에 두고 어떻게 만료하는가"를
캡슐화하는 인터페이스입니다. `(host, remote_path)`를 결정적 캐시 키로 매핑하고,
`get_or_serve(locator)`는 캐시에 있으면 그대로, 없으면 `source.fetch` → write →
serve 합니다. 백엔드는 provider와 함께 선택됩니다.

| 백엔드 | 환경 | 저장 | cond | 만료 |
| --- | --- | --- | --- | --- |
| `DiskImageCache` | 홈/mock | `IMAGE_CACHE_DIR` 로컬 디스크 | `<image>.cond` 사이드카 | APScheduler 디스크 삭제 |
| `MinioImageCache` | 사무실 | MinIO 캐시 prefix(공유) | object **metadata** | last_modified sweep |

- **공유 이득**: 사무실에서 첫 사용자가 tool→MinIO로 채우면, 이후 **모든 worker·
  모든 사용자**가 MinIO에서 relay 받습니다(로컬 디스크는 서버 로컬이라 공유 안 됨).
- serve(사무실): 캐시 키로 MinIO `exists`? → `get`(바이트) + `stat`(cond metadata)
  → `X-Msr-Cond` 헤더로 relay. miss → tool FTP fetch → MinIO `put`(image bytes +
  `metadata={cond}`) → serve. Flask가 relay 경로에 있으므로 cond 헤더가 유지됩니다.
- cond는 작아 object metadata로 충분합니다. 한도를 넘으면 `<key>.cond` 형제 객체로
  fallback(구현 시 크기 가드).

기타 phase 무관 기계:

- **`jobs.py`** — 전체 다운로드 job 실행/상태. 관측 상태는 우리 측 소유(홈: 메모리,
  사무실 다중 worker: Redis 키 + TTL). 실행기는 유계 풀(§4.4). 다운로드된 바이트는
  캐시 백엔드로 write.
- **`scheduler.py`** — APScheduler cron이 `IMAGE_CACHE_TTL_HOURS`보다 오래된 캐시를
  삭제(홈: 디스크 파일, 사무실: 캐시 prefix를 `list`로 훑어 last_modified 초과분을 `delete_many`).
  `create_app`에서 기동.

### 4.6 MinIO 만료 — app-side sweep (기본), native lifecycle (선택)

- **기본(vendored 미수정·admin 불필요)**: 이미지를 전용 캐시 prefix 아래 저장하고,
  APScheduler cron이 캐시 prefix를 `list`로 훑어 last_modified가 기준(기본 72시간)을 넘은 객체를 `delete_many`로
  정리합니다. 우리 코드가 만료를 전적으로 통제하며 `minio_handler`를 수정하지 않습니다.
- **선택(사무실 확정)**: 팀이 `s3:PutBucketLifecycle` admin 권한을 갖고 있으면,
  객체에 tag를 달고 MinIO bucket lifecycle rule로 서버 측 만료(app cleanup 0)로
  업그레이드할 수 있습니다. 단 `minio_handler.put`이 tags를 노출하도록 **양쪽 copy**
  (`minio_handler` + `flask_modules`)를 함께 수정해야 하므로 이번 기본안에서는 제외하고,
  `MIGRATION.md`에 후속 항목으로 남깁니다.

## 5. 컴포넌트와 파일

신규 feature `back_dev_home/msr_image/`:

| 파일 | 역할 |
| --- | --- |
| `routes.py` | blueprint. `GET /msr-images`(목록), `GET /msr-image`(serve), `POST /msr-images`(전체 시작), `GET /msr-images/<job_id>`(폴링) |
| `contracts.py` | `ImageListResponse`, `DownloadJobStatus` TypedDict |
| `data.py` | seam. `get_data_provider("msr_image")` dispatch |
| `providers/__init__.py` | provider lazy import 안 함(홈 기동 보호) |
| `providers/mock.py` | SVG 생성 + 합성 목록 + 합성 cond |
| `providers/office_example.py` | `ftp_handler` 기반 목록/단건/다건 fetch + 경로 조립 + IP 검증. **tracked 스켈레톤**, 사무실에서 `cp office_example.py office.py` |
| `cache.py` | `ImageCache` 인터페이스 + `DiskImageCache`(홈) / `MinioImageCache`(사무실). 키 매핑·get/write/serve·purge·cond |
| `jobs.py` | 전체 다운로드 job 실행/상태(메모리/Redis) |
| `scheduler.py` | APScheduler cron 등록 헬퍼 |
| `MIGRATION.md` | office 어댑터 확정 항목·Verify 커맨드 |
| `tests/` | mock 흐름·경로 결정성·job 전이·오류 계약·office 템플릿 |

기타 수정(phase 무관 인프라, vendored 아님):

- `back_dev_home/meas_hist/` — `MeasHistRow`에 `eqp_ip: str` 추가. office
  어댑터는 doc의 `eqp_ip`를 채우고, mock은 합성 IP를 생성합니다(§6.3).
- `back_dev_home/msr_file/{routes,data,providers}.py` — 이미지 관련 코드 제거
  (`msr_image`로 이전). `/msr-file`, `/msr-files`(측정 데이터)는 그대로.
- `back_dev_home/__init__.py` — rate-limit 예외를 `msr_image` 엔드포인트로 이동,
  `create_app`에서 정리 스케줄러 기동.
- `back_dev_home/requirements.txt` — `apscheduler>=3.10` 추가.
- `.gitignore` — `var/` 및 캐시 경로, `providers/office.py` 추가.
- 프런트엔드 — 신규 `useMsrImageApi.ts`, 갤러리/드로어/대시보드 이미지 컴포넌트,
  "전체 다운로드" 버튼 + 진행 표시(§8).

## 6. 계약 (contracts)

### 6.1 엔드포인트

| Route | 요청 | 응답 |
| --- | --- | --- |
| `GET /api/msr-images` | `eqp_ip`, `class_name`, `msr` | `{msr, class_name, images: [name…], total}` |
| `GET /api/msr-image` | `eqp_ip`, `class_name`, `msr`, `name` | 이미지 바이트(`image/jpeg` office, `image/svg+xml` mock) + 헤더 `X-Msr-Cond`(URL-encoded), `Cache-Control: public, max-age=3600` |
| `POST /api/msr-images` | body `{eqp_ip, class_name, msr}` | `202 {job_id}` |
| `GET /api/msr-images/<job_id>` | — | `{status, done, total, ok, ng, failures}` |

- 네 엔드포인트 모두 rate-limit 예외입니다(갤러리가 이미지 GET을 팬아웃).
- `GET /msr-images`(목록)와 `POST /msr-images`(시작)는 같은 경로·다른 메서드입니다.
- `name`은 256자 상한을 유지합니다(현행 msr-image 가드 이전).

### 6.2 cond 헤더

serve 응답은 이미지 바이트를 본문으로, 그 이미지의 조건을 `X-Msr-Cond` 헤더로
함께 전달합니다. `cond.txt`는 여러 줄·비ASCII일 수 있어 헤더 안전을 위해
URL-encoding 합니다. cond가 없으면(파일 부재) 헤더를 생략하고 이미지만 serve 합니다
(cond는 best-effort, 이미지 존재가 우선). 캐시는 이미지와 cond를 함께 저장해
재요청 시 헤더를 캐시에서 채웁니다(홈: `<image>.cond` 사이드카, 사무실: MinIO object
metadata). 사무실 캐시가 MinIO 공유 저장이므로 **첫 사용자 이후 모든 사용자**가
cond 포함 응답을 MinIO에서 빠르게 받습니다.

### 6.3 `MeasHistRow.eqp_ip`

프런트가 이미지 요청에 `eqp_ip`를 실을 수 있도록 MSR 검색 row에 `eqp_ip`를
추가합니다. OpenSearch `meas_hist` doc은 이미 `eqp_ip` 필드를 가지므로 office
어댑터는 그대로 채우고, mock은 `sem_list`와 같은 방식의 합성 IP를 생성합니다.
이로써 `msr_image` office 어댑터는 IP 조회를 위해 OpenSearch에 의존하지 않고
**순수 FTP feature**로 남습니다.

## 7. 오류 계약 (mock fallback 금지)

source 실패를 mock 이미지로 위장하지 않습니다.

| 상황 | HTTP | 의미 |
| --- | --- | --- |
| `eqp_ip` 형식/서브넷 검증 실패 | 400 | `invalid_tool_ip`(값 은닉) |
| 필수 환경 변수 누락(FTP 자격 등) | 500 | `office_configuration_error` |
| tool FTP 연결 실패/timeout | 503 | `office_source_unavailable`(자격 미노출) |
| tool에 이미지 없음 | 404 | 실제 부재. 프런트는 실패 이미지 상태 표시 |
| 전체 다운로드 시작 | 202 | `{job_id}` 반환, 수집은 백그라운드 |
| 전체 다운로드 부분 실패 | 폴링 결과 | 성공분 캐시, 실패는 최종 `failures[]`로 보고 |
| 알 수 없는 job_id 폴링 | 404 | 만료·오타. 프런트는 재시도 안내 |

프런트엔드는 실패한 `<img>`를 조작된 SVG가 아니라 명시적 실패 상태로 렌더링합니다.

## 8. 프런트엔드

현행: `useMsrFileApi.ts`의 `msrImageUrl(name)` → `/api/msr-image?name=`가
`SiteEvidenceDrawer.vue`, `ImageViewer.vue`, `AlignImages.vue`, `Gallery.vue`에서
`<img :src>`로 직접 쓰입니다.

변경:

- 신규 `useMsrImageApi.ts` — `fetchImageList(eqp_ip, class_name, msr)`,
  `imageUrl(eqp_ip, class_name, msr, name)`(썸네일용 plain URL),
  `fetchImageWithCond(...)`(상세 뷰용 `fetch()` → blob URL + `X-Msr-Cond` 파싱),
  `startDownloadAll(...)` + `pollJob(job_id)`.
- 썸네일(`<img :src>`)은 URL만 필요하므로 헤더를 무시하고 그대로 씁니다. **조건을
  보여 주는 상세 뷰**(`ImageViewer`, `SiteEvidenceDrawer`)만 `fetch()`로 로드해
  cond 헤더를 읽어 표시합니다(`<img>` 태그는 헤더를 읽을 수 없기 때문).
- 갤러리는 `fetchImageList`로 이미지 집합을 얻어 렌더링합니다(기존의 pickle
  `mp_image_name` 열거 대신 tool dir 나열이 권위 출처).
- MSR 뷰에 "전체 다운로드" 버튼 + 진행률(폴링) UI 추가.

## 9. 설정 (환경 변수)

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `SKEWNONO_MSR_IMAGE_PROVIDER` | `mock` | provider 선택(전역 `SKEWNONO_DATA_PROVIDER` override) |
| `SKEWNONO_TOOL_FTP_USER` | `hitachi` | tool FTP 사용자(비기밀 사내 관례) |
| `SKEWNONO_TOOL_FTP_PASSWORD` | `hid` | tool FTP 암호(비기밀 사내 관례) |
| `SKEWNONO_TOOL_FTP_PORT` | `21` | tool FTP 포트 |
| `SKEWNONO_TOOL_FTP_CONCURRENCY` | `6` | 전체 다운로드 host당 동시 연결 수(유계) |
| `SKEWNONO_TOOL_SUBNETS` | — | 허용 tool 서브넷 CIDR 목록(미설정 시 형식 검증만) |
| `IMAGE_CACHE_DIR` | `<project>/var/image_cache` | 홈 디스크 캐시 루트(Git 제외) |
| `SKEWNONO_IMAGE_CACHE_BUCKET` | (기존 MinIO 버킷) | 사무실 MinIO 캐시 버킷 |
| `SKEWNONO_IMAGE_CACHE_PREFIX` | `image_cache/` | 사무실 MinIO 캐시 prefix(측정 데이터와 분리) |
| `IMAGE_CACHE_TTL_HOURS` | `72` | 정리 기준 나이(약 3일) |
| `IMAGE_CACHE_PURGE_HOUR` | `3` | 야간 정리 cron 시각 |
| `SKEWNONO_MSR_IMAGE_MAX_JOBS` | `2` | 동시 전체 다운로드 job 수 |
| `SKEWNONO_MSR_IMAGE_JOB_TTL` | `3600` | job 상태 보존(초). Redis 키 만료에도 사용 |
| `REDIS_*`(기존) | — | 사무실 다중 worker의 job 상태 저장 |

자격 증명은 비기밀이지만 기본값을 두되 환경 변수로 override 가능합니다. 서브넷·포트
등 사내 세부는 gitignored `providers/office.py`/`.env`에서 확정합니다.

## 10. 홈/사무실 동작

- **홈(Phase 1)**: `mock` provider + `DiskImageCache`. 합성 목록·SVG·합성 cond를
  로컬 디스크 캐시에 기록·serve 하므로 목록→갤러리→cond 표시→전체 다운로드→진행→
  야간 정리까지 **오프라인 전 흐름 검증** 가능합니다. tool·OpenSearch·MinIO 불필요.
- **사무실(Phase 2/3)**: `SKEWNONO_MSR_IMAGE_PROVIDER=office` + `MinioImageCache`.
  `providers/office.py`가 `ftp_handler`로 tool에서 fetch, MinIO 캐시 prefix에 저장.
  실제 서브넷·포트·버킷은 `.env`/office.py에서 확정.
- 다중 worker(`gunicorn -w N`) 주의: **MinIO 공유 캐시라 worker·호스트 경계와
  무관하게 캐시를 공유**합니다(로컬 디스크의 서버 로컬 한계 해소). job 상태는 Redis 키
  (우리 관리), 정리 cron 중복 sweep은 멱등이라 무해.

## 11. 테스트

| 층 | 방법 | 확인 |
| --- | --- | --- |
| mock 흐름 | 홈에서 목록/serve/miss/write/purge 단위 테스트 | 합성 목록·SVG 캐시·cond 헤더·만료 삭제 |
| 디스크 캐시 | `DiskImageCache` 단위 테스트 | 키 결정성·cond 사이드카·나이 정리 |
| MinIO 캐시 | `MinioImageCache` + fake MinioObject 주입 | put(metadata=cond)/get/exists·공유 hit·last_modified sweep |
| 경로 조립 | office 순수 헬퍼 단위 테스트 | image/cond 경로 결정성, `.{name}/cond.txt` |
| IP guard | 형식·서브넷 검증 테스트 | malformed→400, 서브넷 밖→400 |
| office fetch | fake FtpClient 주입 | tool 없이 목록·fetch·부분 실패 보고 |
| 유계 풀 | 다중 연결 콜백 동시 증가 | 원자적, 최종 done == total, 연결 수 상한 준수 |
| 전체 다운로드 job | submit→`202`, 폴링 전이, 최종 counts | 비동기 흐름 |
| 정리 | mtime 조작 후 purge | TTL 초과분만 삭제, 최신 보존 |
| 오류 계약 | 연결 실패 강제 | 503/500/404, mock 위장 없음 |
| 라우팅 | provider dispatch | env로만 전환(mock/office/override/invalid) |
| meas_hist | `eqp_ip` row 추가 | mock 합성 IP, 계약 형태 |
| frontend | Nuxt 수동 smoke | 갤러리 목록 렌더, cond 표시, 전체 다운로드 버튼 |
| 문서 | `npm run lint:md` | 변경 문서 오류 0 |

## 12. 인수 기준

- 홈에서 `GET /api/msr-images`가 합성 목록을, `GET /api/msr-image`가 SVG + cond
  헤더를 반환하고, 재요청은 디스크 캐시에서 relay 됩니다.
- 사무실에서 첫 요청이 tool→MinIO 캐시 prefix에 이미지(+cond metadata)를 적재하고,
  이후 **다른 worker·다른 사용자**의 요청이 MinIO에서 relay 되며, 약 3일 후 나이 기반
  sweep으로 삭제됩니다.
- 홈에서 "전체 다운로드"가 `202 {job_id}`를 즉시 반환하고, 폴링이 진행률과 최종
  `{ok, ng, failures}`를 보고하며, 완료 후 갤러리가 캐시에서 relay 됩니다.
- office 어댑터가 tool dir를 나열하고, 이미지 + `.{name}/cond.txt`를 fetch 하며,
  유계 병렬 풀로 host당 동시 연결 수 상한을 지킵니다.
- 프런트가 보낸 `eqp_ip`가 IPv4(+선택 서브넷) 검증을 통과해야만 연결됩니다.
- provider 전환이 **config-only**이며 코드 변경 없이 rollback 됩니다.
- source 실패가 mock 이미지로 위장되지 않고 §7 오류로 노출됩니다.
- `ftp_handler`는 수정되지 않습니다(vendored 규약 준수).
- `routes.py`/`contracts.py`는 phase를 모릅니다. 사무실 지식은 office.py에만 있습니다.
- `msr_image` office 어댑터는 OpenSearch에 의존하지 않습니다(순수 FTP feature).
