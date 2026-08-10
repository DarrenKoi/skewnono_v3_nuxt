# 06 — 브라우저 검증 및 마무리

Status: open
Plan: [`../plan.md`](../plan.md)
Blocked by: 04, 05

이 저장소에는 E2E 스위트가 없습니다 — Playwright 설정도, spec 파일도, 컴포넌트
마운팅 하네스도 없습니다. 그래서 화면 변경의 마지막 게이트는 사람이(또는
Playwright MCP가) 실제로 띄워 보는 것입니다. 특히 **워크북 다운로드는 단위
테스트가 닿지 않는 경로**라(`document`, `URL.createObjectURL`) 여기서 처음이자
유일하게 검증됩니다.

**Files:**

- Modify: `.scratch/equipment-tab-simplify/spec.md` (Status 갱신)

---

- [ ] **Step 1: 앱을 띄운다**

`verify` 스킬의 절차를 따릅니다. 요약하면 저장소 루트에서:

```bash
.venv/bin/python index.py                 # Flask :5050
```

그리고 워크트리의 `front-dev-home/`에서:

```bash
npm run dev                               # Nuxt :3000
```

`/api/*`는 사용자당 5초에 20요청으로 제한되므로 새로고침을 몰아치지 않습니다.

- [ ] **Step 2: TAT 탭을 확인한다**

`http://localhost:3000/ebeam/cd-sem/M14/recipe-status?tab=tat` → 장비별.

확인 항목:

- 표 헤더가 `eqp_id · fab · model · 실행수 · 총 TAT · 평균 · 레시피수` 뿐이다
  (점유율·TAT index·신호 없음).
- 표 위에 다중 fab 경고 배너가 없다.
- 정렬 가능한 네 열이 오름/내림 모두 정상 동작한다.
- 장비 2대를 체크하면 칩이 `측정 N · 레시피 M · 총 …` 형태로 뜬다.
- 트렌드 차트와 레시피 매트릭스가 그대로 뜬다.
- 매트릭스에 CSV 버튼이 없고 복사 버튼은 있다.

- [ ] **Step 3: TAT Excel 파일을 연다**

`Excel` 버튼을 눌러 받은 파일을 열고 확인합니다:

- 시트가 `장비`·`레시피`·`일별추이` 셋이다.
- `일별추이`의 행 수 = 조회 기간의 날짜 수(헤더 제외).
- `레시피`의 장비 열 개수 = 선택한 장비 수 × 3.
- 어느 시트에도 지수·신호 열이 없다.

그다음 **선택을 모두 해제하고** 다시 `Excel`을 누릅니다 → 시트가 `장비`
하나뿐이어야 합니다. 이전 선택의 레시피 시트가 남아 있으면
`comparePayload` 초기화 watch가 동작하지 않은 것입니다.

- [ ] **Step 4: Align/Meas 탭을 확인한다**

`?tab=align`과 `?tab=meas` 각각에서 Step 2·3을 반복합니다. 추가 확인:

- 표에 `fail index`·`신호` 열이 없고 `fail율`은 있다.
- 축을 바꾸면(align ↔ meas) 파일명의 축 부분과 시트의 열 이름이 함께 바뀐다.
- `meas` 탭에서 받은 파일에 `align_*` 열이 하나도 없다.

- [ ] **Step 5: 기존 내보내기 무회귀 확인**

티켓 01이 `recipeCompare`·`recipeParamExport`의 부트스트랩을 갈아끼웠으므로,
그쪽 내보내기가 여전히 동작하는지 한 번 봅니다 — 레시피 비교 화면에서 워크북을
받아 열어보고, 시트 구성과 이미지 블록이 이전과 같은지 확인합니다. 이 경로도
단위 테스트가 닿지 않습니다.

- [ ] **Step 6: 콘솔 확인**

브라우저 콘솔에 에러가 없어야 합니다. Vue의 "Extraneous non-emits event
listener" 경고가 뜬다면 `@loaded`를 받는 컴포넌트에 `defineEmits`가
빠진 것입니다.

- [ ] **Step 7: 스펙 상태를 갱신한다**

`.scratch/equipment-tab-simplify/spec.md`의 `Status: spec`을
`Status: shipped`로 바꾸고, 검증 절에 확인 날짜를 적습니다.

- [ ] **Step 8: main 에 올리고 워크트리를 정리한다**

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git merge --ff-only work/equipment-tab && git push
git worktree remove ../skewnono-equipment-tab
git branch -d work/equipment-tab
git worktree list        # 메인 트리 하나만 남아야 합니다
```

`--ff-only`가 거절되면 그 사이 `main`이 움직인 것입니다. 그때는 워크트리에서
`git merge origin/main`으로 먼저 합치고, **합친 뒤 테스트를 다시 돌립니다** —
깨끗한 자동 병합이 깨진 코드를 만들 수 있고 그 경우 테스트만이 알려줍니다.
