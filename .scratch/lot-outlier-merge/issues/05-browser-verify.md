# 05 — 브라우저 확인 · 병합 · 워크트리 정리

Status: resolved
Plan: [`../plan.md`](../plan.md) · Spec: [`../spec.md`](../spec.md)
Blocked by: 04

자동 E2E 가 없는 저장소입니다 (Playwright 설정도 spec 파일도 컴포넌트 마운트
하네스도 없습니다). 화면으로 확인하는 것이 이 변경의 유일한 통합 테스트이므로,
확인 항목을 티켓으로 둡니다.

**Files:** 없음 (문서 갱신 제외)

---

- [ ] **Step 1: 앱을 띄운다**

`verify` 스킬의 절차를 씁니다. 요지는 Flask(:5050) 와 Nuxt(:3000) 를 각각 띄우고
`LASTUSER=local-dev` 로 접속하는 것입니다.

```bash
cd /Users/daeyoung/Codes/skewnono-lot-outlier-merge
.venv/bin/python index.py                 # 없으면 본체의 .venv 를 씁니다
cd front-dev-home && npm run dev
```

화면이 통째로 비고 콘솔이 조용하면 Flask 가 죽은 것입니다 — 컴포넌트를
의심하기 전에 :5050 을 먼저 보십시오.

- [ ] **Step 2: 확인 목록**

`/ebeam/cd-sem/device-statistics/comparison` 에서 device 를 하나 골라
Lot 요약까지 내려갑니다.

| # | 확인 | 기대 |
| --- | --- | --- |
| 1 | 행(또는 카드) 클릭 | 모달이 **전체** 로 열리고 스텝이 공정순으로 나옵니다 |
| 2 | 초과가 있는 스텝 | rose `초과 N` 배지가 보입니다 |
| 3 | 그 카드 클릭 | 파라미터 이름 · point_count · `> N` 꼬리표가 펼쳐집니다 |
| 4 | 파라미터가 0 인 스텝 | 눌러도 펼쳐지지 않고 chevron 도 없습니다 |
| 5 | 헤더 | `과다 측정 N` 과 `중앙값 · > 문턱` 이 보입니다 |
| 6 | 헤더의 N | 표의 outlier 배지 숫자와 **같습니다** |
| 7 | `초과만` 칩 | 초과 카드만 남고, `N건` 이 그 수로 바뀝니다 |
| 8 | `전체` 칩 | 원래 목록으로 돌아옵니다 |
| 9 | 초과가 없는 lot | 필터 칩이 아예 없습니다 |
| 10 | 모달을 닫고 표의 outlier 배지 클릭 | **같은 모달**이 `초과만` 으로 열립니다 |
| 11 | 슬라이드오버 | 이 페이지에서 더 이상 열리지 않습니다 |
| 12 | `초과만` 상태에서 CSV | `..._params_flagged.csv`, 행 수가 버튼 옆 `N행` 과 같습니다 |
| 13 | `전체` 상태에서 CSV | `..._params.csv`, 전체 행 |
| 14 | 클립보드 복사 | 화면에 보이는 스텝만 붙여넣어집니다 |
| 15 | 버킷 전환 | 모달이 닫힙니다 |
| 16 | 정렬 칩 `recipe 이름` | 카드 순서가 바뀌고 펼침 상태가 카드를 따라갑니다 |
| 17 | 다른 lot 열기 | 펼침이 모두 접힙니다 |
| 18 | 다크 모드 | 배지·펼침 배경이 모두 읽힙니다 |

- [ ] **Step 3: grain 회귀를 직접 본다**

가장 조심할 항목입니다 (D2). 같은 `recipe_id` 가 스텝 두 곳에 걸린 lot 을
찾습니다 — 집의 mock 이 이 경우를 일부러 만듭니다
(`back_dev_home/ebeam/device_statistics/providers/recipe_population.py`
`_apply_shared_recipes`).

확인:

- 카드가 **두 장 다 남아 있습니다** (한 장으로 접히면 `:key` 가 잘못된 것입니다)
- 두 카드에 같은 `초과 N` 이 붙고, 각각 `스텝 2곳` 꼬리표가 있습니다
- 헤더의 `과다 측정` 총계는 **그 값을 두 번 세지 않습니다**
- 한 카드를 펼쳐도 다른 카드는 접힌 채입니다

콘솔에 `Duplicate keys found during update` 가 없어야 합니다.

- [ ] **Step 4: 다른 화면이 멀쩡한지 본다**

`/ebeam/cd-sem/device-statistics/measurement-rules` 에서 cap 위반 배지를 눌러
슬라이드오버가 전과 같이 열리는지 확인합니다 (D3).

- [ ] **Step 5: 스크린샷을 남긴다**

`.playwright-mcp/screenshots/` 아래에 저장합니다 (`.gitignore` 됨).
최소 3장: 전체 상태 모달, 초과만 상태 모달, 펼친 카드.

- [ ] **Step 6: 스펙을 닫는다**

`.scratch/lot-outlier-merge/spec.md` 의 머리를 갱신합니다:

```markdown
Status: shipped
브라우저 확인: 2026-08-15 (초과만/전체, 다중 스텝 recipe 포함)
```

각 이슈 파일의 `Status: open` 을 `Status: resolved` 로 바꿉니다.

- [ ] **Step 7: 병합하고 워크트리를 없앤다**

작업이 `main` 에 올라가는 것으로 끝이 아닙니다 — 같은 세션에서 워크트리까지
치웁니다. `git worktree list` 가 본체 하나만 보여야 이 작업이 끝난 것입니다.

```bash
cd /Users/daeyoung/Codes/skewnono-lot-outlier-merge
git add .scratch/lot-outlier-merge
git commit -- .scratch/lot-outlier-merge \
  -m "docs(scratch): close lot-outlier-merge spec after browser verification"

cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git merge --ff-only work/lot-outlier-merge && git push
git worktree remove ../skewnono-lot-outlier-merge
git branch -d work/lot-outlier-merge
git worktree list
```

`--ff-only` 가 거절되면 그 사이 `main` 이 움직인 것입니다. 자동 병합이 깨끗해도
결과가 깨질 수 있으니, rebase 한 뒤 `npm test` 와 타입체크를 **다시** 돌리고
Step 2 의 1·7·10 을 다시 봅니다.
