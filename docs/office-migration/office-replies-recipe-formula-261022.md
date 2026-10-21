# recipe-search Formula parameter — Office 회신 기록 (2026-10-22)

- 작성일: 2026-10-22입니다.
- 범위: 다른 parameter 값으로 계산하는 Formula parameter 를 recipe 열어 보기 화면에
  보여 주는 작업입니다. 사무실에서 `read_af_pr_condition` 을 바꾸고, 집에서 mock 과
  화면을 맞췄습니다.
- 원문은 사용자가 손으로 옮긴 그대로 둡니다. 오타도 고치지 않습니다.
- 확정된 사실은 `docs/datatables/hitachi/recipe_idp.txt` 의 ENMP `formula` 절에
  있습니다. 이 문서는 무엇을 묻고 무엇을 들었는지의 기록입니다.

| 순서 | 방향 | 내용 | 반영 commit |
| --- | --- | --- | --- |
| 1 | Office → Home | reader 변경 통지와 집 쪽 작업 목록 | `5de74c80` |
| 2 | Home → Office | 질문 Q1–Q3 | - |
| 3 | Office → Home | Q1–Q3 회신과 추가 발견 4건 | `54d1475b` |
| - | 사용자 | key 철자는 `Formula` | `8a321975` |

## 1. 사무실 통지 (원문)

```text
for ther recipe-search page, some parameters are formular based so that their results are from the caculation of the existing parameters in the recipe.
Office agent already update this features to office_utils/idp_amp_reader.py. : read_af_pr_condition now captures the ENMP formular : "max(($13),...)" line as a ninth group {"Formula": expr}. Every ENMP carries the line - empty on non-Formula parameters, and empty sets nothing, so the group's presence is the flag.
Flows through the live office.py _to_rows as {key: 'Formular', value: 'max(...)', section 'formula'} - zero changes needed in office.py/office_example.py.
office gate: 32 failed / 370 passed - identical with the office agent's chang revered (mock-behavior assertions under the office provider, pre-existing). Zero regressions.

Formula params in recipe-search
$N = N-th parameter of the recipe, 1-based .idp block order (verified: $13-18= CELL_BARY1...4, CELL_SPY, CELL_SPY1; unnamed blocks are valid refs)
```

읽은 내용입니다.

- ENMP 에 9번째 group `formula` 가 생겼고, 빈 값이면 group 자체가 없습니다. 그래서
  group 이 있느냐가 Formula 여부의 표지입니다.
- office adapter 는 바꿀 것이 없습니다. 기존 `_to_rows` 가 section 을 붙여 줍니다.
- `Formular` 와 `Formula` 가 섞여 있어 철자를 사용자에게 물었고, `Formula` 로
  확정했습니다(user-confirmed 2026-10-22).
- 처음 구현은 `$N` 을 `idp_image_info` 의 N 번째 **row** 로 풀었습니다. 3번 회신에서
  이 가정을 바꿨습니다.

## 2. 집에서 보낸 질문

- Q1. Formula parameter 의 AF/PR slot(`img_add2`)이 `non` 일 수 있습니까?
  (A 없음 / B 있음 / C 모름)
- Q2. `idp_image_info` 의 row 하나가 .idp block 하나와 정확히 대응합니까?
  (A 예 / B 아니오 / C 모름)
- Q3. 그 parameter 들의 AMP `Measurement` 는 정확히 `Formula` 입니까?
  (A 예 / B 다른 철자)

## 3. 사무실 회신 (원문)

```text
new findings from the office agent.
1. More operators than abs/max: also min(), average(), and bare +. And refs appear without the ($N) wrapping: max($2,$3,$4,$5), $17+$18. Your substitution must be a plain \$(\d+) token replace anywhere in the string - do NOT assume parens or a function context.
2. $N can reference another FORMULA param. MAX_DEL = max(($10)..($14)) where $11-$14 are themselves formulas (MC_BS-SB1 etc.); MF_WIG = $12+$13+$14 (all three are formulas).
3. A formula params itself can be UNNAMED (name "", formula abs($2-$3), PRMS measurement=8). Two consequences: (a) the resolution map may map a block number to "" - render $N (unnamed) or keep $N raw, never substitute an empty string; (b) these rows sit in idp_image_info with empty Parameter - the Formula table can show for them too.
4. Duplicate refs are legal (max($5,$6,$6,$7)) - harmless for substitution.
Re-confirmations: all params have a real ENMP slot (Q1: A); PRMP number == block number for all blocks (Q2: suffix-of-img-meas2 resolution holds); measurement : 8 -> exact "Formula" on every sampled PRMS including the unnamed ones (Q3:A).
Fleet-wide bonus: a CG5000's ENMP (older model) also carries the formula :'' line, same format.
the remaining unknowns are only the crossing case (a $N past a del block, none exists in a ~90 live formulas across recipes that I checked) which suffix resolution already immune-covers.
```

### 질문별 답

- Q1 → **A.** Formula parameter 는 모두 실제 ENMP slot 이 있습니다.
- Q2 → 파일 번호(PRMP·PRMS `00NN`)가 block 번호와 같습니다. 그래서 row 위치가 아니라
  `img_meas2` 번호로 `$N` 을 찾는 방식이 맞다는 답입니다.
- Q3 → **A.** 이름 없는 것을 포함해 표본 PRMS 모두 정확히 `Formula` 입니다.

### 읽은 내용과 틀렸던 가정

- **틀린 가정: `$N` = N 번째 row.** 파일 번호로 찾도록 바꿨습니다. 삭제된 block 이
  있어도 뒤의 참조가 옆 block 으로 밀리지 않습니다. 사무실은 삭제된 block 너머를
  가리키는 참조를 약 90개 formula 중에서 보지 못했습니다.
- 발견 1·4(괄호 없는 참조, `min`·`average`·`+`, 중복 참조)는 이미 `\$(\d+)` 전역
  치환이라 코드 변경이 필요 없었습니다. 실제 표본으로 test 만 추가했습니다.
- 발견 2(formula 가 formula 를 참조)는 이름만 바꿔 보여 주므로 변경이 없습니다.
- 발견 3(이름 없는 formula)은 집에서 한 번도 재현되지 않던 경로였습니다. 참조는
  빈 문자열로 바꾸지 않고 `$N` 그대로 두고, 표와 제목에는 `(이름 없음)` 을
  보입니다.
- `measurement=8`, `measurement : 8` 은 AMP 의 `Measurement` field 를 가리키는
  표기로 읽었습니다. 값 자체는 `Formula` 입니다.

### 반영 (`54d1475b`)

- frontend: `formulaRefNames` 가 block 번호 → Parameter 표를 `img_meas2` 번호로
  만들고, `resolveFormula` 가 그 표로 치환합니다.
- mock: 실제 표본 수식에서 고르고, recipe 마다 이름 없는 formula row 를 마지막
  block 으로 하나 둡니다. formula parameter 의 `img_add2` 는 비우지 않습니다(Q1).
- `recipe_idp.txt`: 위 사실과 CG5000 도 같은 줄을 가진다는 점을 기록했습니다.

## 4. 남은 OFFICE-VERIFY

- 이름 없는 block 이 formula 가 **아닌** 경우도 있는지. mock 은 이름 없는 row 를 모두
  formula 로 둡니다.
