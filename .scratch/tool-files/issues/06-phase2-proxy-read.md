# 06: Phase 2 proxy 읽기 지원

**What to build:** 개발자가 office Windows PC(Phase 2)에서도 클라우드와 똑같이 탐색기로 목록을 보고 파일을 받을 수 있게 합니다. Windows PC는 장비 FTP에 직접 접속할 수 없으므로 기존 FTP proxy를 거칩니다. proxy에는 읽기 라우트만 추가하고, proxy를 쓰는 기존 서비스의 동작은 바꾸지 않습니다.

**Blocked by:** 01 (ftp_handler core 읽기 확장), 02 (관리자 전용 파일 탐색기)

**Status:** ready-for-agent

- [ ] 수정은 `flask_modules`에 먼저 하고 push한 뒤, vendored copy에 복사합니다
- [ ] proxy 서버에 `list_details`와 `fetch` 라우트를 추가합니다(`_sknn_v3` 접미사). 요청마다 새 FTP 연결을 엽니다. envelope는 기존 credentials wire를 재사용하고, deadline은 남은 초로 보냅니다
- [ ] `list_details`에 `remote_dir=null`을 보내면 PWD와 그 목록을 돌려줍니다. entries에는 `modified`(ISO 또는 null)와 `is_link`를 담습니다
- [ ] `fetch`는 원본 바이트를 `octet-stream`으로 보냅니다. proxy는 FTP에서 받는 동안, 클라이언트는 chunk 단위로 받는 동안 같은 상한을 적용합니다
- [ ] 오류는 `{code, error}`로 보내고 클라이언트가 예외로 복원합니다(스펙의 대응표). 원격 401·404·5xx와 JSON이 아닌 응답은 `ProxyError`로 처리합니다
- [ ] `proxy.FtpClient`의 읽기 메서드(`home`, `list_details`, `download`)는 direct와 시그니처가 같아야 하고, 이를 테스트로 검증합니다. `put`과 `remove`는 `WriteNotSupported`를 냅니다. import할 때 Flask를 불러오지 않습니다. `PROXY_URL`, `PROXY_TOKEN`과 Bearer 동작은 기존 것을 재사용합니다
- [ ] proxy transport는 쓰기를 지원하지 않는다고 선언합니다. 08이 정의하는 `transport_supports_write` 규칙에서 거짓이 되게 합니다. 08이 아직 머지되지 않았다면 이 선언만 해 둡니다
- [ ] tool_files는 Windows에서 proxy transport를 고르고, proxy용 deadline env(기본 45 s)를 씁니다
- [ ] 기존 5개 proxy 라우트와 `FtpFleetDownloader`의 양쪽 동작은 바꾸지 않습니다. 기존 테스트 파일은 수정하지 않습니다. flask_modules ftp 테스트 5개와 SKEWNONO 전체 suite가 통과해야 하고, 사본 diff는 비어 있어야 합니다
- [ ] Flask test client로 proxy 서버를 띄우고, `proxy.FtpClient`가 direct와 같은 결과와 같은 예외를 내는지 확인합니다
- [ ] office 반영 순서(flask_modules push → scheduler1 webapp pull·재시작 → SKEWNONO pull)를 tool_files MIGRATION.md에 적습니다
