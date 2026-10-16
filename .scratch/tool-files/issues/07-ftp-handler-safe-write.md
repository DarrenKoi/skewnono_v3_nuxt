# 07: ftp_handler core 안전한 쓰기

**What to build:** `core.FtpClient`에 쓰기 기능을 더합니다. 같은 이름의 파일은 덮어쓰지 않고, 중간에 끊겨도 반쯤 쓰인 파일이 원래 이름으로 남지 않게 합니다. 앞으로 tool-files 업로드와 레시피 일괄 복사가 함께 쓸 부품입니다. 화면은 없는 준비(prefactor) 티켓이며, `flask_modules`를 수정하는 작업이라 08과 분리했습니다.

**Blocked by:** 01 (ftp_handler core 읽기 확장)

**Status:** done (2026-10-17)

- [x] 수정은 `flask_modules`에 먼저 하고 push한 뒤, vendored copy에 복사합니다
- [x] `put(remote_path, data, *, deadline=None)`을 구현합니다. 같은 폴더에 충돌하지 않는 임시 이름으로 STOR한 뒤 RNFR/RNTO로 바꿉니다. 대상이 이미 있으면 거부합니다
- [x] 실패하면 자기가 만든 임시 파일만 best-effort로 지웁니다. 지우지 못하면 그 경로를 예외에 담습니다. RNTO 응답만 유실된 경우에는 `TransferUncertain`을 냅니다
- [x] 덮어쓰기 거부의 보장 범위를 docstring에 적습니다. best-effort이고, 단일 writer를 전제하며, 서버별 RNTO 동작은 `OFFICE-VERIFY`입니다
- [x] 기존 `upload`와 `remove`는 바꾸지 않습니다. 삭제는 기존 `remove`를 그대로 씁니다
- [x] fake FTP 테스트로 확인합니다: 덮어쓰기 거부, RNTO 거절, rename 실패 시 정리, 임시 파일 정리 실패, RNTO 응답 유실, 동시에 같은 대상을 만드는 경우
- [x] 기존 테스트 파일은 수정하지 않습니다. flask_modules ftp 테스트 5개와 SKEWNONO 전체 suite가 통과해야 하고, 사본 diff는 비어 있어야 합니다

## Comments

2026-10-17 완료. flask_modules `d826b63` → SKEWNONO vendored copy(`core/client.py`, `core/__init__.py`만 복사, `diff -rq` 출력 없음).

- API는 `put(remote_path, data, *, deadline=None)`입니다. 새 예외는 `TargetExists`와 `TransferUncertain`이며 `core.__all__`에 추가했습니다(기존 이름은 그대로입니다).
- 임시 이름은 `<대상>.<12자리 hex>.part`이고 대상과 같은 폴더에 만듭니다.
- 존재 확인은 `SIZE`입니다. 데이터 연결 없이 제어 채널 한 번으로 끝나기 때문입니다. vsftpd처럼 ASCII 모드에서 SIZE를 550으로 거절하는 서버가 있어 먼저 `TYPE I`를 보냅니다. 550만 "없음"으로 보고, 502 같은 다른 거절은 그대로 올려 확인이 조용히 꺼지지 않게 했습니다. 확인은 STOR 전과 rename 직전에 두 번 합니다.
- 임시 파일을 지우지 못하면 원래 예외를 그대로 올리고 `temp_path` 속성과 `add_note`로 경로를 남깁니다. 별도 예외 타입으로 감싸지 않은 것은 호출자가 `TransferTimeout`, `error_perm` 같은 원래 타입으로 분기할 수 있게 하려는 것입니다. `TransferUncertain`도 `temp_path`를 가집니다.
- rename 중 연결 오류(OSError, EOFError)는 RNFR 단계였더라도 모두 `TransferUncertain`으로 보고합니다. ftplib `rename`이 두 명령을 한 번에 보내서 구분할 수 없기 때문이며, 보수적으로 보고하는 쪽을 택했습니다.
- 새 테스트는 flask_modules `tests/test_ftp_client_put.py`의 8개입니다. 마지막 rename 직전 확인과 RNTO 사이에 다른 writer가 들어오는 경우는 덮어써지는 것이 알려진 한계이며, 이를 기록하는 characterization 테스트로 남겼습니다(처음부터 통과하는 테스트입니다).
- flask_modules ftp 테스트 7개 모듈(새 파일 포함) 179개가 통과했고, 기존 테스트 파일은 수정하지 않았습니다. SKEWNONO 전체는 3967 passed / 13 skipped로 변경 전과 같고, ruff도 통과했습니다.
- 확인하지 못한 것: 실제 서버의 RNTO가 기존 파일을 덮어쓰는지 거절하는지, 디렉터리 대상에 SIZE가 550을 내는지, 실제 ftplib `storbinary`가 callback 예외 뒤에 소켓을 어떻게 남기는지는 `OFFICE-VERIFY`이며 09에서 확인합니다.
