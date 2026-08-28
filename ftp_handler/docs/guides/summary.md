# ftp_handler — 목적 요약

장비 FTP 수집 기능을 목적별 네 개의 서브패키지로 구성했다. 각 서브패키지는
re-export 허브라서 호출부는 리프 이름만 import 한다. direct 다운로더와 proxy
다운로더는 하나의 공개 인터페이스(`FleetTransport` 심)를 공유하므로 전송 방식
교체는 import 한 줄만 바꾸면 된다. 케이스별 레시피는 `usage.md`를, 실행
가능한 코드는 각 폴더의 `examples.py`를 참고하라.

## 구조

```
ftp_handler/
  core/                 공유 기본 요소 (stdlib만 사용; 다른 것에 의존하지 않음)
    client.py           FtpClient — 단일 서버, 즉석 list/download/upload/remove
    listing.py          _normalize_listing — 두 규모 모두에서 쓰는 NLST 정규화기
  direct_downloader/    FTP 서버와 직접 통신
    fleet_downloader.py FtpFleetDownloader — 동시 팬아웃 + list_dirs 탐색 + size_dirs 크기측정
    collect.py          collect_fleet — archive → parse → index 글루 (minio/opensearch import 없음)
  proxy/                방화벽 안 클라이언트용 HTTP 전송
    flask_proxy.py      서버 절반 (flask 필요) — 실제 FTP를 수행, base64 바이트 반환
    proxy_downloader.py 클라이언트 절반 (requests 필요) — direct와 같은 인터페이스를 HTTP로
  web_app/
    jobs.py             BackgroundJobs — 웹 요청 스레드 밖에서 플릿 다운로드 실행
  docs/  + 각 폴더의 examples.py
```

## 서브패키지

### `core` — 공유 기본 요소
- **`FtpClient`** (`client.py`): 컨텍스트 매니저로 연결 하나를 재사용한다. 즉석 연산
  네 가지(`download`/`upload`/`remove`)와 세 가지 목록 방식 — `list_dir`(NLST),
  `list_entries`(MLSD, 디렉터리/파일 구분), `list_details`(LIST → 크기 + KST 기준
  mtime를 담은 타입드 `FileInfo`). 서버 오류는 그대로 전파된다.
- **`_normalize_listing`** (`listing.py`): NLST 경로 정규화기. 단일 서버 다운로더와
  플릿 다운로더가 동일하게 동작하도록 공유한다. stdlib만 쓰므로 copy-out proxy
  번들에 bare 이름으로 함께 따라간다.

### `direct_downloader` — 동시 플릿, 직접 FTP
- **`FtpFleetDownloader`** (`fleet_downloader.py`): 동기식, **이벤트 루프 없음**
  (순수 `ThreadPoolExecutor`)이라 async 웹 워커를 포함한 어떤 컨텍스트에서도
  안전하다. `download`(수집 또는 `on_file`로 스트리밍), `list_dirs`(탐색 패스 →
  `to_specs()` → `download`), `size_dirs`(RAM 예산 패스; `SIZE`만, 가져오지 않음 →
  `SizingReport.total_bytes`/`by_host()`/`to_specs()`), `upload`(쓰기 방향;
  `UploadSpec`/`UploadFile`이 메모리상 `bytes`를 `BytesIO`로 곧장 STOR — 디스크 파일
  불필요, 파일 단위 실패 격리)가 하나의 엔진을 공유하며 `max_concurrency` 상한,
  호스트별 타임아웃, 호스트별 실패 격리를 갖는다. 헬퍼: `specs_from_hosts`,
  `download_fleet`, `list_fleet`, `size_fleet`, `save_to_dir`,
  `upload_specs_from_hosts`, `upload_fleet`.
- **`collect_fleet` / `build_host_specs`** (`collect.py`): 파일마다 archive → parse
  → index. 각 단계를 콜러블로 주입받으므로 minio/opensearch를 import 하지 않는다 —
  DAG은 얇게 유지되고 이 계층은 단위 테스트가 가능하다.

### `proxy` — 방화벽 안 클라이언트용 HTTP 전송
- **`flask_proxy.py`** (서버): FTP egress가 허용된 곳에서 실행된다. Flask
  블루프린트(`/download_sknn_v3`, `/list_dirs_sknn_v3`, `/size_dirs_sknn_v3`,
  `/upload_sknn_v3`, `/healthz_sknn_v3`),
  선택적 `FTP_PROXY_TOKEN`. 실제 FTP 는 `FtpFleetDownloader`를 재사용한다.
  로그인 계정은 spec 이 실어 보낸 `user`/`password`를 쓰고(클라이언트 생성자
  계정이 기본, 호스트별 override 가 우선), 둘 다 없을 때만 서버 환경 변수
  `FTP_PROXY_FTP_USER` / `FTP_PROXY_FTP_PASSWORD`로 되돌아간다.
- **`proxy_downloader.py`** (클라이언트): 패키지가 이 모듈의 `FtpFleetDownloader`를
  re-export 한다 — `direct_downloader`와 같은 이름·같은 데이터클래스를 HTTP로
  제공한다. 스펙을 배치로 묶어 동시에 POST 하며, `on_file`은 로컬에서 실행된다.
  `__init__`은 `flask_proxy`를 import 하지 않으므로 클라이언트를 import 해도 `flask`가
  필요 없다.

### `web_app` — 서버 안에서의 논블로킹 실행
- **`BackgroundJobs`** (`jobs.py`): 블로킹 `download()`를 백그라운드 스레드에서
  실행한다. `submit()`은 즉시 job id를 반환하고, `get()`은 폴링용 스냅샷을 반환한다.
  `create_jobs_blueprint`가 submit/status 라우트를 노출한다. 인프로세스
  레지스트리(단일 프로세스 범위)이며, 상태 직렬화는 카운트만 담고 파일 바이트는
  절대 담지 않는다.

## 조각들이 맞물리는 방식

```
core.FtpClient ──────────── 단일 서버
core.listing ───── 공유 NLST 정규화기 ──────────────────────────────┐
                                                                    │
direct_downloader.FtpFleetDownloader ── FleetTransport 심 ── proxy.FtpFleetDownloader (HTTP)
        │  (list_dirs → to_specs → download)                        proxy.flask_proxy (실제 FTP)
direct_downloader.collect_fleet (on_file로 archive→parse→index)
web_app.BackgroundJobs ── 요청 스레드 밖에서 download() 실행
```

테스트는 `ftp_handler.core.client.FTP`와
`ftp_handler.direct_downloader.fleet_downloader.FTP`를 패치한다 — 실제 서버는 결코
쓰지 않는다. 레시피는 `usage.md`, 결정 사항은 `../adr/`를 참고하라.
