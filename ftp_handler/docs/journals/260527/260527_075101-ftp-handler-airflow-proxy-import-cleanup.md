# FTP handler Airflow/proxy import cleanup

## 1. 진행 사항

- `ftp_handler` 문서 구조를 정리했다. 기존 `ftp_handler/CONTEXT.md`, `ftp_handler/ftp_fleet_downloader.md`, `ftp_handler/handoff_ftp_fleet_downloader.md`를 먼저 `ftp_handler/adr/`로 옮겼고, 이후 요청에 맞춰 전체 ADR 폴더를 `ftp_handler/docs/adr/` 아래로 이동했다.
- direct FTP downloader와 Flask proxy downloader가 같은 public name으로 교체 가능해야 한다는 요구를 기준으로 import 경로를 점검했다.
- `ftp_handler.ftp_flask_downloader`와 `ftp_handler.ftp_flask_proxy`가 package import 모드(`ftp_handler.*`)에서는 `ftp_handler.ftp_fleet_downloader`의 dataclass를 그대로 공유하고, copy-out/bare import 모드에서는 기존처럼 같은 폴더의 `ftp_fleet_downloader.py`를 import하도록 수정했다.
- Airflow DAG가 `airflow_mgmt` 밖의 top-level package인 `ftp_handler`, `ops_store` 등을 import할 수 있도록 `airflow_mgmt/dags/eqp_ftp/eqp_ftp_collector_dag.py`의 bootstrap을 diagnostics DAG와 같은 `_find_root()` 패턴으로 정리했다.
- `tests/test_ftp_flask_proxy.py`에 package import 모드에서도 `DownloadReport`, `HostSpec`, `ListDir`, `ListingReport` 등이 direct/proxy 사이에서 같은 class object인지 확인하는 회귀 테스트를 추가했다.
- `python3 -m unittest tests.test_ftp_flask_proxy tests.test_ftp_fleet_downloader tests.test_ftp_client -v`를 실행했고 68개 테스트가 통과했다.
- `python3 -m compileall airflow_mgmt/dags/eqp_ftp ftp_handler tests`와 `git diff --check`를 실행해 문법 및 whitespace 검사를 통과했다.

## 2. 수정 내용

- `ftp_handler/docs/adr/CONTEXT.md`: FTP fleet, direct/proxy path, `FleetTransport`, listing pass 등 용어 문서를 package-local docs 아래로 이동했다.
- `ftp_handler/docs/adr/ftp_fleet_downloader.md`: async/thread 기반 FTP fleet downloader 설계 문서를 package-local docs 아래로 이동했고, 내부 ADR 링크를 새 위치에 맞게 조정했다.
- `ftp_handler/docs/adr/handoff_ftp_fleet_downloader.md`: handoff 문서를 package-local docs 아래로 이동했고, 현재 파일 위치에 맞춰 표현을 정리했다.
- `ftp_handler/docs/adr/0001-proxy-batch-sizing.md`: 기존 ADR 폴더 전체 이동에 따라 `ftp_handler/docs/adr/` 아래로 옮겨졌다.
- `ftp_handler/ftp_flask_downloader.py`: package-relative import를 우선 사용하고, copied-out bare import 환경에서는 fallback 하도록 변경했다.
- `ftp_handler/ftp_flask_proxy.py`: Flask proxy도 direct downloader를 package-relative import로 우선 가져오고, standalone/copy-out 실행에서는 bare import fallback을 사용하도록 변경했다.
- `airflow_mgmt/dags/eqp_ftp/eqp_ftp_collector_dag.py`: `ROOT_DIR` 탐색을 diagnostics DAG 스타일의 `_find_root()` 함수로 맞추고, `ftp_handler`가 `airflow_mgmt` 밖에 있을 때 `REPO_ROOT`도 `sys.path`에 추가하도록 정리했다.
- `tests/test_ftp_flask_proxy.py`: copy-out/bare import 테스트 설명을 현재 구조에 맞게 바꾸고, package import identity 테스트를 추가했다.
- `CLAUDE.md`: `ftp_handler` 참고 문서 위치를 `ftp_handler/docs/adr/`로 갱신했다.
- `ftp_handler/docs/journals/260527/260527_075101-ftp-handler-airflow-proxy-import-cleanup.md`: 이번 작업 내역을 기록하는 journal 파일을 생성했다.

## 3. 다음 단계

- Airflow가 설치된 환경에서 `python3 -m pytest airflow_mgmt/tests -v`를 다시 실행해 DAG parse/import integrity를 확인한다.
- 실제 Airflow worker 또는 회사 배포 환경에서 `eqp_ftp_collector` DAG가 `ftp_handler`, `ops_store`, `minio_handler`를 모두 import할 수 있는지 확인한다.
- 실제 FTP 접근 가능 환경에서 direct download와 Flask proxy download를 각각 한 번씩 실행해 network/passive mode, timeout, batch size 설정을 검증한다.
- `parse_records()` 구현이 정해지면 샘플 FTP 파일 기준으로 parser와 deterministic `_id` 생성 테스트를 추가한다.

## 4. 메모리 업데이트

변경 없음. 실제 메모리 파일 업데이트는 요청되지 않아 수행하지 않았다.
