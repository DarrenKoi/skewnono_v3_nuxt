# 담당자·임원 두 audience 가 같은 URL 을 공유합니다

Device statistics 페이지는 [[audiences]] 두 종류 — 담당자(operator) 와 임원(executive) — 를 모두 first-class 로 섬기되, **두 audience 가 같은 URL 을 공유** 합니다. role 별 tab 분리 / 별도 IA / 별도 URL 모두 채택하지 않았습니다. 이유는 단순합니다: 담당자가 "이 lot 좀 봐달라" 며 임원에게 link 를 forward 하는 흐름이 일상적이고, 이때 양쪽이 *같은 화면을 보지 못하면* evidence artifact 의 의미가 깨집니다.

## 고려된 대안

- **Hide-by-tab IA** — 같은 데이터를 "담당자 보기 / 임원 보기" 두 tab 으로 분리. role 별 정보 밀도를 다르게 줄 수 있어 매력적이나, forward 된 link 가 어느 tab 으로 열리느냐에 따라 임원이 담당자가 보던 view 를 못 보거나, 그 반대. tab 상태를 URL query 에 박더라도 "왜 임원이 담당자 화면을 봐야 하나" 라는 1차 인지 비용이 매번 발생.
- **별도 페이지 분리** (예: `/device-statistics/operator` / `/device-statistics/executive`) — URL 자체가 다르므로 forward 시 audience 가 잘못 도착할 수 있고, 동시 변경이 어려움 (두 페이지 동기화 부담).
- **Role-aware 자동 분기** — 로그인 role 에 따라 다른 화면. forward 가능하나 임원이 담당자의 lot 을 *담당자의 시점* 으로 본다는 use case 가 깨짐.

## 결과로 따라오는 제약

- 한 페이지 안에서 두 audience 의 dominant scan path 가 *공존* 해야 함 — 임원은 zone ② 의 *분포 한 눈* 을 보고 (zoom-out 시에도 신호등 색 패턴이 보여야), 담당자는 zone ② 의 *행 내부 stacked bar* 를 가까이서 읽음. Q5 의 soft tint 결정이 이 dual-scan 을 한 디자인 손잡이로 풀어 낸 사례.
- "임원만 보이는" 또는 "담당자만 보이는" surface 를 만들 수 없음 — forward 시 깨지므로. 모든 surface 가 양 audience 에게 의미 있어야.
- Bucket / scope / focused lot 등 lens 가 *URL query 에 박혀야* forward 시 같은 해석 frame 으로 열림 — [[bucket]] 정의의 "URL-stateful & audience-shared" 속성이 여기서 유래.

## 되돌리기 어려운 이유

URL forwarding 행동은 *조직 문화* — 한 번 자리 잡으면 페이지가 바뀌어도 link 가 계속 돌아다닙니다. 나중에 audience 별 페이지로 분리하면 기존 forward 된 link 가 일제히 *오답 페이지* 로 도착하게 되고, 사용자는 "왜 이게 안 보이지?" 라는 마찰을 페이지 단위가 아니라 *링크 단위로* 겪습니다.
