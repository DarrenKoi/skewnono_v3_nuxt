# ftp_handler 재구조화 · 비동기 제거 · 웹 백그라운드 러너

- 날짜: 2026-05-27 08:33
- 범위: `ftp_handler/` 전반, `airflow_mgmt/dags/eqp_ftp/eqp_ftp_collector_dag.py`, `tests/`, `CLAUDE.md`

## 1. 진행 사항

1. **코드 리뷰 (Airflow 실행 관점)** — `/code-review` 로 "Airflow 샌드박스 / 멀티스레드 디스크 I/O" 관점에서 3개 finder 앵글로 검토. 핵심 발견:
   - `host_timeout` 초과 시 스레드가 취소되지 않고 계속 RETR + `on_file`(MinIO/OpenSearch 쓰기)을 수행 → 요약 리포트 산출 이후에도 미집계 파일이 기록됨.
   - `pool.shutdown(wait=False)` 로 타임아웃 호스트 스레드 누수.
   - 워커에 `opensearch-py` 미설치 → 런타임에 `OSDoc()` 에서 `ModuleNotFoundError` (DAG 파싱은 통과, 태스크 실행 시 매번 실패). 삭제된 DAG NOTE가 이 블로커를 가렸음.
   - 8GiB 워커에서 `max_concurrency=48 × 파일크기` 메모리 / urllib3 풀 한계.
2. **asyncio → ThreadPoolExecutor 전환** — 사용자가 "Flask 서버에서 직접 다운로드 태스크로 실행" 의도를 밝힘. `asyncio.run()` 이 이미 실행 중인 이벤트 루프(async 워커/gevent/eventlet)에서 `RuntimeError` 를 던지는 위험을 제거하기 위해 `_run_fleet` 의 오케스트레이션을 순수 스레드풀로 교체. 동작 보존, 이벤트 루프 안에서도 안전하게 호출됨을 검증.
3. **웹 비차단 러너 신규 작성** — 요청 스레드를 막지 않고 백그라운드에서 fleet 다운로드를 돌리는 `BackgroundJobs` 작성.
4. **목적 기반 서브패키지 재구조화** — 사용자 결정(`AskUserQuestion`): `core/` 공용 프리미티브 분리 + 각 서브패키지 `__init__.py` 재노출 허브. `direct_downloader` ↔ `proxy` 가 동일 이름을 노출해 import 한 줄로 전환 가능(`FleetTransport` seam).
5. **테스트·예제·문서 정비** — 신규 jobs 테스트, 폴더별 `examples.py`, 케이스별 사용 가이드(`docs/usage.md`), `docs/summary.md` 재작성, `CLAUDE.md` 갱신.

## 2. 수정 내용

### 동작 변경 (asyncio 제거)
- `ftp_handler/direct_downloader/fleet_downloader.py`
  - `import asyncio` 제거, `from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError` 추가.
  - `download` / `list_dirs` 가 `asyncio.run` 대신 `_run_fleet` 직접 호출. `_download_all`/`_list_all`/`run_host`(async) 제거.
  - `_run_fleet` 를 동기 스레드풀로 재작성: `pool.submit` → `future.result(timeout=host_timeout)`, 호스트별 실패 격리 유지, `shutdown(wait=False)` 유지.
  - 모듈 docstring "Why threads, not aioftp" 및 `download`/`list_dirs` docstring을 "이벤트 루프 없음, 어디서든 안전" 으로 갱신.

### 신규 파일
- `ftp_handler/web_app/jobs.py` — `BackgroundJobs`(ThreadPoolExecutor + 락 보호 레지스트리, `submit`/`get`/`shutdown`, `keep_last` 제거 정책), `Job` 데이터클래스, `summarize`(리포트 → 카운트, 바이트 비노출), `job_to_dict`, `create_jobs_blueprint`(flask 지연 import).
- `tests/test_ftp_fleet_jobs.py` — 9개 테스트(즉시 반환/백그라운드 완료/예외→error job/스냅샷 격리/직렬화 바이트 비노출/eviction).
- 폴더별 예제: `core/examples.py`, `direct_downloader/examples.py`, `proxy/examples.py`, `web_app/examples.py`.
- 문서: `ftp_handler/docs/usage.md`(케이스별 레시피 + 표), `ftp_handler/docs/summary.md`(재작성).
- 각 서브패키지 `__init__.py`(재노출 허브): `core/`, `direct_downloader/`, `proxy/`, `web_app/`.
- `core/listing.py` — `_normalize_listing` 를 여기로 이동(공용 프리미티브).

### 파일 이동 (git rename, 히스토리 보존)
- `ftp_client.py` → `core/client.py` (import: `ftp_handler.core.listing` 에서 `_normalize_listing`)
- `ftp_fleet_downloader.py` → `direct_downloader/fleet_downloader.py` (`_normalize_listing` 정의 제거 → `..core.listing` 에서 import, copy-out 대비 bare fallback)
- `eqp_ftp_collect.py` → `direct_downloader/collect.py` (`from .fleet_downloader import ...`)
- `ftp_flask_proxy.py` → `proxy/flask_proxy.py` (`..direct_downloader.fleet_downloader` / bare `fleet_downloader` fallback)
- `ftp_flask_downloader.py` → `proxy/proxy_downloader.py` (동일 패턴)
- `ftp_fleet_jobs.py` → `web_app/jobs.py`
- `ftp_handler/examples.py` 삭제(내용을 폴더별로 분산)

### 기타 수정
- `airflow_mgmt/dags/eqp_ftp/eqp_ftp_collector_dag.py` — import 경로를 `from ftp_handler.direct_downloader import build_host_specs, collect_fleet` 로 변경, docstring 모듈 경로 갱신.
- `tests/test_ftp_client.py` — import + 패치 타겟 `ftp_handler.core.client.FTP`.
- `tests/test_ftp_fleet_downloader.py` — import + 패치 타겟 `ftp_handler.direct_downloader.fleet_downloader.FTP`.
- `tests/test_ftp_flask_proxy.py` — bare copy-out 경로를 위해 `core/`,`direct_downloader/`,`proxy/` 를 sys.path에 추가, bare import(`fleet_downloader`/`proxy_downloader`/`flask_proxy`), 패키지 경로 테스트 모듈명 갱신.
- `ftp_handler/__init__.py`, `CLAUDE.md` — 새 4-서브패키지 레이아웃 반영.

### 검증
- ftp 4개 스위트 77 테스트 통과, `compileall` 통과, DAG import 경로 확인, 이벤트 루프 내부에서 `download()` 정상 동작 확인.
- 참고: 저장소 전체에서 `test_api_*` 3건 에러는 기존 환경 문제(`flask_apscheduler` 미설치)로 본 작업과 무관.

## 3. 다음 단계

미해결로 남은 항목(사용자 확인 필요):

1. **(미결) 고아 스레드 협력적 취소** — `host_timeout` 초과 후에도 스레드가 `on_file` 쓰기를 계속하는 문제. 호스트별 "stop" 플래그를 두어 RETR/`on_file` 전에 확인하는 방식 제안. → 적용할지?
2. **(배포/환경) `opensearch-py` 워커 설치** — Airflow 태스크가 매 실행 `OSDoc()` 에서 실패. ops 설치 / `@task.virtualenv` / 벤더링 중 택1. → 코드 변경이 아니므로 어떻게 처리할지 확인 필요.
3. **DAG 재배포** — import 경로가 `ftp_handler.direct_downloader` 로 바뀌었으므로 git-register 배포를 동기화해야 함.
4. **copy-out 번들 문서화** — 프록시 단독 실행 시 이제 4개 파일(`flask_proxy.py`/`proxy_downloader.py` + `fleet_downloader.py` + `listing.py`)을 평면 복사해야 함. usage.md에 명시했으나 실제 운영 절차 점검 필요.

## 4. 메모리 업데이트

MEMORY.md 에 신규 항목 추가(아키텍처 변경):
- ftp_handler 4-서브패키지 레이아웃(core/direct_downloader/proxy/web_app) + 재노출 허브 컨벤션 + 패치 타겟 변경.
- fleet 다운로더가 asyncio가 아닌 ThreadPoolExecutor 기반(이벤트 루프 없음)이라는 점.

(주의: 기존 메모리 `project_api_tasks_layout` 의 "빈 __init__ / 풀 경로 import" 컨벤션과 달리, ftp_handler는 사용자 명시 요청으로 재노출 허브를 채택 — 두 패키지의 컨벤션이 다름.)
