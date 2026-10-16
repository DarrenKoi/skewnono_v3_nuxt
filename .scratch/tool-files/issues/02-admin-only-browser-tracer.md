# 02: 관리자 전용 파일 탐색기 (tracer bullet)

**What to build:** 관리자가 `/ebeam/<tool>/<fab>/tool-files?eqp=<eqp_id>` URL로 장비 파일 탐색기를 엽니다. breadcrumb으로 폴더를 이동하고, 이름·크기·수정 시각으로 정렬하고, 이름으로 걸러 보고, 파일을 하나씩 PC로 받을 수 있습니다. 집에서는 mock 트리로, 클라우드에서는 장비 FTP에 직접 붙어 동작합니다. 이 단계에서 `granted`는 관리자뿐이고, 나머지 사용자는 모두 `none`입니다. 행에서 들어가는 진입점은 03에서 만듭니다.

**Blocked by:** 01 (ftp_handler core 읽기 확장)

**Status:** done (2026-10-17)

- [x] 새 feature `tool_files`를 ebeam 아래에 평평하게 둡니다. 페이지 slug `tool-files`와 이름을 맞추고, feature_map에 API와 페이지 mapping을 모두 등록합니다
- [x] `access`, `list`, `download` API를 스펙의 계약대로 만듭니다. 모든 응답에 `Cache-Control: no-store`를 붙이고, 요청마다 권한을 다시 판정합니다
- [x] 장비 해석: sem_list의 한 행에서 IP, fab, 모델, 계정을 함께 가져옵니다. 계정은 msr_image `account_for()`를 재사용합니다. 중복 행은 IP·fab·모델이 모두 같을 때만 합치고, 다르면 409를 냅니다. 행이 없으면 404, 장비·slug·fab이 맞지 않으면 400, IP가 비었거나 잘못되면 503입니다
- [x] 경로 검증: PWD를 기준 루트로 삼고 구성요소 단위로 검사합니다. `.`, `..`, 역슬래시, 드라이브 문자, 제어 문자를 거부하고, 경로 문자열은 정규화하지 않습니다. 링크 항목은 목록에서 빼고 다운로드도 거부합니다. 경로 키는 불투명하게 다루며, 응답에 `root`, `parent`, `crumbs`를 함께 줍니다
- [x] 상한 env(다운로드 크기, direct deadline, 목록 원문 줄 수·바이트)를 읽습니다. 잘못된 값은 로그를 남기고 기본값으로 바꿉니다
- [x] 오류 코드는 스펙의 표를 따르고, 라우트에서 직접 `error_json`으로 변환합니다. 파일이 없거나 550이 오면 404 `file_unavailable`로 응답합니다
- [x] 다운로드 응답은 `attachment`, `filename`과 `filename*`, `octet-stream`, `nosniff` 헤더를 붙입니다
- [x] mock 트리에 다음을 넣습니다: 깨진 바이트 파일명, 빈 폴더, 파일 수천 개짜리 폴더, 상한을 넘는 파일, 링크, 홈이 `/`가 아닌 계정, 항상 연결에 실패하는 eqp_id. mock은 네트워크를 쓰지 않습니다. 폴더 구조는 `OFFICE-VERIFY`로 표시합니다
- [x] office template은 `core.FtpClient`로 direct 연결합니다. `office_example.py`와 MIGRATION.md를 작성하고, 실제 FTP 실패를 mock으로 fallback하지 않습니다
- [x] 페이지에는 breadcrumb, 같은 fab 안의 장비 선택기, 이름 필터, 정렬 표(시각이 null인 항목은 맨 뒤), 파일별 다운로드를 둡니다. 다운로드는 `fetch`로 상태를 먼저 확인해서 오류 JSON이 파일로 저장되지 않게 합니다. 상한을 넘는 파일은 버튼을 비활성화하고 이유를 표시합니다. 경로는 `?path=`에 둡니다. 시각 표현은 `--sk-*` 토큰만 씁니다
- [x] 비관리자에게는 "권한 없음" 안내를 보여 줍니다. 신청 카드는 05에서 만듭니다
- [x] HTTP 라우트 테스트(Flask test client, mock)로 다음을 확인합니다: 목록, 다운로드 바이트 일치, 깨진 파일명 왕복, 413, `bad_path`의 각 규칙, 링크 거부, 404, 409, 503. 비관리자 요청에서는 FTP 대역이 호출되지 않아야 합니다
- [x] 프론트 순수 함수 테스트(`node --test`)로 정렬, 크기 표시, 화면 선택을 확인합니다
- [x] `browser-verify` 스킬로 URL 진입, 폴더 이동, 다운로드를 실제 브라우저에서 확인합니다

## Comments

2026-10-17 완료.

- provider가 바꿔 끼우는 것은 FTP 연결 자체입니다. mock은 `core.FtpClient`와 같은 인터페이스를 가진 가짜 FTP 서버이므로, 장비 해석·경로 검사·오류 매핑은 집에서도 office와 같은 코드로 돕니다. 06(proxy)은 연결 클래스 하나만 바꾸면 됩니다.
- 테스트: tool_files HTTP·template·slug 테스트 32개, 프론트 순수 함수 테스트 5개입니다. 라우트 테스트는 뼈대와 함께 구현해서 처음부터 green이었습니다. 그래서 mutation 5개(링크 필터, 관리자 검사, 구성요소 단위 루트 검사, 중복 행, 550 매핑)로 테스트가 실제로 실패할 수 있는지 확인했고, 다섯 개 모두 잡혔습니다.
- 브라우저(agent-browser, worktree 서버 :5051/:3001)에서 확인했습니다: 루트 목록, 폴더 이동, URL `?path=`, 다운로드(blob 2048 B), 150 MB 파일의 버튼 비활성, 비관리자 안내, 없는 경로 오류. console 오류는 0건입니다.
- 스펙과 다르게 한 점이 두 가지 있습니다.
  - 링크를 가리키는 다운로드를 따로 거부하지 않습니다. 확인하려면 다운로드마다 상위 폴더 LIST가 필요하기 때문입니다. 목록에서는 링크를 숨기고, 손으로 쓴 URL은 N1과 같은 한계로 둡니다(MIGRATION.md에 적었습니다).
  - 계열별 허용 루트 설정은 아직 두지 않았습니다. 루트는 PWD이고, 실제 트리를 보고 필요해지면 추가합니다.
- 응답에 `max_bytes`를 추가했습니다. 화면이 413이 날 버튼을 미리 끌 수 있게 하기 위해서입니다.
- msr_image의 `_content_disposition`에 `kind` 인자를 추가해 다운로드에 재사용했습니다(기본값 `inline`이라 기존 동작은 같습니다).
