# tttm / pm-tune 수집 기간(window) 스펙

사용자 요청 원문(2026-08-25 ~ 26). 이 두 메시지가 스펙의 전부입니다.

1. "in tttm, pm-tune pages, we have to enlarge the data gathering. 1 week
   window is too short. let's enlarge it to be 3 weeks."
2. (같은 턴, 직후) "or make it selectible. 1w, 2w, 3w."
3. (다음 턴) "then, keep 2주 as default. and user can decide from
   1주|2주|3주|4주"

## 해석 (구현자가 확정한 가정)

- "data gathering" 은 두 페이지의 payload 를 계산할 때 되짚는 측정 run 의
  기간입니다. 이전에는 UI 라벨만 "1주 윈도우" 였고 서버는 고정 창(tttm 60일 /
  pm_planning 30일)에서 장비당 10 / 8 run 만 열었습니다.
- 선택 가능한 창은 두 페이지가 공유하는 하나의 설정입니다 (두 페이지는 같은
  비교 대상 scope 를 공유합니다).
- 최종 상태: 선택지 1|2|3|4 주, 기본 2주. 서버는 그 밖의 값을 400 으로
  거절합니다.
- 창을 넓히면 실제로 더 많은 run 이 모여야 합니다 — office adapter 의 장비당
  run 상한이 창과 함께 커져야 합니다.
- recipe picker(`/tttm/recipes`) 도 같은 창으로 계산됩니다.
