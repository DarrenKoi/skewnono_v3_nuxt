# 05 — 브라우저 확인 (두 화면)

Status: open
Spec: [`../spec.md`](../spec.md)
Blocked by: 02, 03

자동 E2E 가 없는 저장소입니다. `verify` 스킬로 Flask(:5050) + Nuxt(:3000) 를
띄우고 손으로 확인합니다.

이 스펙이 `lot-outlier-merge` 와 다른 점은 **화면이 둘**이라는 것입니다.
`DrillSlideover` 를 고치는 순간 measurement-rules 가 범위에 들어옵니다 (결정 D2).
그 화면에는 하네스가 없으므로, 여기서 안 보면 아무도 안 봅니다.

## A. device-statistics — `/ebeam/cd-sem/device-statistics/comparison`

- [ ] 표의 outlier 배지가 새 토큰 색으로 보인다 (라이트)
- [ ] 배지에 마우스를 올리면 색이 **눈에 띄게** 변한다 (라이트) — 티켓 01 의
      hover 값이 너무 미묘하면 여기서 드러납니다
- [ ] 다크 모드에서 위 둘을 반복
- [ ] 배지를 눌러 연 모달의 초과 표시가 표의 배지와 **같은 계열**로 보인다
      (이 스펙이 없애려던 두 종류 빨강이 사라졌는지)
- [ ] 카드를 펼쳤을 때 파라미터 행이 이전과 같은 모양이다 (공유 컴포넌트로
      바뀌었지만 폭 `w-16`/`w-28`, `max-w-2xl` 이 유지되는지)
- [ ] `분석 제외` 배지의 문구와 tooltip 이 그대로다
- [ ] 콘솔 오류·경고 0건

## B. measurement-rules — cap 위반 슬라이드오버

- [ ] 위반이 있는 device 의 슬라이드오버가 열린다
- [ ] 초과 배지가 `--sk-bad` 계열로 보인다 (rose → 토큰 전환은 **의도된 변화**)
- [ ] 배지 크기가 이전과 같다 (`sk-badge-lg` — 슬라이드오버는 뷰포트 80% 라
      카드보다 큰 글자를 씁니다. 공유하면서 작아지지 않았는지)
- [ ] 왼쪽 4px 초과 띠가 남아 있다 (`DrillSlideover:30-34`)
- [ ] 파라미터 행 tint 가 flagged 행에만 있다
- [ ] 다크 모드 반복
- [ ] 콘솔 오류·경고 0건

## 스크린샷

`.playwright-mcp/screenshots/` 아래에 저장합니다 (`CLAUDE.md`). 두 화면의
라이트·다크 4장이 최소치입니다.
