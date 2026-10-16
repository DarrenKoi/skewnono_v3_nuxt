# 01: ftp_handler core 읽기 확장

**What to build:** `core.FtpClient`가 장비 파일 탐색에 필요한 읽기 기능을 갖추게 합니다. 로그인 홈 조회, 수신 도중 상한과 deadline을 거는 다운로드, 원문 상한과 deadline이 있는 상세 목록, 링크 표시가 그것입니다. 기존 `ftp_handler` 소비자(msr_image, recipe_search, scripts, Airflow DAG, scheduler webapp proxy)의 동작은 하나도 바뀌지 않아야 합니다. 화면이 없는 준비(prefactor) 티켓입니다. 스펙은 `.scratch/tool-files/spec.md`의 "ftp_handler 수정"을 따릅니다.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 수정은 `flask_modules`에 먼저 하고 push한 뒤, 그 결과를 SKEWNONO의 vendored copy로 복사합니다
- [ ] `home()`은 호출할 때 PWD를 조회합니다. `__enter__`에는 PWD 호출을 넣지 않습니다
- [ ] `download(remote_path, *, max_bytes=None, deadline=None)`는 수신 callback 안에서 바이트 수와 경과 시간을 검사합니다. 넘으면 즉시 중단하고 부분 버퍼와 연결을 폐기한 뒤 `TransferTooLarge` 또는 `TransferTimeout`을 냅니다. 기본값으로 호출하면 지금과 똑같이 동작합니다
- [ ] `list_details(..., max_entries=None, max_raw_bytes=None, deadline=None)`는 수신 중에 원문 줄 수(파싱에 실패한 줄 포함), 원문 바이트, 경과 시간을 검사합니다
- [ ] `FileInfo` 맨 끝에 `is_link: bool = False`를 추가하고, 값은 `raw`의 첫 글자로 판별합니다. `_parse_list_line()`의 4-tuple 반환은 바꾸지 않습니다
- [ ] fake FTP 서버 테스트로 다음을 확인합니다: 로그인 홈이 `/`가 아닌 경우, latin-1 원시 바이트 왕복, Unix·DOS·미지원 형식의 LIST 줄, 링크, 상한과 정확히 같은 크기와 1바이트 초과, LIST에 표시된 크기보다 실제로 큰 파일, 조금씩 계속 들어오는 전송, 파싱되지 않는 줄만 대량으로 오는 경우, 중간 단절과 로그인 실패 시 자원 정리
- [ ] 기존 테스트 파일은 수정하지 않습니다. flask_modules의 ftp 테스트 5개(`test_ftp_client`, `test_ftp_fleet_downloader`, `test_ftp_flask_proxy`, `test_ftp_encoding`, `test_ftp_fleet_jobs`)와 SKEWNONO 전체 suite가 모두 통과해야 합니다
- [ ] 기존 공개 이름(`core`, `direct_downloader`, `proxy`의 `__all__`)이 하나도 줄지 않아야 합니다
- [ ] `diff -rq --exclude=__pycache__`로 비교한 두 사본에 차이가 없어야 합니다
- [ ] 코드는 Python 3.11 문법만 씁니다
