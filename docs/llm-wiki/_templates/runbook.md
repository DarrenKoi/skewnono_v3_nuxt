---
tags: [runbook, <task>]
level: beginner | intermediate
last_updated: YYYY-MM-DD
status: in-progress
owner: <작성자>
sources: [raw/specs/<file>.md, src/<path>]
---

# Runbook: <작업명>

> 한 줄 요약 — 누가, 언제, 무엇을 위해 이 절차를 실행하는가.

## 왜 필요한가? (Why)

- 이 절차가 다루는 상황
- 실행 빈도 (1 회성·정기·on-demand)
- 실패 시 영향

## 사전 조건 (What you need)

### 권한·접근

- [ ] <시스템> 의 <역할> 권한
- [ ] <리포지터리> write access

### 도구

- `<tool>@<version>`
- `<tool>@<version>`

### 환경 변수 / 설정

```bash
export <KEY>=<value>
```

## 절차 (How)

### Step 1 — <단계명>

```bash
<command>
```

**기대 결과**: <어떤 출력이 보여야 하는가>

**실패 시**: <대처법>

### Step 2 — <단계명>

```bash
<command>
```

**기대 결과**:
**실패 시**:

### Step 3 — <단계명>

...

## 검증 (Verification)

- [ ] 체크 1: <어떻게 확인하는가>
- [ ] 체크 2:
- [ ] 체크 3:

## 롤백 (Rollback)

문제 발생 시:

```bash
<rollback command>
```

## 자주 발생하는 문제 (Troubleshooting)

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| <error message> | <cause> | <fix> |

## 참고 자료 (References)

- 관련 컴포넌트: [components/<name>.md](../components/<name>.md)
- 원본 스펙: [raw/specs/<file>.md](../../raw/specs/<file>.md)
- 외부:
