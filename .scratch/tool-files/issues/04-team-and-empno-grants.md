# 04: 팀·사번 승인 저장소와 판정

**What to build:** 관리자가 `/admin/access`의 새 섹션에서 팀(`dept_nm`)이나 사번에 접근 권한을 주고 회수합니다. 팀은 실제 구성원 디렉터리에서 고르고, 사번은 직접 입력합니다. 승인된 팀의 구성원이나 승인된 사번은 신청 없이 바로 탐색기를 씁니다.

**Blocked by:** 02 (관리자 전용 파일 탐색기)

**Status:** done (2026-10-17)

- [x] 권한 판정을 순수 함수로 구현하고 스펙의 판정 표를 그대로 따릅니다. `untrusted_identity`, admin, `store_unavailable`, 사번 승인, `probe_member`(unavailable, found+dept_nm, absent 각각) 순서입니다. `lookup_member`는 쓰지 않습니다
- [x] grant 저장소의 mock은 JSON 파일입니다. mtime 갱신과 원자적 교체를 쓰며, 파일이 손상되거나 읽을 수 없으면 503을 냅니다. office template은 Redis HASH를 쓰고, 장애는 `error_json`의 503으로 변환합니다
- [x] 저장소와 FTP는 하나의 provider 선택이 함께 결정합니다. office tool_files를 `validate_env()`에 등록해서 다음 경우에 부팅을 거부합니다: sem_list와 짝이 맞지 않을 때, 전역 mode가 office가 아닐 때, Redis 설정이 없을 때
- [x] mock directory 대역은 사번별로 found·absent·unavailable을 돌려줍니다. 여러 팀 구성원과 dept_nm이 없는 부분 프로필을 포함합니다. 기존 `probe_member`의 동작은 바꾸지 않습니다
- [x] 관리자 API를 만듭니다: 목록, 팀 목록, grant 추가, 회수. 대상은 JSON body로 받고, `granted_by`는 서버 identity로 채웁니다
- [x] 팀 목록은 HSCAN으로 읽고 empno로 중복을 제거합니다. 600초 캐시를 두고, 읽을 수 없는 행이 있으면 `complete: false`를 냅니다. 장애는 503입니다
- [x] `/admin/access` 섹션에 팀 승인(인원수 포함, `complete: false`일 때는 0명 경고를 끔), 개인 승인, 회수를 둡니다. 개인 승인을 회수해도 팀 승인이 남아 있으면 접근이 유지된다는 점을 화면에 표시합니다
- [x] 승인·회수는 수행자, 대상, 결과, request_id를 `logger.info`로 기록합니다
- [x] HTTP 테스트로 판정 표 전체를 확인합니다: admin, 사번, 팀, absent, 팀 없음, declared·token·anonymous, directory unavailable, 저장소 손상. 회수 뒤 직접 URL로 접근하면 거부되어야 합니다
- [x] provider 계약 테스트는 access_control 선례를 따릅니다. office template을 직접 import하고 bytes를 돌려주는 FakeRedis를 씁니다
- [x] 부팅 거부 테스트 3종을 작성합니다
- [x] `browser-verify` 스킬로 관리자 섹션에서 팀과 사번을 승인한 뒤, 다른 identity로 들어갈 수 있는지 확인합니다

## Comments

- 판정은 `backend/ebeam/tool_files/access.py`의 `decide(source, empno, grants, probe)`입니다. 승인 목록과 directory를 둘 다 callable로 받아 필요한 행에서만 읽습니다. 그래서 관리자는 저장소 장애 중에도 들어가고, 사번 승인은 directory를 부르지 않습니다.
- mock 저장소는 mtime 캐시 없이 매 호출 파일을 읽습니다. 작은 JSON이고, 워커 간 전파라는 목적은 캐시 없이도 같기 때문입니다. 쓰기는 같은 폴더의 임시 파일 + `os.replace`입니다.
- `GET /api/admin/tool-files`는 지금 `{grants}`만 돌려줍니다. `requests`는 05에서 붙습니다. 개인 승인 행에는 directory가 아는 현재 `dept_nm`이 실려, 화면이 "팀 승인으로 유지"를 표시합니다.
- anonymous 출처는 identity 게이트가 라우트보다 먼저 401을 내므로, 판정 단위 테스트에서만 확인합니다. declared·token은 `resolve_identity` monkeypatch로 HTTP까지 확인했습니다.
- 감사 로그의 request_id는 activity middleware가 둔 `g._activity_request_id`입니다.
- 부팅 거부는 `_runtime/data_provider.py`의 `_OFFICE_NEEDS_OFFICE_MODE_AND_REDIS`에 tool_files를 등록하는 방식입니다. sem_list 짝은 02의 `_OFFICE_DEPENDENCIES` 등록으로 이미 막혀 있었습니다.
- 브라우저 확인(:5051/:3001): 팀 목록(계측기술팀 2명, 공정기술팀 1명)에서 팀 승인, 사번 2건 승인, "팀 승인으로 유지" 배지 표시. 1000002(팀) 목록 열림, 1000003(사번) 열림 → 회수 뒤 거부, 1000004(dept 없음)·7777777(absent) 거부, 1000005는 "구성원 정보를 확인하지 못했습니다". console 오류 0건.
