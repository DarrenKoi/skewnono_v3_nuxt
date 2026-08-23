# Herdr 오케스트레이션 운영 정책 v1

작성일과 마지막 검토일은 2026-08-24입니다. 이 문서는 이 저장소에서 Herdr를
이용해 Manager와 worker를 운영할 때 따르는 최소 정책입니다. 명령 예시는 이
머신의 `herdr 0.8.2`에서 확인했습니다.

## 1. 검토 결론

Herdr는 multi-agent planner나 task scheduler가 아니라 **agent-aware terminal
runtime과 automation API**, 즉 control plane입니다. 작업 분해, 의존성 판단,
검증, 재작업, 통합 정책은 Manager가 책임집니다.

이 저장소에서는 다음 원칙만 채택합니다.

| 원칙 | 이유 |
| --- | --- |
| 기본값은 orchestration을 사용하지 않는 것입니다 | 작은 작업의 위임 비용이 구현 비용보다 큽니다 |
| orchestration을 시작한 Manager는 제품 코드를 구현하지 않습니다 | 조정 context와 구현 context를 분리합니다 |
| 쓰기 작업은 worktree와 파일 소유권으로 격리합니다 | 여러 세션이 같은 main checkout을 공유합니다 |
| worker session을 후속 수정에도 재사용합니다 | 저장소 context를 다시 만드는 비용을 줄입니다 |
| agent 종료 상태와 task 성공을 구분합니다 | `idle`과 `done`은 성공 증거가 아닙니다 |
| 통합은 한 번에 한 branch씩 직렬로 수행합니다 | 독립 branch의 의미적 충돌을 확인해야 합니다 |

다음은 현재 도입하지 않습니다.

- 모든 작업을 위한 `.orchestration/` 상태 머신
- 전역 단조 증가 `TASK-NNN` 번호와 단일 `current` 포인터
- 상시 Designer와 별도 Tester agent
- Socket API coordinator와 custom plugin

반복 운영에서 실제 필요가 확인되기 전까지 instruction과 Herdr CLI만으로
운영합니다.

## 2. 실행 전 조건

Manager는 Herdr 제어 명령을 실행하기 전에 다음 preflight를 끝냅니다.

```bash
test "${HERDR_ENV:-}" = 1
herdr --version
herdr integration status --outdated-only
git status --short
```

완료 조건은 다음과 같습니다.

- `HERDR_ENV=1`입니다. 아니라면 현재 세션에서 Herdr pane을 제어하지 않습니다.
- 설치된 버전과 명령 문법을 확인했습니다.
- 사용할 agent integration이 current입니다.
- 기존 working tree 변경을 확인하고 작업 범위와 구분했습니다.
- 목표, 제외 범위, acceptance check를 한 문장씩 정의했습니다.

### 2.1 Herdr skill의 신선도

CLI 문법은 이 문서가 아니라 설치된 바이너리의 `herdr --skill`과 command-group
help를 source of truth로 사용합니다.

2026-08-24 실측에서 `~/.claude/skills/herdr/SKILL.md`와
`~/.agents/skills/herdr/SKILL.md`는 같은 inode를 공유하지만, 둘 다 구세대
`herdr wait agent-status` 문법을 담고 있습니다. 현재 0.8.2 문법은
`herdr agent wait`와 `herdr pane wait-output`입니다. 실제 orchestration 전에
skill을 갱신하고 다시 읽어야 합니다.

```bash
herdr --skill > ~/.claude/skills/herdr/SKILL.md
```

현재 integration 상태는 Claude, Codex, OpenCode 모두 current로 확인했습니다.
Herdr 또는 agent 도구를 업데이트한 뒤에는 skill과 integration을 다시 확인합니다.

## 3. Routing threshold

작업을 먼저 가장 낮은 tier에 배치합니다. 높은 tier의 조건을 명시할 수 있을 때만
올립니다.

| Tier | 조건 | 기본 토폴로지 |
| --- | --- | --- |
| T0 | 단일 파일 또는 한정된 수정이며 별도 설계 판단이 없습니다 | 현재 세션이 직접 수행합니다 |
| T1 | 한 subsystem의 여러 파일을 수정하고 범위가 명확합니다 | Manager → Coder |
| T2 | 동작 변경과 회귀 위험이 있어 독립 검토가 필요합니다 | Manager → Coder → `oc-review` |
| T3 | 여러 subsystem 또는 병렬 구현 단위가 있고 인터페이스 합의가 필요합니다 | Manager → 선택적 Designer → Coder 여러 명 → Reviewer |

다음 작업은 보통 T0입니다.

- 오타와 문구 수정
- 단일 UI 속성 변경
- 한 endpoint의 국소 validation
- 단일 테스트 또는 mock 값 수정

다음 작업은 T3 후보입니다.

- `back_dev_home/`과 `front-dev-home/`을 함께 바꾸는 신규 feature
- 새 tool family를 여러 feature에 연결하는 작업
- 여러 feature의 provider contract를 동시에 바꾸는 refactoring

병렬 worker는 token 사용량을 줄이는 수단이 아닙니다. 서로 독립적인 긴 작업의
wall-clock을 줄이거나 독립 검증을 얻을 때 사용합니다.

## 4. 역할과 결과 계약

### 4.1 Manager

Manager는 다음을 소유합니다.

- repository instruction과 현재 변경 상태 조사
- tier 선택, task 분해, dependency와 write ownership 확정
- worker prompt와 acceptance check 작성
- pane, agent, worktree ID 기록
- blocked 질문의 사용자 escalation
- 결과 파일, Git diff, 검증 출력 확인
- reviewer finding의 채택 또는 반박
- 직렬 통합, push, worktree와 branch 정리

orchestration을 시작한 뒤에는 feature 구현, worker 소유 파일 수정, reviewer를
대신한 독립 리뷰를 수행하지 않습니다. 작은 작업을 T0로 분류해 현재 세션이 직접
처리하는 것은 이 제한의 예외가 아니라 orchestration을 시작하지 않은 것입니다.

### 4.2 Designer

Designer는 T3에서 다음 중 하나가 필요할 때만 사용합니다.

- subsystem 사이의 interface를 구현 전에 확정해야 합니다.
- 여러 구현안의 trade-off가 acceptance에 영향을 줍니다.
- 되돌리기 어려운 결정을 ADR로 남겨야 합니다.

Designer의 기본 산출물은 문서이며 제품 코드는 수정하지 않습니다. 결정이 이미
spec이나 ADR에 있으면 Designer를 다시 기용하지 않습니다.

### 4.3 Coder

Coder는 assignment에 적힌 파일만 수정합니다. 범위 밖 변경이 필요해지면 먼저
`BLOCKED`로 반환하고 Manager가 ownership을 다시 배정할 때까지 기다립니다.
review finding의 수정은 새 Fixer가 아니라 원래 Coder에게 돌려보냅니다.

### 4.4 Reviewer

Reviewer는 기본적으로 read-only입니다. 이 저장소에서는 우선 `oc-review`를
사용합니다. Reviewer는 actionable finding마다 다음을 반환합니다.

- 위치: `file:line` 또는 문서 section
- 위반한 repository rule 또는 acceptance criterion
- 사용자에게 미치는 영향
- 가장 작은 수정 방향

Reviewer의 종료 상태가 아니라 Manager가 finding과 근거를 대조한 결과가 review
판정입니다.

### 4.5 Tester

테스트 러너, watcher, dev server는 agent가 아니라 pane에서 실행합니다. 코드
이해와 판단이 필요한 일은 Agent surface를, 일반 process는 Pane surface를
사용합니다.

## 5. 쓰기 격리

이 저장소에서는 worktree와 파일 집합 두 층을 모두 확인합니다.

### 5.1 Worktree 규칙

- 두 파일 이상을 수정하는 작업은 전용 Git worktree에서 수행합니다.
- writer를 병렬 실행할 때는 단일 파일 작업이어도 writer마다 별도 worktree를
  사용합니다.
- read-only Designer와 Reviewer는 write worktree가 필요하지 않습니다.
- branch는 `work/<task-slug>` 형태의 임시 운반 수단이며 main 통합 후 삭제합니다.
- worktree 생성과 제거의 source of truth는 repo의 `CLAUDE.md`와 현재 세션에
  주입된 repository instructions입니다.

```bash
git worktree add ../skewnono-<task> -b work/<task>
# worktree에서 수정, 검증, 명시적 경로 commit
# main checkout으로 돌아와서 실행
git merge --ff-only work/<task>
git push
git worktree remove ../skewnono-<task>
git branch -d work/<task>
git worktree list
```

Herdr의 `worktree create`를 사용해도 같은 Git 규칙을 지킵니다.
`herdr worktree remove`는 checkout만 제거하고 branch는 삭제하지 않으므로 branch
정리를 별도로 확인합니다.

### 5.2 파일 소유권

병렬 실행 전 각 worker의 대상 파일 집합을 적습니다.

```text
파일 집합이 서로소이고 공유 contract가 변하지 않음  → 병렬 가능
파일이 하나라도 겹치거나 공유 contract를 바꿈        → 순차 실행
```

경로가 달라도 하나의 invariant를 공유하면 한 worker가 소유합니다.

- 한 feature의 `providers/mock.py`와 `providers/office_example.py`
- office DB 사실을 함께 반영하는 `docs/datatables/<source>.txt`와 관련 mock
- API response shape를 함께 바꾸는 `contracts.py`, provider, frontend consumer

커밋은 자신이 수정한 명시적 경로만 사용합니다. broad staging과 whole-tree
restore를 사용하지 않습니다.

## 6. 실행 프로토콜

### 6.1 PLAN

Manager는 worker를 만들기 전에 다음을 확정합니다.

```text
goal:         사용자가 얻게 될 결과
scope:        수정하거나 조사할 경로
out_of_scope: 의도적으로 건드리지 않을 경로와 동작
acceptance:   실행할 검사와 눈으로 확인할 결과
dependencies: 먼저 끝나야 하는 task
write_owner:  파일 집합별 단일 writer
```

완료 조건은 모든 write target에 owner가 하나만 있고, 병렬 task 사이에 숨은
contract 의존성이 없으며, 각 task의 acceptance가 명령 또는 구체적인 관찰로
판정 가능하다는 것입니다.

### 6.2 DISPATCH

Worker prompt에는 저장소 전체 탐색을 맡기지 않고 필요한 context와 경로를
지정합니다.

```text
ROLE
GOAL
READ FIRST
WRITE SCOPE
OUT OF SCOPE
ACCEPTANCE CHECKS
RETURN CONTRACT
```

Manager는 pane을 만든 JSON 응답에서 실제 pane ID를 읽고, agent 이름과 pane,
worktree, branch, file scope를 기록합니다. ID는 불투명한 문자열로 취급하며
예측하거나 조합하지 않습니다.

### 6.3 MONITOR와 COLLECT

한 worker의 후속 작업에는 기존 pane과 agent session을 재사용합니다. 정상 흐름은
다음과 같습니다.

```bash
herdr agent wait <name> --timeout 600000
herdr agent prompt <name> "$TASK" --wait --timeout 600000
herdr agent read <name> --source recent-unwrapped --lines 150
```

`agent prompt --wait`는 기본적으로 첫 `idle`, `done`, `blocked` 중 하나까지
기다리므로 동일한 `--until` 목록을 반복하지 않습니다. Herdr는 개별 turn ID를
추적하지 않으므로 이미 working 중인 agent에게 prompt를 보내지 않습니다.

`blocked`이면 UI와 transcript를 읽고 필요한 사용자 결정을 요청합니다.
`unknown`은 완료로 해석하지 않습니다. 긴 결과는 transcript에만 남기지 않고
worker가 지정된 Markdown 결과 파일에 기록하게 합니다.

Worker의 return contract는 다음과 같습니다.

```text
status:   DONE | BLOCKED | FAILED
summary:  변경 또는 조사 결과 2~3줄
files:    변경한 경로 전체
checks:   실행한 명령과 실제 결과
risks:    남은 위험과 검증하지 못한 동작
blocker:  BLOCKED일 때 필요한 결정
```

### 6.4 VERIFY와 REVIEW

Manager는 `status: DONE`, `idle`, `done`만으로 task를 통과시키지 않습니다.

1. assignment의 목표와 실제 diff가 일치하는지 확인합니다.
2. 보고된 파일 목록과 `git diff --name-only`를 대조합니다.
3. 범위 밖 변경과 다른 session의 변경이 섞이지 않았는지 확인합니다.
4. acceptance command의 출력과 종료 코드를 확인합니다.
5. T2와 T3는 독립 Reviewer에게 보냅니다.
6. finding을 원래 Coder에게 반환하고 같은 session에서 수정하게 합니다.

Provider 관련 변경은 mock, office template, contract, frontend consumer와 schema
문서를 함께 추적합니다. 집에서 실행할 수 없는 office 전용 동작은 검증했다고
쓰지 않고 `OFFICE-VERIFY` 또는 browser-only/office-only 미검증으로 표시합니다.

### 6.5 INTEGRATE

통합은 Manager가 한 번에 한 branch씩 수행합니다.

1. 현재 main과 대상 branch의 상태를 다시 확인합니다.
2. 앞선 통합으로 main이 이동했다면 대상 branch를 새 main 위에 갱신합니다.
3. 갱신된 branch에서 영향 범위 acceptance를 다시 실행합니다.
4. main에 `--ff-only`로 통합하고 diff를 확인합니다.
5. 모든 branch 통합 뒤 조합된 변경에 필요한 최종 gate를 실행합니다.
6. coherent commit 집합을 push합니다.
7. push 성공 직후 worktree와 임시 branch를 제거합니다.

검증 명령은 변경 범위에 맞춥니다.

| 변경 범위 | 최소 gate |
| --- | --- |
| Python | `.venv/bin/python -m ruff check .`와 영향 feature pytest |
| 공용 backend runtime 또는 여러 feature | 전체 `.venv/bin/python -m pytest -q` |
| Frontend | `npm test`, `npm run typecheck`, 필요한 lint와 수동 UI 확인 |
| Markdown | 루트의 `npm run lint:md` |
| Backend와 frontend contract 동시 변경 | 양쪽 gate와 API shape 대조 |

각 branch merge 직후 무조건 backend 전체 suite를 반복하지 않습니다. 전체 suite는
공용 backend 또는 여러 feature의 결합 위험이 있거나 acceptance가 요구할 때
실행합니다.

### 6.6 CLEANUP

완료 조건은 push가 아니라 다음 상태입니다.

- 필요한 검증이 최종 통합 상태에서 통과했습니다.
- 생성한 Herdr worker와 pane의 결과를 수집했습니다.
- 생성한 worktree와 임시 branch를 제거했습니다.
- `git worktree list`에 의도한 checkout만 남았습니다.
- 사용자에게 변경, 검증, 미검증 위험을 함께 보고했습니다.

## 7. 테스트 비용과 worktree 차이

`providers/office.py`는 gitignored이므로 새 worktree에는 없을 수 있습니다.
`.venv/`와 `node_modules/`도 gitignored입니다. worker는 도구가 없다는 이유로
검증을 생략했다고 숨기지 않고 main checkout의 interpreter 또는 설치 경로를
사용하거나, 실행 불가 이유를 명시합니다.

Pytest 결과는 `passed`뿐 아니라 `passed + skipped`를 함께 기록합니다. worktree와
main checkout의 skip 수 차이가 환경 차이인지 collection 회귀인지 Manager가
판단할 수 있어야 합니다.

Backend 전체 suite는 반드시 repo root에서 `python -m pytest` 형태로 실행합니다.
`pytest tests/`만 실행하면 `back_dev_home/**/tests/`의 provider-contract suite를
건너뜁니다.

## 8. 복구와 사실의 우선순위

한 자료를 모든 상태의 source of truth로 삼지 않습니다.

| 질문 | 우선 확인할 자료 |
| --- | --- |
| 무엇을 하기로 했는가 | spec, assignment, acceptance criteria |
| agent가 지금 실행 중인가 | Herdr agent와 pane 상태 |
| 어떤 코드가 실제로 남았는가 | worktree의 Git status, diff, log |
| task가 성공했는가 | diff, 산출물, acceptance check 출력 |

Herdr 상태와 기록이 다르면 Herdr는 **현재 process 상태**에 대해서만 우선합니다.
Herdr의 `done`이 코드 성공을 증명하거나, Herdr의 `unknown`이 Git 변경을 무효로
만들지는 않습니다.

Worker가 중간에 종료되면 먼저 다음을 확인합니다.

```bash
git -C ../skewnono-<task> status --porcelain
git -C ../skewnono-<task> diff --stat
git -C ../skewnono-<task> log --oneline main..
```

| 상태 | 조치 |
| --- | --- |
| 변경과 commit이 assignment 안에서 일관됩니다 | 기존 session을 재기동하거나 새 Coder에게 인계합니다 |
| 미커밋 변경이 assignment 안에 있습니다 | 원래 Coder session을 재사용해 이어서 작업합니다 |
| 범위 밖 변경이 섞였습니다 | 변경 출처를 분리하고 사용자 또는 Manager 판단을 받습니다 |
| 복구 가치가 없고 폐기 범위가 명확합니다 | 정확한 경로만 지정해 폐기하고 무엇을 버렸는지 기록합니다 |

부분 변경을 곧바로 전체 rollback하지 않습니다. 폐기 전에는 diff로 정확한 대상을
확정하며, shared main checkout에 whole-tree `checkout`, `restore`, `stash`를
실행하지 않습니다.

## 9. T3에서만 쓰는 최소 영속 상태

T0~T2는 대화 context와 기존 `.scratch/<task-slug>/` spec/issue만 사용합니다.
동시 Coder가 둘 이상인 T3에서 복구 필요가 확인되면 다음 최소 구조를 사용합니다.

```text
.orchestration/<YYYY-MM-DD-task-slug>/
├── STATE.json
└── workers/<name>/
    ├── ASSIGNMENT.md
    └── RESULT.md
```

소유권은 다음과 같습니다.

```text
Manager만 write: STATE.json, workers/*/ASSIGNMENT.md
Worker만 write:  workers/<자기 이름>/RESULT.md
```

`STATE.json`은 task status, worker role, pane ID, worktree, branch, file scope만
기록합니다. 목표와 결정은 `.scratch/` spec과 `docs/adr/`에 두며 복제하지
않습니다. 전역 `current` 파일과 증가 번호는 만들지 않습니다.

## 10. Herdr 0.8.2 명령 부록

아래는 2026-08-24 실측 예시입니다. 실행 전 현재 `herdr --skill`과 relevant
command group help를 다시 확인합니다.

```bash
# caller의 cwd와 focus를 보존한 pane 생성
split=$(herdr pane split --current --direction right --cwd "$PWD" --no-focus)
pane_id=$(printf '%s\n' "$split" | jq -r '.result.pane.pane_id')

# 기존 shell pane에서 agent 시작
herdr agent start coder-api --kind codex --pane "$pane_id"

# settle 확인 후 작업 전달과 결과 읽기
herdr agent wait coder-api --timeout 600000
herdr agent prompt coder-api "$TASK" --wait --timeout 600000
herdr agent read coder-api --source recent-unwrapped --lines 150

# 일반 명령은 agent가 없는 별도 shell pane의 Pane surface 사용
test_split=$(herdr pane split --current --direction down --cwd "$PWD" --no-focus)
test_pane_id=$(printf '%s\n' "$test_split" | jq -r '.result.pane.pane_id')
herdr pane run "$test_pane_id" ".venv/bin/python -m ruff check ."
herdr pane wait-output "$test_pane_id" --regex "passed|failed" --timeout 120000
```

Herdr 상태의 의미는 다음과 같습니다.

| 상태 | 의미 | Manager 조치 |
| --- | --- | --- |
| `working` | agent가 처리 중입니다 | 기다리거나 현재 출력만 확인합니다 |
| `blocked` | 승인 또는 질문 UI가 감지됐습니다 | 내용을 읽고 필요한 결정을 요청합니다 |
| `idle` | 입력 가능하며 결과가 seen 상태입니다 | 결과를 수집하고 task 검증을 시작합니다 |
| `done` | 입력 가능하며 unseen background 완료입니다 | `idle`과 동일하게 결과를 별도 검증합니다 |
| `unknown` | agent는 있으나 lifecycle 판정이 불확실합니다 | 완료로 간주하지 않고 pane과 transcript를 조사합니다 |

## 11. 도입 순서

1. stale Herdr skill을 0.8.2 출력으로 갱신합니다.
2. T2 한 건을 Manager + Coder + `oc-review`로 끝까지 운영합니다.
3. 실제 비용과 실패 지점을 기록합니다.
4. 독립 구현 단위가 확인된 작업에서만 T3와 병렬 Coder를 시도합니다.
5. 복구 필요가 실제로 발생했을 때만 `.orchestration/` 최소본을 도입합니다.
6. instruction과 CLI로 해결되지 않는 반복 문제가 쌓이기 전에는 Socket API나
   plugin을 만들지 않습니다.

## 12. 근거 자료

- [Herdr 공식 문서](https://herdr.dev/docs/)
- [Herdr Agent automation](https://herdr.dev/docs/agent-automation/)
- [Herdr CLI reference](https://herdr.dev/docs/cli-reference/)
- 설치된 바이너리의 `herdr --skill` 출력
- `CLAUDE.md`와 현재 repository instructions: worktree, commit, test 규칙
- `.claude/oc-project.md`: `oc-*` review overlay와 escalation surface
- `docs/agents/issue-tracker.md`: `.scratch/` spec과 issue 규칙
- `docs/back-end/provider-selection.md`: mock과 office provider 전환 규칙
