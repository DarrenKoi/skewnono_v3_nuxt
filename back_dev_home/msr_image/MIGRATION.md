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
- `ftp_handler`(vendored)는 절대 수정하지 않고 `FtpClient`를 인스턴스화만
  합니다. 코드 안에서 모듈 수준 이름 `FtpClient`로 참조해야 테스트가
  monkeypatch로 대체할 수 있습니다.
- 완료 기준: 아래 확인 명령이 모두 초록색으로 통과하는 것입니다.

## 엔드포인트별 동작

| 함수 | 시그니처 | 동작 |
| --- | --- | --- |
| `list_images` | `(eqp_ip, class_name, msr, _config=None) -> list[str]` | FTP로 디렉터리를 리스팅하고 `.jpeg`/`.jpg`만 필터링합니다 |
| `fetch_image` | `(locator, _config=None) -> FetchedImage` | 이미지 바이트를 내려받아 `image/jpeg`로 반환하고, cond 사이드카는 best-effort로 붙입니다 |
| `download_all` | `(eqp_ip, class_name, msr, names, on_file, concurrency=6, _config=None)` | `FtpClient` 연결의 bounded ThreadPool로 파일별 진행 상황을 `on_file` 콜백에 보고합니다 |

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

## MinIO 캐시 prefix 주의사항

- `SKEWNONO_IMAGE_CACHE_BUCKET`/`SKEWNONO_IMAGE_CACHE_PREFIX`는 측정 데이터가
  저장되는 버킷·prefix(`minio_handler/minio_config.py`가 가리키는 것)와
  **반드시 분리**해야 합니다. 캐시는 TTL 경과 시 통째로 삭제(`purge`)되므로,
  측정 원본 데이터와 같은 prefix를 공유하면 원본이 함께 지워질 수 있습니다.
- `minio_cache.py`의 `MinioImageCache`는 클라이언트를 `use_prefix(None)`로
  passthrough 상태로 두고 `_key()`만을 유일한 prefix 소스로 사용합니다.
  office MinIO가 사용자 네임스페이스 prefix를 요구한다면(예:
  `user/2067928/...`), 클라이언트 쪽 기본 prefix에 기대지 말고
  `SKEWNONO_IMAGE_CACHE_PREFIX`에 **전체 prefix**를 넣어야 합니다. 예:

  ```text
  SKEWNONO_IMAGE_CACHE_PREFIX=user/2067928/image_cache/
  ```

  클라이언트에 별도 default prefix까지 설정하면 `_resolve_key()`가 prefix를
  두 번 붙이게 되어 `put`/`get`/`exists`/`stat` 모두 어긋나고, `purge`가
  넘겨받는 오브젝트 이름도 이미 이중 prefix가 붙은 상태라 `delete_many`가
  재차 잘못 resolve해 아무것도 지우지 못하는(에러 없이 조용히 실패하는)
  상황이 생깁니다. `msr_file` MIGRATION.md에 기록된 동일 함정을 참고하십시오.

## 후속 과제 1: Redis 기반 JobRegistry (multi-worker)

- `jobs.py`의 `MemoryJobRegistry`는 프로세스 메모리에 job 상태를 보관합니다.
  home(단일 프로세스)에서는 문제가 없지만, office가 `gunicorn -w N`으로
  여러 워커 프로세스를 띄우면 `download_all` job을 생성한 워커와 상태를
  폴링하는 워커가 다를 수 있어 상태가 유실됩니다.
- office 전용 후속 작업으로 `JobRegistry` Protocol을 구현하는
  Redis 기반 레지스트리(`RedisJobRegistry` 등)를 추가해야 합니다. 키는
  `job_id`로 네임스페이스하고, `job_ttl`(`SKEWNONO_MSR_IMAGE_JOB_TTL`)을
  Redis TTL로도 걸어 두어 오래된 job 상태가 무한히 쌓이지 않도록 합니다.
- 이 작업은 **office 전용**입니다. mock/home은 단일 프로세스이므로
  `MemoryJobRegistry`를 그대로 유지합니다.

## 후속 과제 2 (선택): 태그 기반 native lifecycle

- 현재 `purge()`는 애플리케이션 레벨에서 `last_modified`를 스캔해 TTL이
  지난 오브젝트를 `delete_many`로 지우는 방식입니다(스케줄러가 주기 호출).
- MinIO/S3의 native lifecycle 규칙(태그 기반 만료)으로 대체하면 스캔 없이
  버킷이 스스로 정리되지만, 이는 **선택 사항**이며 아래 두 가지가 모두
  필요합니다.
  - office 버킷에 `s3:PutBucketLifecycle` 권한이 있어야 합니다.
  - `minio_handler`에 lifecycle 규칙 설정 API를 추가해야 하며, `minio_handler`는
    vendored 코드이므로 이 저장소와 `flask_modules`의 두 사본을 모두
    수정해야 합니다(`CLAUDE.md`의 vendored 규칙 참고).
- 우선순위는 낮습니다. 애플리케이션 레벨 purge가 정상 동작하는 한 필수는
  아닙니다.

## 확인

```bash
SKEWNONO_MSR_IMAGE_PROVIDER=office .venv/bin/pytest back_dev_home/msr_image/tests/test_office_template.py
SKEWNONO_MSR_IMAGE_PROVIDER=office .venv/bin/python -c "from back_dev_home.msr_image import data; print(data.list_images('<tool-ip>', '<class>', '<msr>'))"
```

두 명령 모두 저장소 루트에서 실행해야 합니다. 첫 번째는 템플릿 로직(경로
조립 + FTP 클라이언트 사용법)이 fake `FtpClient`로 검증되는지 확인하는
회귀 테스트이고, 두 번째는 `office.py`를 실제로 만든 뒤 실 장비 IP로 붙여
보는 스모크 테스트입니다.
