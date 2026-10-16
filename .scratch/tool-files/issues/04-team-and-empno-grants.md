# 04: 팀·사번 승인 저장소와 판정

**What to build:** 관리자가 `/admin/access`의 새 섹션에서 팀(`dept_nm`)이나 사번에 접근 권한을 주고 회수합니다. 팀은 실제 구성원 디렉터리에서 고르고, 사번은 직접 입력합니다. 승인된 팀의 구성원이나 승인된 사번은 신청 없이 바로 탐색기를 씁니다.

**Blocked by:** 02 (관리자 전용 파일 탐색기)

**Status:** ready-for-agent

- [ ] 권한 판정을 순수 함수로 구현하고 스펙의 판정 표를 그대로 따릅니다. `untrusted_identity`, admin, `store_unavailable`, 사번 승인, `probe_member`(unavailable, found+dept_nm, absent 각각) 순서입니다. `lookup_member`는 쓰지 않습니다
- [ ] grant 저장소의 mock은 JSON 파일입니다. mtime 갱신과 원자적 교체를 쓰며, 파일이 손상되거나 읽을 수 없으면 503을 냅니다. office template은 Redis HASH를 쓰고, 장애는 `error_json`의 503으로 변환합니다
- [ ] 저장소와 FTP는 하나의 provider 선택이 함께 결정합니다. office tool_files를 `validate_env()`에 등록해서 다음 경우에 부팅을 거부합니다: sem_list와 짝이 맞지 않을 때, 전역 mode가 office가 아닐 때, Redis 설정이 없을 때
- [ ] mock directory 대역은 사번별로 found·absent·unavailable을 돌려줍니다. 여러 팀 구성원과 dept_nm이 없는 부분 프로필을 포함합니다. 기존 `probe_member`의 동작은 바꾸지 않습니다
- [ ] 관리자 API를 만듭니다: 목록, 팀 목록, grant 추가, 회수. 대상은 JSON body로 받고, `granted_by`는 서버 identity로 채웁니다
- [ ] 팀 목록은 HSCAN으로 읽고 empno로 중복을 제거합니다. 600초 캐시를 두고, 읽을 수 없는 행이 있으면 `complete: false`를 냅니다. 장애는 503입니다
- [ ] `/admin/access` 섹션에 팀 승인(인원수 포함, `complete: false`일 때는 0명 경고를 끔), 개인 승인, 회수를 둡니다. 개인 승인을 회수해도 팀 승인이 남아 있으면 접근이 유지된다는 점을 화면에 표시합니다
- [ ] 승인·회수는 수행자, 대상, 결과, request_id를 `logger.info`로 기록합니다
- [ ] HTTP 테스트로 판정 표 전체를 확인합니다: admin, 사번, 팀, absent, 팀 없음, declared·token·anonymous, directory unavailable, 저장소 손상. 회수 뒤 직접 URL로 접근하면 거부되어야 합니다
- [ ] provider 계약 테스트는 access_control 선례를 따릅니다. office template을 직접 import하고 bytes를 돌려주는 FakeRedis를 씁니다
- [ ] 부팅 거부 테스트 3종을 작성합니다
- [ ] `browser-verify` 스킬로 관리자 섹션에서 팀과 사번을 승인한 뒤, 다른 identity로 들어갈 수 있는지 확인합니다
