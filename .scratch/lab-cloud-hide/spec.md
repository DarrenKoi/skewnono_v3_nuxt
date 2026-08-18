# 실험실 페이지 프로덕션 숨김 (lab-cloud-hide)

작성 2026-08-19. 요구사항은 대화에서 확정되었으며, 아래는 사용자가 말한 내용을
그대로 옮긴 것입니다. 구현 diff 에서 역으로 유추한 항목은 없습니다.

## 배경

TTTM(`/tttm`) 과 PM-Tune(`/pm-tune`) 은 실험실(lab) 메뉴에 있는 페이지입니다.
두 페이지의 추정기가 아직 검증되지 않아, 프로덕션 배포본에서 일반 사용자에게
노출되는 것을 원하지 않습니다.

## 사용자가 요구한 것

1. **프로덕션(클라우드 배포)에서 두 페이지를 숨긴다.**
   > "the pages 'tttm', 'pm-tune' can be hidden in the production mode (cloud
   > deployed)? ... I think the pages need to be tested more before deployed."

2. **`office.py` 삭제로 숨기는 방식은 채택하지 않는다.** 사용자가 그 방법을
   물었고, provider 폴백 때문에 숨김이 아니라 가짜 데이터 노출이 된다는 설명을
   듣고 철회했습니다.

3. **판정 기준은 `is_cloud()` 다.**
   > "is_cloud() 기반은 좋은 것 같은데"

   따라서 Phase 1 (home) 과 Phase 2 (사내 localhost) 에서는 계속 보여야 합니다.

4. **`is_admin` 게이팅은 넣지 않는다.**
   > "is_admin은 없어도 좋아."

5. **URL 직접 접근은 계속 허용한다.** 라우트를 막으면 안 됩니다.
   > "url을 아는 사람들은 들어와서 봐도 돼 (파워 유저, 베타테스터)."
   > "still I want to see the page via the urls. no problem some users can visit."

6. **실험실 페이지 단위의 open/hidden 옵션이어야 한다.** TTTM·PM-Tune 전용
   하드코딩이 아니라, 실험실의 각 페이지가 켜고 끌 수 있는 축이어야 합니다.
   > "make sure to have open / hidden options for pages in 실험실. for now,
   > pm-tune and tttm can be hidden."

## 범위 밖

- 백엔드 라우트 차단 (`/api/tttm/*` 등) — 요구사항 5 와 정면으로 충돌합니다.
- 리다이렉트 미들웨어 (`afm-hidden.global.ts` 같은 것) — 같은 이유입니다.
- `providers/office.py` 관련 변경 일체.
- 두 페이지 자체의 로직·UI 변경.

## 제약

- SPA 는 `ssr: false` 이므로 `runtimeConfig.public` 은 빌드 시점에 고정됩니다.
  사무실에서 빌드한 산출물이 그대로 클라우드로 가므로(`scripts/deploy/pack.py`),
  빌드 타임 플래그는 매 pack 마다 기억해야 하는 절차가 됩니다.
- `/api/health/providers` 는 `@require_admin` 입니다. 관리자만 올바르게 보이는
  메뉴는 목적에 맞지 않습니다.
