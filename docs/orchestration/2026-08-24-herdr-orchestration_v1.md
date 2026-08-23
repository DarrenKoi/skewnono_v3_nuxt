# Herdr 오케스트레이션 구성안 v1

작성일은 2026-08-24입니다. 이 문서는 조사 요약본인
[`2026-08-24-herdr-orchestration.md`](2026-08-24-herdr-orchestration.md)를 이어받아,
거기에 **설치된 herdr 0.8.2 실측 검증**과 **이 저장소 고유의 제약**을 더해
실제로 채택할 구성을 확정한 것입니다.

원문 가이드는 <https://chatgpt.com/share/6a8b5a4e-4610-83ee-8a32-6eb657260200>이고,
검증 기준은 이 머신의 `herdr 0.8.2`(`herdr --version` 실측)입니다.

## 0. 요약

Herdr는 "여러 AI가 알아서 협업하는 multi-agent framework"가 아니라
**agent-aware terminal runtime + automation API**, 즉 control plane입니다.
orchestration 로직은 Manager agent의 instruction에 들어가고, Manager가
`herdr` CLI로 pane과 worker를 제어합니다.

원문 가이드는 방향은 옳지만 절반이 과잉 설계입니다. 실제로 채택할 것은
여섯 가지입니다.

| # | 원칙 | 근거 |
| --- | --- | --- |
| 1 | Manager는 구현하지 않는다 | orchestration 실패의 대부분을 여기서 막습니다 |
| 2 | Routing threshold — 대부분의 작업은 orchestration하지 않는다 | 원문에 없는 가장 큰 구멍입니다 |
| 3 | write owner를 worktree 층과 파일 층 두 겹으로 격리한다 | 이 저장소는 한 워킹 트리를 여러 세션이 공유합니다 |
| 4 | worker session을 재사용한다 | 토큰 비용의 실제 원인은 context 재구축입니다 |
| 5 | Agent completion은 task completion이 아니다 | herdr의 `done`은 성공이 아니라 알림 배지입니다 |
| 6 | 통합(merge)은 반드시 직렬로 한다 | 이 저장소에서 확인된 "조용히 병합된 잘못된 코드" 때문입니다 |

반대로 버리는 것은 다섯 가지입니다.

| 버릴 것 | 이유 |
| --- | --- |
| `.orchestration/` 파일 상태 머신 풀셋 | "Herdr는 control plane일 뿐"이라 해놓고 상태 머신을 손으로 재구현하는 자기모순입니다 |
| `TASK-NNN` 단조 증가 번호 | 다음 번호를 알려면 스캔이 필요하고, 동시 세션에서 번호 충돌이 실제로 납니다 |
| `.orchestration/current` 단일 파일 | 활성 task가 하나라고 가정하는 글로벌 뮤텍스입니다 |
| Designer 상시 기용 | 산출물이 advisory인데 repo 재탐색 비용을 통째로 한 번 더 냅니다 |
| Phase 3~4 (Socket API orchestrator, Plugin) | Phase 1~2에서 영원히 머무는 것이 이 저장소에는 맞습니다 |

## 1. Herdr의 실제 성격

Herdr 자체는 LLM planner도 scheduler도 제공하지 않습니다. Manager가 CLI를
호출해 pane을 만들고, worker를 시작하고, 상태를 기다리고, 결과를 읽는 형태가
Herdr가 의도한 orchestration 방식입니다.

| 용어 | 의미 |
| --- | --- |
| `Pane` | 실제 shell 또는 agent가 실행되는 terminal |
| `Agent` | Claude, Codex, OpenCode 등 실행 중인 process |
| `Agent State` | `idle / working / blocked / done / unknown` |
| `Workspace` | project 또는 task 격리 단위 |
| `Worktree Workspace` | Git worktree와 함께 열리는 workspace |
| `Integration` | agent lifecycle과 session 복원 정확도 향상 |
| `Herdr CLI` | Manager가 worker를 제어하는 핵심 API |
| `Socket API` | custom orchestrator를 만들 때 쓰는 하위 계층 |

핵심은 **Pane ≠ Agent**입니다. 0.8.2의 skill 문서 원문은 이렇게 못박습니다 —
*"`agent start` requires an existing available shell pane and never creates,
splits, or moves layout."* 즉 Manager가 **먼저 pane을 만들고**, 그 pane이
프롬프트에서 대기 중일 때 `agent start`를 해야 합니다.

## 2. herdr 0.8.2 실측 검증

### 2.1 존재가 확인된 명령

원문 가이드가 제시한 명령은 대부분 0.8.2에 실재합니다.

| 용도 | 명령 | 비고 |
| --- | --- | --- |
| pane 생성 | `herdr pane split --current --direction right --cwd "$PWD" --no-focus` | 새 pane ID는 `.result.pane.pane_id` |
| agent 시작 | `herdr agent start <name> --kind <kind> --pane <id>` | `kind`에 `claude`, `codex`, `opencode`, `gemini`, `hermes` 등 포함 |
| 지시 전달 | `herdr agent prompt <name> "<text>" --wait --timeout <ms>` | 텍스트와 Enter를 원자적으로 전송 |
| 상태 대기 | `herdr agent wait <name> [--until STATUS]... [--timeout MS]` | |
| 결과 읽기 | `herdr agent read <name> --source recent-unwrapped --lines 150` | 로그·트랜스크립트는 `recent-unwrapped` |
| 일반 명령 | `herdr pane run <pane_id> "<command>"` | |
| 출력 대기 | `herdr pane wait-output <pane_id> --regex "passed\|failed" --timeout <ms>` | 이미 존재하는 출력도 매칭됩니다 |
| worktree | `herdr worktree create --cwd PATH --branch NAME --base REF --label TEXT` | 네 플래그 모두 실재합니다 |
| integration | `herdr integration install claude` / `herdr integration status [--outdated-only]` | |
| skill 출력 | `herdr --skill` | 설치된 바이너리와 호환되는 skill 본문 |

"코드 이해가 필요하면 Agent, 명령 실행이면 Pane"이라는 구분도 그대로
유효합니다. 테스트 러너, watcher, 서버는 agent가 아니라 pane으로 돌립니다.

### 2.2 지금 바로 고쳐야 하는 것 세 가지

**(a) 로컬에 설치된 herdr skill이 stale합니다. 이것이 가장 시급합니다.**

원문 가이드의 핵심 조언은 "CLI 문법은 `ORCHESTRATOR.md`에 적지 말고 herdr
skill을 source of truth로 삼아라"입니다. 그런데 그 source of truth가 지금
깨져 있습니다.

```text
~/.claude/skills/herdr/SKILL.md  →  herdr wait agent-status <pane> --status idle
herdr 0.8.2 실제                  →  unknown command: wait
```

바이너리는 `herdr agent wait` / `herdr pane wait-output`인데, 설치된 skill
파일은 구세대 `herdr wait ...` 문법을 씁니다. orchestration을 시작하기 전에
반드시 갱신해야 합니다.

```bash
herdr --skill > ~/.claude/skills/herdr/SKILL.md
```

이 갱신은 herdr를 업데이트할 때마다 반복해야 합니다.

**(b) `agent prompt --wait`에 `--until`을 덧붙이지 않습니다.**

원문 가이드는 `--until idle --until done --until blocked`를 함께 붙이라고
하지만, 0.8.2 skill 원문은 반대로 지시합니다 — *"For normal agent work,
`--wait` is enough: it waits for the first settled `idle`, `done`, or `blocked`
state. **Do not repeat those defaults with `--until`**."*

다만 원문이 경고한 **prompt/wait race 자체는 여전히 실재**합니다. Herdr는
개별 turn ID를 추적하지 않으므로, 이미 working 중인 agent에게 prompt를 보내면
직전 turn의 완료가 wait를 만족시킬 수 있습니다. 그래서 순서는 유지합니다.

```bash
herdr agent wait coder-api --timeout 600000          # 먼저 settle 확인
herdr agent prompt coder-api "$TASK" --wait --timeout 600000
herdr agent read coder-api --source recent-unwrapped --lines 150
```

0.8.2는 여기에 안전장치를 하나 더 두었습니다. `agent prompt`는 승인·질문
다이얼로그에서 대기 중인 agent에 대해 입력을 보내기 전에 `agent_blocked`로
거부합니다. 이 경우 blocked UI를 읽고 사용자에게 물어야 하며, 임의로
응답을 밀어 넣지 않습니다.

**(c) `pane split`에는 `--cwd "$PWD"`를 붙입니다.**

0.8.2 skill은 caller의 작업 디렉터리를 명시적으로 보존하라고 요구합니다.
원문 가이드 예시에는 이 플래그가 빠져 있습니다.

### 2.3 원문 조사의 링크 오류 정정

전신 문서의 "공식 근거 자료" 중 두 개는 존재하지 않는 저장소입니다
(HTTP 404 실측). 실재하는 것으로 교체했으며, 정정본은 이 문서 10장에 있습니다.

| 잘못된 링크 | 상태 | 대체 |
| --- | --- | --- |
| `github.com/herdr-io/herdr` | 404 | `github.com/herdrdev/herdr` |
| `github.com/herdr-orch/orchestrator` | 404 | `github.com/hungv47/herdr-agent-orchestration` |

## 3. 채택하는 원칙

### 3.1 Manager는 구현하지 않는다

원문 가이드가 가장 강조하는 정책이고, 저도 동의합니다. orchestration이
무너지는 첫 지점이 Manager가 "이건 내가 빨리 고치는 게 낫겠다"고 판단하는
순간입니다. 그때부터 Manager context가 코드 세부사항으로 오염되고, 이후의
모든 위임 판단이 나빠집니다.

```text
Manager가 하는 일:
repo 조사 / task 분해 / dependency 분석 / worker 선택 / worktree 생성 /
prompt 작성 / 상태 monitoring / diff 확인 / 테스트 결과 확인 /
review 판단 / merge / 사용자 보고

Manager가 하지 않는 일:
feature 구현 / worker가 작업 중인 파일 수정 / 직접 코드 리뷰 /
실패한 worker 작업을 몰래 고치기
```

단 하나 예외를 둡니다. **3.2의 threshold 아래 작업은 애초에 orchestration
대상이 아니므로**, Manager가 직접 하는 것이 아니라 그냥 이 세션이 평소처럼
처리하는 일반 작업입니다. "Manager는 구현하지 않는다"는 orchestration을
시작하기로 결정한 이후에만 적용됩니다.

### 3.2 Routing threshold — 언제 orchestration을 하지 않는가

원문 가이드에 없는 가장 큰 구멍입니다. 역할 정의만 있고 진입 조건이 없으면,
20줄짜리 단일 파일 수정에 Designer와 Reviewer를 띄우게 됩니다.

| 티어 | 조건 | 토폴로지 | 예상 토큰 배수 |
| --- | --- | --- | ---: |
| T0 — orchestration 안 함 | 단일 파일, 단일 subsystem, 설계 판단 불필요 | 이 세션이 직접 수행 | 1.0× |
| T1 | 여러 파일이지만 한 subsystem, 회귀 위험 낮음 | Manager → Coder | 1.3~1.8× |
| T2 | 여러 파일 + 동작 변경 + 회귀 위험 있음 | Manager → Coder → `oc-review` | 1.8~2.5× |
| T3 | 여러 subsystem 동시 변경, 인터페이스 확정 필요 | Manager → (Designer) → Coder ×2 → Reviewer | 2.5~4× |

**기본값은 T0입니다.** 상위 티어로 올라가려면 조건을 만족했다고 명시해야
합니다. 다음은 전부 T0입니다.

```text
오타 수정
버튼 색상 변경
Flask endpoint에 validation 하나 추가
단위 테스트 하나 수정
mock 값 하나 조정
```

반대로 T3가 정당한 경우는 이렇습니다.

```text
back_dev_home + front-dev-home 동시 변경이 필요한 신규 feature
새 tool family(vendor) 온보딩
여러 feature의 provider 계층을 동시에 건드리는 refactoring
```

그리고 원문 가이드의 중요한 통찰 하나를 그대로 유지합니다 —
**병렬 worker는 토큰을 줄이지 않습니다. wall-clock을 줄입니다.**
orchestration의 목적은 비용 절감이 아니라 품질, 독립 검증, 병렬성,
장시간 작업의 안정성입니다.

### 3.3 write owner를 두 겹으로 격리한다

원문의 "1 coder = 1 worktree"는 이 저장소에서는 권장이 아니라 **강제**입니다.
`CLAUDE.md`가 `git add -A` / `git add .` / `git commit -a` / bare `git stash`를
금지하는 이유가 정확히 *"여러 agent 세션이 하나의 워킹 트리를 공유한다"*이기
때문입니다. worker 둘을 같은 checkout에 넣으면 커밋이 조용히 오염됩니다.
에러는 나지 않고 로그만 망가집니다.

**층 1 — worktree 격리.** 동시에 코드를 쓰는 worker는 각자 worktree를 가집니다.
단, `herdr worktree create`가 `CLAUDE.md`의 worktree 규약을 대체하지 않도록
합니다. 절차는 `CLAUDE.md`에 이미 정해져 있습니다.

```bash
git worktree add ../skewnono-<task> -b work/<task>
# ...작업과 커밋은 worktree 안에서...
git -C . merge --ff-only work/<task> && git push
git worktree remove ../skewnono-<task> && git branch -d work/<task>
```

작업이 `main`에 올라간 직후 **같은 세션에서** worktree를 제거하는 것까지가
완료 조건입니다. `git worktree list`가 main 트리 하나만 보여야 합니다.

**층 2 — 파일 격리.** worktree만으로는 부족합니다. 병렬 판정 기준은 이렇습니다.

```text
두 worker의 대상 파일 집합이 서로소   → 병렬 가능
한 파일이라도 겹침                    → 순차
```

이 저장소에서 특히 조심할 겹침이 하나 있습니다. `providers/mock.py`와
`providers/office_example.py`는 **같은 수식을 공유하는 한 쌍**이라 서로 다른
worker에게 나눠주면 안 됩니다. 한쪽에만 가드가 들어가고 다른 쪽에는 안 들어가는
drift가 실제로 발생한 이력이 있습니다. 한 feature의 provider 쌍은 항상 한
worker가 소유합니다.

같은 이유로 `docs/datatables/<source>.txt`와 해당 feature의 `mock.py`도 한
쌍입니다. 사무실 DB 사실은 두 곳에 동시에 반영해야 하므로, 이 둘을 다른
worker에게 분리하면 문서와 코드가 갈립니다.

### 3.4 worker session을 재사용한다

원문 가이드는 토큰 비용을 2~4배로 추정하면서 원인을 "worker마다 repository를
다시 읽는 것"으로 지목합니다. 절반만 맞습니다. 실제 비용은 두 갈래입니다.

| 비용 원인 | 대응 |
| --- | --- |
| worker마다 context 재구축 | **session 재사용** — subtask마다 agent를 새로 띄우지 않습니다 |
| Manager가 모든 worker output을 들고 context가 부푸는 것 | worker가 요약된 return contract만 반환하게 합니다 |

구체적으로는, 한 worker에게 후속 작업이 있으면 pane과 agent를 살려두고
`agent prompt`로 이어서 지시합니다. 리뷰 피드백 반영(Fixer)도 새 agent가 아니라
**원래 구현한 coder에게** 보냅니다. 그 agent는 이미 해당 코드의 context를
가지고 있으므로, 새 worker를 띄우는 것보다 압도적으로 쌉니다.

worker에게 "repository를 분석하라"고 하지 않는 것도 같은 이유입니다.

```text
나쁨:  "Repository를 분석하고 검색 기능을 구현하라."        → 탐색 20~40k
좋음:  "다음 세 파일만 조사하라: <경로 3개>. 지시는 <ASSIGNMENT 경로>." → 5~15k
```

### 3.5 Agent completion은 task completion이 아니다

원문의 경고가 정확하고, 0.8.2 문서도 같은 말을 합니다. `idle`과 `done`은
**동일한 내부 상태**이며 차이는 "결과를 사람이 봤느냐"뿐입니다. 즉 `done`은
성공 신호가 아니라 읽지 않은 알림 배지입니다. `unknown`은 완료를 뜻하지
않습니다.

따라서 worker에게 반드시 return contract를 요구합니다.

```text
status:   DONE | BLOCKED | FAILED
summary:  <2~3줄>
files:    <변경한 경로 전부>
checks:   <실행한 명령과 결과>
risks:    <남은 위험>
blocker:  <BLOCKED일 때만>
```

그리고 Manager는 `status: DONE`만으로 통과시키지 않고 acceptance 명령을
직접 확인합니다.

### 3.6 통합은 반드시 직렬로 한다

이 저장소 고유의 규칙이고, 원문 가이드에는 없습니다. 자세한 근거는 4.2에
있습니다.

```text
INTEGRATE (직렬 — 병렬 금지)
1. worker 브랜치를 한 번에 하나만 merge --ff-only
2. 각 merge 직후 .venv/bin/python -m pytest -q 전체 재실행
3. 다음 브랜치는 갱신된 main 위로 rebase한 뒤 재검증
4. 통과한 브랜치만 push, 그 즉시 worktree remove + branch -d
```

## 4. 이 저장소 고유의 함정 다섯 가지

### 4.1 하나의 워킹 트리를 여러 세션이 공유합니다

3.3에서 다뤘습니다. 요점은 **broad staging이 에러 없이 다른 세션의
half-finished 편집을 삼킨다**는 것입니다. worker prompt에 명시적으로
넣어야 합니다.

```text
커밋은 반드시 명시적 경로로만 합니다.
git add -A / git add . / git commit -a / bare git stash 는 금지입니다.
```

### 4.2 조용히 병합되는 잘못된 코드

병렬 worker의 진짜 위험은 Git 충돌이 아닙니다. 충돌은 눈에 보이니까
안전합니다. 이 저장소에서 확인된 위험은 그 반대입니다.

worker A가 작업하는 동안 `main`이 움직이면, **충돌 없이 auto-merge된 결과가
office 전용 경로에서만 깨지고 테스트는 전부 통과**할 수 있습니다. 집에서
돌리는 테스트는 mock 경로만 지나가기 때문입니다.

그래서 3.6의 직렬 통합이 필요하고, 여기에 더해 provider 계층을 건드린
작업에는 `home-to-office` 스킬로 mock↔office 정합성을 별도 확인합니다.

### 4.3 worktree의 테스트 결과는 그대로 믿으면 안 됩니다

`providers/office.py`는 gitignored라 새로 만든 worktree에는 존재하지 않습니다.
따라서 worker가 보고하는 skip 수는 main 체크아웃과 **정당하게 다릅니다.**

RESULT의 검증 항목은 `passed`만이 아니라 **`passed + skipped` 합계**를 적게
합니다. 그러지 않으면 Manager가 "테스트가 줄었다 = 회귀"로 오판합니다.

### 4.4 Reviewer는 새로 만들지 않고 `oc-*`를 재사용합니다

이 저장소에는 이미 리뷰 경로가 있습니다.

| 스킬 | 용도 | 특성 |
| --- | --- | --- |
| `oc-review` | Standards + Spec 2축 리뷰 | opencode를 `--agent plan` 읽기 전용으로 실행 |
| `oc-simplify` | 재사용·단순화·효율·altitude | 분석은 opencode, 편집은 Claude |
| `oc-discuss` | 설계 판단을 3라운드까지 논쟁 | AGREED / DISPUTED / I-WAS-WRONG로 종결 |

원문 가이드가 요구한 "Reviewer는 write 권한 없이"를 `--agent plan`이 이미
**강제로** 만족시키고, `.claude/oc-project.md`에 이 저장소의 escalation
surface와 추가 smell 목록까지 들어 있습니다. herdr reviewer pane을 새로 띄우는
것보다 정확도와 비용 모두 낫습니다. 기록도 `docs/opencode/`에 자동으로 남습니다.

다만 원문의 "Reviewer는 절대 코드를 수정하지 않는다"는 **정책이지 법칙이
아닙니다.** reviewer → Manager → coder 왕복은 느리고 토큰만 태웁니다. 실제
invariant는 3.3의 "한 파일에 한 명만 write owner"이므로, 그 owner가 놀고 있고
수정이 bounded하다면 왕복을 생략해도 됩니다. `oc-*`는 어차피 읽기 전용이므로
이 판단은 herdr reviewer agent를 쓸 때만 의미가 있습니다.

### 4.5 테스트는 계층으로 나눠 돌립니다

전체 스위트는 약 3040개 테스트에 약 115초입니다. device-statistics의
주간 스냅샷 테스트가 대부분을 차지합니다. worker마다 이걸 돌리면 병렬화
이득이 그대로 증발합니다.

| 단계 | 명령 | 비용 |
| --- | --- | --- |
| worker 자체 게이트 | `.venv/bin/python -m ruff check .` | 약 0.02초, 무조건 실행 |
| worker acceptance | `.venv/bin/python -m pytest back_dev_home/<feature> -q` | 초 단위 |
| 프론트엔드 worker | `npm test` / `npm run typecheck` / `npm run lint` | `front-dev-home/`에서 |
| 통합 시 1회 | `.venv/bin/python -m pytest -q` | 약 115초 |
| Markdown 변경 시 | `npm run lint:md` | 루트에서 |

전체 스위트는 반드시 루트에서 `python -m pytest` 형태로 실행합니다. `-m`이
루트를 `sys.path`에 올려주기 때문입니다. `pytest tests` 단독은
`back_dev_home/**/tests/`의 provider-contract 스위트를 통째로 건너뛰는데,
그쪽이 mock→office 스왑을 지키는 절반입니다.

## 5. Worker Routing Policy

### 5.1 프로파일

모델명을 직접 박지 않고 프로파일 이름으로 둡니다. 모델은 자주 바뀌지만
workflow는 안 바뀌기 때문입니다.

| 프로파일 | 용도 | effort |
| --- | --- | --- |
| `fast-low` | 로그·테스트 출력 요약, 기계적 수정, 단순 문서 갱신 | low |
| `code-medium` | 범위가 정해진 구현, 테스트 작성, 재현 가능한 버그 수정 | medium |
| `reason-high` | 아키텍처 설계, dependency 분석, 어려운 디버깅, 모호한 요구사항 | high |
| `review-high` | 독립 리뷰, 회귀·호환성·보안 검토, 통합 전 최종 승인 | high |

### 5.2 role → profile 매핑

| Role | 기본 프로파일 | escalation | 이 저장소에서의 실행 주체 |
| --- | --- | --- | --- |
| Manager | `reason-high` | — | 이 Claude Code 세션 |
| Designer | `reason-high` | — | 기본적으로 기용하지 않음 (6장 참조) |
| Coder | `code-medium` | `reason-high` | herdr pane의 `claude` 또는 `codex` |
| Reviewer | `review-high` | `reason-high` | `oc-review` (opencode, 읽기 전용) |
| Fixer | `code-medium` | `reason-high` | **원래 구현한 coder를 재사용** |
| Tester | shell | `fast-low` | `herdr pane run`, agent 아님 |

원칙은 "작업을 완수할 수 있는 가장 작은 프로파일로 시작하고, 필요할 때만
올린다"입니다. escalation 조건은 다음과 같습니다.

```text
요구사항이 모호할 때
subsystem 경계를 넘을 때
아키텍처나 API 설계가 필요할 때
회귀 위험이 클 때
이전 worker가 반복해서 blocked 되었을 때
보안 · 데이터 정합성 · 운영 안정성이 걸려 있을 때
```

### 5.3 Manager 모델 티어링

전신 문서는 "Manager 자체는 싼 모델로도 되는 경우가 많다"고 적었는데,
저는 부분적으로만 동의합니다. Manager의 일은 균질하지 않습니다.

| Manager 단계 | 성격 | 싼 모델로 내려도 되는가 |
| --- | --- | --- |
| DISPATCH / MONITOR / COLLECT | 기계적 — 상태를 읽고 다음 명령을 보냄 | 됩니다 |
| PLAN / DEPENDENCY GRAPH | 이 작업 전체의 품질을 결정 | 안 됩니다 |
| INTEGRATE 판정 | 되돌리기 어려운 결정 | 안 됩니다 |

실무적으로 한 세션 안에서 모델을 갈아 끼우기는 어렵습니다. 그러므로 Manager는
강한 모델로 두되, **실제 절감은 Manager가 읽는 양을 줄이는 데서** 나옵니다.
worker가 raw 트랜스크립트가 아니라 3.5의 return contract만 돌려주게 하는 것이
Manager 모델을 낮추는 것보다 효과가 큽니다.

### 5.4 agent kind

herdr 0.8.2가 인식하는 kind에는 `claude`, `codex`, `opencode`, `gemini`,
`grok`, `hermes`, `cursor`, `copilot` 등이 포함됩니다. 이 저장소의 기본
조합은 다음과 같습니다.

```text
Manager   = 이 Claude Code 세션 (별도 pane 아님)
Coder     = herdr pane + claude 또는 codex
Reviewer  = oc-review (opencode, 읽기 전용)
Tester    = herdr pane run (agent 없음)
```

`herdr integration install claude`(또는 `codex`)를 해 두면 lifecycle 상태
판정이 정확해집니다. 장시간 무인 운용에서는 이것이 특히 중요합니다.
설치 상태는 `herdr integration status --outdated-only`로 확인합니다.

## 6. 파일 배치 — 최소본

원문 가이드는 task마다 `TASK.md` / `CONTEXT.md` / `PLAN.md` / `STATE.json` /
`DECISIONS.md` + worker별 `ASSIGNMENT.md` / `RESULT.md`를 만들라고 합니다.
task 하나당 여덟 개 이상의 파일입니다. 이 저장소에는 과잉이고, 무엇보다
**이미 있는 이슈 트래커와 중복**됩니다.

| 이미 존재하는 것 | 역할 |
| --- | --- |
| `.scratch/` | 이슈와 스펙 (`docs/agents/issue-tracker.md`) |
| `docs/opencode/` | `oc-*` 리뷰 기록 |
| `docs/adr/` | 아키텍처 결정 기록 |

그래서 분리합니다. **정적인 것은 기존 위치에, 런타임만 새 위치에** 둡니다.

```text
.scratch/<task-slug>.md          ← 목표 · 범위 · 수용 기준 · 계획 (기존 트래커 그대로)
docs/adr/                        ← 되돌리기 어려운 결정 (DECISIONS.md 대체)

.orchestration/<task-slug>/      ← T3에서만 생성
├── STATE.json                   ← Manager 단독 write
└── workers/<name>/
    ├── ASSIGNMENT.md            ← Manager write
    └── RESULT.md                ← Worker write
```

세 가지 규칙을 함께 둡니다.

**(1) 디렉터리 이름은 날짜 + slug입니다.** `TASK-NNN` 단조 증가 번호는
다음 번호를 알기 위해 스캔이 필요하고, 한 워킹 트리를 여러 세션이 공유하는
이 환경에서는 두 Manager가 같은 번호를 잡는 race가 실제로 납니다.
`2026-08-24-measurement-search`처럼 쓰면 카운터도 스캔도 충돌도 없습니다.

**(2) `current` 파일은 만들지 않습니다.** 활성 task가 하나라고 가정하는
글로벌 뮤텍스입니다. 지금도 herdr에는 workspace가 둘 이상 떠 있습니다.
활성 여부는 각 `STATE.json`의 `status`에서 유도합니다.

**(3) write ownership은 겹치지 않습니다.**

```text
Manager만 write:  STATE.json, workers/*/ASSIGNMENT.md
Worker만 write:   workers/<자기 이름>/RESULT.md
```

`STATE.json`의 최소 형태는 이렇습니다.

```json
{
  "task": "2026-08-24-measurement-search",
  "status": "planning | executing | reviewing | integrating | completed | blocked",
  "workers": {
    "coder-api": {
      "role": "coder",
      "profile": "code-medium",
      "status": "working",
      "worktree": "../skewnono-measurement-search-api",
      "branch": "work/measurement-search-api",
      "pane": "w5:pD",
      "files": ["back_dev_home/meas_hist/providers/mock.py"]
    }
  }
}
```

`files`를 넣는 이유는 3.3의 파일 단위 격리를 Manager가 기계적으로 판정할 수
있게 하기 위해서입니다. T1·T2에서는 이 디렉터리 자체를 만들지 않고, 상태를
Manager의 대화 context와 `.scratch/` 항목만으로 유지합니다.

## 7. 복구

### 7.1 Manager context가 유실됐을 때

새 Manager에게 다음 순서로 읽히면 복구됩니다.

```text
1. .orchestration/ 아래에서 status가 completed가 아닌 디렉터리를 찾습니다
2. STATE.json 을 읽습니다
3. .scratch/<task-slug>.md 로 목표와 수용 기준을 확인합니다
4. workers/*/RESULT.md 로 각 worker가 어디까지 했는지 확인합니다
5. herdr agent list 와 herdr pane list 로 실제 실행 상태를 대조합니다
6. 영속 상태와 herdr 실제 상태가 다르면 herdr 쪽을 사실로 봅니다
```

마지막 줄이 원문 가이드와 다릅니다. 원문은 "persisted state가 대화 기록보다
우선한다"고만 합니다. 저는 한 단계 더 명시합니다 — **`STATE.json`은 Manager가
마지막으로 기록한 의도이고, herdr lifecycle은 지금 실제로 벌어지는 일입니다.**
둘이 어긋나면 herdr가 맞고 `STATE.json`이 낡은 것입니다.

### 7.2 worker가 중간에 죽었거나 부분 변경만 남았을 때

원문 가이드에 없는 시나리오이고, 실제로는 가장 자주 겪게 됩니다.

```bash
git -C ../skewnono-<task> status --porcelain    # 미커밋 변경이 있는가
git -C ../skewnono-<task> diff --stat           # 어느 파일을 얼마나 건드렸나
git -C ../skewnono-<task> log --oneline main..  # 커밋은 어디까지 갔나
```

판정은 셋 중 하나입니다.

| 상태 | 조치 |
| --- | --- |
| 커밋까지 갔고 변경이 일관됨 | 새 worker에게 이어받게 하거나 그대로 리뷰로 보냅니다 |
| 미커밋 변경이 있고 범위가 ASSIGNMENT 안 | 같은 worker를 재기동해 이어서 시키는 것이 가장 쌉니다 |
| 범위 밖 파일이 섞였거나 판단 불가 | 롤백합니다 |

롤백할 때도 **명시적 경로로만** 되돌립니다. 워킹 트리를 공유하는 환경이므로
whole-tree `git checkout` / `git restore` / `git stash pop`은 금지입니다.
되돌릴 경로는 `diff --stat` 출력에서 그대로 가져옵니다.

```bash
git -C ../skewnono-<task> checkout -- <경로1> <경로2>
```

worktree 자체를 버릴 때는 `git worktree remove`와 `git branch -d`를 같이
실행해서 잔여 체크아웃이 남지 않게 합니다.

## 8. 도입 순서

한꺼번에 다 만들지 않습니다.

**v1 — 지금 할 것**

```text
[ ] herdr --skill > ~/.claude/skills/herdr/SKILL.md      (2.2-a, 가장 먼저)
[ ] herdr integration install claude ; herdr integration status
[ ] AGENTS.md 에 "Agent Roles" 포인터 섹션 약 15줄 추가
      - Manager 로 지시받았으면 이 문서를 읽어라
      - worker 로 시작됐으면 자기 ASSIGNMENT 만 읽고 범위 밖으로 나가지 마라
[ ] 토폴로지는 Manager + Coder 1명 + oc-review 로 시작 (T2)
[ ] Designer, Tester agent, .orchestration/ 디렉터리는 만들지 않음
```

**v1.5 — T2가 안정된 뒤**

```text
[ ] Coder 2명 병렬 + worktree 격리 (T3)
[ ] .orchestration/<slug>/ 최소본 도입 (STATE.json + workers/)
[ ] 3.6 직렬 통합 프로토콜을 실제로 한 번 완주
```

**v2 — 필요가 실증된 뒤에만**

```text
[ ] Designer 역할 (아키텍처가 실제로 막혔을 때)
[ ] ORCHESTRATOR.md 분리 (이 문서가 너무 커졌을 때)
[ ] Socket API / Plugin  ← 현재로서는 도입 예정 없음
```

`ORCHESTRATOR.md`를 지금 만들지 않는 이유는, 이 문서가 이미 그 역할을 하고
있고 `CLAUDE.md`·`AGENTS.md`와 3중으로 겹칠 위험이 있기 때문입니다. 분리한다면
그때도 herdr CLI 문법은 넣지 않고 "설치된 herdr skill을 source of truth로 삼는다"
한 줄만 둡니다. 그래야 herdr가 올라가도 문서가 stale해지지 않습니다.

## 9. 원문 대비 채택·기각 요약

| 원문의 주장 | 판정 | 사유 |
| --- | --- | --- |
| Herdr는 control plane이다 | 채택 | 0.8.2 문서·CLI와 일치합니다 |
| Manager는 구현하지 않는다 | 채택 | orchestration 실패의 대부분을 막습니다 |
| 1 coder = 1 worktree | 채택(강화) | 이 저장소에서는 권장이 아니라 강제입니다 |
| dependency 기준 병렬화 | 채택(강화) | worktree 층 + 파일 층 두 겹으로 확장했습니다 |
| 코드 이해→Agent, 명령 실행→Pane | 채택 | 테스트 러너는 pane으로 돌립니다 |
| `done`은 성공이 아니다 | 채택 | 0.8.2도 idle/done을 같은 상태로 정의합니다 |
| prompt/wait race 주의 | 채택(수정) | 순서는 유지하되 `--wait`에 `--until`을 덧붙이지 않습니다 |
| worker 간 직접 통신 금지 (star) | 채택 | 책임 소재가 흐려집니다 |
| Worker Routing Policy 표 | 채택(확장) | Manager 티어링과 escalation 조건을 추가했습니다 |
| `.orchestration/` 8파일 상태 머신 | 기각 | 기존 `.scratch/`·`docs/adr/`와 중복이며, T3 최소본으로 대체했습니다 |
| `TASK-NNN` 번호 | 기각 | 동시 세션에서 번호 충돌이 납니다. 날짜+slug로 대체 |
| `current` 단일 파일 | 기각 | 활성 task 하나를 가정하는 글로벌 뮤텍스입니다 |
| Designer 상시 기용 | 기각 | 산출물이 advisory인데 repo 재탐색 비용을 한 번 더 냅니다 |
| Reviewer는 절대 write 금지 | 기각(완화) | 실제 invariant는 "한 파일에 한 write owner"입니다 |
| Phase 3~4 (Socket API, Plugin) | 보류 | Phase 1~2로 충분합니다 |
| 토큰 2~4배 | 채택(보완) | 원인은 repo 재탐색뿐 아니라 Manager context 팽창입니다 |
| 언제 orchestration을 하지 않는가 | **원문에 없음 → 신규** | 3.2의 T0~T3 threshold가 이 구성의 진입 조건입니다 |
| worker 중간 사망 복구 | **원문에 없음 → 신규** | 7.2 |
| Manager 모델 티어링 | **원문에 없음 → 신규** | 5.3 |

## 10. 근거 자료

herdr 관련 링크는 2026-08-24에 도달 가능(HTTP 200)한 것만 남겼습니다.

- [Herdr 공식 문서](https://herdr.dev/docs/)
- [Herdr — Agent automation](https://herdr.dev/docs/agent-automation/)
- [Herdr — CLI reference](https://herdr.dev/docs/cli-reference/)
- [herdrdev/herdr (공식 저장소)](https://github.com/herdrdev/herdr)
- [hungv47/herdr-agent-orchestration (captain/worker 실험)](https://github.com/hungv47/herdr-agent-orchestration)
- [awslabs/cli-agent-orchestrator](https://github.com/awslabs/cli-agent-orchestrator)
- 로컬 기준 문서: `herdr --skill` 출력 (설치된 바이너리와 항상 일치)

이 저장소 쪽 근거는 `CLAUDE.md`(worktree·커밋 규약, 명령, provider 규칙),
`.claude/oc-project.md`(`oc-*` 오버레이), `docs/agents/issue-tracker.md`,
`docs/back-end/provider-selection.md`입니다.
