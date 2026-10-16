# tool-files 검토 r2

판정: r1은 기존 지적을 상당 부분 해소했습니다. 다만 아래 N1~N9를 정리하기 전에는 `ready-for-agent`로 보기 어렵습니다. 업로드·삭제 구현 후 off, 관리자만 쓰기, 개발자 전용 Phase 2 proxy의 신규 라우트는 읽기만 제공, `dept_nm` 팀 키, 앱 관리자 승인이라는 결정은 그대로 수용합니다. 아래 CLOSED는 명세 수준에서 해소되었다는 뜻이며 구현 검증 완료가 아닙니다.

기준 커밋은 `05fccce8`과 후속 `0330952c`입니다. 이하 `spec`은 `.scratch/tool-files/spec.md`입니다. 외부 저장소 근거의 `flask_modules/`는 `/Users/daeyoung/Codes/flask_modules/`를 뜻합니다.

## R 항목별 재검토

| 항목 | 판정 | 심각도 | 근거와 필요한 조치 |
| --- | --- | --- | --- |
| R1 | CLOSED | low | `spec:124,342`에 사내 신뢰 전제와 인증 체계 제외를 명시했습니다. 재논의하지 않습니다. |
| R2 | CLOSED | med | `spec:123`에 Phase 2 local-dev 관리자 예외를 명시했습니다. 최종 운영 결정과 일치합니다. |
| R3 | CLOSED | med | `spec:125`의 feature 전용 probe 대역이 기존 directory의 mock unavailable과 분리됩니다. |
| R4 | PARTIAL | high | `spec:185~196`의 proxy 방향은 맞습니다. home/wire 계약과 공유 webapp deadline이 미완성입니다. N3·N4가 남습니다. |
| R5 | PARTIAL | med | `spec:142,179`의 PWD 기준은 direct 문제를 닫습니다. proxy에서 PWD를 얻는 방법은 N4에서 확정해야 합니다. |
| R6 | CLOSED | med | `spec:129,136`에 동일 행과 `account_for()` 및 tool type 키를 명시했습니다. resolver에는 전체 roster 대신 해석한 단일 행을 전달해야 합니다. |
| R7 | PARTIAL | med | `spec:255~267`에 직접 오류 변환을 정했습니다. 그러나 목록 누락을 파일 부재로 확정하는 규칙은 N9처럼 수정해야 합니다. |
| R8 | CLOSED | med | `spec:219~224`에 mock 손상 503, 빈 키 정상, 결과 불명 안내와 직접 예외 변환을 구별했습니다. |
| R9 | PARTIAL | high | `spec:141~147`의 문자열 검사만으로 중간 디렉터리 링크를 거부하지 못합니다. N1이 남습니다. |
| R10 | CLOSED | high | `spec:180,194,206,318`은 실제 수신량 제한을 양쪽 transport에 요구합니다. 구현 시 HTTP 전체 버퍼 수신 후 검사로 대체하면 안 됩니다. |
| R11 | PARTIAL | high | `spec:180~206,340`의 장비별 공유 동시성 제한 연기는 작은 v1에서 수용할 수 있습니다. 그러나 LIST 수집량·시간은 실제로 막히지 않아 N3의 구멍이 남습니다. |
| R12 | PARTIAL | med | `spec:132`는 IP가 다른 중복만 거부합니다. 같은 eqp_id/IP라도 fab·모델·계정 선택 필드가 다르면 임의 행 선택 문제가 남습니다. 이 필드가 모두 같은 중복만 합치고 나머지는 409로 명시하십시오. |
| R13 | PARTIAL | med | `spec:92~94`의 두 seam 및 sem_list 결합은 맞습니다. `backend/_runtime/data_provider.py:144~153`의 feature 강제 office는 전역 mode와 독립이고 directory는 `backend/_auth/directory.py:170~171`의 mode를 따릅니다. tool_files·sem_list만 office, 전역 mock이면 실FTP와 unavailable directory가 섞입니다. office 개방 조건에 directory mode·Redis 설정 검사도 추가하십시오. |
| R14 | CLOSED | med | `spec:113~122`가 absent·팀 없음과 장애를 구별하고 캐시 지연을 수용합니다. |
| R15 | PARTIAL | med | `spec:65,237,247~250`의 출처·입력 방향은 맞지만 JSON 공통 규칙이 multipart 및 admin 팀 입력과 충돌합니다. N8을 반영하십시오. |
| R16 | PARTIAL | high | `spec:217~218,327`은 WATCH/MULTI를 도입했으나 같은 timestamp, 거절 경쟁, 재시도 결과가 미정입니다. 승인자 한 명이어도 신청자가 동시에 씁니다. 축소 범위는 현 상태로 불충분하며 N7이 필요합니다. |
| R17 | PARTIAL | low | `spec:269~273`의 best-effort·2048자 한계 수용은 v1에 적절합니다. `logger.info` 내용에는 수행자·대상·작업·성공/실패·request_id를 명시하십시오. 기존 `backend/_logging/opensearch_handler.py:288~304`는 message를 저장하므로 새 인덱스 없이 가능합니다. |
| R18 | PARTIAL | med | `spec:239~253`에 body·HSCAN·complete·503이 있습니다. 캐시 TTL과 HSCAN 중복 사번 제거가 빠졌습니다. TTL을 정하고 empno로 중복 제거한 뒤 집계하며, `complete:false`의 0명을 조직 개편으로 표시하지 않도록 추가하십시오. |
| R19 | PARTIAL | low | `spec:289,341`의 시각 정밀도 설명과 미지원 줄 경고 생략은 v1에서 수용 가능합니다. 지원 형식만 보이는 목록이라는 한계를 화면 설명에 남기고, N9처럼 이것을 부재의 확증으로 쓰지만 않으면 됩니다. |
| R20 | CLOSED | med | `spec:228,252,287`의 no-store·attachment·filename escaping·fetch 오류 검사가 기존 문제를 닫습니다. |
| R21 | PARTIAL | med | `spec:316~332`의 transport 테스트는 개선되었습니다. 두 사본 비교 검사가 있다는 오기와 Redis 경쟁을 mock HTTP만으로 입증하는 공백은 N2·N7에 남습니다. |
| R23 | CLOSED | low | `spec:136`에서 기존 로더와 순수 함수를 import하며 설정 이동을 없앴습니다. |
| R24 | CLOSED | low | `spec:25~28,338`에서 파일별 다운로드로 한정했습니다. |

R22는 기각된 최종 결정이므로 재판정하지 않습니다. 새로 추가된 쓰기의 안전 조건만 아래에서 검토합니다.

## 새 문제와 남은 구체적 수정

### N1. [high] 링크 필터는 중간 경로를 보호하지 않습니다

- 근거: `spec:140~147,170`은 LIST의 링크 항목을 빼는 방식입니다. `ftp_handler/core/client.py:252~267,280~292`는 `/home/link/child/file`의 `link`를 검사하지 않고 요청한 최종 경로를 사용합니다. 이전에 공유한 정상 URL의 중간 폴더가 링크로 교체되어도 구성요소 접두어 검사는 통과합니다. 쓰기가 켜지면 다른 위치를 변경할 수 있습니다.
- 수정: 각 경로의 중간 구성요소와 최종 대상을 같은 FTP 연결에서 확인하고 링크 경유를 거부한다고 명시하십시오. FTP 검사 뒤 대상이 교체되는 경쟁까지 막는다고 보장하지 말고, 허용 루트의 실제 강제가 필요하면 server chroot/계정 제한 확인을 활성화 조건으로 정하십시오. `OFFICE-VERIFY` 메모만으로 "루트 밖 접근 불가"를 보장하지 않습니다.

### N2. [med] 소비자 조사와 호환 규칙의 보장 범위를 바로잡아야 합니다

- 근거: `spec:162`의 "테스트 외 소비자 없음"은 문자 그대로 틀립니다. 양쪽 `ftp_handler/core/examples.py:49~52`가 실행 가능한 소비자입니다. `~/Codes`를 ignored/hidden 파일까지 포함해 검색한 결과 그 외 배포용 직접 호출은 찾지 못했고, fleet가 `_normalize_listing`만 import한다는 설명은 `ftp_handler/direct_downloader/fleet_downloader.py:50~56`과 일치합니다. scheduler1 webapp 자체의 체크아웃은 이 로컬 검색 범위에 없어 실제 등록·설정을 확인할 수 없습니다.
- 근거: `spec:151,324`와 달리 `tests/test_vendored_ftp_handler.py:19~42` 및 전체 테스트 본문에는 flask_modules와의 파일 비교가 없습니다. 현재 두 사본은 별도 `diff -rq --exclude=__pycache__`로 일치함을 확인했습니다. 테스트 통과와 사본 일치는 다른 검사입니다.
- 근거: `ftp_handler/core/client.py:43~58`은 slots dataclass입니다. `spec:170`의 필드 추가는 기존 6개 인자 생성에는 호환되지만 `fields/asdict/slots/repr` 형식은 바뀝니다. 메모리 실험에서 옛 pickle을 새 slots 클래스에 복원하면 새 기본값 slot이 채워지지 않았습니다. 그런 저장 소비자는 찾지 못했으므로 별도 pickle 이행 체계는 불필요합니다.
- 수정: "실행 예제 외 배포 소비자를 발견하지 못함, 원격 호스트 미검증"으로 고치고 사본 diff를 별도 필수 확인으로 적으십시오. FileInfo 스키마 확장을 호환 규칙의 명시적 예외로 허용하되 기존 positional 생성과 속성은 보존하십시오. `download(path, ...)` 예시도 기존 keyword 이름 `remote_path`를 유지해야 합니다(`client.py:280`). 링크 표시를 위해 `_parse_list_line()`의 4원소 반환을 바꾸면 기존 테스트가 깨집니다(`flask_modules/tests/test_ftp_client.py:219~223`). `raw`에서 링크를 판별하거나 별도 내부 함수를 쓰십시오. `home()` 때문에 기존 `__enter__`에 PWD를 추가하면 PWD가 없는 기존 FakeFTP도 깨지므로 명시적 home 호출 때 조회하십시오(`flask_modules/tests/test_ftp_client.py:29~83`).

### N3. [high] 120초 deadline과 LIST 한도는 공유 proxy 호스트를 보호하지 못합니다

- 근거: `spec:180~204`는 download에만 deadline, LIST에는 `max_entries`만 추가합니다. 현재 `ftp_handler/core/client.py:251~261`은 원문 전체를 모은 뒤 파싱합니다. 수만 개의 미지원 줄 또는 멈추지 않는 LIST는 유효 항목 수가 늘지 않아 제한을 우회합니다. `spec:203`의 120초는 `flask_modules/api/wsgi.ini:49`의 60초 및 단독 proxy `ftp_handler/proxy/wsgi.ini:35`의 75초보다 깁니다. 후자는 attach 방식에서는 사용되지 않습니다(`:4~5`). 실제 scheduler 호스트 설정은 미확인입니다.
- 수정: max_entries를 수신 callback에서 조기에 검사하고, 미지원 줄을 포함한 원문 바이트/줄 한도와 LIST deadline도 넣으십시오. deadline을 시작하는 시점과 소켓의 남은 시간 설정, 중단 시 FTP 연결 폐기까지 정하십시오. Phase 2는 실제 공유 webapp·ingress 제한보다 짧은 별도 유효 deadline을 사용하고 HTTP 전송 여유를 남기십시오. 원격 설정 확인 없이 공유 webapp harakiri를 올리는 변경은 요구하지 않습니다. 불필요한 새 분산 동시성 시스템은 추가하지 않습니다.

### N4. [med] 두 proxy 라우트만으로 home·FileInfo·예외를 어떻게 운반할지 빠졌습니다

- 근거: `spec:185~196`은 `home/list_details/download`를 약속하지만 list와 fetch만 정의합니다. 최초 `home()`에 필요한 PWD, JSON의 datetime 및 `is_link`, root·credentials·encoding·한도 전달 형식이 없습니다. proxy가 한 HTTP 요청마다 새 FTP 연결을 열면 Python context manager가 원격 연결 하나를 유지한다는 뜻도 아닙니다. 기존 context 계약은 `ftp_handler/core/client.py:154~159`, 클라이언트/서버 import 분리는 `ftp_handler/proxy/__init__.py:1~15`에 있습니다.
- 수정: 새 route의 정확한 요청/응답 envelope를 추가하십시오. 예를 들어 list 라우트에 home-only 동작을 허용하고 실제 PWD와 entries를 반환하면 세 번째 route나 원격 세션 저장소가 필요 없습니다. HTTP별 독립 연결임을 명시하고, file key는 여러 연결에서도 재사용 가능한 표현으로 정하십시오. `modified`는 ISO/null, 링크 필드는 반드시 전달하고 shared 예외 클래스와 wire code 대응표를 작성하십시오. ListingTooLarge·경로 거부·원격 401/404/5xx·비JSON 응답도 처리해야 합니다. deadline은 서로 다른 머신의 monotonic 절대값이 아니라 잔여 기간으로 전달하십시오. proxy client를 import할 때 Flask 서버 모듈을 import하지 않고 기존 URL/TOKEN 및 선택적 인증 동작을 재사용하십시오. 인증 도입은 요구하지 않습니다.

### N5. [med] can_write와 403/501의 우선순위가 충돌합니다

- 근거: `spec:120`의 can_write 조건대로라면 Phase 2 관리자도 플래그 on에서 true가 됩니다. `spec:187,264`는 같은 요청에 501을 약속하고 `:288`은 쓰기 UI를 표시합니다. `:315`의 on 테스트도 transport 구별 없이 성공을 요구합니다.
- 수정: `can_write = flag_on and is_admin_request() and transport_supports_write`로 정하고 capability는 서버에서 판정하십시오. 직접 API 요청은 플래그 off→403, 비관리자→403, 나머지 proxy→501 순서로 고정하고 FTP/HTTP 호출 전에 거부하십시오. mock·direct의 on 성공과 proxy의 501을 각각 테스트하십시오. 기존 proxy upload 라우트는 호환성 때문에 그대로 둔다는 뜻이며, "proxy 읽기 전용"은 이번에 추가하는 API에만 해당한다고 명시하십시오(`ftp_handler/proxy/flask_proxy.py:269`, `spec:188,196`).

### N6. [high] 임시 STOR 후 RNTO는 기본 덮어쓰기 금지를 보장하지 않습니다

- 근거: `spec:182,235,288`은 사전 존재 검사와 RNFR/RNTO를 안전한 put으로 제시하고 overwrite true도 노출합니다. 두 요청이 동시에 "없음"을 확인한 뒤 같은 대상에 RNTO하면, 대상 교체를 허용하는 서버에서는 나중 요청이 앞 파일을 덮습니다. Python `ftplib.FTP.rename()`도 RNFR/RNTO만 보내며 no-clobber 옵션은 없습니다. 앱 관리자가 한 명이어도 여러 탭이나 장비 측 프로세스가 파일을 만들 수 있습니다. 기존 `ftp_handler/core/client.py:286~288`의 무조건 STOR와는 별개로 새 보장을 정의해야 합니다.
- 수정: 임시 파일은 대상과 같은 폴더의 충돌하지 않는 이름으로 만들고, `overwrite=False`의 보장을 서버별로 확인하십시오. FTP 서버의 rename이 원자적인지, 기존 대상에 RNTO가 실패하는지, 존재 검사가 미지원 LIST 때문에 거짓 음성이 되지 않는지도 확인 조건에 넣으십시오. 지원하지 않는 서버에서는 쓰기 활성화를 거부하거나 동시 외부 writer가 없다는 운영 전제를 명시해야 합니다. 임시 이름 사용만으로 "안전한 쓰기"를 보장한다고 쓰지 마십시오. RNTO 성공 응답만 유실된 경우는 성공 여부 불명으로 안내하고, 정리는 자기 임시 파일에만 한정하십시오. fake FTP 테스트에 동시 생성·RNTO 거절·응답 유실을 추가하십시오.

### N7. [high] requested_at 비교와 WATCH만 선언해서는 경쟁과 재시도 계약이 완성되지 않습니다

- 근거: `spec:217~218`은 timestamp를 버전처럼 쓰지만 중복 불가 조건이 없습니다. 기존 timestamp helper는 초 단위라 같은 초의 재신청이 같은 값이 됩니다(`backend/access_control/providers/mock.py:66~67`). 거절은 WATCH 대상이라는 설명도 없고, 승인 후 재요청은 신청이 지워져 동일 결과라는 약속과 충돌합니다. 팀 전체 승인도 어떤 시점의 pending을 지우는지 미정입니다. `backend/_runtime/office_redis.py:138`의 STORE_ERRORS에는 WatchError가 포함되어 단순 재사용하면 정상 경쟁을 503으로 오분류합니다.
- 수정: 별도 revision 필드를 만들지 않더라도 requested_at을 사번별 엄격히 증가하는 변경 토큰으로 원자적으로 발급한다고 정하십시오. 승인과 거절 모두 WATCH→read/토큰 비교→MULTI→변경→EXEC 순서로 처리하고, WatchError는 먼저 구별하여 다시 읽은 뒤 변경된 신청이면 409로 응답하십시오. 무관한 사번 변경에 대해서는 제한된 재시도를 정하십시오. grant가 있고 신청이 없는 승인 재시도는 성공 no-op, 새 신청이 있으면 옛 토큰으로 삭제하지 않는 규칙을 추가하십시오. 팀 승인은 transaction에서 읽은 pending 집합만 삭제하고 저장된 dept_nm은 정리 기준일 뿐 현재 소속·권한 증거가 아님을 적으십시오.
- 검증: `spec:327`의 mock HTTP 경쟁 테스트만으로 Redis WATCH 의미는 입증되지 않습니다. 네트워크 없는 fake는 실패 분기 검증에 쓰고, 실제 Redis의 서로 다른 두 연결에서 승인↔재신청, 거절↔재신청, 팀 승인↔개인 승인/재신청을 재현하는 별도 통합 검사를 추가하십시오. 집 실행 필수로 강제할 필요는 없지만 office 검증 항목에는 있어야 합니다.

### N8. [med] 업로드의 body·자원 제한과 관리자 입력 예외를 구별해야 합니다

- 근거: `spec:235`는 multipart인데 `:248`은 모든 body를 JSON object로 제한합니다. `:250`의 dept_nm 금지는 `:244`의 관리자 팀 승인과 충돌합니다. `:202~206`은 다운로드 상한뿐이고 `put()`에는 입력 크기·STOR 전체 deadline·중단 정리 조건이 없습니다. 큰 업로드를 `data: bytes`로 만들 때부터 메모리를 사용합니다.
- 수정: 신청 body에만 서버 identity/소속 규칙을 적용하고, 관리자 대상 empno·dept_nm 입력은 각 API 계약에 따라 검증한다고 적으십시오. upload는 multipart의 필수 fab/eqp_id/폴더 키/파일명/overwrite 타입을 따로 정의하십시오. multipart 파싱 전에 body 상한을 적용하고 실제 파일 바이트 및 STOR 총시간도 제한하십시오. off·비관리자·proxy 거부는 파일 전체를 읽기 전에 수행하며 부분 업로드는 자기 임시 파일만 best-effort 정리하고 정리 실패 경로를 기록하십시오. 이는 쓰기를 유지한다는 결정을 바꾸지 않습니다.

### N9. [med] 불완전한 LIST의 파일 누락은 404의 확증이 아닙니다

- 근거: `spec:267`은 "같은 폴더 목록에 없으면 file_not_found"로 정하지만 `ftp_handler/core/client.py:245~261`은 미지원 줄·날짜 오류를 버립니다. 권한 때문에 RETR가 550인 실제 파일의 LIST 줄까지 파싱에서 빠지면 "없음"이라고 오판합니다. LIST 경고를 v1에서 생략하더라도 이 오류는 남습니다.
- 수정: 파서가 버린 줄이 있거나 목록의 완전성을 확인할 수 없으면 404로 확정하지 말고 "파일 부재 또는 FTP 접근 거부"라는 별도 일반 오류로 응답하십시오. 부재를 확실히 확인한 경우만 file_not_found로 정합니다. 파서 내부의 완전성 정보만 추가하면 되며, 제외하기로 한 LIST 경고 UI를 다시 만들 필요는 없습니다.

## 더 줄일 부분

- [low] `spec:120`의 미래 grant `level` 필드 이행 설계는 삭제하십시오. v1 관리자 쓰기 판정과 관계없는 미래 데이터 모델 약속입니다. `spec:95~99`처럼 현재 필요한 순수 함수 분리만 유지하고, 일괄 복사용 job 인터페이스·범용 전략 객체는 만들지 않습니다.
- [low] 덮어쓰기 확인 UI와 `overwrite=True`가 v1 필수가 아니라면 `spec:235,288`에서 이 옵션만 후속으로 미루면 쓰기 보장과 테스트 범위가 작아집니다. 업로드·삭제 자체를 빼자는 제안은 아닙니다.

검증 범위: `~/Codes`의 Python 및 텍스트 소비자 검색, 현재 두 ftp_handler 사본 diff, slots 복원 및 timestamp 충돌의 메모리 확인을 수행했습니다. 실FTP·실Redis·scheduler1 배포 설정·실제 RNTO 의미는 확인하지 않았습니다. 소스 변경이나 commit 없이 이 보고서만 작성했습니다.
