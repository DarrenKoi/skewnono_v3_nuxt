# 장비 파일 탐색기 (tool-files)

Status: ready-for-agent

## Problem Statement

장비 관리자는 장비에 있는 파일(로그, 레시피, 설정 파일)을 PC로 가져오려면 지금은
FileZilla 같은 FTP 클라이언트를 따로 켜고, 장비 IP와 계열별 FTP 계정을 직접 알아야
합니다. SKEWNONO에는 이미 장비 목록, 장비 IP, 계열별 FTP 계정, FTP 클라이언트가 모두
있지만, 사람이 장비 파일을 둘러보고 받을 수 있는 화면은 없습니다.

동시에 장비 FTP는 생산 장비의 파일 시스템이므로 아무나 열 수 있어서는 안 됩니다.
승인된 팀의 구성원과 개별 승인을 받은 사람만 접근해야 하고, 승인자는 앱 관리자
한 명(2067928)입니다.

## Solution

장비 범위 페이지 `/ebeam/<tool>/<fab>/tool-files?eqp=<eqp_id>`에 FileZilla 형태의
파일 탐색기를 둡니다. 들어가는 길은 `장비 상태`의 `장비 리스트`와 `스토리지` 하위
탭에 있는 각 장비 행의 "파일 열기" 버튼입니다. top nav나 FeatureTab은 추가하지
않습니다. 대부분의 사용자는 권한이 없어서, 메뉴로 두면 잠긴 문만 보여 주게 되기
때문입니다.

v1의 기능은 탐색(폴더 이동, 목록, 크기·수정 시각)과 PC로 다운로드입니다. 업로드와
삭제는 구현과 테스트까지 마치지만 서버 플래그로 꺼진 상태로 출고합니다.

권한은 두 가지 방식으로 줍니다.

- **팀 승인**: 등록된 팀 이름(`dept_nm`)에 속한 사람은 신청 없이 바로 들어갑니다.
- **개인 승인**: 그 밖의 사람은 페이지에서 사유를 적어 신청합니다. 관리자가
  `/admin/access`에서 사번(empno) 단위로 승인하거나 거절합니다.

## User Stories

1. 장비 관리자로서, 스토리지 탭에서 디스크가 가득 찬 장비 행의 "파일 열기"를 누르면 바로 그 장비의 파일 탐색기가 열리기를 원합니다. 장비를 다시 고를 필요가 없게 하기 위해서입니다.
2. 장비 관리자로서, 장비 리스트 탭의 행에서도 같은 탐색기를 열고 싶습니다. 디스크 문제가 아니어도 파일을 받을 일이 있기 때문입니다.
3. 장비 관리자로서, 탐색기 안에서 같은 fab의 다른 장비로 바꿀 수 있기를 원합니다. 목록 화면으로 돌아갔다 오지 않기 위해서입니다.
4. 장비 관리자로서, 현재 경로가 breadcrumb으로 보이고 상위 폴더를 눌러 바로 올라갈 수 있기를 원합니다. 깊은 폴더에서 길을 잃지 않기 위해서입니다.
5. 장비 관리자로서, 폴더를 더블클릭하면 그 폴더로 들어가기를 원합니다. FileZilla와 같은 조작감을 기대하기 때문입니다.
6. 장비 관리자로서, 각 항목의 이름, 크기, 수정 시각을 보고 이 열들로 정렬하기를 원합니다. 최근 로그나 큰 파일을 빨리 찾기 위해서입니다.
7. 장비 관리자로서, 현재 폴더 안에서 파일 이름으로 걸러 보기를 원합니다. 파일이 수천 개인 로그 폴더에서 원하는 것을 찾기 위해서입니다.
8. 장비 관리자로서, 파일을 눌러 PC로 다운로드하기를 원합니다. 장비 파일을 분석하거나 공유하는 것이 이 기능의 주 목적이기 때문입니다.
9. 장비 관리자로서, 여러 파일을 골라 한 번에 받기를 원합니다. 같은 날짜의 로그 여러 개를 받는 일이 흔하기 때문입니다.
10. 장비 관리자로서, 다운로드 상한을 넘는 파일은 왜 받을 수 없는지 화면에서 알기를 원합니다. 조용히 실패하면 장비 문제로 오해하기 때문입니다.
11. 장비 관리자로서, 장비가 꺼져 있거나 FTP에 접속하지 못하면 "장비에 연결할 수 없음"이라는 안내를 보고 다시 시도할 수 있기를 원합니다. 권한 문제와 장비 문제를 구별하기 위해서입니다.
12. 장비 관리자로서, 파일 이름이 깨져 보이더라도 그 파일을 정상적으로 받을 수 있기를 원합니다. 일부 장비의 파일명 바이트가 손상되어 있다는 것이 알려져 있기 때문입니다.
13. 장비 관리자로서, 마지막으로 보던 경로가 URL에 남아서 링크로 공유하거나 새로고침해도 그 폴더가 다시 열리기를 원합니다.
14. 승인된 팀의 구성원으로서, 신청 절차 없이 처음부터 탐색기를 쓰고 싶습니다. 팀 단위 승인의 목적이 그것이기 때문입니다.
15. 승인되지 않은 사용자로서, 페이지를 열면 파일 목록 대신 "권한 요청" 카드를 보고 사유 한 줄을 적어 신청하기를 원합니다. 따로 신청 페이지를 찾지 않기 위해서입니다.
16. 신청한 사용자로서, 다시 페이지를 열었을 때 내 신청이 대기 중인지, 거절되었는지 보기를 원합니다.
17. 거절된 사용자로서, 사유를 고쳐 다시 신청할 수 있기를 원합니다.
18. 사용자로서, 소속 정보를 일시적으로 확인할 수 없을 때는 "권한 없음"이 아니라 "소속 확인 불가, 잠시 후 다시 시도"를 보기를 원합니다. 인프라 장애를 정책 거부로 오해하지 않기 위해서입니다.
19. 자기 신고(`declared`)나 API 토큰으로 식별된 사용자는 팀이나 사번이 승인되어 있어도 접근할 수 없어야 합니다. 쿠키나 사번 입력만으로 생산 장비 파일 시스템이 열리면 안 되기 때문입니다.
20. 관리자로서, `/admin/access`의 새 섹션에서 대기 중인 신청을 사번, 이름, 팀, 사유, 신청 시각과 함께 보기를 원합니다.
21. 관리자로서, 신청을 승인하면 그 사번이 개인 승인 목록에 들어가고 신청이 목록에서 사라지기를 원합니다.
22. 관리자로서, 신청을 거절하기를 원합니다.
23. 관리자로서, 같은 팀에서 신청이 여러 건 쌓였으면 "이 팀 전체 승인" 한 번으로 팀 승인을 추가하고 그 팀의 대기 신청을 정리하기를 원합니다.
24. 관리자로서, 팀 승인은 직접 입력하지 않고 실제 구성원 디렉터리에 있는 팀 이름 목록에서 고르기를 원합니다. 오타 하나로 팀 전체가 막히는 일을 막기 위해서입니다.
25. 관리자로서, 승인된 팀 목록과 개인 목록을 보고 각각 회수하기를 원합니다.
26. 관리자로서, 신청 없이 사번을 직접 입력해 개인 승인을 추가하기를 원합니다. 미리 권한을 줘야 하는 사람이 있기 때문입니다.
27. 관리자로서, 권한 저장소가 내려가 있을 때 빈 목록 대신 장애 안내를 보기를 원합니다. 빈 목록을 보고 권한이 사라졌다고 판단해 다시 부여하는 일을 막기 위해서입니다.
28. 관리자로서, 누가 언제 어느 장비의 어떤 파일을 받았는지 사용 기록에서 보기를 원합니다. 생산 장비이므로 감사 기록이 승인만큼 중요하기 때문입니다.
29. 운영자로서, 업로드와 삭제 기능을 서버 설정 하나로 켜고 끌 수 있기를 원합니다. 기능은 미리 만들어 두되, 위험해서 아직 열지 않기 위해서입니다.
30. 운영자로서, 쓰기 기능이 꺼져 있으면 업로드·삭제 요청이 FTP에 닿지 않고 거부되기를 원합니다. 화면에서 버튼을 숨기는 것만으로는 막을 수 없기 때문입니다.
31. 쓰기 기능이 켜졌을 때 장비 관리자로서, 현재 폴더에 파일을 드래그해 업로드하기를 원합니다.
32. 쓰기 기능이 켜졌을 때 장비 관리자로서, 파일 삭제 전에 파일 이름이 들어간 확인 화면을 보기를 원합니다. 생산 장비에서 지운 파일은 되돌릴 수 없기 때문입니다.
33. 쓰기 기능이 켜졌을 때 관리자로서, 업로드와 삭제가 모두 사용 기록에 남기를 원합니다.
34. 집(Phase 1) 개발자로서, 장비에 닿지 않아도 가짜 디렉터리 트리로 탐색기 전체를 개발하고 확인하기를 원합니다.
35. office 담당자로서, 다른 feature처럼 `office_example.py`를 복사하는 것만으로 실제 장비 FTP와 Redis 권한 저장소로 전환하기를 원합니다.

## Implementation Decisions

### 모듈

- **새 백엔드 feature `tool_files`** (ebeam 아래 평평하게, 페이지 slug `tool-files`와 같은 이름). 구성은 다른 feature와 같은 `routes.py` / `contracts.py` / `data.py` / `providers/{mock,office_example}.py`입니다. `_logging/feature_map.py`에 slug를 등록해 사용 기록이 이 feature로 쌓이게 합니다.
- **swap surface가 둘입니다.** 하나는 파일 시스템(FTP 대 가짜 트리), 다른 하나는 권한 저장소(Redis 대 mtime JSON 파일)입니다. 같은 feature 안에 두 seam이 있는 선례는 `msr_file`, `msr_image`이고, `provider-selection.md`의 규칙을 따릅니다.
- **권한 판정은 순수 함수 하나**에 둡니다. 입력은 identity 출처, 사번, directory probe 결과, 승인 목록입니다. 출력은 닫힌 어휘입니다.

  ```text
  AccessVerdict = "granted" | "pending" | "rejected" | "none" | "directory_unavailable" | "untrusted_identity"
  granted ⇔ 신뢰 출처(cookie/local)
            ∧ (is_admin(empno) ∨ "emp:<empno>" ∈ grants ∨ "team:<dept_nm>" ∈ grants)
  ```

  `is_admin`이 참이면 directory를 조회하지 않습니다. 사번 승인이 맞으면 directory를 조회하지 않습니다. 팀 승인을 확인해야 할 때만 `probe_member`를 쓰고, 그 결과가 `unavailable`이면 `directory_unavailable`(503)입니다. `lookup_member`는 실패를 감추는 설계라 권한 판정에 쓰지 않습니다.
- **directory에 팀 목록 읽기 함수를 추가합니다.** 관리 화면의 팀 선택기를 채우기 위해 `members` 해시에 있는 `dept_nm`의 고유값과 각 팀의 인원수를 돌려줍니다. 관리자 전용이고 결과는 캐시합니다. 집에서는 가짜 행에서 만든 목록을 씁니다.
- **장비 해석**: `eqp_id`를 받아 `sem_list`에서 `eqp_ip`와 계열을 찾고, FTP 계정은 msr_image가 쓰는 `SKEWNONO_TOOL_FTP_*` 설정(`eqp_id` > `fab_name` > 계열 slug > 기본값 순서)을 그대로 따릅니다. 설정 파싱은 두 feature가 함께 쓰도록 공용 위치로 옮기고 msr_image는 그것을 import합니다. 복사본을 만들지 않습니다.
- **FTP 접근은 `ftp_handler.core.FtpClient`**를 요청마다 열고 닫습니다. 목록은 `list_details`(LIST)를 씁니다. MLSD가 없는 옛 장비 데몬에서도 동작하기 때문입니다. 인코딩은 `SKEWNONO_TOOL_FTP_ENCODING`을 따릅니다.
- **경로는 불투명한 키입니다.** 서버가 목록에서 돌려준 경로 문자열을 클라이언트가 그대로 다운로드 요청에 되돌려 줍니다. 클라이언트는 경로를 조립하거나 디코딩하지 않습니다(breadcrumb 표시용 분할만 합니다). latin-1 설정에서 깨진 파일명을 그대로 받을 수 있게 하기 위해서입니다.
- **경로 검사**는 라우트 경계에서 합니다. `..` 구성요소를 거부하고, 계열별 허용 루트 설정이 있으면 그 아래만 허용합니다. 허용 루트의 실제 값은 모르므로 기본값은 FTP 로그인 홈이고 `OFFICE-VERIFY`로 표시합니다.
- **다운로드 상한**: `FtpClient.download`는 파일 전체를 메모리에 올리므로 크기 상한을 둡니다(기본 100 MB, env로 조정, `OFFICE-VERIFY`). 상한 초과는 목록 단계에서 이미 알 수 있으므로 화면은 다운로드 버튼을 비활성화하고 이유를 보여 줍니다. 서버도 다시 확인합니다. 여러 파일 다운로드는 v1에서 파일별 순차 다운로드이고, zip 묶음은 하지 않습니다.
- **쓰기 플래그**: `SKEWNONO_TOOL_FILES_WRITE`가 참일 때만 업로드·삭제 라우트가 동작합니다. 거짓이면 FTP에 접속하기 전에 403 `write_disabled`를 돌려줍니다. 기본값은 거짓입니다. 쓰기 권한은 읽기 권한과 같은 승인 목록을 씁니다. 등급을 나누는 것은 플래그를 켜는 시점에 다시 결정합니다.

### 저장소 키 (office, Redis)

```text
skewnono:tool_files:grants    HASH  "team:<dept_nm>" | "emp:<empno>" -> {granted_at, granted_by}
skewnono:tool_files:requests  HASH  <empno> -> {reason, dept_nm, requested_at, status: pending|rejected}
```

- 사번은 대문자로 정규화합니다(`_auth/admin.py`, `access_control`과 같은 규칙).
- 신청은 사번당 하나입니다. 다시 신청하면 덮어쓰고 `pending`으로 돌아갑니다.
- 승인은 grant를 추가하고 신청을 지웁니다. 거절은 신청의 status를 `rejected`로 바꿉니다.
- 팀 전체 승인은 팀 grant를 추가하고, 그 `dept_nm`으로 들어온 대기 신청을 지웁니다.
- 장애 처리는 `access_control/MIGRATION.md`의 표를 따릅니다. 읽기 실패는 503, 쓰기 실패는 "저장되지 않음" 503입니다. 거부로 바꿔 말하지 않습니다.

### API

모두 `/api` 아래입니다. `<tool_slug>`는 기존 ebeam feature처럼 검증합니다.

| Method | Path | 권한 | 내용 |
|:--|:--|:--|:--|
| GET | `/<tool_slug>/tool-files/access` | 로그인 | `{verdict, can_write, request?}`. 페이지가 처음 부르는 호출 |
| GET | `/<tool_slug>/tool-files/list?eqp_id=&path=` | granted | `{path, entries: [{name, path, is_dir, size, modified}]}` |
| GET | `/<tool_slug>/tool-files/download?eqp_id=&path=` | granted | 파일 바이트, `Content-Disposition: attachment` |
| POST | `/<tool_slug>/tool-files/upload` | granted + 플래그 | multipart, 대상 폴더 |
| DELETE | `/<tool_slug>/tool-files/file?eqp_id=&path=` | granted + 플래그 | 파일 하나 삭제 |
| POST | `/tool-files/requests` | 로그인 | `{reason}`. 본인 신청 생성·갱신 |
| GET | `/admin/tool-files` | admin | `{grants, requests}` |
| GET | `/admin/tool-files/teams` | admin | `[{dept_nm, members}]` |
| POST | `/admin/tool-files/grants` | admin | `{kind: "team"\|"emp", value}` |
| DELETE | `/admin/tool-files/grants/<kind>/<value>` | admin | 회수 |
| POST | `/admin/tool-files/requests/<empno>/approve` | admin | |
| POST | `/admin/tool-files/requests/<empno>/reject` | admin | |

오류 코드: 권한 없음 403 `forbidden`, 신뢰할 수 없는 identity 403 `untrusted_identity`, 쓰기 꺼짐 403 `write_disabled`, 장비 연결 실패 503 `tool_unreachable`, 소속 확인 불가 503 `directory_unavailable`, 상한 초과 413 `too_large`, 잘못된 경로 400 `bad_path`.

장비 FTP 연결 실패는 기존 503 `SourceUnavailable` 관례를 따릅니다(502는 인프라 몫).

### 프론트엔드

- 페이지 하나와 하위 컴포넌트 몇 개입니다. 구성은 breadcrumb, 장비 선택기, 파일 이름 필터, 정렬 가능한 파일 표, 다운로드 버튼입니다. 왼쪽 폴더 트리는 v1에서 넣지 않습니다(breadcrumb과 더블클릭으로 충분합니다).
- 경로는 `?path=`로 URL에 둡니다.
- `access` 응답에 따라 탐색기, 신청 카드, 대기·거절 안내, 장애 안내 중 하나를 그립니다.
- 업로드 드롭존과 삭제 버튼은 `can_write`가 참일 때만 그립니다.
- `/admin/access`에 섹션을 하나 추가합니다. 대기 신청, 팀 승인, 개인 승인의 세 칸입니다. 팀 선택기는 `/admin/tool-files/teams`에서 채웁니다.
- 스토리지 표와 장비 리스트 표의 행에 "파일 열기" 액션을 추가합니다.
- 시각 요소는 `DESIGN.md`의 `--sk-*` 토큰만 씁니다.

### 집 (Phase 1) mock

- 파일 시스템 mock은 계열별로 그럴듯한 가짜 트리를 만듭니다. 폴더 이름과 깊이는 실제 구조를 모르므로 `OFFICE-VERIFY`입니다. 다만 알려진 성질은 따라 합니다. 일부 파일명은 깨진 바이트(latin-1로 디코딩한 모양)로 만들고, 빈 폴더와 파일 수천 개짜리 폴더를 넣고, 상한을 넘는 큰 파일 항목을 하나 넣습니다. 특정 eqp_id 하나는 항상 연결 실패를 냅니다. tidy한 mock이 office 버그를 숨기지 않게 하기 위해서입니다.
- 권한 저장소 mock은 `access_control`처럼 mtime 키의 JSON 파일입니다.

## Testing Decisions

- 좋은 테스트는 사용자가 쓰는 길로 부르고 결과를 리터럴 기대값과 비교합니다. 내부 함수 호출 순서나 구현 세부를 확인하지 않습니다.
- **주 seam은 Flask test client를 통한 HTTP 라우트**입니다. `LASTUSER` 쿠키와 identity 출처를 바꿔 가며 mock 위에서 다음을 확인합니다.
  - 판정 표 전체: admin, 사번 승인, 팀 승인, 승인 없음, 대기, 거절, `declared`/`token` 출처, directory `unavailable`.
  - 신청 → 승인 → 접근, 신청 → 거절 → 재신청, 팀 전체 승인이 대기 신청을 정리하는지.
  - 목록, 다운로드 바이트 일치, 깨진 파일명 파일의 왕복 다운로드, 상한 초과 413, `..` 경로 400, 연결 실패 503.
  - 쓰기 플래그 off에서 업로드·삭제가 403이고 mock 트리가 바뀌지 않는지. 플래그 on에서 업로드한 파일이 목록에 나타나고 삭제한 파일이 사라지는지. 꺼 둔 코드가 썩지 않도록 on 경로를 반드시 실행합니다.
- **provider 계약 테스트**: 두 저장소 각각 mock과 office template이 같은 계약을 지키는지 확인합니다. 선례는 `access_control/tests/`의 `test_contract.py`, `test_mock_store.py`, `test_office_template.py`, `test_routes.py`입니다. office template 테스트는 `office_example`을 `sys.modules`에 alias해서 실제로 실행합니다(`importorskip`만으로는 깨진 office 테스트를 숨깁니다).
- 프론트엔드는 `node --test`로 순수 함수만 테스트합니다. 대상은 breadcrumb 분할, 정렬, 파일 크기 표시, `access` 응답에서 그릴 화면을 고르는 함수입니다.
- 브라우저 확인은 `browser-verify` 스킬로 합니다. 대상은 스토리지 행에서 진입, 폴더 이동, 다운로드, 신청 카드, `/admin/access` 섹션입니다.

## Out of Scope

- **여러 장비에 걸친 레시피 복사와 디스크 일괄 정리.** 파일 수백 개를 여러 장비로 옮기는 일은 HTTP 요청 하나에 태우면 중간에 끊기고 이어 할 수 없습니다. 별도 세션에서 설계합니다. 출발점은 `.scratch/recipe-bulk-copy/handoff.md`입니다.
- 장비 간 2-pane 복사, 폴더 업로드·다운로드, zip 묶음 다운로드, 스트리밍 다운로드.
- fab이나 장비 단위로 나눈 권한, 읽기와 쓰기 권한 등급 분리, 권한 만료.
- 사내 DB의 장비 담당자 필드로 권한을 자동 부여하는 것.
- 승인·거절 알림(메일, 메신저).
- 파일 미리보기(텍스트·이미지 뷰어).

## Further Notes

- 승인 키는 `dept_nm`(user-confirmed 2026-10-17)입니다. 조직 개편으로 팀 이름이 바뀌면 팀 승인이 끊기므로, 관리 화면의 팀 승인 행에는 해당 팀의 현재 인원수를 함께 보여 줍니다. 0명이 된 팀 승인은 개편 신호입니다.
- 승인자는 앱 관리자(2067928) 한 명입니다(user-confirmed 2026-10-17). 관리자 판정은 기존 `require_admin`을 씁니다.
- 주 용도는 PC로 가져오기입니다(user-confirmed 2026-10-17). 디스크 정리와 장비 간 복사는 웹 밖에서 합니다.
- `/api/*` rate limit(50 req / 5 s)은 탐색에서는 문제가 되지 않습니다. 여러 파일 순차 다운로드가 한도에 닿으면 `_EXEMPT_BLUEPRINTS`에 넣을지 그때 판단합니다.
