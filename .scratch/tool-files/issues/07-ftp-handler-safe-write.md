# 07: ftp_handler core 안전한 쓰기

**What to build:** `core.FtpClient`에 쓰기 기능을 더합니다. 같은 이름의 파일은 덮어쓰지 않고, 중간에 끊겨도 반쯤 쓰인 파일이 원래 이름으로 남지 않게 합니다. 앞으로 tool-files 업로드와 레시피 일괄 복사가 함께 쓸 부품입니다. 화면은 없는 준비(prefactor) 티켓이며, `flask_modules`를 수정하는 작업이라 08과 분리했습니다.

**Blocked by:** 01 (ftp_handler core 읽기 확장)

**Status:** ready-for-agent

- [ ] 수정은 `flask_modules`에 먼저 하고 push한 뒤, vendored copy에 복사합니다
- [ ] `put(remote_path, data, *, deadline=None)`을 구현합니다. 같은 폴더에 충돌하지 않는 임시 이름으로 STOR한 뒤 RNFR/RNTO로 바꿉니다. 대상이 이미 있으면 거부합니다
- [ ] 실패하면 자기가 만든 임시 파일만 best-effort로 지웁니다. 지우지 못하면 그 경로를 예외에 담습니다. RNTO 응답만 유실된 경우에는 `TransferUncertain`을 냅니다
- [ ] 덮어쓰기 거부의 보장 범위를 docstring에 적습니다. best-effort이고, 단일 writer를 전제하며, 서버별 RNTO 동작은 `OFFICE-VERIFY`입니다
- [ ] 기존 `upload`와 `remove`는 바꾸지 않습니다. 삭제는 기존 `remove`를 그대로 씁니다
- [ ] fake FTP 테스트로 확인합니다: 덮어쓰기 거부, RNTO 거절, rename 실패 시 정리, 임시 파일 정리 실패, RNTO 응답 유실, 동시에 같은 대상을 만드는 경우
- [ ] 기존 테스트 파일은 수정하지 않습니다. flask_modules ftp 테스트 5개와 SKEWNONO 전체 suite가 통과해야 하고, 사본 diff는 비어 있어야 합니다
