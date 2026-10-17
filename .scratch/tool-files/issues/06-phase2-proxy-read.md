# 06: Phase 2 proxy 읽기 지원

**What to build:** 개발자가 office Windows PC(Phase 2)에서도 클라우드와 똑같이 탐색기로 목록을 보고 파일을 받을 수 있게 합니다. Windows PC는 장비 FTP에 직접 접속할 수 없으므로 기존 FTP proxy를 거칩니다. proxy에는 읽기 라우트만 추가하고, proxy를 쓰는 기존 서비스의 동작은 바꾸지 않습니다.

**Blocked by:** 01 (ftp_handler core 읽기 확장), 02 (관리자 전용 파일 탐색기)

**Status:** done (2026-10-17)

- [x] 수정은 `flask_modules`에 먼저 하고 push한 뒤, vendored copy에 복사합니다
- [x] proxy 서버에 `list_details`와 `fetch` 라우트를 추가합니다(`_sknn_v3` 접미사). 요청마다 새 FTP 연결을 엽니다. envelope는 기존 credentials wire를 재사용하고, deadline은 남은 초로 보냅니다
- [x] `list_details`에 `remote_dir=null`을 보내면 PWD와 그 목록을 돌려줍니다. entries에는 `modified`(ISO 또는 null)와 `is_link`를 담습니다
- [x] `fetch`는 원본 바이트를 `octet-stream`으로 보냅니다. proxy는 FTP에서 받는 동안, 클라이언트는 chunk 단위로 받는 동안 같은 상한을 적용합니다
- [x] 오류는 `{code, error}`로 보내고 클라이언트가 예외로 복원합니다(스펙의 대응표). 원격 401·404·5xx와 JSON이 아닌 응답은 `ProxyError`로 처리합니다
- [x] `proxy.FtpClient`의 읽기 메서드(`home`, `list_details`, `download`)는 direct와 시그니처가 같아야 하고, 이를 테스트로 검증합니다. `put`과 `remove`는 `WriteNotSupported`를 냅니다. import할 때 Flask를 불러오지 않습니다. `PROXY_URL`, `PROXY_TOKEN`과 Bearer 동작은 기존 것을 재사용합니다
- [x] proxy transport는 쓰기를 지원하지 않는다고 선언합니다. 08이 정의하는 `transport_supports_write` 규칙에서 거짓이 되게 합니다. 08이 아직 머지되지 않았다면 이 선언만 해 둡니다
- [x] tool_files는 Windows에서 proxy transport를 고르고, proxy용 deadline env(기본 45 s)를 씁니다
- [x] 기존 5개 proxy 라우트와 `FtpFleetDownloader`의 양쪽 동작은 바꾸지 않습니다. 기존 테스트 파일은 수정하지 않습니다. flask_modules ftp 테스트 5개와 SKEWNONO 전체 suite가 통과해야 하고, 사본 diff는 비어 있어야 합니다
- [x] Flask test client로 proxy 서버를 띄우고, `proxy.FtpClient`가 direct와 같은 결과와 같은 예외를 내는지 확인합니다
- [x] office 반영 순서(flask_modules push → scheduler1 webapp pull·재시작 → SKEWNONO pull)를 tool_files MIGRATION.md에 적습니다

## Comments

- flask_modules `cbe39e2`에 `ftp_handler/proxy/proxy_client.py`(새 `FtpClient`)와 `flask_proxy.py`의 두 라우트(`list_details_sknn_v3`, `fetch_sknn_v3`)를 추가했습니다. 테스트는 새 파일 `tests/test_ftp_proxy_client.py`(19개)이며, 기존 ftp 테스트 7개 모듈은 수정 없이 통과합니다. 사본은 SKEWNONO `chore(ftp_handler): resync with flask_modules (proxy reads)`로 복사했고 `diff -rq` 결과는 비어 있습니다.
- 오류 응답은 HTTP 422 + `{code, error}` 하나로 정했습니다. 그 밖의 상태(401, 404, 5xx)와 예상하지 않은 body는 `code`가 있어도 모두 `ProxyError`입니다. 그래서 라우트가 아직 배포되지 않은 proxy의 404가 "파일 없음"으로 읽히지 않습니다.
- 예외는 기존 `_session` 매핑을 그대로 타도록 상속을 골랐습니다. `FileUnavailable`은 `error_perm`(404 `file_unavailable`)이고, `ToolUnreachable`과 `ProxyError`는 `ConnectionError`(503 `tool_unreachable`)입니다. routes.py는 바꾸지 않았습니다.
- 로그인 실패 시점이 다릅니다. direct는 `__enter__`에서 `error_perm 530`을 내고, proxy는 첫 요청에서 `ToolUnreachable`을 냅니다. 둘 다 `ftplib.all_errors`이므로 화면 응답은 같은 503입니다. proxy 쪽은 530을 `unavailable`로 오인하지 않도록 연결·로그인 단계의 모든 실패를 `unreachable`로 보냅니다.
- `list_details`의 `pattern`과 `tz`도 wire로 보냅니다(`pattern`, `tz_offset_s`). 그래야 시그니처만이 아니라 결과도 direct와 같습니다.
- `fetch`는 proxy가 core `download`로 상한·deadline을 검사하며 다 받은 뒤 원본 바이트를 보냅니다. 실패를 JSON으로 돌려주려면 응답을 시작하기 전에 결과를 알아야 하기 때문입니다. 클라이언트는 chunk마다 같은 상한을 다시 검사합니다.
- `home()`은 `remote_dir=null`로 요청하므로 proxy가 home 목록도 함께 읽습니다(세 번째 라우트 없음). 그래서 화면 한 번에 HTTP 두 번이 듭니다.
- 라우트는 direct deadline(120 s)을 넘기므로, office template의 `_ProxyClient`가 `list_details`/`download`의 deadline을 `SKEWNONO_TOOL_FILES_PROXY_DEADLINE`(45 s) 이하로 줄입니다. transport는 msr_image와 달리 import 시점이 아니라 호출 시점에 `platform.system()`으로 판정합니다.
- `transport_supports_write()`는 office template(Windows면 거짓)과 mock(참)에 선언만 했습니다. data.py·routes.py 연결은 08이 합니다.
- 집에서 확인하지 못한 것: 실제 scheduler1 webapp의 harakiri 값과 blueprint 등록, 실제 장비를 상대로 한 proxy 목록·다운로드(09에서 확인).
