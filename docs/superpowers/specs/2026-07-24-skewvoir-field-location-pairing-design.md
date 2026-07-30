# Skewvoir CD 상관관계 위치 매칭 설계

작성일: 2026-07-24

수정일: 2026-07-30

범위: Skewvoir `상관 / 분포`의 CD↔CD 비교

## 배경

현재 `buildCdCdRelationship`은 서로 다른 CD parameter를
`chip_number#sequence`로 연결합니다. 그러나 `sequence`는 측정 row마다 고유하며,
같은 chip에서 측정한 서로 다른 parameter도 sequence가 절대 같지 않습니다.
따라서 동일 위치의 두 CD가 모두 존재해도 pair가 0개가 되고 산점도와 후속 분포가
비어 보입니다.

CD↔CD 비교는 측정 순서가 아니라 chip 위치를 기준으로 해야 합니다.

## 결정

CD↔CD의 기본 매칭 키는 `chip_number`로 고정합니다. `sequence`는 매칭에 사용하지
않으며, `chip_coordinate`는 같은 chip에 여러 관측치가 있을 때만 세부 위치를
구분하는 보조 키로 사용합니다.

UI에 매칭 방식 선택기나 URL query를 추가하지 않습니다. 단일 MSR과 SET scope가
동일한 매칭 규칙을 사용하도록 순수 관계 함수에 규칙을 모읍니다.

CD↔FDC는 per-sequence `dynamic_fdc`와 CD row를 연결하는 별도 관계이므로 기존
sequence 매칭을 유지합니다.

## CD↔CD 매칭 알고리즘

먼저 `isMeasuredRow`를 통과한 X/Y parameter row를 `chip_number`별로 모읍니다.
두 parameter 중 한쪽에만 존재하는 chip은 pair를 만들지 않고 `missingN`에
1을 더합니다.

양쪽 parameter가 모두 존재하는 chip은 다음 순서로 처리합니다.

### 단일 관측치

X와 Y가 각각 한 개이면 두 값을 바로 한 pair로 만듭니다. 두 row의 sequence가
달라도 결과에 영향을 주지 않습니다.

### 복수 관측치

한쪽에라도 두 개 이상의 row가 있으면 `chip_coordinate`를 확인합니다.

1. 양쪽의 모든 row에 비어 있지 않은 `chip_coordinate`가 있고, 양쪽의 coordinate
   집합이 완전히 같으면 `chip_number + chip_coordinate`별로 pair를 만듭니다.
2. 동일 coordinate에 같은 parameter의 row가 반복되면 해당 CD의 산술평균을
   사용합니다.
3. coordinate가 비어 있거나 양쪽 coordinate 집합이 다르면 coordinate 일부만
   억지로 연결하지 않습니다. 대신 해당 chip의 X 전체 평균과 Y 전체 평균으로
   chip-level pair 하나를 만듭니다.

이 규칙은 가능한 경우 같은 세부 위치를 보존하면서, office 데이터의
`chip_coordinate`가 없거나 불완전해도 빈 결과로 퇴행하지 않도록 합니다.

## 결과 모델

`PairedPoint.key`는 매칭 grain을 드러냅니다.

- 단일 관측치 또는 chip 평균 fallback: `chip_number`
- coordinate 매칭: `chip_number#chip_coordinate`

`PairedPoint.chip`은 기존 focus 동작을 위해 항상 `chip_number`를 유지합니다.
`PairedPoint.sequence`는 매칭 키가 아니라 정렬과 기존 공간 그룹 연결을 위한
대표값입니다. 각 X 그룹에서 가장 작은 sequence를 사용합니다.

`missingN`은 한쪽 parameter에만 존재한 chip 수입니다. 동일 chip 안의 coordinate
불일치는 chip 평균 fallback으로 비교할 수 있으므로 missing으로 세지 않습니다.

## 적용 범위

### 단일 MSR

`views/Correlation.vue`의 Paired Scatter, Marginal Distribution, Group
Distribution, Paired Evidence가 모두 `buildCdCdRelationship`의 결과를 사용합니다.
현재 구조를 유지하되 새 chip 기반 결과가 모든 패널에 함께 반영되도록 합니다.

### SET scope

`CorrelationScatter.vue` 내부의 기존 `chip_number#sequence` 조인을 제거합니다.
SET scope도 중앙 관계 함수를 통해 만든 point를 전달받아 단일 MSR과 동일한 규칙을
사용합니다.

### 변경하지 않는 범위

- CD↔FDC sequence 매칭
- backend API와 response shape
- query string과 공유 URL
- parameter 선택 UI와 차트 배치
- 상관계수 및 readiness 계산 방식

## 테스트

`utils/skewvoirAnalysis/relationships.test.ts`에서 다음 계약을 고정합니다.

1. 같은 `chip_number`이고 sequence가 다른 X/Y가 pair를 만듭니다.
2. 서로 다른 chip은 pair를 만들지 않습니다.
3. chip당 X/Y가 하나씩이면 `chip_coordinate`가 달라도 chip 기준으로 연결합니다.
4. 복수 관측치의 coordinate 집합이 같으면 coordinate별 pair를 만듭니다.
5. 동일 coordinate의 반복 row는 parameter별 평균을 사용합니다.
6. 복수 관측치에서 coordinate가 비어 있으면 chip 평균 pair 하나로 대체합니다.
7. 복수 관측치에서 coordinate 집합이 다르면 chip 평균 pair 하나로 대체합니다.
8. 한쪽 parameter에만 존재하는 chip은 `missingN`에 포함합니다.
9. 측정 실패 row는 `isMeasuredRow`에 의해 제외합니다.
10. CD↔FDC 결과는 기존 sequence 기반 계약을 유지합니다.

관련 순수 테스트를 먼저 실패시키고 구현 후 통과시킵니다. 이후 frontend 전체
test와 typecheck를 실행하며, 실행 중인 Skewvoir 화면에서 서로 다른 CD 두 개를
선택해 pair와 분포가 나타나는지 확인합니다.
