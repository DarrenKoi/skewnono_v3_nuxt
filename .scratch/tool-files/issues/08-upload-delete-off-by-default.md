# 08: 업로드·삭제 (기본 off)

**What to build:** 운영자가 서버 플래그 `SKEWNONO_TOOL_FILES_WRITE`를 켜면, 관리자가 탐색기에서 현재 폴더에 파일을 드래그해 올리고, 파일 이름이 표시된 확인 화면을 거쳐 삭제할 수 있습니다. 플래그는 기본으로 꺼져 있습니다. 꺼져 있을 때 쓰기 요청은 FTP에 닿기 전에 거부됩니다.

**Blocked by:** 02 (관리자 전용 파일 탐색기), 07 (ftp_handler core 안전한 쓰기)

**Status:** done (2026-10-17)

- [x] `can_write`의 정의는 `플래그 ∧ is_admin_request() ∧ transport_supports_write`입니다. 서버가 판정해서 `access` 응답에 담습니다. mock과 direct transport는 `transport_supports_write`가 참입니다
- [x] upload와 delete API는 스펙의 계약을 따릅니다. 거부 순서는 플래그 off 403, 관리자 아님 403, 쓰기를 지원하지 않는 transport 501입니다. 모두 body를 읽기 전, FTP 호출 전에 판정합니다
- [x] 501은 **쓰기를 지원하지 않는다고 선언한 가짜 transport**로 테스트합니다. 그래서 06(proxy)이 머지되었는지와 관계없이 이 티켓만으로 끝낼 수 있습니다
- [x] upload는 multipart(`fab`, `eqp_id`, `dir`, `file` 하나)로 받습니다. 파싱 전에 `Content-Length`를 상한과 비교해 413을 내고, 실제로 읽은 바이트도 다시 셉니다. 파일 이름은 basename만 쓰고 경로 검증을 적용합니다. 덮어쓰기는 지원하지 않으며, 같은 이름이 있으면 409 `file_exists`입니다
- [x] 쓰기에는 07의 `put`을, 삭제에는 `remove`를 씁니다. `TransferUncertain`은 503 `transfer_uncertain`으로 응답합니다
- [x] mock 트리에서도 쓰기가 실제로 동작하도록 만듭니다
- [x] 화면: `can_write`일 때만 드롭존과 삭제 버튼을 보여 줍니다. 삭제 확인 화면에는 파일 이름을 표시합니다. `file_exists`면 "같은 이름이 있어 올리지 않았습니다", `transfer_uncertain`이면 새로고침을 안내합니다
- [x] 업로드와 삭제는 수행자, identity 출처, 작업, 대상, 결과, request_id를 `logger.info`로 기록합니다
- [x] HTTP 테스트로 확인합니다: 플래그 off면 403이고 트리가 그대로인지, 켜져 있어도 비관리자면 403인지, 가짜 무쓰기 transport면 501인지(세 경우 모두 body를 읽지 않음), 관리자 업로드가 목록에 나타나는지, 같은 이름이면 409인지, 삭제하면 사라지는지, 파싱 전 413인지. **꺼 둔 코드가 썩지 않도록, 켜진 경로를 반드시 실행합니다**
- [x] MIGRATION.md에 "플래그를 켜기 전 확인할 조건"(계열별 RNTO 동작, 서버 측 쓰기 범위 제한)을 적습니다

## Comments

2026-10-17 완료. 프로세스는 `mattpocock-skills:tdd`를 썼고, 합의된 seam(Flask test client + mock provider, 프론트는 순수 함수)에서만 테스트했습니다.

- **거부 순서.** `_require_write()`가 403 `write_disabled` → 403 `forbidden` → 501 `write_not_supported` 순서로 판정하고, 그 뒤 기존 `_require_access()`도 적용합니다. 읽으면 예외를 던지는 `wsgi.input`과 예외를 던지는 `open_client`로 세 경우 모두 body를 읽지 않고 FTP를 열지 않는다는 것을 확인했습니다. 이 `wsgi.input`이 실제로 읽힐 때 실패하는지도 대조 실험으로 확인했습니다.
- **플래그.** `config.write_enabled()`는 `1`/`true`/`yes`/`on`(대소문자 무시)일 때만 켜집니다. `chat/config.py`와 같은 파싱입니다.
- **`transport_supports_write()`.** `data.py`가 provider로 dispatch합니다. 작업을 시작할 때는 main에 06이 없어서 mock과 `office_example.py`에 `return True`를 두었습니다. rebase할 때 06의 구현(office_example은 Windows/proxy에서 거짓, mock은 참)을 그대로 남기고 제 것은 지웠습니다. 06에는 `data.py` dispatcher가 없어서 이 티켓에서 추가했습니다.
- **413.** `Content-Length`가 상한(`SKEWNONO_TOOL_FILES_MAX_UPLOAD_BYTES`, 기본 100 MB)을 넘으면 파싱 전에 413입니다. 실제 바이트는 `request.max_content_length = cap`으로 셉니다. 이 설정은 Content-Length가 없는 본문(chunked)도 파싱 중에 상한에서 끊습니다. werkzeug의 `RequestEntityTooLarge`는 blueprint에서 `too_large`로 매핑했습니다(앱 공통 처리는 `request_entity_too_large`를 냅니다). 처음에는 `file.read(cap + 1)` 재검사도 넣었지만, 위 설정 때문에 도달할 수 없는 코드여서 지웠습니다.
- **파일 이름.** `\`를 `/`로 바꾼 뒤 마지막 조각(basename)만 씁니다. 폴더 키와 최종 경로는 둘 다 `check_path(ftp.home(), …)`로 검사합니다. `file` 필드가 두 개 이상이면 400 `bad_request`입니다.
- **추가 매핑(티켓 밖).** 장비 인코딩으로 보낼 수 없는 이름(latin-1에서 한글)은 그대로 두면 `UnicodeEncodeError`로 500이 되므로 400 `bad_path`로 응답합니다. 한글 이름 업로드가 필요한지는 MIGRATION 체크리스트에 남겼습니다.
- **`transfer_uncertain`.** 메시지는 "목록을 다시 확인하라"는 내용만 담고, 임시 파일 경로나 예외 note는 담지 않습니다(07의 STOR 거절 false alarm 문제 때문입니다). 테스트로 `.part`가 메시지에 없음을 확인합니다.
- **감사 기록.** 기존 `_audit`에 `source=`(identity 출처)를 추가했습니다. 그래서 grant와 revoke 로그에도 이 필드가 생깁니다. upload와 delete는 장비 해석 뒤의 성공과 실패 코드(`ok`, `file_exists` 등)를 한 줄씩 남깁니다. 장비를 해석하기 전에 거부된 요청(403/501/413/400)은 대상을 알 수 없어서 기록하지 않습니다. 경로와 status는 기존 activity 로그에 남습니다.
- **mock.** `put`과 `remove`가 모듈 전역 `_TREE`를 실제로 바꾸고, 올린 바이트를 그대로 다운로드할 수 있습니다. 같은 이름이면 `TargetExists`입니다. 테스트는 autouse fixture로 매번 새 트리를 씁니다. mock은 `TransferUncertain`을 내지 않으므로 그 경우는 monkeypatch로 확인했습니다.
- **화면.** `can_write`일 때만 드롭존(클릭하면 파일 선택, 여러 파일은 파일마다 요청 하나씩 순서대로)과 파일별 삭제 버튼을 보여 줍니다. 삭제 확인은 UModal이고 파일 이름을 보여 줍니다. 업로드와 삭제 뒤에는 목록을 새로 고칩니다. 업로드 413은 다운로드 문구가 아니라 "업로드 상한" 문구로 안내합니다(`toolFilesErrorMessage(code, 'upload')`). 삭제 버튼은 DESIGN.md의 `button-destructive` 규칙(`text-rose-600` + 확인 창)을 따랐습니다. 이 화면에는 z-50 레이어가 없어서 모달이 정상적으로 위에 뜹니다.
- **확인하지 못한 것.** 실제 장비의 RNTO와 SIZE 동작, 서버 측 쓰기 범위 제한은 `OFFICE-VERIFY`이며 MIGRATION.md의 "플래그를 켜기 전 확인할 조건"과 09에서 확인합니다.
