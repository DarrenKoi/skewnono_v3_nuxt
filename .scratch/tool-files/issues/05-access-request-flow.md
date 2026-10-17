# 05: 권한 신청·승인 흐름

**What to build:** 권한이 없는 사용자가 탐색기를 열면 "권한 요청" 카드가 보이고, 사유 한 줄을 적어 신청합니다. 다시 열면 대기 중인지 거절되었는지 보이고, 거절되면 다시 신청할 수 있습니다. 관리자는 `/admin/access`에서 대기 신청을 승인하거나 거절하고, 같은 팀 신청은 "이 팀 전체 승인"으로 한 번에 처리합니다.

**Blocked by:** 04 (팀·사번 승인 저장소와 판정)

**Status:** done (2026-10-17)

- [x] 신청은 신뢰 출처(cookie·local)에서만 받습니다. body에서는 `reason`만 받고 길이는 200자까지입니다. 사번과 dept_nm은 서버가 정합니다. 이미 `granted`인 사람이 신청하면 아무것도 하지 않습니다
- [x] 신청할 때마다 새 `request_id`(uuid4 hex)를 발급합니다. `requested_at`은 표시용으로만 씁니다
- [x] 승인과 거절은 둘 다 WATCH → `request_id` 비교 → MULTI → EXEC 순서로 처리합니다. `request_id`가 다르면 409 `request_changed`입니다. 승인 재시도에서 grant는 있고 신청이 없으면 no-op 성공으로 처리합니다
- [x] `WatchError`는 `STORE_ERRORS`보다 먼저 잡습니다. 다시 읽어서 그 사번의 신청이 바뀌었으면 409를 내고, 무관한 변경이면 최대 3회까지 재시도합니다
- [x] 팀 전체 승인은 트랜잭션 안에서 읽은 pending 신청 가운데 저장된 dept_nm이 같은 것만 지웁니다
- [x] 응답이 끊겨 결과를 알 수 없으면 "결과 확인 불가, 새로고침"으로 안내합니다
- [x] 탐색기 화면은 verdict별로 다음을 보여 줍니다: 신청 카드, 대기 안내, 거절 안내(재신청 가능), 신뢰 출처 안내, 소속 확인 불가 안내, 저장소 장애 안내
- [x] 관리자 섹션에 대기 신청 칸을 만듭니다. 사번, 이름, 팀, 사유, 신청 시각을 보여 주고 승인·거절·팀 전체 승인 버튼을 둡니다. 사유는 HTML로 해석하지 않습니다
- [x] 신청·승인·거절은 `logger.info`로 기록합니다
- [x] HTTP 테스트로 확인합니다: 신청 → 승인 → 접근, 신청 → 거절 → 재신청, 승인 사이에 재신청이 끼면 409, 팀 전체 승인 정리, declared·token 신청 거부
- [x] fake Redis가 `WatchError`를 던지게 해서 재시도와 409 분기를 확인합니다
- [x] `browser-verify` 스킬로 비관리자 identity로 신청하고 관리자로 승인하는 흐름을 확인합니다

## Comments

2026-10-17 구현 기록입니다.

- **판정.** `decide()`에 다섯 번째 인자 `requests`를 lazy callable로 추가했습니다. 팀 판정까지 통과하지 못한 경우에만 읽으므로, 관리자·사번 승인·팀 승인 사용자는 신청 저장소를 읽지 않습니다. 신청 저장소를 읽지 못하면 `store_unavailable`입니다. directory 장애는 대기 신청보다 먼저 `directory_unavailable`로 판정합니다.
- **mock 저장소.** 신청은 grants 파일 옆의 `requests.json`(grants 경로에서 파생)에 둡니다. 기존 grants 파일 형식을 바꾸지 않기 위해서입니다. 같은 lock, 원자적 교체, 손상 시 503 규칙을 그대로 따릅니다. 승인은 두 파일을 grant부터 씁니다. 그 사이에 중단되면 신청이 남지만, 다시 승인해도 무해합니다.
- **office 저장소.** 승인·거절·팀 승인은 `WATCH requests` → `request_id` 비교 → `MULTI` → `EXEC`입니다. `WatchError`는 `STORE_ERRORS`보다 안쪽에서 먼저 잡습니다. 그 사번의 신청 원문이 바뀌었으면 409, 아니면 재시도합니다. "최대 3회 재시도"는 첫 시도 + 재시도 3회(총 4회)로 해석했고, 모두 실패하면 503 `store_unavailable`(저장되지 않음)입니다.
- **신청 API.** body가 잘못되면 400이고, 사유는 앞뒤 공백을 지운 뒤 1~200자입니다. 이미 `granted`이면 200 `{verdict: "granted"}`로 아무것도 쓰지 않습니다. directory나 저장소 장애 중에는 신청을 받지 않습니다(503). 소속이 없는(absent) 사람도 신청할 수 있고 `dept_nm`은 null입니다.
- **재신청과 상태.** 거절된 신청은 `rejected`로 남고, 재신청하면 새 `request_id`로 `pending`이 됩니다. 관리자 목록 응답은 pending과 rejected를 모두 내려 주고, 화면이 pending만 보여 줍니다.
- **팀 전체 승인.** 저장된 `dept_nm`이 같은 **pending** 신청만 지우고, rejected 신청은 남깁니다. 응답에 지운 사번 목록(`cleared`)을 담습니다.
- **감사 기록.** 기존 `_audit` 한 줄에 `access_request_id` 필드를 덧붙였습니다. 결과는 `ok`, `request_changed`, `store_unavailable`이고, 팀 승인은 `ok cleared=<사번들>`입니다.
- **activity 로그.** `/api/tool-files/requests`는 tool slug가 없어 fallback이 대시가 들어간 `tool-files` slug를 만들었습니다. 그래서 `_logging/feature_map.py`에 `/api/tool-files` → `tool_files` 규칙을 추가했습니다.
- **프론트엔드.** `toolFilesErrorCode`를 composable에서 `utils/toolFiles.ts`로 옮겨 순수 함수 테스트를 붙였습니다. 응답 없이 실패하면 `no_response`가 되어 "결과를 확인할 수 없습니다. 새로고침해 주세요."를 보여 줍니다. access 조회 자체가 실패했을 때의 안내는 "권한 없음"에서 저장소 장애 문구로 바꿨습니다. 409를 받으면 관리자 목록을 새로 읽어 바뀐 신청을 바로 보여 줍니다.
- **office 확인 항목.** 실제 Redis 연결 두 개로 재현하는 경쟁 상황은 MIGRATION.md "Verify at the office"에 넣었습니다.
