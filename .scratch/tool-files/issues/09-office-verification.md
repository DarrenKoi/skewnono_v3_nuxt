# 09: office 실기 확인

**What to build:** 집에서 확인할 수 없는 부분을 office에서 실제 장비, 실제 Redis, 실제 proxy로 확인합니다. 그 결과를 스펙, MIGRATION.md, mock의 `OFFICE-VERIFY` 표시에 반영합니다.

**Blocked by:** 02, 03, 04, 05, 06, 08 (모두 done)

**Status:** ready-for-human

아래 순서대로 진행합니다. 각 단계 끝의 질문 번호(Q1…)는 맨 아래 답안지와 짝입니다. 답안지만 채워서 돌려주면 집에서 mock·문서·스펙에 반영합니다.

## 0. 반영 (순서 고정)

- [ ] flask_modules를 scheduler1 webapp 호스트에서 `git pull`하고 webapp을 재시작합니다
- [ ] `python -m scripts.verify.check_ftp_proxy`로 proxy가 살아 있는지 봅니다. `POST /list_details_sknn_v3`가 404가 아니어야 합니다 (Q1)
- [ ] SKEWNONO를 `git pull`합니다. 클라우드와 Windows PC 모두에서 `cp backend/ebeam/tool_files/providers/office_example.py backend/ebeam/tool_files/providers/office.py`
- [ ] 부팅 로그에 `tool_files ... office`가 나오고, 부팅 거부가 없는지 봅니다 (Q2)
- [ ] 클라우드와 Windows PC의 Flask 버전이 3.1 이상인지 봅니다: `python -c "import importlib.metadata as m; print(m.version('flask'))"`. 업로드가 요청별 `max_content_length`를 쓰므로 3.0이면 업로드만 500이 납니다 (Q25)

## 1. Phase 3 클라우드: 읽기

관리자(2067928)로 진행합니다. 계열마다(CD-SEM, HV-SEM) 장비 하나씩 고릅니다.

- [ ] `스토리지` 또는 `장비 리스트` 행의 "파일 열기"로 탐색기에 들어갑니다
- [ ] 로그인 폴더 경로를 적습니다 (Q3, Q4)
- [ ] 하위 폴더를 열고, 숨김 파일(`.`으로 시작)이 보이는지 봅니다 (Q5)
- [ ] 한글이 들어간 파일 이름이 어떻게 보이는지 보고, 그 파일을 받아 저장된 이름을 봅니다 (Q6). `tool_encoding` 오류가 나오면 `SKEWNONO_TOOL_FTP_ENCODING=latin-1`이 빠진 것입니다
- [ ] 작은 파일 하나를 받아 열어 봅니다 (Q7)
- [ ] 100 MB가 넘는 파일의 버튼이 비활성인지, 가장 큰 로그·레시피 파일 크기를 적습니다 (Q8)
- [ ] 파일이 가장 많은 폴더의 항목 수를 적습니다 (Q9)

## 2. 승인·신청 (클라우드)

- [ ] `/admin/access`의 장비 파일 접근 섹션에서 팀 목록이 뜨고 경고(일부 못 읽음)가 없는지 봅니다 (Q10)
- [ ] 우리 팀 이름의 표기와 인원수가 맞는지 봅니다 (Q11)
- [ ] 다른 사람(일반 사용자)에게 탐색기 URL을 열어 달라고 하고 신청 카드가 보이는지, 신청 → 관리자 승인 → 새로고침 뒤 목록이 열리는지 봅니다 (Q12)
- [ ] 그 사람의 개인 승인을 회수하면 다음 요청부터 거부되는지 봅니다 (Q13)
- [ ] 활동 로그(OpenSearch)에 신청·승인 줄이 남는지 봅니다 (Q14)

## 3. Redis 경쟁 (클라우드 또는 Phase 2, Redis에 닿는 곳)

- [ ] `python -m scripts.verify.check_tool_files_races`를 실행합니다. 실제 키는 건드리지 않고 `skewnono:tool_files:racecheck:*`만 쓰고 지웁니다. 다섯 줄이 모두 `ok`이고 마지막이 `5/5 scenarios passed`여야 합니다 (Q15)

## 4. Phase 2 Windows PC: proxy 읽기

- [ ] 1단계의 목록 보기와 다운로드를 장비 하나로 다시 합니다 (Q16)
- [ ] 화면에 업로드·삭제가 보이지 않는지 봅니다 (Q17)
- [ ] scheduler1 webapp의 harakiri와 앞단 timeout 값을 적습니다. proxy deadline 45 s는 harakiri 60 s를 가정한 값입니다 (Q18)
- [ ] 크기가 큰 파일(수십 MB)을 받아 45 s 안에 끝나는지, 넘으면 "장비 응답이 너무 느려" 안내(503)가 나오는지 봅니다. proxy 502가 나오면 실패입니다 (Q19)

## 5. 회귀

- [ ] Phase 3와 Phase 2 양쪽에서 측정 이미지(msr_image)와 recipe_search 원본 보기가 그대로 되는지 봅니다 (Q20)

## 6. 쓰기 플래그 전제 (확인만, 켜지 않음)

`MIGRATION.md`의 "플래그를 켜기 전 확인할 조건"을 계열마다 봅니다. 장비 FTP에 직접 접속해서 확인하는 항목이라, 장비 담당자와 함께 테스트 폴더에서만 합니다.

- [ ] 대상 이름에 파일이 있을 때 RNTO가 거절되는지 (Q21)
- [ ] 없는 파일에 SIZE를 보내면 550인지 (Q22)
- [ ] 계정이 로그인 폴더 밖에 쓸 수 없게 막혀 있는지 (Q23)
- [ ] 한글 이름 업로드가 필요한지 (Q24)

## 7. 결과 반영 (집에서)

- [ ] 답안지를 받아 mock 트리·`_MEMBERS`·상한 기본값·proxy deadline을 고치고, `docs/datatables`와 mock을 함께 바꿉니다
- [ ] `OFFICE-VERIFY` 표시를 `office 확인 YYYY-MM-DD`로 바꿉니다
- [ ] 쓰기 플래그를 켤지 결정합니다 (Q21–Q24가 모두 A일 때만)

## 답안지

A = 집의 가정이 맞음, B = 다름(옆에 한 줄 메모), ? = 확인 못 함. 값을 묻는 문항은 예시 형식으로 적습니다.

| Q | 질문 | 답 |
| :-- | :-- | :-- |
| 1 | proxy 새 라우트가 404가 아님 | |
| 2 | 부팅 로그에 tool_files office, 부팅 거부 없음 | |
| 3 | CD-SEM 로그인 폴더 (예: `/`) | |
| 4 | HV-SEM 로그인 폴더 (예: `/home/hitachi`) | |
| 5 | 숨김 파일이 목록에 보임 | |
| 6 | 한글 파일명이 깨져 보이지만 받기는 됨 | |
| 7 | 받은 파일 내용이 정상 | |
| 8 | 가장 큰 로그·레시피 크기 (예: `log 40MB, rcp 2MB`) | |
| 9 | 가장 많은 폴더의 항목 수 (예: `12000`) | |
| 10 | 팀 목록이 뜨고 일부 못 읽음 경고 없음 | |
| 11 | 우리 팀 표기와 인원수가 맞음 (표기 예: `계측기술팀`) | |
| 12 | 신청 → 승인 → 목록 열림 | |
| 13 | 회수 뒤 거부 | |
| 14 | 신청·승인 활동 로그가 남음 | |
| 15 | 경쟁 스크립트 5/5 | |
| 16 | Phase 2 proxy 목록·다운로드 | |
| 17 | Phase 2에서 업로드·삭제 안 보임 | |
| 18 | harakiri / 앞단 timeout (예: `60s / 60s`) | |
| 19 | 큰 파일이 45 s 안이거나 503 안내 (502 아님) | |
| 20 | msr_image·recipe_search 회귀 없음 | |
| 21 | 기존 대상에 RNTO 거절 | |
| 22 | 없는 파일 SIZE = 550 | |
| 23 | 로그인 폴더 밖 쓰기 막힘 | |
| 24 | 한글 이름 업로드 불필요 | |
| 25 | Flask 버전, 클라우드 / Windows PC (예: `3.1.3 / 3.1.2`) | |
