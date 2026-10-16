# tool-files 명세 검토 r1

판정: 현재 `ready-for-agent` 상태로 구현을 시작하기에는 보안 경계와 배포 계약이 부족합니다. 특히 FTP 루트 이탈, 실제 수신량 제한, Windows 사무실 접속 경로를 먼저 명세에 반영해야 합니다. v1은 목록과 단일 파일 다운로드, 팀·개인 승인에 한정하는 것이 적절합니다.

검토 기준은 현재 체크아웃의 `CLAUDE.md`, `.scratch/tool-files/spec.md`와 아래에 인용한 실제 코드입니다. 심각도는 `high`가 무단 접근·장비 영향·자원 고갈·필수 배포 불능, `med`가 잘못된 판정·장애 오표시·계약 및 검증 공백, `low`가 v1에서 줄일 수 있는 편의 기능입니다. 아직 구현되지 않은 기능의 결함을 확정한 것이 아니라, 명세대로 구현할 때 발생하는 구체적인 문제를 지적합니다. 사용자 확인에 따라 회사 내부의 신뢰된 사용자만 사용하고 LASTUSER를 의도적으로 악용하지 않는다는 운영 전제를 적용합니다. 쿠키 위조 방어 및 신규 인증 인프라는 v1 필수 범위로 요구하지 않습니다.

## 1. 코드와 다르거나 명세 안에서 모순되는 내용

### R1. [low] LASTUSER의 신뢰 근거는 사내 운영 전제로 적습니다

- 문제: 명세 53행의 "쿠키나 사번 입력만으로 열리면 안 된다"는 표현은 현재 쿠키 처리와 문자 그대로 일치하지 않습니다. 다만 사용자가 LASTUSER를 악용하지 않는 사내 서비스임을 확인했으므로 이를 출시 차단 보안 결함으로 분류하지 않습니다.
- 근거: `backend/_auth/provider.py:53~68`은 쿠키 문자열을 읽고, `backend/_auth/middleware.py:131~133`은 `SOURCE_COOKIE`로 분류합니다. `backend/_auth/admin.py:65~85`는 출처와 allowlist를 검사합니다. 쿠키를 암호학적으로 검증하는 방식은 아닙니다.
- 명세 변경: "회사 내부의 신뢰된 사용자와 인프라가 제공하는 LASTUSER를 신뢰한다. 자기 신고 화면의 declared 및 token 출처는 tool-files 권한으로 인정하지 않는다"로 표현을 정리합니다. 새 인증 게이트웨이·서버 세션 도입이나 쿠키 위조 차단 테스트를 v1 선행 조건으로 추가하지 않습니다.

### R2. [med] office localhost의 기본 관리자와 승인자 한 명이라는 설명이 다릅니다

- 문제: 명세 14, 69, 81~85, 169행의 "승인자 2067928 한 명", "복사만으로 office 전환"을 함께 만족하지 못합니다. Phase 2에서 쿠키 없이 접근하면 `local-dev/local`이고, 기존 관리자 판정으로 바로 granted입니다. 이는 악용과 별개로 정상 개발·검증 중 실제 사용자 확인 없이 관리자 화면과 FTP가 열리는 동작입니다.
- 근거: `backend/__init__.py:247~248`은 데이터 provider가 아니라 `is_cloud()`로 identity provider를 고릅니다. `backend/_auth/provider.py:77~93`, `backend/_auth/admin.py:24~39`에 비클라우드 기본 identity와 관리자 목록이 있습니다.
- 명세 변경: cloud에서는 기존 `require_admin`과 `SKEWNONO_ADMIN_USERS`를 따르며 2067928은 기본값이라고 적습니다. Phase 2의 local-dev 관리자도 허용하는 개발 예외라면 이를 명시합니다. Phase 2에서도 승인자 한 명을 엄격히 유지하려면 tool-files office 경계에서 local 출처를 거부하고 Phase 2 관리자 allowlist를 설정합니다. 사내 사용 전제를 이유 없이 새 인증 시스템으로 확대하지 않습니다.

### R3. [med] 집에서는 기존 probe로 팀 승인 성공을 재현할 수 없습니다

- 문제: 명세 85, 140~153행대로 가짜 FTP·권한 저장소만 만들면, 개인 승인 없는 팀원은 집에서 항상 `directory_unavailable`입니다. 팀 선택기에 쓰는 가짜 행과 권한 판정이 서로 다른 소속을 보게 됩니다.
- 근거: `backend/_auth/directory.py:158~171`은 mock 모드에서 `Probe(None, "unavailable")`을 반환합니다. `:246~253`의 `lookup_member()`만 가짜 팀을 반환합니다. 이 둘의 차이는 의도된 동작입니다.
- 명세 변경: 기존 probe의 의미를 바꾸지 않습니다. tool-files의 mock 입력에 `found/absent/unavailable`과 여러 팀·부분 프로필을 제공하는 명시적인 directory 대역을 둡니다. HTTP 테스트뿐 아니라 실제 집 화면에서도 팀 승인 성공·실패·장애를 재현하게 하고, office 입력만 기존 `probe_member()`를 사용하도록 적습니다.

### R4. [high] FtpClient 직접 접속만으로 Phase 2를 지원할 수 없습니다

- 문제: 명세 68~69, 88행은 같은 기능을 집·office에서 전환한다고 하지만, Windows 사무실 PC는 장비 FTP에 직접 연결하지 못하는 환경입니다. `FtpClient`를 열면 방화벽에서 막힙니다.
- 근거: `backend/msr_image/providers/office_example.py:9~30`은 이 제약 때문에 Windows에서는 HTTP proxy, Linux에서는 direct downloader를 선택합니다. `ftp_handler/core/client.py:184~190`은 직접 FTP 연결만 합니다. `ftp_handler/proxy/proxy_downloader.py:289~328`의 기존 목록·크기 API는 `FtpClient.list_details()`와 같은 반환 계약이 아닙니다.
- 명세 변경: v1의 Phase 2 지원 여부를 분명히 적습니다. 전체 단계 지원을 유지한다면 상세 LIST, 경로 바이트 왕복, 실제 전송량 상한을 proxy에서도 보장하는 최소 transport 계약과 프록시 호스트 배포를 포함해야 합니다. 단순 import 교체로 해결된다고 쓰지 않습니다. 이를 v1에서 빼려면 "Phase 2 실제 FTP 미지원, mock 개발 및 Phase 3 direct만 지원"으로 범위와 사용자 스토리를 함께 수정해야 합니다.

### R5. [med] 로그인 홈은 현재 클라이언트의 경로 기준점이 아닙니다

- 문제: 명세 90행의 기본값 "FTP 로그인 홈"을 그대로 구현할 수 없습니다. `list_details("")`로 홈을 나열해도 반환 경로는 `/x.txt`가 되어 다음 요청은 서버 루트를 기준으로 파일을 찾습니다. 홈이 `/home/ftpuser`이면 다른 파일을 받거나 550이 날 수 있습니다.
- 근거: `ftp_handler/core/client.py:184~190`에는 PWD 조회·홈 고정이 없습니다. `:252~267`은 `remote_dir.rstrip('/') + '/' + name`으로 경로를 만듭니다.
- 명세 변경: 초기 경로와 서버 기준 루트의 표현을 확정합니다. 로그인 직후 확인한 홈 또는 검증된 설정 루트를 기준점으로 삼고, UI 루트·breadcrumb·FTP 명령의 경로 변환을 한 곳에서 정의합니다. 홈이 `/`이 아닌 FTP 대역을 필수 검증 사례로 추가합니다.

### R6. [med] 계정 우선순위는 대체로 맞지만 계열 키와 재사용 대상이 불명확합니다

- 문제: 명세 87행의 "계열 slug"를 API의 `cdsem/hvsem`으로 구현하면 기존 계정 설정과 달라집니다. 계정 파서만 옮겨도 실제 계정 선택 규칙은 공용화되지 않습니다.
- 근거: `backend/msr_image/config.py:12~38`은 파싱만 합니다. 실제 우선순위는 `backend/msr_image/ftp_accounts.py:44~76`의 `account_for()`입니다. 계열 키는 `model_to_tool_type()` 결과인 `cd-sem/hv-sem/veritysem/provision`입니다. `backend/ebeam/_tool_specs.py:83~88`은 API slug와 tool type을 구별합니다.
- 명세 변경: 우선순위를 `eqp_id > fab_name > model_to_tool_type(eqp_model_cd) > 기본 계정`으로 정확히 씁니다. 이미 해석한 sem_list 행에 기존 순수 `account_for()` 규칙을 재사용하고, 선택한 기본 계정도 명시적으로 FtpClient에 전달합니다. 공용화 시 msr_image의 설정·계정 테스트와 기존 import 호환 여부를 검증 범위에 넣습니다. 파서만을 위한 대규모 설정 이동은 R23처럼 줄입니다.

### R7. [med] SourceUnavailable은 앱 전역의 자동 503 계약이 아닙니다

- 문제: 명세 126~128행의 오류 코드를 기존 예외를 던지는 것만으로 얻을 수 없습니다. "502는 인프라 몫"도 현재 코드와 다릅니다.
- 근거: `backend/msr_image/errors.py:8~10,28~30`의 `SourceUnavailable`은 `MsrImageError`이며 code는 `office_source_unavailable`입니다. `backend/msr_image/routes.py:36~37,120~126`이 직접 변환합니다. `backend/__init__.py:139~151`은 정확히 기본형인 `LookupError`를 502, `RuntimeError`를 503으로 바꿉니다. 임의 하위 클래스는 500입니다.
- 명세 변경: tool-files 라우트에서 기능 예외를 `error_json()`의 `{code,error}` 응답으로 변환한다고 명시합니다. 연결·로그인 실패, 권한 부족, 사라진 파일, 잘못된 입력, 설정 오류, directory·grant store 장애를 구분합니다. 삭제·이동된 파일은 404 `file_not_found`, 경로 거부는 명시한 400/403, 접속 실패는 503로 계약을 정합니다. FTP 550은 파일 부재와 권한 거부 모두 가능하므로 숫자만 보고 전부 404로 단정하지 않습니다. "502는 인프라 몫" 문장은 삭제합니다.

### R8. [med] access_control mock의 장애 동작을 복사하면 요구사항에 어긋납니다

- 문제: 명세 105행은 모든 저장소 읽기 실패를 503으로 정하지만, 143행의 "access_control처럼"을 그대로 복사하면 손상된 JSON은 빈 목록·권한 없음으로 바뀝니다.
- 근거: `backend/access_control/providers/mock.py:118~125,151~166`은 읽기 실패를 빈 저장소로 바꿉니다. `backend/access_control/MIGRATION.md:73~98`은 office와 mock의 이 차이를 명시합니다. `StoreUnavailableError`는 `RuntimeError` 하위형이므로 라우트에서 잡지 않으면 전역 처리상 500입니다.
- 명세 변경: 재사용할 것은 mtime 갱신과 원자적 파일 교체 방식뿐이라고 한정합니다. 새 권한 저장소는 양쪽 provider 모두 손상·읽기 불가를 `503 store_unavailable`로 반환하고 쓰기를 거부합니다. 최초 파일 없음·빈 Redis hash는 정상적인 빈 상태로 별도 정의합니다. `AccessVerdict`에도 `store_unavailable`을 넣거나 HTTP 503 오류 계약으로 분리합니다.

## 2. 반드시 추가하거나 명확히 해야 하는 요구사항

### R9. [high] 경로 문자열 왕복은 접근 권한 증명이 아닙니다

- 문제: 명세 89~90, 113~117행에서 공격자는 목록을 거치지 않고 `path=/etc/...`, `C:\\...` 또는 허용 루트와 접두어가 같은 이웃 경로를 직접 보낼 수 있습니다. `..` 검사만으로는 로그인 홈·설정 루트 안이라는 것을 보장하지 못합니다. LIST에서 발견한 심볼릭 링크도 루트 밖 파일로 이어질 수 있습니다.
- 근거: `ftp_handler/core/client.py:118~125`는 링크를 일반 파일처럼 반환하고 대상을 버립니다. `:267~275,280~292`는 전달받은 경로를 명령에 사용하며 루트 검사가 없습니다. 기존 이미지 경계는 `backend/msr_image/paths.py:11~29`에서 구분자·제어문자까지 검사합니다.
- 명세 변경: 모든 목록·다운로드 요청에서 서버 기준 루트와 경로 구성요소를 검증합니다. 절대 경로·역슬래시·드라이브·NUL/CR/LF·제어문자 처리, 이중 URL decode 금지, 접두어가 아닌 경계 단위 포함 검사 규칙을 정합니다. 파일명을 strip·재인코딩·Unicode 정규화해 원래 바이트를 바꾸지 않습니다. 링크는 v1에서 제외하고 디렉터리 링크도 허용하지 않는 정책을 둡니다. FTP만으로 실제 링크 해석을 검증할 수 없는 서버는 서버 측 chroot/접근 제한을 office 개방 조건으로 둡니다. 초기 루트·부모 이동에는 서버가 반환한 별도 키를 제공하여 "클라이언트는 경로를 조립하지 않는다"와 breadcrumb 요구를 함께 만족시킵니다.

### R10. [high] 실제 받은 바이트 수에 상한이 있어야 합니다

- 문제: 명세 91행의 목록 크기와 다운로드 직전 크기 검사는 충분하지 않습니다. 1 MB로 나열된 로그가 RETR 중 계속 커지거나 서버가 틀린 크기를 보고하면 `download()`는 끝까지 메모리에 쌓습니다. 다운로드가 끝난 뒤 `len(data)`를 검사하면 이미 메모리를 사용한 뒤입니다.
- 근거: `ftp_handler/core/client.py:280~284`는 제한 없는 `BytesIO.write`를 callback으로 씁니다. 요청당 연결과 timeout 설정인 `:162~190`에도 총 바이트 제한은 없습니다.
- 명세 변경: LIST 크기는 UI 안내용이라고 씁니다. 실제 수신 callback에서 누적 바이트가 상한을 넘는 즉시 연결·전송을 중단하고 부분 버퍼를 폐기하여 413을 반환해야 합니다. transport가 이 기능을 제공하지 않으면 해당 API 보완이 선행 조건입니다. 브라우저 스트리밍을 v1에서 제외해도 내부 chunk 수신 제한은 필요합니다. 정확한 상한 단위와 env 이름, 0·음수·잘못된 설정 처리도 정합니다. proxy를 지원하면 프록시 측 FTP 수신부터 제한하고 HTTP 응답 수신도 제한해야 합니다.

### R11. [high] 요청 횟수 제한은 장비 연결·메모리·총 처리시간 제한이 아닙니다

- 문제: 명세 마지막 행처럼 429가 나중 문제라고 두면 여러 탭·사용자의 병렬 요청으로 한 장비에 세션이 몰리고 앱 처리 슬롯이 묶입니다. socket timeout은 조금씩 계속 데이터를 보내는 전송의 전체 시간을 제한하지 않습니다. 수천 파일 목록도 전체 수집 후 파싱하므로 크기가 제한되지 않습니다.
- 근거: `backend/__init__.py:22~57,93~106`의 limiter는 사용자별 요청 수이며 Redis 장애 때 프로세스별 fallback입니다. `ftp_handler/core/client.py:169,185~188,251~255,282~284`는 socket timeout과 전체 버퍼만 있습니다. `wsgi.ini:11~15,56~68`은 4 workers × 4 threads 및 긴 harakiri를 기록합니다.
- 명세 변경: 전송 전체 deadline, 장비당 동시 FTP 연결 수, 인스턴스 전체 전송 수, LIST 원문 바이트·항목 수 상한과 초과 응답을 정합니다. 장비당 제한은 다중 worker에 걸쳐 적용되어야 하며 프로세스 안의 lock만으로 보장한다고 쓰지 않습니다. 구체적인 안전 수치는 office 확인 전 보수적인 제안값으로 표시합니다. 기본 API limiter는 유지하고 429·busy·시간 초과를 화면에서 구분합니다. 느린 다운로드에는 취소·중단 정책도 정의합니다.

### R12. [high] 장비 선택을 검증된 단일 행에 결합해야 합니다

- 문제: 명세 87, 109행의 "eqp_id로 찾고 slug 검증"만으로는 다른 계열 eqp_id, 빈 IP, 중복 eqp_id의 서로 다른 IP, 클라이언트가 보낸 임의 IP를 처리하는 규칙이 없습니다. 조회 결과와 계정 조회가 서로 다른 roster를 쓰면 잘못된 대상에 자격 증명을 보낼 수도 있습니다.
- 근거: `backend/sem_list/roster.py:14~21,47~59`는 모델 분류와 실제 mock 중복을 설명합니다. `backend/sem_list/providers/office_example.py:116~129`는 IP·fab의 빈 값을 허용합니다. `backend/ebeam/storage/providers/office_example.py:133~143`은 fab는 sem_list로 보정하지만 eqp_id/IP는 storage 원본을 사용합니다. 기존 IP 검사는 `backend/msr_image/paths.py:46~61`에 있습니다.
- 명세 변경: 서버는 eqp_id로 조회한 동일 행에서 IP·fab·모델·계정을 해석합니다. API slug와 모델 계열 일치, 선택한 fab와 장비 일치 규칙을 정하고 fab를 검사하려면 요청 계약에도 넣습니다. 이는 fab별 권한 도입과 별개인 대상 일관성 검사입니다. 없는 장비는 404, 서로 충돌하는 중복은 오류로 종료하고 첫 행을 임의 선택하지 않습니다. IP는 유효 IPv4 및 운영 장비 subnet 정책으로 검사하며 client 제공 host/port/계정은 무시하거나 거부합니다. storage 진입 링크도 sem_list에서 다시 해석하고 오래된 행은 안내합니다.

### R13. [high] 실제 FTP와 mock 승인 저장소가 섞이는 배포를 막아야 합니다

- 문제: 명세 76, 69행은 두 seam을 두면서 두 개의 해석 결과를 어떻게 묶는지 정하지 않습니다. office FTP가 가짜 장비 IP를 읽거나, 집용 JSON grant가 실제 장비 접근 권한이 되는 조합이 생길 수 있습니다.
- 근거: `backend/_runtime/data_provider.py:12~20,135~160`은 feature별로 독립 해석하고 office 복사본이 없으면 mock을 선택합니다. `:62~66,179~195`는 storage와 sem_list 등의 mismatch를 부팅에서 막는 기존 방식입니다. `docs/back-end/provider-selection.md:84~98`은 추가 swap 선례를 설명할 뿐 새로운 두 저장소의 결합을 자동 보장하지 않습니다.
- 명세 변경: v1에서는 tool-files의 동일 provider 선택이 FTP와 권한 저장소를 함께 선택하게 합니다. 별도 독립 env는 만들지 않습니다. office tool-files는 office sem_list에 의존하도록 기존 부팅 의존성 검사에 등록하고, directory의 office mode·실제 Redis 설정도 배포 점검에 넣습니다. 전역 mock kill switch, 강제 office+복사본 없음, mixed 상태 거부를 테스트합니다. 실제 FTP에서 mock 데이터로 fallback하는 동작은 금지합니다.

### R14. [med] directory의 absent·부분 프로필·캐시 지연을 판정표에 넣어야 합니다

- 문제: 명세는 unavailable만 정의합니다. members에 사번이 없거나 `dept_nm`이 비어 있는 경우를 장애로 볼지 승인 불가로 볼지 불명확합니다. 전출된 직원이 캐시된 옛 팀으로 계속 접근할 수도 있습니다.
- 근거: `backend/_auth/directory.py:59~65,184~210,225~232`는 부분 필드, absent, 손상 행의 unavailable, 600초 버킷 캐시를 정의합니다. `_decode()`의 소속 문자열 정리는 `:117~137`에 있습니다. members hash 자체가 없는 경우도 `hget()` 결과 None으로 absent가 됩니다.
- 명세 변경: 팀 판정은 `found`이며 비어 있지 않은 `dept_nm`일 때만 수행합니다. absent·팀 없음은 개인 승인이나 관리자 예외가 없다면 none이고, unavailable은 503입니다. hash 전체 누락을 운영 오류로 구별할 필요가 있는지 명시합니다. 팀 변경 반영의 최대 지연을 600초 캐시 기준으로 공개하고 허용 여부를 결정합니다. 더 짧은 반영이 필요하면 tool-files 권한 입력을 별도로 갱신해야 하며 기존 표시용 캐시 전체를 무조건 변경하지 않습니다. 신청 때 저장한 팀 이름을 현재 소속 증거로 쓰지 않습니다.

### R15. [med] 신청 API의 출처 및 입력 계약을 완성해야 합니다

- 문제: 명세 113, 118~124행의 "로그인"만으로는 declared/token 출처의 신청을 허용하는지 알 수 없습니다. 이 출처는 기능을 사용할 수 없으므로 승인해도 계속 접근하지 못하는 신청이 쌓일 수 있습니다. 잘못된 JSON과 무제한 사유도 저장소·UI 오류를 일으킵니다. LASTUSER 악용을 전제로 한 지적은 아닙니다.
- 근거: `backend/_auth/middleware.py:118~164`는 declared와 token도 identity로 받습니다. `backend/_auth/admin.py:65~85`의 출처 검사는 admin에 한정됩니다. 기존 API의 기본 검증 선례는 `backend/access_control/routes.py:42~51`이며 새 신청의 body 계약은 아직 없습니다.
- 명세 변경: 요청 생성·내 상태 조회에 허용할 출처를 명시하고 본인 empno는 body가 아닌 서버 identity로 결정합니다. declared/token 신청은 거부하고 신뢰 출처로 다시 접속하라는 안내를 주는 것이 가장 작습니다. body object, kind enum, 사번·팀·reason의 타입·길이·빈 값 및 JSON Content-Type을 검증합니다. 클라이언트의 dept_nm·granted_by·status는 받지 않습니다. 타인의 신청 조회·변경은 admin에만 허용하고 사유와 파일명을 HTML로 해석하지 않습니다. 별도 CSRF 체계나 인증 인프라 신설은 이번 검토의 v1 필수 요구에 넣지 않습니다.

### R16. [med] 승인·재신청·회수의 동시성 및 합성 권한 규칙이 없습니다

- 문제: 명세 97~105행의 두 hash 갱신은 하나의 원자적 동작이 아닙니다. 승인 grant만 저장되고 신청 삭제가 실패한 뒤 "저장되지 않음"이라고 답할 수 있습니다. 관리자가 옛 신청을 승인하는 동안 사용자가 재신청하면 새 신청이 지워질 수 있습니다. 개인 grant를 지워도 팀 grant가 있으면 접근은 유지됩니다.
- 근거: `backend/access_control/providers/office_example.py:173~181`도 grant 생성과 부가 정리는 별도 명령입니다. 이 코드를 여러 상태 전이에 그대로 확대할 수 없습니다. `backend/access_control/providers/mock.py:42,50,128~148`의 lock은 프로세스 안에서만 유효하고 고정 임시 파일명도 다중 writer를 직렬화하지 못합니다. 실제 배치는 `wsgi.ini:11~17`의 다중 worker입니다.
- 명세 변경: 신청 revision을 두고 승인·거절이 읽은 버전과 같은 신청에만 적용되게 합니다. grant 생성·대상 신청 삭제는 Redis의 조건부 원자 연산으로 묶고 재시도를 멱등하게 처리합니다. 통신 단절로 commit 여부를 모를 때는 "결과 확인 불가, 새로고침"을 반환하고 무조건 미저장이라 쓰지 않습니다. JSON mock은 한 프로세스 사용으로 한정하거나 다중 writer 잠금을 둡니다. 회수는 해당 grant만 제거하며 다른 팀·개인 grant나 admin 우회가 남으면 접근 유지됨을 UI와 테스트에 명시합니다. granted 상태 재신청은 거절 또는 no-op으로 정의합니다.

### R17. [med] 감사 요구는 feature_map 등록만으로 충족되지 않습니다

- 문제: 명세 62, 75행은 "누가 어떤 장비의 어떤 파일을 받았는지"를 요구하지만 feature slug 등록만 지시합니다. HTTP 200은 PC 저장 완료를 증명하지 못하며 기존 사용 통계는 파일별 다운로드 장부가 아닙니다. 일반 query 로그는 길이 제한도 있습니다.
- 근거: `backend/_logging/activity.py:122~152`는 일반 path·query·identity·status를 기록하고 `:233~250`은 통계 저장 실패를 삼킵니다. `backend/_logging/policy.py:144~152`는 query를 2048자로 자릅니다. `backend/_logging/opensearch_handler.py:256~266`은 큐가 차면 로그를 버립니다. `backend/_logging/feature_map.py:56~106,147~160`은 API와 페이지 mapping이 별도입니다.
- 명세 변경: API·페이지 mapping을 모두 등록하고 실제 해석한 eqp_id/fab, 작업, 경로의 안전한 식별값, 받은 바이트 수, 결과, identity_source, request_id를 명시적으로 기록합니다. 승인·거절·회수도 대상과 수행자를 기록합니다. "FTP fetch 성공/HTTP 응답 준비"와 "사용자 PC 저장 완료"를 구별합니다. 기존 best-effort 로그로 충분하다면 유실 가능성과 모니터링을 명세에 적습니다. 누락 없는 감사를 필수로 유지한다면 내구성 있는 기록과 기록 실패 시 다운로드 허용 여부를 별도 수용 조건으로 정합니다. 암묵적으로 보장한다고 쓰지 않습니다.

### R18. [med] 팀 목록 API의 장애·크기·정확성 계약이 없습니다

- 문제: 명세 86, 120, 167행은 `members` 전체를 읽어 팀과 인원수를 캐시한다고만 합니다. Redis 장애나 잘못된 행을 빈 팀 목록·0명으로 바꾸면 관리자는 조직 개편으로 오인합니다. 팀 이름에 `/`가 있으면 `<value>` 경로를 사용하는 회수 API도 불안정합니다.
- 근거: `backend/_auth/directory.py:51~61`의 hash 값은 사번별 JSON이며 별도 팀 색인은 없습니다. `:293~328`의 기존 bulk 조회는 실패를 bare profile로 낮추므로 관리용 팀 목록의 장애 판정에 그대로 사용할 수 없습니다. `backend/access_control/routes.py:55~63`의 단일 경로 변수 선례는 팀 이름의 임의 문자열을 전제하지 않습니다.
- 명세 변경: 관리자 전용 제한 시간·캐시 TTL·불완전 응답 표시를 정하고, 실패를 503 또는 명시적인 stale 상태로 반환합니다. invalid row를 제외했다면 완전한 인원수라고 표시하지 않습니다. 마지막 정상 목록과 현재 유효한 팀을 혼동하지 않습니다. 큰 hash는 HSCAN 등으로 제한된 양씩 읽되 순회 중 변동 시 인원수는 snapshot 보장이 없음을 정합니다. 회수 대상 kind/value는 JSON body 또는 안전한 식별 키로 전달하여 `/`, `%`, 공백, 한글도 왕복하게 합니다.

### R19. [med] LIST의 호환성·시각·빈 결과를 과신하면 안 됩니다

- 문제: 명세 40, 88, 142행의 LIST 선택만으로 모든 옛 FTP 데몬에서 올바른 표를 보장할 수 없습니다. 지원하지 않는 출력 줄은 조용히 사라져 실제 파일이 있어도 빈 폴더처럼 보입니다. 최근 파일의 연도와 오래된 파일의 시각도 정확한 원본 값이 아닙니다.
- 근거: `ftp_handler/core/client.py:70~89,93~107,110~140,245~261`은 Unix·DOS 두 형식만 처리하고 날짜 오류·미지원 형식을 건너뜁니다. 기본 시간대는 `:35~40`의 KST이며 연도 추정과 자정 보정이 있습니다. 숨김 파일 포함 여부도 `:252`의 서버 기본 LIST 동작에 따릅니다.
- 명세 변경: "서버가 LIST로 반환하고 현재 파서가 지원하는 항목"을 v1 보장 범위로 씁니다. 미지원 출력·부분 누락이 확인되면 정상적인 빈 폴더와 구분하는 오류/경고 계약을 추가합니다. 시각은 서버 현지 시각이며 추정 정밀도임을 명시하고 null 정렬도 정합니다. 실제 계열별 LIST·숨김 파일·인코딩을 office에서 확인하기 전에는 전체 파일 탐색을 보장한다고 표시하지 않습니다.

### R20. [med] 다운로드 HTTP 계약과 브라우저 실패 처리가 없습니다

- 문제: 명세 42~43, 115, 126행은 attachment만 지정합니다. 권한 회수 뒤 URL·브라우저 캐시가 남는 경우, 한글·따옴표 파일명, 백엔드가 JSON 오류를 반환한 경우의 처리도 필요합니다. 다중 파일 자동 저장은 브라우저에서 막힐 수 있습니다.
- 근거: `backend/msr_image/routes.py:90~107`에는 이미 filename escaping과 RFC 6266 `filename*` 처리가 있습니다. `backend/__init__.py:121~126`은 HTTP 예외도 JSON으로 돌려줍니다. 기본 제한은 `:93~106`의 앱 공용 50/5초입니다. 새 API 표에는 캐시·헤더·오류 읽기 규칙이 없습니다.
- 명세 변경: 파일 응답을 `attachment`, 안전한 basename의 `filename`/`filename*`, `application/octet-stream`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`로 정의합니다. 목록·access 응답도 권한 정보가 공용 캐시에 남지 않게 합니다. 기존 content-disposition의 escaping 원리를 재사용하되 경로 바이트 키는 다운로드 표시 이름과 분리합니다. 매 요청 권한을 다시 판정하고 frontend는 401/403/413/429/503 JSON을 파일로 저장하지 않게 합니다. 경로가 URL·referer·서버 로그에 남는 특성도 알려야 합니다. 다중 다운로드를 유지한다면 실패 시 중단·재시도·사용자 취소·브라우저 허용 동작까지 수용 조건에 넣습니다.

### R21. [med] mock HTTP 테스트만으로 실제 FTP 보안 조건을 입증할 수 없습니다

- 문제: 명세 145~155행은 판정표와 일반 경로 테스트를 잘 잡았으나, 앞의 위험을 만드는 실제 계층을 통과하는 검증이 없습니다. 또한 "access_control 선례는 office template을 sys.modules에 alias한다"는 설명은 현재 파일과 다릅니다.
- 근거: `backend/access_control/tests/test_office_template.py:12~18,24~45`는 `office_example as office`를 직접 import하고 byte 응답의 FakeRedis를 주입합니다. `ftp_handler/core/client.py:184~195,251~284`의 실제 socket·LIST 파서·수신 callback은 새 mock 트리 HTTP 테스트에서 실행되지 않습니다. `CLAUDE.md:Commands`는 자동 E2E suite 부재와 수동 브라우저 확인을 명시합니다.
- 명세 변경: 다음을 출시 전 검증 목록에 추가합니다. alias는 HTTP dispatcher로 template을 실행할 때 필요한 테스트 기법으로만 설명하고 직접 template 단위 테스트도 유지합니다.
  - 실제 transport를 통과하는 fake FTP 대역으로 non-root 홈, latin-1 원시 바이트 왕복, Unix/DOS/미지원 LIST, 링크, 사라진 파일, 중간 연결 단절, 연결·로그인 실패의 자원 정리를 확인합니다.
  - 목록 크기보다 실제 전송량이 큰 파일, 지속적으로 조금씩 오는 파일, 상한과 정확히 같은 크기 및 1바이트 초과, LIST 한도 초과를 검증합니다. off 플래그 테스트만으로 이를 대신하지 않습니다.
  - 모든 데이터 API의 declared/token/anonymous/unknown-source 거부, 거부 요청에서 FTP 호출 없음, 승인 후 회수한 직접 URL 거부, admin override와 R2에서 선택한 Phase 2 local 정책을 확인합니다. 사내 신뢰 운영 전제에 따라 LASTUSER 위조 공격 검증은 v1 필수 검사에서 제외합니다.
  - directory absent·부분 프로필·malformed JSON·캐시 변경, grant store WRONGTYPE·timeout·손상 JSON, 저장 후 응답 단절, 승인·재신청 경쟁을 검증합니다. Redis transaction의 의미는 단순 dict fake만으로 입증하지 않습니다.
  - office 강제 선택/복사본 없음 및 sem_list mismatch 부팅 거부, mock에서 네트워크를 호출하지 않는지 확인합니다. 공용 계정 코드 변경 시 기존 msr_image 설정·계정 테스트를 함께 실행합니다.
  - 집에서는 순수 함수·HTTP·template 대역 검증으로 표시합니다. Windows proxy와 Phase 3 direct는 각각 실제 읽기 전용 장비에서 LIST·다운로드·취소·deadline·파일명 저장을 확인합니다. Python 3.11을 별도로 확인합니다. CI 3.14 성공으로 office 실행을 입증했다고 쓰지 않습니다.

## 3. v1에서 삭제할 범위

### R22. [high] 숨겨서 출고할 업로드·삭제 전체를 삭제합니다

- 문제: 명세 24~25, 63~67, 92, 116~117, 135, 152행은 읽기가 주목적인 v1에 쓰기 라우트·UI·테스트를 모두 요구합니다. 플래그 하나를 켜면 기존 읽기 승인자 전원에게 생산 장비 변경 권한을 줍니다. 파일 존재 시 덮어쓰기, 중단된 STOR의 부분 파일, 업로드 크기, 동시 쓰기, 복구 정책도 정의되지 않았습니다.
- 근거: `ftp_handler/core/client.py:286~292`는 STOR 덮어쓰기와 DELE를 즉시 실행하며 복구·원자 업로드는 없습니다. 명세 162행은 읽기·쓰기 권한 분리를 out of scope로 두고, 170행은 주 용도를 PC 가져오기로 확인합니다.
- 명세 변경: v1에서 upload/delete 라우트, `SKEWNONO_TOOL_FILES_WRITE`, `can_write`, 드롭존·삭제 UI, on/off 테스트와 사용자 스토리 29~33을 삭제합니다. 존재하지 않는 라우트는 직접 호출해도 FTP에 닿지 않아야 합니다. 쓰기 기능은 별도 명세에서 권한·덮어쓰기·부분 실패·복구·감사를 정한 뒤 추가합니다. 플래그가 안전 설계를 대신하지 않습니다.

### R23. [low] 설정 파서 공용화를 위한 msr_image 전체 재편은 줄입니다

- 문제: 명세 87행은 새 브라우저 때문에 기존 이미지 설정 코드를 공용 위치로 옮기게 합니다. 이미지 캐시·job·purge 등의 설정까지 포함한 타입을 공용 FTP 설정으로 재편할 필요는 없습니다.
- 근거: `backend/msr_image/config.py:69~109,112~134`는 FTP 외에 이미지 전용 설정을 많이 담습니다. 계정 선택은 이미 `backend/msr_image/ftp_accounts.py:44~76`의 작은 순수 함수로 분리되어 있습니다. `CLAUDE.md:API Abstraction Layer`는 provider seam을 유지하도록 합니다.
- 명세 변경: "공용 위치로 이동"을 필수 구현 사항에서 삭제하고 기존 설정 로더·계정 resolver를 우선 재사용합니다. 독립 공용 코드가 꼭 필요해지면 실제 공유하는 파싱·계정 선택만 최소 이동하고 이미지 공개 설정과 동작은 보존합니다. 새 범용 설정 프레임워크·독립 seam 설정은 만들지 않습니다.

### R24. [low] 다중 파일 자동 다운로드는 v1에서 뺄 수 있습니다

- 문제: 명세 43, 91행의 순차 다운로드도 큐 상태·일부 실패·취소·브라우저 다중 저장 허용·공용 rate limit 처리가 필요합니다. 한 파일을 PC로 가져오는 핵심 사용 흐름보다 추가 검증 부담이 큽니다.
- 근거: `backend/__init__.py:93~106`은 모든 비면제 API에 공용 예산을 적용합니다. `backend/msr_image/routes.py:139`의 기존 단일 파일 라우트는 브라우저 다중 저장 제어를 제공하지 않습니다. 명세 159~160행은 이미 대량 작업·zip을 제외했습니다.
- 명세 변경: 사용자 스토리 9와 다중 선택·순차 자동 저장 큐를 후속으로 옮기고 v1은 파일별 명시적 다운로드로 정합니다. 여러 파일이 v1 필수라면 삭제 대신 R20의 실패·취소·브라우저 검증을 반드시 추가합니다. 장비 선택기·breadcrumb·현재 폴더 필터·정렬은 현재 요구를 충족하는 작은 UI이므로 굳이 더 줄일 필요는 없습니다.

## 확인 결과와 범위

코드와 맞는 부분도 있습니다. feature 자동 등록과 ebeam 아래 평평한 배치는 `backend/__init__.py:287~300` 및 `CLAUDE.md:Feature-sliced Backend Layout`과 일치합니다. `lookup_member()`를 권한 판정에 쓰지 않겠다는 선택은 맞습니다. 계정의 eqp_id 우선순위, 요청별 FtpClient context 사용, latin-1을 통한 파일명 바이트 보존 방향, Redis 장애를 정책 거부로 바꾸지 않겠다는 목표도 유지해야 합니다. 단, 각 목표는 위에서 지적한 추가 계약이 있어야 완성됩니다.

네트워크 없이 메모리에서 실행한 assert 확인은 모두 통과했습니다. 직접 넣은 LASTUSER 수용, mock probe의 unavailable과 표시용 가짜 팀 차이, 비클라우드 local-dev 관리자, `CDSEM`과 `CD-SEM` 계정 키 차이, 빈 remote_dir의 절대 경로 생성과 미지원 LIST 줄 누락, download 전체 버퍼 수집을 확인했습니다. 이는 현재 코드 동작의 재현이며 새 기능의 테스트 통과를 뜻하지 않습니다.

이 검토는 실제 Redis·FTP·Windows·사내 proxy·클라우드 인증 인프라에 접속하지 않았습니다. 따라서 서버 chroot·링크·LIST 형식, 안전한 장비 동시성·용량 수치는 office 확인 사항입니다. LASTUSER는 사용자 확인에 따라 기존 사내 신뢰 모델을 수용합니다. 기존 코드 전체의 리팩터링, 구현, commit은 하지 않았으며 보고서만 작성했습니다.
