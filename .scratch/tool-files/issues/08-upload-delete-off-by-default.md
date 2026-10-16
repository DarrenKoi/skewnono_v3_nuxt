# 08: 업로드·삭제 (기본 off)

**What to build:** 운영자가 서버 플래그 `SKEWNONO_TOOL_FILES_WRITE`를 켜면, 관리자가 탐색기에서 현재 폴더에 파일을 드래그해 올리고, 파일 이름이 표시된 확인 화면을 거쳐 삭제할 수 있습니다. 플래그는 기본으로 꺼져 있습니다. 꺼져 있을 때 쓰기 요청은 FTP에 닿기 전에 거부됩니다.

**Blocked by:** 02 (관리자 전용 파일 탐색기), 07 (ftp_handler core 안전한 쓰기)

**Status:** ready-for-agent

- [ ] `can_write`의 정의는 `플래그 ∧ is_admin_request() ∧ transport_supports_write`입니다. 서버가 판정해서 `access` 응답에 담습니다. mock과 direct transport는 `transport_supports_write`가 참입니다
- [ ] upload와 delete API는 스펙의 계약을 따릅니다. 거부 순서는 플래그 off 403, 관리자 아님 403, 쓰기를 지원하지 않는 transport 501입니다. 모두 body를 읽기 전, FTP 호출 전에 판정합니다
- [ ] 501은 **쓰기를 지원하지 않는다고 선언한 가짜 transport**로 테스트합니다. 그래서 06(proxy)이 머지되었는지와 관계없이 이 티켓만으로 끝낼 수 있습니다
- [ ] upload는 multipart(`fab`, `eqp_id`, `dir`, `file` 하나)로 받습니다. 파싱 전에 `Content-Length`를 상한과 비교해 413을 내고, 실제로 읽은 바이트도 다시 셉니다. 파일 이름은 basename만 쓰고 경로 검증을 적용합니다. 덮어쓰기는 지원하지 않으며, 같은 이름이 있으면 409 `file_exists`입니다
- [ ] 쓰기에는 07의 `put`을, 삭제에는 `remove`를 씁니다. `TransferUncertain`은 503 `transfer_uncertain`으로 응답합니다
- [ ] mock 트리에서도 쓰기가 실제로 동작하도록 만듭니다
- [ ] 화면: `can_write`일 때만 드롭존과 삭제 버튼을 보여 줍니다. 삭제 확인 화면에는 파일 이름을 표시합니다. `file_exists`면 "같은 이름이 있어 올리지 않았습니다", `transfer_uncertain`이면 새로고침을 안내합니다
- [ ] 업로드와 삭제는 수행자, identity 출처, 작업, 대상, 결과, request_id를 `logger.info`로 기록합니다
- [ ] HTTP 테스트로 확인합니다: 플래그 off면 403이고 트리가 그대로인지, 켜져 있어도 비관리자면 403인지, 가짜 무쓰기 transport면 501인지(세 경우 모두 body를 읽지 않음), 관리자 업로드가 목록에 나타나는지, 같은 이름이면 409인지, 삭제하면 사라지는지, 파싱 전 413인지. **꺼 둔 코드가 썩지 않도록, 켜진 경로를 반드시 실행합니다**
- [ ] MIGRATION.md에 "플래그를 켜기 전 확인할 조건"(계열별 RNTO 동작, 서버 측 쓰기 범위 제한)을 적습니다
