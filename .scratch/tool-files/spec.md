# 장비 파일 탐색기 (tool-files)

Status: ready-for-agent

개정 r2 (2026-10-17): Codex 1차·2차 검토(`codex-r1.md`, `codex-r2.md`)를 반영했습니다.
항목별 처리는 맨 아래 "검토 반영 기록"에 있습니다.

## Problem Statement

장비 관리자가 장비에 있는 파일(로그, 레시피, 설정 파일)을 PC로 가져오려면 지금은
FileZilla 같은 FTP 클라이언트를 따로 켜야 합니다. 장비 IP와 계열별 FTP 계정도 직접
알아야 합니다. SKEWNONO에는 장비 목록, 장비 IP, 계열별 FTP 계정, FTP 클라이언트가
이미 모두 있습니다. 하지만 사람이 장비 파일을 둘러보고 받을 수 있는 화면은 없습니다.

장비 FTP는 생산 장비의 파일 시스템이므로 아무나 열 수 있어서는 안 됩니다. 승인된
팀의 구성원과 개별 승인을 받은 사람만 접근해야 하며, 승인자는 앱 관리자입니다.

## Solution

장비 범위 페이지 `/ebeam/<tool>/<fab>/tool-files?eqp=<eqp_id>`에 FileZilla 형태의
파일 탐색기를 둡니다. 진입점은 `장비 상태` 아래 `장비 리스트`와 `스토리지` 하위 탭의
각 장비 행에 있는 "파일 열기" 버튼입니다. top nav나 FeatureTab에는 추가하지 않습니다.
대부분의 사용자는 권한이 없어서, 메뉴로 두면 잠긴 문만 보여 주게 되기 때문입니다.

v1의 기능은 두 가지입니다. 폴더 이동과 목록 보기(크기·수정 시각 포함), 그리고
파일 하나씩 PC로 다운로드하는 것입니다. 업로드와 삭제는 구현과 테스트까지 마치되,
서버 플래그로 꺼진 상태로 출고합니다. 플래그를 켜더라도 v1에서 쓰기를 할 수 있는
사람은 앱 관리자뿐입니다.

권한은 두 가지 방식으로 줍니다.

- **팀 승인**: 등록된 팀 이름(`dept_nm`)에 속한 사람은 신청 없이 바로 들어갑니다.
- **개인 승인**: 그 밖의 사람은 페이지에서 사유를 적어 신청합니다. 관리자는
  `/admin/access`에서 사번(empno) 단위로 승인하거나 거절합니다.

환경별 동작은 다음과 같습니다.

- 집은 mock으로 동작합니다.
- 클라우드(Linux)는 장비 FTP에 직접 연결합니다.
- office Windows PC(Phase 2)는 장비 FTP에 직접 닿지 못하므로 FTP proxy를 거칩니다.
  Phase 2는 개발자(앱 관리자) 한 명이 개발과 검증에만 쓰는 환경입니다. 그래서 proxy에는
  읽기(목록, 다운로드)만 추가합니다.

## User Stories

1. 장비 관리자로서, 스토리지 탭에서 디스크가 가득 찬 장비 행의 "파일 열기"를 눌러 바로 그 장비의 파일 탐색기를 열고 싶습니다. 장비를 다시 고를 필요가 없기 때문입니다.
2. 장비 관리자로서, 장비 리스트 탭의 행에서도 같은 탐색기를 열고 싶습니다.
3. 장비 관리자로서, 탐색기 안에서 같은 fab의 다른 장비로 바꿀 수 있기를 원합니다.
4. 장비 관리자로서, 현재 경로를 breadcrumb으로 보고 상위 폴더를 눌러 바로 올라가기를 원합니다.
5. 장비 관리자로서, 폴더를 더블클릭하면 그 폴더로 들어가기를 원합니다.
6. 장비 관리자로서, 각 항목의 이름, 크기, 수정 시각을 보고 이 열들로 정렬하기를 원합니다. 최근 로그나 큰 파일을 빨리 찾기 위해서입니다.
7. 장비 관리자로서, 현재 폴더 안에서 파일 이름으로 걸러 보기를 원합니다.
8. 장비 관리자로서, 파일을 눌러 PC로 다운로드하기를 원합니다. 이것이 이 기능의 주 목적입니다.
9. 장비 관리자로서, 상한을 넘는 파일은 왜 받을 수 없는지 화면에서 알기를 원합니다.
10. 장비 관리자로서, 장비가 꺼져 있거나 FTP에 접속하지 못하면 "장비에 연결할 수 없음"이라는 안내를 보고 다시 시도할 수 있기를 원합니다. 권한 문제와 장비 문제를 구별하기 위해서입니다.
11. 장비 관리자로서, 목록을 연 뒤 사라졌거나 FTP 계정이 읽을 수 없는 파일을 받으려 하면 "파일이 없거나 접근할 수 없음"이라는 안내를 보기를 원합니다.
12. 장비 관리자로서, 파일 이름이 깨져 보여도 그 파일을 정상적으로 받을 수 있기를 원합니다. 일부 장비는 파일명 바이트가 손상되어 있다는 것이 알려져 있기 때문입니다.
13. 장비 관리자로서, 보고 있는 경로가 URL에 남아서 새로고침하거나 링크를 공유해도 그 폴더가 다시 열리기를 원합니다.
14. 개발자로서, office Windows PC(Phase 2)에서도 proxy를 통해 탐색과 다운로드를 검증할 수 있기를 원합니다.
15. 승인된 팀의 구성원으로서, 신청 절차 없이 처음부터 탐색기를 쓰고 싶습니다.
16. 승인되지 않은 사용자로서, 페이지를 열면 파일 목록 대신 "권한 요청" 카드를 보고 사유 한 줄을 적어 신청하기를 원합니다.
17. 신청한 사용자로서, 다시 페이지를 열었을 때 내 신청이 대기 중인지 거절되었는지 보기를 원합니다.
18. 거절된 사용자로서, 사유를 고쳐 다시 신청할 수 있기를 원합니다.
19. 사용자로서, 소속 정보를 일시적으로 확인할 수 없을 때 "권한 없음"이 아니라 "소속 확인 불가, 잠시 후 다시 시도"를 보기를 원합니다.
20. 자기 신고(`declared`)나 API 토큰으로 식별된 사용자는 권한을 인정받지 못하고, 신뢰할 수 있는 출처로 다시 접속하라는 안내를 봐야 합니다. 이런 사용자는 신청도 할 수 없습니다.
21. 관리자로서, `/admin/access`의 새 섹션에서 대기 중인 신청을 사번, 이름, 팀, 사유, 신청 시각과 함께 보기를 원합니다.
22. 관리자로서, 신청을 승인하면 그 사번이 개인 승인 목록에 들어가고 신청이 목록에서 사라지기를 원합니다.
23. 관리자로서, 신청을 거절하기를 원합니다.
24. 관리자로서, 신청을 보는 사이에 사용자가 다시 신청했다면 옛 신청에 대한 승인이나 거절이 거부되고 새 신청이 보이기를 원합니다.
25. 관리자로서, 같은 팀에서 신청이 여러 건 쌓였을 때 "이 팀 전체 승인" 한 번으로 팀 승인을 추가하고 그 팀의 대기 신청을 정리하기를 원합니다.
26. 관리자로서, 팀 승인은 직접 입력하지 않고 실제 구성원 디렉터리에 있는 팀 이름 목록에서 고르기를 원합니다. 오타 하나로 팀 전체가 막히는 일을 막기 위해서입니다.
27. 관리자로서, 승인된 팀의 현재 인원수를 함께 보기를 원합니다. 0명이 되었다면 조직 개편으로 팀 이름이 바뀌었다는 신호이기 때문입니다.
28. 관리자로서, 승인된 팀 목록과 개인 목록을 보고 각각 회수하기를 원합니다. 개인 승인을 회수해도 팀 승인이 남아 있으면 접근이 유지된다는 사실을 화면에서 알기를 원합니다.
29. 관리자로서, 신청이 없어도 사번을 직접 입력해 개인 승인을 추가하기를 원합니다.
30. 관리자로서, 권한 저장소나 디렉터리가 내려가 있을 때 빈 목록이 아니라 장애 안내를 보기를 원합니다. 빈 목록을 보고 권한이 사라졌다고 판단해 다시 부여하는 일을 막기 위해서입니다.
31. 관리자로서, 누가 언제 어느 장비의 어떤 파일을 받았는지 사용 기록에서 보기를 원합니다.
32. 운영자로서, 업로드와 삭제를 서버 설정으로 켜고 끌 수 있기를 원합니다. 기능은 미리 만들어 두되, 위험해서 아직 열지 않기 위해서입니다.
33. 운영자로서, 쓰기가 꺼져 있으면 업로드·삭제 요청이 FTP에 닿기 전에 거부되기를 원합니다.
34. 쓰기가 켜졌을 때 관리자로서, 현재 폴더에 파일을 드래그해 업로드하기를 원합니다. 같은 이름의 파일이 있으면 기본적으로 거부되기를 원합니다.
35. 쓰기가 켜졌을 때 관리자로서, 업로드가 중간에 끊겨도 반쯤 쓰인 파일이 원래 이름으로 남지 않기를 원합니다.
36. 쓰기가 켜졌을 때 관리자로서, 파일을 삭제하기 전에 파일 이름이 들어간 확인 화면을 보기를 원합니다.
37. 집(Phase 1) 개발자로서, 장비에 닿지 않아도 가짜 디렉터리 트리와 가짜 디렉터리 소속을 이용해 탐색기와 승인 흐름 전체를 개발하고 확인하기를 원합니다.
38. office 담당자로서, 다른 feature처럼 `office_example.py`를 복사하는 것만으로 실제 장비 FTP와 Redis 권한 저장소로 함께 전환하기를 원합니다.
39. `ftp_handler`를 이미 쓰고 있는 다른 서비스(SKEWNONO의 msr_image와 recipe_search, flask_modules의 Airflow DAG, scheduler webapp의 proxy)의 담당자로서, 이번 변경 뒤에도 기존 동작이 바뀌지 않기를 원합니다.
40. 이후 레시피 일괄 복사를 만드는 개발자로서, 권한 판정, 장비 해석, 경로 검증, 안전한 쓰기를 다시 만들지 않고 호출하기를 원합니다.

## Implementation Decisions

### 모듈

- **새 백엔드 feature `tool_files`**를 ebeam 아래에 평평하게 둡니다. 페이지 slug `tool-files`와 같은 이름입니다. 구성은 다른 feature와 같이 `routes.py` / `contracts.py` / `data.py` / `providers/{mock,office_example}.py`입니다. `_logging/feature_map.py`에는 API와 페이지 mapping을 **둘 다** 등록합니다.
- **seam은 둘이지만 provider 선택은 하나입니다.** 파일 시스템(FTP ↔ 가짜 트리)과 권한 저장소(Redis ↔ JSON 파일)를 따로 고르지 않습니다. feature 하나의 provider 해석이 두 seam을 함께 결정하므로, "실제 FTP + mock 승인" 같은 혼합 상태는 만들어질 수 없습니다.
  - office tool_files는 office `sem_list`에 의존합니다. 그래서 `validate_env()`의 부팅 짝 검사에 등록합니다(`storage` ↔ `sem_list`와 같은 방식).
  - 실제 FTP에서 mock 데이터로 fallback하는 동작은 금지합니다.
  - directory(`probe_member`)는 feature 설정이 아니라 전역 `get_mode()`를 따릅니다. 그래서 `SKEWNONO_TOOL_FILES_PROVIDER=office`로 이 feature만 강제하고 전역 mode가 mock이면, 실제 FTP에 붙은 상태에서 팀 판정이 전부 `directory_unavailable`이 됩니다. tool_files가 office로 해석될 때 `get_mode()`가 office가 아니면 `validate_env()`가 부팅을 거부합니다. Redis 설정(`REDIS_HOST` 등)이 없을 때도 마찬가지로 거부합니다.
- **공용 부품 네 가지**는 라우트 밖의 함수로 둡니다. 이후 레시피 일괄 복사 job이 그대로 호출하게 하기 위해서입니다.
  1. 권한 판정
  2. 장비 해석
  3. 경로 검증
  4. 안전한 쓰기와 삭제(`ftp_handler` 쪽)

### 권한 판정

권한 판정은 순수 함수 하나입니다. 입력은 identity 출처, 사번, directory probe 결과, 승인 목록이고, 출력은 닫힌 어휘입니다.

```text
AccessVerdict = "granted" | "pending" | "rejected" | "none"
              | "untrusted_identity" | "directory_unavailable" | "store_unavailable"

1. 출처가 cookie/local이 아니면       → untrusted_identity
2. is_admin(empno)                     → granted
3. 승인 저장소 읽기 실패               → store_unavailable
4. "emp:<empno>" ∈ grants              → granted
5. probe_member(empno)
     unavailable                       → directory_unavailable
     found, dept_nm이 비어 있지 않고 "team:<dept_nm>" ∈ grants → granted
     (absent이거나 dept_nm이 없으면 팀 판정을 건너뜁니다)
6. 신청 상태에 따라                    → pending / rejected / none
```

- **쓰기 판정은 `granted`와 별개입니다.** 서버가 판정해서 `access` 응답의 `can_write`로 내려 줍니다.

  ```text
  can_write = SKEWNONO_TOOL_FILES_WRITE ∧ is_admin_request() ∧ transport_supports_write
  ```

  `transport_supports_write`는 mock과 direct에서 참, proxy에서 거짓입니다. 쓰기 API를 직접 호출하면 다음 순서로 거부합니다. 플래그 off는 403 `write_disabled`, 관리자가 아니면 403 `forbidden`, proxy면 501 `write_not_supported`입니다. 모두 요청 body를 읽기 전, FTP·HTTP 호출 전에 판정합니다. 쓰기 판정을 위해 저장 데이터를 추가하지 않습니다.
- `lookup_member`는 실패를 감추는 설계이므로 판정에 쓰지 않습니다.
- directory 캐시는 600초입니다. 따라서 **팀을 옮긴 사람의 권한은 최대 10분 늦게 반영됩니다.** 이 지연은 감수합니다. 신청 때 저장한 팀 이름은 표시용일 뿐, 현재 소속의 근거로 쓰지 않습니다.
- **Phase 2 예외.** 쿠키가 없는 office localhost는 `local-dev/local`이 되고, 기존 관리자 판정에서 관리자로 처리됩니다. 이는 개발 예외로 받아들입니다. 클라우드의 관리자는 기존 `SKEWNONO_ADMIN_USERS`를 따르며, 기본값은 2067928입니다.
- **신뢰 모델.** 인프라가 제공하는 LASTUSER 쿠키는 기존 사내 신뢰 모델을 따릅니다. 쿠키 위조 방어나 새 인증 체계는 만들지 않습니다.
- **집(mock) directory 대역.** 기존 `probe_member`는 mock 모드에서 항상 `unavailable`을 돌려줍니다. 이것은 의도된 동작이므로 바꾸지 않습니다. 대신 tool_files mock provider가 사번별로 `found` / `absent` / `unavailable`을 돌려주는 전용 대역을 씁니다. 이 대역에는 여러 팀의 구성원과 팀 정보가 없는 부분 프로필이 들어 있습니다.

### 장비 해석

- 입력은 `tool_slug`, `fab`, `eqp_id`입니다. 서버는 sem_list에서 이 eqp_id의 행을 찾고, IP, fab, 모델, 계정을 **같은 행에서** 해석합니다.
- 해석 결과에 따라 다음과 같이 응답합니다.
  - 행이 없으면 404 `tool_not_found`입니다.
  - 같은 eqp_id의 행이 여러 개일 때는 IP, fab, 모델(계정 선택에 쓰는 필드)이 모두 같으면 하나로 합칩니다. 하나라도 다르면 409 `tool_ambiguous`입니다. 첫 행을 임의로 고르지 않습니다. mock에도 이런 중복 eqp_id가 약 10건 있습니다.
  - 행의 모델 계열이 `tool_slug`와 다르거나 fab이 요청과 다르면 400 `tool_mismatch`입니다.
  - IP가 비어 있거나 유효한 IPv4가 아니면 503 `tool_unreachable`입니다.
- 클라이언트가 보낸 host, port, 계정은 받지 않습니다.
- FTP 계정은 msr_image의 설정 로더와 순수 함수 `account_for()`를 **그대로 import해서** 씁니다. 우선순위는 `eqp_id > fab_name > model_to_tool_type(eqp_model_cd) > 기본 계정`입니다. 계열 키는 API slug(`cdsem`)가 아니라 tool type(`cd-sem`)입니다. 설정을 공용 위치로 옮기지 않습니다.

### 경로 검증

- 경로는 **서버가 발급하는 불투명한 키**입니다. 클라이언트는 목록 응답의 `path`, `parent`, breadcrumb 조각을 그대로 돌려줄 뿐, 경로를 조립하거나 디코딩하지 않습니다. 그래야 latin-1 설정에서 깨진 파일명도 바이트 그대로 받을 수 있습니다.
- 목록, 다운로드, 쓰기 요청마다 다음을 검사합니다.
  - 기준 루트는 접속 직후 `PWD`로 받은 로그인 홈입니다. 계열별 허용 루트를 설정했다면 그것을 우선합니다(`OFFICE-VERIFY`).
  - 경로를 `/` 단위 구성요소로 나눈 뒤 루트의 구성요소가 앞부분과 일치하는지 봅니다. 문자열 접두어 비교는 쓰지 않습니다(`/rcp`와 `/rcp2`를 구별하기 위해서입니다).
  - `.`과 `..` 구성요소, 역슬래시, 드라이브 문자(`C:`), NUL·CR·LF·제어 문자는 거부합니다. URL decode는 한 번만 합니다.
  - strip, 재인코딩, Unicode 정규화는 하지 않습니다. 원래 바이트가 바뀌기 때문입니다.
- 위반하면 400 `bad_path`를 돌려줍니다.
- v1에서는 LIST에서 링크(`l`)로 나온 항목을 목록에서 빼고, 링크를 직접 가리키는 다운로드도 거부합니다.
- **실제 보안 경계는 FTP 계정의 권한입니다.** 루트 검사는 실수와 조작된 URL을 막는 가드레일입니다. 이것만으로 "루트 밖 접근 불가"가 보장되지는 않습니다. 경로 중간의 폴더가 링크라면 문자열 검사로는 잡을 수 없고, FTP만으로는 링크가 가리키는 대상을 검증할 수도 없습니다. v1은 읽기 전용이고 사용자는 승인된 사람이므로, 이 한계는 감수합니다.
- **쓰기 플래그를 켜기 전에 확인할 조건이 있습니다.** 장비 FTP 계정이 허용 루트 밖에 쓸 수 없도록 서버 쪽에서 제한(chroot 또는 계정 권한)되어 있는지 office에서 확인해야 합니다(`OFFICE-VERIFY`).

### ftp_handler 수정

`ftp_handler`는 vendored copy입니다. 수정은 `flask_modules`에 먼저 하고 SKEWNONO로 복사합니다. `test_vendored_ftp_handler.py`는 사본의 동작을 테스트할 뿐, 두 사본이 같은지는 비교하지 않습니다. 그래서 머지 전에 `diff -rq --exclude=__pycache__ ~/Codes/flask_modules/ftp_handler ftp_handler`의 출력이 비어 있는지 따로 확인해야 합니다.

**기존 소비자 조사 (2026-10-17, `~/Codes` 전체 grep).**

| 소비자 | 쓰는 API |
|:--|:--|
| SKEWNONO msr_image office adapter | `direct_downloader`/`proxy`의 `FtpFleetDownloader`, `HostSpec`, `ListDir` |
| SKEWNONO recipe_search office adapter | 같음 |
| SKEWNONO scripts(probe, verify, deploy pack) | 같음, `proxy_downloader.PROXY_URL`·`PROXY_TOKEN` |
| flask_modules Airflow `eqp_ftp_collector_dag` | `direct_downloader.build_host_specs`, `collect_fleet` |
| scheduler1 webapp | `proxy.flask_proxy`의 blueprint(기존 5개 라우트) |
| `core.FtpClient`, `FileInfo`, `list_details` | 테스트와 `core/examples.py`(실행 예제) 외에 배포된 소비자는 찾지 못했습니다 |

scheduler1 webapp의 체크아웃은 로컬에 없어서, 그쪽의 blueprint 등록과 설정은 확인하지 못했습니다.

`direct_downloader.fleet_downloader`는 `core.FtpClient`를 쓰지 않습니다. 자체적으로 `ftplib`를 다루고, core와 공유하는 것은 `_normalize_listing` 하나뿐입니다. 따라서 `core.FtpClient`를 바꿔도 위 서비스들의 실행 경로에는 닿지 않습니다.

**호환 규칙 (추가만 하고 바꾸지 않습니다).**

- 기존 함수, 메서드, 라우트의 시그니처, 기본값, 동작, wire 형식은 그대로 둡니다.
- 새 매개변수는 keyword-only이고 기본값은 `None`입니다. `None`이면 지금과 똑같이 동작합니다.
- 기존 매개변수 이름도 유지합니다. 예를 들어 `download`의 첫 인자는 계속 `remote_path`입니다.
- `FileInfo`에 새 필드 `is_link: bool = False`를 맨 끝에 추가합니다. 이것은 **호환 규칙의 명시적 예외**입니다. 기존 6개 인자의 위치 생성과 속성은 그대로이지만, `fields()`, `asdict()`, `repr`의 결과는 달라집니다. 이 결과에 기대는 소비자나 pickle로 저장하는 소비자는 찾지 못했습니다.
- `is_link`는 `raw`의 첫 글자(`l`)로 판별합니다. `_parse_list_line()`의 4-tuple 반환 형식은 바꾸지 않습니다. 기존 테스트(`test_ftp_client.py`)가 이 형식을 검증하고 있기 때문입니다. `list_details`는 지금처럼 링크도 돌려주고, 링크를 거르는 일은 tool_files가 합니다.
- `__enter__`에는 PWD를 추가하지 않습니다. `home()`을 호출할 때 조회합니다. 기존 테스트의 FakeFTP에는 PWD가 없기 때문입니다.
- `_normalize_listing`과 `fleet_downloader`는 건드리지 않습니다.
- `upload`는 그대로 두고, 안전한 쓰기는 새 메서드 `put`으로 추가합니다.
- 새 예외는 새 클래스로 만듭니다. 기존 예외 계층은 바꾸지 않습니다.
- proxy 패키지에 이름을 추가할 때 기존 re-export(`FtpFleetDownloader`, `HostSpec`, `ListDir`, ...)는 바꾸지 않습니다.
- Python 3.11 문법만 씁니다.

**`core.FtpClient`에 추가하는 것.**

- `home()`: PWD 결과입니다.
- `download(remote_path, *, max_bytes=None, deadline=None)`: 수신 callback에서 누적 바이트가 상한을 넘거나 경과 시간이 deadline(남은 초)을 넘으면 그 즉시 중단합니다. 중단하면 부분 버퍼를 버리고 **그 FTP 연결도 폐기**합니다. 예외는 각각 `TransferTooLarge`, `TransferTimeout`입니다. socket timeout만으로는 조금씩 계속 들어오는 전송을 끊을 수 없습니다.
- `list_details(..., max_entries=None, max_raw_bytes=None, deadline=None)`: LIST 수신 callback 안에서 원문 줄 수(파싱에 실패한 줄 포함), 원문 바이트, 경과 시간을 검사합니다. 하나라도 넘으면 `ListingTooLarge` 또는 `TransferTimeout`입니다. 파싱된 항목 수만 세면, 파싱되지 않는 줄이 수만 개 들어올 때 상한을 그대로 빠져나갑니다.
- `put(remote_path, data, *, deadline=None)`: 같은 폴더에 충돌하지 않는 임시 이름(대상 이름 + 무작위 접미사)으로 STOR한 뒤 RNFR/RNTO로 이름을 바꿉니다. 대상이 이미 있으면 거부합니다. 실패하면 **자기가 만든 임시 파일만** best-effort로 지우고, 지우지 못하면 그 경로를 예외에 담습니다. RNTO의 성공 응답만 유실된 경우는 `TransferUncertain`("성공 여부 불명, 새로고침")입니다.
  - **보장 범위.** 존재 확인과 RNTO 사이에는 경쟁 구간이 남습니다. `ftplib`의 rename에는 no-clobber 옵션이 없습니다. 기존 대상이 있을 때 서버가 RNTO를 거절하는지, rename이 원자적인지는 서버마다 다릅니다(`OFFICE-VERIFY`). 따라서 "덮어쓰기 거부"는 동시에 쓰는 다른 writer가 없다는 운영 전제 위의 best-effort입니다. v1 writer는 관리자 한 명뿐입니다. 쓰기 플래그를 켜기 전에 계열별로 이 동작을 확인합니다.
  - v1에는 `overwrite=True`가 없습니다.
- 이 로직을 core에 두는 이유는 FTP 연결이 열린 쪽에서 실행되어야 하기 때문입니다.

**`proxy.FtpClient` 신설 (읽기 전용).**

- `core.FtpClient`와 같은 이름의 읽기 메서드 `home`, `list_details`, `download`를 HTTP로 수행합니다. `put`과 `remove`는 호출하면 `WriteNotSupported`를 냅니다.
- proxy는 개발자 한 명이 Phase 2에서 개발할 때만 씁니다(user-confirmed 2026-10-17). proxy에는 인증이 없으므로 쓰기 라우트를 아예 만들지 않습니다. 플래그로 꺼 두는 것보다 이 편이 단순하고 안전합니다.
- tool_files는 msr_image와 같은 규칙으로 transport를 고릅니다. Windows면 proxy, 그 밖이면 direct입니다.

**proxy 서버에 라우트 두 개를 추가합니다** (`_sknn_v3` 접미사 규칙을 따릅니다). "proxy는 읽기 전용"은 이번에 새로 추가하는 API에만 해당합니다. 기존 `upload_sknn_v3`는 호환성 때문에 그대로 둡니다.

- **HTTP 요청마다 FTP 연결을 새로 엽니다.** `proxy.FtpClient`의 context manager는 원격 연결 하나를 유지한다는 뜻이 아닙니다. 그래서 경로 키는 연결이 달라도 다시 쓸 수 있는 절대 경로 문자열입니다.
- 요청 공통 envelope는 `{host, port, user, password, encoding, ...}`입니다. 기존 `_credentials_to_wire` 형식을 재사용합니다. deadline은 서로 다른 머신의 시각을 비교하지 않도록 **남은 초**(`deadline_s`)로 보냅니다.
- `list_details`: `{remote_dir | null, max_entries, max_raw_bytes, deadline_s}`를 받아 `{home, entries: [{name, path, is_dir, size, modified: ISO | null, is_link, raw}]}`를 돌려줍니다. `remote_dir`가 null이면 PWD만 조회하고 그 목록을 돌려줍니다. 이렇게 하면 `home()`을 위한 세 번째 라우트나 원격 세션 저장소가 필요 없습니다.
- `fetch`: `{remote_path, max_bytes, deadline_s}`를 받아 파일 하나를 `application/octet-stream` 원본 바이트로 돌려줍니다. 기존 download 라우트는 base64 JSON 일괄 방식이라 RAM이 33% 더 듭니다. 상한은 proxy가 FTP에서 받을 때부터 적용하고, 클라이언트도 HTTP 응답을 chunk 단위로 받으면서 같은 상한을 적용합니다. 전체를 버퍼에 받은 뒤 검사하지 않습니다.
- 오류는 `{code, error}` JSON입니다. 코드와 예외의 대응은 다음과 같습니다.
  - `too_large` → `TransferTooLarge`
  - `listing_too_large` → `ListingTooLarge`
  - `timeout` → `TransferTimeout`
  - `unavailable`(FTP 550) → `FileUnavailable`
  - `unreachable`(연결·로그인 실패) → `ToolUnreachable`
  - `bad_request` → `ValueError`

  원격의 401, 404, 5xx 응답이나 JSON이 아닌 응답은 `ProxyError`입니다.
- `proxy.FtpClient`를 import해도 Flask 서버 모듈은 import되지 않습니다. 기존 `PROXY_URL`, `PROXY_TOKEN`과 선택적 Bearer 헤더 동작을 재사용합니다. 기존 테스트 `test_both_transports_expose_an_identical_method_signature`와 같은 방식으로, 두 `FtpClient`의 읽기 메서드 시그니처가 같은지 테스트합니다.
- 기존 5개 라우트(`download`, `list_dirs`, `size_dirs`, `upload`, `healthz`)는 바꾸지 않습니다.

### 상한 (제안값, 모두 `OFFICE-VERIFY`)

| 항목 | 기본값 | env |
|:--|:--|:--|
| 다운로드 최대 크기 | 100 MB | `SKEWNONO_TOOL_FILES_MAX_BYTES` |
| 업로드 최대 크기 | 100 MB | `SKEWNONO_TOOL_FILES_MAX_UPLOAD_BYTES` |
| 전송 deadline (direct) | 120 s | `SKEWNONO_TOOL_FILES_DEADLINE` |
| 전송 deadline (proxy) | 45 s | `SKEWNONO_TOOL_FILES_PROXY_DEADLINE` |
| 목록 최대 원문 줄 수 | 20000 | `SKEWNONO_TOOL_FILES_MAX_ENTRIES` |
| 목록 최대 원문 바이트 | 4 MB | `SKEWNONO_TOOL_FILES_MAX_LIST_BYTES` |

- direct deadline 120 s는 SKEWNONO `wsgi.ini`의 harakiri 720 s보다 짧습니다.
- proxy deadline 45 s는 공유 webapp에서 HTTP 전송 여유를 남기기 위한 값입니다. flask_modules `api/wsgi.ini`의 harakiri가 60 s이기 때문입니다. 다만 scheduler1의 실제 설정은 확인하지 못했습니다(`OFFICE-VERIFY`). 공유 webapp의 harakiri를 올리는 변경은 하지 않습니다.

0, 음수, 숫자가 아닌 값이 들어오면 부팅 로그를 남기고 기본값을 씁니다. LIST에 나온 크기는 화면에 보여 주는 용도입니다. 실제로 강제하는 상한은 수신 중에 검사하는 쪽입니다.

### 저장소 키 (office, Redis)

```text
skewnono:tool_files:grants    HASH  "team:<dept_nm>" | "emp:<empno>" -> {granted_at, granted_by}
skewnono:tool_files:requests  HASH  <empno> -> {request_id, reason, dept_nm, requested_at, status: pending|rejected}
```

- 사번은 대문자로 정규화합니다.
- 신청은 사번당 하나입니다. 다시 신청하면 덮어쓰고, 새 `request_id`(uuid4 hex)를 받아 `pending`으로 돌아갑니다. 이미 `granted`인 사람의 신청은 아무것도 하지 않습니다.
- **변경 토큰은 `request_id`입니다.** `requested_at`은 초 단위라서 같은 초에 재신청하면 값이 겹칩니다. 그래서 표시용으로만 씁니다. 승인과 거절 요청에는 관리자가 보고 있던 신청의 `request_id`를 함께 보냅니다.
- 승인과 거절은 둘 다 같은 순서로 처리합니다. `WATCH requests` → 신청 읽기와 `request_id` 비교 → `MULTI` → 변경 → `EXEC`입니다.
  - `request_id`가 다르거나 신청이 없으면 409 `request_changed`입니다. 다만 승인 재시도에서 신청이 없고 해당 grant가 이미 있으면, 성공으로 보고 아무것도 하지 않습니다(no-op).
  - `WatchError`는 **`STORE_ERRORS`보다 먼저** 잡습니다. `WatchError`가 `RedisError`의 하위형이라 그대로 두면 503으로 잘못 분류되기 때문입니다. 잡은 뒤에는 다시 읽어 판정합니다. 그 사번의 신청이 바뀌었으면 409, 무관한 필드만 바뀌었으면 최대 3회까지 재시도합니다.
  - 팀 전체 승인은 transaction 안에서 읽은 pending 신청 가운데 저장된 `dept_nm`이 같은 것만 지웁니다. 저장된 `dept_nm`은 무엇을 정리할지 정하는 기준일 뿐, 현재 소속이나 권한의 근거가 아닙니다.
- 장애 처리는 다음과 같습니다.
  - 읽기와 쓰기에 실패하면 503 `store_unavailable`입니다.
  - 응답이 끊겨 저장 여부를 알 수 없으면 "결과 확인 불가, 새로고침"으로 안내합니다. "저장되지 않음"이라고 단정하지 않습니다.
  - 라우트가 저장소 예외를 직접 `error_json`으로 바꿉니다. `RuntimeError` 하위형이 전역 처리기로 가면 500이 되기 때문입니다.
- 키가 없거나 hash가 비어 있으면 정상적인 빈 상태입니다.
- **mock(JSON 파일).** access_control에서 가져오는 것은 mtime 갱신과 원자적 파일 교체 두 가지뿐입니다. access_control mock은 읽기 실패를 빈 저장소로 바꾸지만, 그 동작은 **따르지 않습니다**. 파일이 손상되었거나 읽을 수 없으면 503을 돌려주고 쓰기를 거부합니다. 집은 단일 프로세스이므로 다중 writer 잠금은 두지 않습니다.

### API

모든 경로는 `/api` 아래에 있습니다. `<tool_slug>`는 기존 ebeam feature와 같은 방식으로 검증합니다. 모든 응답에 `Cache-Control: no-store`를 붙이고, 요청마다 권한을 다시 판정합니다.

| Method | Path | 권한 | 내용 |
|:--|:--|:--|:--|
| GET | `/<tool_slug>/tool-files/access` | 로그인 | `{verdict, can_write, request?}` |
| GET | `/<tool_slug>/tool-files/list?fab=&eqp_id=&path=` | granted | `{root, path, parent, crumbs, entries: [{name, path, is_dir, size, modified}]}` |
| GET | `/<tool_slug>/tool-files/download?fab=&eqp_id=&path=` | granted | 파일 바이트 |
| POST | `/<tool_slug>/tool-files/upload` | 쓰기 | multipart: `fab`, `eqp_id`, `dir`(폴더 키), `file` 하나 |
| POST | `/<tool_slug>/tool-files/delete` | 쓰기 | `{fab, eqp_id, path}` |
| POST | `/tool-files/requests` | 신뢰 출처 | `{reason}` |
| GET | `/admin/tool-files` | admin | `{grants, requests}` |
| GET | `/admin/tool-files/teams` | admin | `{teams: [{dept_nm, members}], complete}` |
| POST | `/admin/tool-files/grants` | admin | `{kind: "team"\|"emp", value}` |
| POST | `/admin/tool-files/grants/revoke` | admin | `{kind, value}` |
| POST | `/admin/tool-files/requests/approve` | admin | `{empno, request_id}` |
| POST | `/admin/tool-files/requests/reject` | admin | `{empno, request_id}` |
| POST | `/admin/tool-files/teams/approve` | admin | `{dept_nm}` |

- 대상 값은 URL 경로가 아니라 JSON body로 받습니다. 팀 이름에 `/`, `%`, 공백, 한글이 들어갈 수 있기 때문입니다.
- body 검증 규칙입니다.
  - upload 외의 POST body는 JSON object여야 합니다. `kind`는 enum이고, 사번·팀·사유는 타입과 빈 값을 검사합니다. 사유는 200자까지입니다.
  - **신청(`/tool-files/requests`)** 은 `reason`만 받습니다. 본인 사번과 `dept_nm`은 서버의 identity와 directory에서 정합니다. 클라이언트가 보낸 `empno`, `dept_nm`, `status`는 받지 않습니다.
  - **관리자 API**는 대상인 `empno`와 `dept_nm`을 body로 받습니다. 이것이 계약입니다. 다만 `granted_by`는 항상 서버 identity로 채웁니다.
  - **upload**는 multipart입니다. multipart를 파싱하기 전에 `Content-Length`가 업로드 상한보다 크면 413을 돌려줍니다. 쓰기 거부 판정(403·403·501)도 body를 읽기 전에 합니다. 실제로 읽은 바이트 수도 다시 셉니다. 업로드의 최종 파일 이름은 `file`의 파일명에서 basename만 쓰고, 경로 검증 규칙을 똑같이 적용합니다.
  - 사유와 파일명은 HTML로 해석하지 않습니다.
- **다운로드 응답.** 헤더는 `Content-Disposition: attachment`, `application/octet-stream`, `X-Content-Type-Options: nosniff`입니다. 파일 이름 escaping은 msr_image `_content_disposition`의 규칙(`filename` + RFC 6266 `filename*`)을 쓰되, `inline`을 `attachment`로 바꿉니다. 다운로드 키와 표시 이름은 따로 다룹니다.
- **팀 목록.** `members` hash를 HSCAN으로 나눠 읽습니다.
  - HSCAN은 같은 키를 두 번 돌려줄 수 있으므로 empno로 중복을 제거한 뒤 집계합니다.
  - 결과는 관리자 전용으로 600초 캐시합니다(directory 캐시와 같은 값).
  - 디코딩하지 못한 행이 있으면 `complete: false`를 돌려줍니다. 이때 화면은 0명인 팀을 "조직 개편 신호"로 표시하지 않습니다.
  - Redis 장애는 503입니다. 빈 목록이나 0명으로 바꾸지 않습니다.
  - 인원수는 snapshot이 아닙니다.

오류 코드:

| HTTP | code | 상황 |
|:--|:--|:--|
| 400 | `bad_path` / `bad_request` / `tool_mismatch` | 경로 위반, body 검증 실패, 장비·slug·fab 불일치 |
| 403 | `forbidden` / `untrusted_identity` / `write_disabled` | 권한 없음, 신뢰할 수 없는 출처, 쓰기 꺼짐(또는 관리자 아님) |
| 404 | `tool_not_found` / `file_unavailable` | 장비 없음, 파일이 없거나 접근할 수 없음 |
| 409 | `tool_ambiguous` / `request_changed` / `file_exists` | 중복 eqp_id 충돌, 신청 변경, 같은 이름 파일 있음 |
| 413 | `too_large` / `listing_too_large` | 상한 초과 |
| 501 | `write_not_supported` | Phase 2(proxy)에서 쓰기 시도 |
| 503 | `tool_unreachable` / `tool_timeout` / `transfer_uncertain` / `directory_unavailable` / `store_unavailable` | 장비 연결·로그인 실패, deadline 초과, 쓰기 성공 여부 불명, 디렉터리·저장소 장애 |

FTP 550은 파일이 없을 때도, 권한이 거부될 때도 나옵니다. LIST 파서가 모르는 형식의 줄은 버리므로, 목록에 없다고 해서 부재를 확정할 수도 없습니다. 그래서 둘을 구별하지 않고 `file_unavailable` 하나로 응답합니다.

### 감사 기록

- 새 로그 필드나 인덱스 변경은 만들지 않습니다(핵심 기능 외 인덱스 변경 금지 규칙). eqp_id, fab, 경로는 query string으로 기존 activity 로그에 남습니다.
- **한계를 명시합니다.** 기존 로그는 best-effort라서 큐가 차거나 저장에 실패하면 유실될 수 있습니다. query는 2048자에서 잘립니다. HTTP 200은 "서버가 보냈다"는 뜻이지 "사용자 PC에 저장되었다"는 뜻이 아닙니다. 누락 없는 감사가 필요해지면 별도 기록 저장소를 설계합니다.
- 업로드와 삭제는 경로가 POST body에 있어 query 로그에 남지 않습니다. 그래서 라우트가 `logger.info`로 직접 기록합니다. 승인, 거절, 회수도 같은 방식으로 기록합니다.
  - 메시지에 담는 항목은 수행자, identity 출처, 작업, 대상(eqp_id, fab, 경로 또는 empno·팀), 결과(성공·실패 코드), request_id입니다.
  - 기존 OpenSearch handler가 message를 저장하므로 인덱스는 바꾸지 않아도 됩니다.

### 프론트엔드

- 페이지 하나와 하위 컴포넌트 몇 개로 구성합니다.
  - 화면 요소는 breadcrumb, 장비 선택기, 파일 이름 필터, 정렬 가능한 파일 표, 파일별 다운로드 버튼입니다.
  - 왼쪽 폴더 트리는 v1에 넣지 않습니다.
- 경로 키는 `?path=`로 URL에 둡니다.
- `access` 응답에 따라 다음 중 하나를 그립니다.
  - 탐색기
  - 신청 카드
  - 대기·거절 안내
  - 신뢰 출처 안내
  - 장애 안내
- 다운로드는 먼저 `fetch`로 상태를 확인합니다. 오류 JSON이 파일로 저장되지 않게 하기 위해서입니다. 상한을 넘는 파일은 목록 단계에서 버튼을 비활성화하고 이유를 보여 줍니다.
- 업로드 드롭존과 삭제 버튼은 `can_write`가 참일 때만 그립니다.
- 삭제 확인 화면에는 파일 이름을 표시합니다.
- `file_exists`가 오면 "같은 이름의 파일이 있어 올리지 않았습니다"라고 안내합니다. 덮어쓰기는 v1에 없습니다.
- `transfer_uncertain`이 오면 새로고침해서 실제 결과를 확인하라고 안내합니다.
- 수정 시각은 서버 현지 시각(KST로 가정)이며 LIST에서 추정한 값입니다. 연도와 초는 정확하지 않을 수 있습니다. 시각이 없는 항목은 정렬하면 맨 뒤로 갑니다.
- `/admin/access`에 섹션을 하나 추가합니다. 대기 신청, 팀 승인(인원수 포함), 개인 승인의 세 칸입니다.
- 스토리지 표와 장비 리스트 표의 행에 "파일 열기" 액션을 추가합니다.
- 스타일은 `DESIGN.md`의 `--sk-*` 토큰만 씁니다.

### 집 (Phase 1) mock

- 계열별로 그럴듯한 가짜 트리를 만듭니다. 폴더 이름과 깊이는 `OFFICE-VERIFY`입니다.
- mock이 실제보다 깔끔하면 office 버그를 숨깁니다. 그래서 알려진 성질을 일부러 따라 합니다.
  - 깨진 바이트 파일명
  - 빈 폴더
  - 파일이 수천 개인 폴더
  - 상한을 넘는 큰 파일
  - 링크 항목
  - 로그인 홈이 `/`가 아닌 계정
  - 항상 연결에 실패하는 eqp_id 하나
- mock은 네트워크를 호출하지 않습니다.

## Testing Decisions

- 좋은 테스트는 사용자가 쓰는 길로 부르고, 결과를 리터럴 기대값과 비교합니다. 내부 호출 순서는 확인하지 않습니다.
- **주 seam은 Flask test client로 부르는 HTTP 라우트입니다.** mock 위에서 다음을 확인합니다.
  - 판정 표 전체: admin, 사번 승인, 팀 승인, absent, 팀 없음, 대기, 거절, `declared`/`token`/anonymous 출처, directory unavailable, 저장소 손상.
  - 거부된 요청에서는 FTP 대역이 호출되지 않아야 합니다. 승인 후 회수했다면 직접 URL로 접근해도 거부되어야 합니다. 개인 승인을 회수해도 팀 승인이 있으면 접근이 유지되어야 합니다.
  - 신청 → 승인 → 접근 흐름과 신청 → 거절 → 재신청 흐름을 확인합니다. 승인하는 사이에 재신청이 들어오면 409가 나와야 하고, 팀 전체 승인은 그 팀의 대기 신청을 정리해야 합니다.
  - 목록, 다운로드 바이트 일치, 깨진 파일명 왕복, 413, `bad_path` 각 규칙, 링크 거부, 404, 503을 확인합니다.
  - 쓰기 플래그가 꺼져 있으면 업로드·삭제가 403이고 트리가 바뀌지 않아야 합니다. 플래그가 켜져 있어도 관리자가 아니면 403입니다. mock과 direct에서는 관리자가 업로드한 파일이 목록에 나타나고, 같은 이름이면 409이며, 삭제하면 사라져야 합니다. proxy transport에서는 501이고 `can_write`가 거짓이어야 합니다. 거부되는 모든 경우에 body를 읽지 않아야 합니다. **꺼 둔 코드가 썩지 않도록 켜진 경로를 반드시 실행합니다.**
  - 업로드 `Content-Length`가 상한을 넘으면 multipart를 파싱하기 전에 413이어야 합니다.
- **ftp_handler 테스트** (`flask_modules`에서 작성하고 복사합니다). 실제 transport를 통과하는 fake FTP 서버를 띄워 다음을 확인합니다.
  - 로그인 홈이 `/`가 아닌 경우, latin-1 원시 바이트 왕복, Unix·DOS·미지원 형식의 LIST 줄, 링크 항목.
  - 상한과 정확히 같은 크기, 1바이트 초과, LIST에 표시된 크기보다 실제로 더 큰 파일, 조금씩 계속 오는 전송의 deadline.
  - 중간 단절, 연결·로그인 실패 시 자원 정리.
  - `put`: 덮어쓰기 거부, RNTO 거절, rename 실패 시 자기 임시 파일만 정리, RNTO 응답 유실 시 `TransferUncertain`.
  - LIST에서 파싱되지 않는 줄만 대량으로 오는 경우 원문 상한에 걸리는지.
  - 기존 테스트의 FakeFTP(PWD 없음)로 기존 메서드가 그대로 동작하는지.
  - proxy 쌍은 Flask test client로 서버 라우트를 띄우고, `proxy.FtpClient`가 direct와 같은 결과와 예외를 내는지 확인합니다. `put`/`remove`가 `WriteNotSupported`를 내는지도 확인합니다.
- **기존 소비자 회귀 확인.** 머지 전에 다음이 모두 통과해야 합니다.
  - `flask_modules`의 기존 ftp 테스트 전부: `test_ftp_client`, `test_ftp_fleet_downloader`, `test_ftp_flask_proxy`, `test_ftp_encoding`, `test_ftp_fleet_jobs`.
  - SKEWNONO의 `test_vendored_ftp_handler`, msr_image·recipe_search·scripts 테스트, 그리고 전체 suite.
  - 두 사본의 `diff -rq --exclude=__pycache__` 결과가 비어 있는지. 테스트 통과와 사본 일치는 별개의 확인입니다.
  - 기존 테스트 파일은 수정하지 않습니다. 기존 테스트를 고쳐야만 통과한다면 호환 규칙을 어긴 것입니다.
  - 기존 공개 이름의 목록(`core`, `direct_downloader`, `proxy`의 `__all__`)이 줄어들지 않았는지 확인합니다.
- **provider 계약 테스트.** 선례는 `access_control/tests/`입니다. office template은 `test_office_template.py`처럼 직접 import하고, bytes를 돌려주는 FakeRedis를 주입합니다. HTTP dispatcher로 template을 돌려야 할 때만 `office_example`을 `sys.modules`에 alias합니다. FakeRedis로는 `WATCH`/`MULTI`의 의미를 입증할 수 없습니다. 그래서 집에서는 다음 두 가지를 확인합니다. 하나는 fake가 `WatchError`를 던지게 해서 재시도와 409 분기를 보는 것이고, 다른 하나는 HTTP 테스트의 상태 전이입니다. 실제 의미는 office 확인 항목에 넣습니다.
- **부팅 테스트.** 다음 경우에 부팅이 거부되어야 합니다.
  - office를 강제했는데 복사본이 없을 때
  - sem_list와 짝이 맞지 않을 때
  - tool_files만 office이고 전역 mode가 mock일 때
- msr_image의 설정·계정 테스트를 함께 실행합니다(`account_for()` 재사용 확인).
- 프론트엔드는 `node --test`로 순수 함수만 테스트합니다. 정렬(시각 null 포함), 크기 표시, `access` 응답에서 화면을 고르는 함수가 대상입니다.
- 브라우저 확인은 `browser-verify` 스킬로 합니다.
- **office에서 확인할 것** (집에서는 할 수 없습니다). Phase 3 direct와 Phase 2 proxy 각각에서 실제 장비를 대상으로 읽기 전용으로 확인합니다. 항목은 LIST 형식, 숨김 파일, 인코딩, 다운로드, deadline, 파일명 저장입니다. Python 3.11에서 실행합니다. 확인이 끝난 뒤에는 기존 msr_image 이미지 조회와 recipe_search 원본 조회가 Phase 2 proxy에서 여전히 동작하는지도 봅니다.
  - 실제 Redis에 연결 두 개를 열고 경쟁 상황을 재현합니다. 대상은 승인 ↔ 재신청, 거절 ↔ 재신청, 팀 승인 ↔ 개인 승인·재신청입니다. 집에서 반드시 돌릴 필요는 없습니다.
  - **쓰기 플래그를 켜기 전**에는 계열별로 다음을 확인합니다. 기존 대상이 있을 때 RNTO가 거절되는지, 서버 쪽 쓰기 범위 제한(chroot 또는 계정 권한)이 있는지입니다.

## Out of Scope

- **여러 장비에 걸친 레시피 복사와 디스크 일괄 정리.** 별도 세션에서 설계합니다. 출발점은 `.scratch/recipe-bulk-copy/handoff.md`입니다.
- proxy를 통한 쓰기(`put`, `remove` 라우트)와 proxy 인증(`FTP_PROXY_TOKEN`) 도입.
- 여러 파일 동시 다운로드, zip 묶음, 폴더 업로드·다운로드, 브라우저 스트리밍.
- 쓰기 권한 등급(관리자 외 쓰기), fab·장비 단위 권한, 권한 만료. 이 데이터 모델은 레시피 일괄 복사를 설계할 때 정합니다.
- 덮어쓰기 업로드(`overwrite=True`)와 덮어쓰기 확인 UI.
- 장비당 동시 FTP 연결 수 제한(여러 worker 공통). 장비 부하 문제가 보이면 추가합니다.
- 파서가 모르는 LIST 줄을 화면에 경고하는 기능.
- 쿠키 위조 방어와 새 인증 체계.
- 승인·거절 알림, 파일 미리보기, 사내 DB 장비 담당자 필드를 이용한 자동 권한 부여.

## Further Notes

- user-confirmed 2026-10-17:
  - 승인 키는 `dept_nm`입니다.
  - 승인자는 앱 관리자입니다.
  - 주 용도는 PC로 가져오기입니다.
  - 업로드·삭제는 구현하되 꺼 둔 채로 출고합니다.
  - Phase 2는 proxy로 지원합니다.
  - proxy는 개발자 한 명만 개발용으로 씁니다.
  - `ftp_handler`는 여러 서비스가 쓰므로 기존 기능에 영향이 없어야 합니다.
- proxy 호스트는 `skewnono-scheduler1-webapp`입니다. office 반영 순서는 다음과 같습니다.
  1. `flask_modules`에 push합니다.
  2. scheduler1 webapp에서 pull하고 재시작합니다.
  3. SKEWNONO에서 `git pull`합니다.
  4. `tool_files`의 `office_example.py`를 복사합니다.
- `/api/*` rate limit(50 req / 5 s)은 탐색과 파일별 다운로드에는 문제가 되지 않습니다. 화면은 429를 "잠시 후 다시"로 따로 표시합니다.

## 검토 반영 기록 (codex-r1)

| 항목 | 처리 | 비고 |
|:--|:--|:--|
| R1 | 반영 | 사내 신뢰 모델로 표현 정리 |
| R2 | 반영 | Phase 2 local-dev 관리자는 개발 예외 |
| R3 | 반영 | tool_files mock 전용 directory 대역 |
| R4 | 반영 | proxy에 읽기 라우트 두 개 추가(사용자 결정). 쓰기는 proxy에서 미지원 |
| R5 | 반영 | PWD 기준 루트 |
| R6 | 반영 | `account_for()` 재사용, tool type 키 |
| R7 | 반영 | 라우트에서 직접 변환, 오류 코드 표 |
| R8 | 반영 | mock 손상도 503 |
| R9 | 반영 | 구성요소 단위 루트 검사, 링크 제외 |
| R10 | 반영 | 수신 중 상한, proxy 양쪽 |
| R11 | 일부 | deadline과 항목 수 상한만. 장비당 동시성은 Out of Scope |
| R12 | 반영 | 단일 행 해석, 중복 409 |
| R13 | 반영 | 하나의 provider 선택, 부팅 짝 검사 |
| R14 | 반영 | absent·팀 없음 처리, 600초 지연 명시 |
| R15 | 반영 | 신뢰 출처만 신청 가능, body 검증 |
| R16 | 일부 | `requested_at` 대조 + `MULTI`. 승인자가 한 명이므로 revision 체계는 두지 않음 |
| R17 | 일부 | 새 필드 없이 한계 명시, 쓰기·승인은 `logger.info` |
| R18 | 반영 | HSCAN, `complete`, 대상은 body로 |
| R19 | 일부 | 시각 정밀도 명시. 미지원 줄 경고는 Out of Scope |
| R20 | 반영 | 다운로드 헤더, fetch로 상태 확인 |
| R21 | 반영 | 선례 설명 정정, fake FTP 테스트와 기존 소비자 회귀 확인 추가 |
| R22 | 기각 | 사용자 결정으로 구현 후 off 유지. 쓰기는 관리자 한정, 덮어쓰기 거부, 임시 이름 후 rename, proxy 쓰기 없음 |
| R23 | 반영 | 설정 이동 없음 |
| R24 | 반영 | 여러 파일 다운로드 삭제 |

## 검토 반영 기록 (codex-r2)

| 항목 | 처리 | 비고 |
|:--|:--|:--|
| N1 중간 경로 링크 | 반영 | 실제 경계는 FTP 계정 권한이라고 명시. 루트 검사는 가드레일. 쓰기를 켜기 전에 서버 측 제한 확인 |
| N2 소비자·호환 범위 | 반영 | `examples.py` 명시, 원격 미검증, 사본 diff를 별도로 확인, `FileInfo`는 명시적 예외, `remote_path` 유지, 파서 반환은 그대로, PWD는 지연 조회 |
| N3 LIST·deadline | 반영 | 수신 중 원문 줄·바이트·시간 검사, proxy deadline 45 s, 중단 시 연결 폐기 |
| N4 proxy wire | 반영 | 요청마다 새 연결, envelope, `remote_dir=null`로 home 조회, 남은 초 deadline, 오류 코드 대응표 |
| N5 `can_write`와 501 | 반영 | transport 조건 추가, 403→403→501 순서, body를 읽기 전 거부 |
| N6 RNTO 덮어쓰기 | 반영 | best-effort와 단일 writer 전제 명시, `TransferUncertain`, 자기 임시 파일만 정리, 켜기 전 계열별 확인 |
| N7 경쟁·재시도 | 반영 | `request_id` 토큰, 승인·거절 모두 WATCH, `WatchError`를 먼저 구별, 승인 재시도는 no-op, 실제 Redis 경쟁은 office에서 확인 |
| N8 업로드 body | 반영 | multipart 계약, 파싱 전 413, 신청과 관리자 입력 규칙 분리 |
| N9 404 확증 | 반영(단순화) | 부재와 거부를 `file_unavailable` 하나로 통합. 완전성 정보는 만들지 않음 |
| R12 중복 행 | 반영 | IP·fab·모델이 모두 같을 때만 합치고, 나머지는 409 |
| R13 directory mode | 반영 | tool_files가 office로 해석되는데 전역 mode가 office가 아니면 부팅 거부 |
| R16·R18·R17 | 반영 | N7, HSCAN 중복 제거와 TTL, 로그 메시지 항목 |
| 과잉 범위: `level` 필드 | 반영 | 스펙에서 삭제하고 레시피 복사 설계로 넘김 |
| 과잉 범위: `overwrite=True` | 반영 | v1에서 제외 |
