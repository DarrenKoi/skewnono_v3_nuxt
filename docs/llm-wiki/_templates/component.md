---
tags: [component]
level: intermediate
last_updated: YYYY-MM-DD
status: in-progress
owner: <작성자>
sources: [raw/specs/<file>.md, src/<path>]
---

# <Component Name>

> 한 줄 요약 — 이 컴포넌트가 시스템에서 맡는 역할.

## 왜 존재하는가? (Why)

- 해결하는 문제
- 이 컴포넌트가 없으면 발생하는 일
- 대안을 검토했다면 link → [decisions/<adr>.md](../decisions/<adr>.md)

## 무엇인가? (What)

### 책임 범위

- 이 컴포넌트가 책임지는 것
- 책임지지 **않는** 것 (경계 명시)

### 핵심 진입점

- `src/<path>/<file>.<ext>:<line>` — 설명
- `src/<path>/<file>.<ext>:<line>` — 설명

### 의존성

- 내부: [<component>](./other-component.md)
- 외부: `<library>@<version>`

### 데이터 모델 / 인터페이스

```<lang>
// 핵심 타입 또는 API 시그니처
```

## 어떻게 쓰는가? (How)

### 호출 예시

```<lang>
// 실행 가능한 짧은 예제
```

### 자주 쓰는 패턴

- 패턴 1: 설명 + 코드 위치
- 패턴 2: 설명 + 코드 위치

### 안티패턴

- 하지 말 것: 이유

## 참고 자료 (References)

- 원본 스펙: [raw/specs/<file>.md](../../raw/specs/<file>.md)
- 의사결정: [decisions/<adr>.md](../decisions/<adr>.md)
- 외부 문서:
