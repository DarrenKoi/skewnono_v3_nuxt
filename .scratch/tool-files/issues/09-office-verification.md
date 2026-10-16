# 09: office 실기 확인

**What to build:** 집에서 확인할 수 없는 부분을 office에서 실제 장비, 실제 Redis, 실제 proxy로 확인합니다. 그 결과를 스펙, MIGRATION.md, mock의 `OFFICE-VERIFY` 표시에 반영합니다.

**Blocked by:** 02, 03, 04, 05, 06

**Status:** ready-for-human

- [ ] 반영 순서를 지킵니다. flask_modules push → scheduler1 webapp pull·재시작 → SKEWNONO pull → tool_files `office_example.py` 복사
- [ ] Phase 3 direct와 Phase 2 proxy 각각에서, 계열별 장비 하나 이상을 대상으로 읽기 전용 확인을 합니다. LIST 형식, 숨김 파일, 로그인 홈, 인코딩(깨진 파일명 다운로드), 다운로드, 상한, deadline, 저장된 파일명을 봅니다. Python 3.11에서 실행합니다
- [ ] scheduler1 webapp의 실제 harakiri와 ingress timeout을 확인하고, proxy deadline 45 s가 적절한지 판단합니다
- [ ] 상한 기본값(100 MB, 120 s, 20000줄, 4 MB)이 실제 로그와 레시피 크기에 맞는지 확인합니다
- [ ] 실제 Redis에 연결 두 개를 열고 경쟁 상황을 재현합니다. 승인 ↔ 재신청, 거절 ↔ 재신청, 팀 승인 ↔ 개인 승인·재신청입니다
- [ ] 회귀 확인: 기존 msr_image 이미지 조회와 recipe_search 원본 조회가 Phase 2 proxy와 Phase 3에서 여전히 동작하는지 봅니다
- [ ] 실제 장비 폴더 구조를 mock 트리와 datatables 문서에 반영합니다. 두 곳을 함께 바꿉니다
- [ ] **쓰기 플래그를 켜기 전 조건**을 확인하고 결과를 기록합니다. 기존 대상이 있을 때 RNTO가 거절되는지, 서버 측 쓰기 범위 제한(chroot 또는 계정 권한)이 있는지를 계열별로 봅니다. 확인했다고 해서 바로 켜지는 않습니다
