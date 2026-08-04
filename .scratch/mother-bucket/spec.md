# device-statistics comparison — bucket 규칙 정정 + mother_para 도입

Status: approved (2026-08-04, user-confirmed)

## 문제

`/ebeam/cd-sem/device-statistics/comparison` 의 Lot 요약이 bucket 클릭을 반쪽만
반영합니다. 표의 숫자는 bucket 마다 바뀌지만, **버킷 정의 자체가 틀렸고** 일부
열은 bucket 을 아예 따라가지 않습니다.

- `only_normal` 이 `\bCD\b` 토큰을 이름 아무 데서나 찾아 `CD(E)`/`CD(F)`
  (추가계측)까지 포함합니다. `CONTEXT.md` 의 Main 정의와 어긋납니다.
- `mother_normal` 이 스텝 단위(`skip_yn` + 순수 CD 접미사)로만 갈립니다. 실제
  의미인 **mother 파라미터 view** 가 어디에도 구현돼 있지 않습니다 —
  `mother_para` 는 이 feature 의 데이터에 아예 없는 컬럼입니다.
- `중앙값 / outlier` 두 열은 의도적으로 bucket 과 무관하게 계산됩니다
  (`deviceProfile.ts:6-9`). 사용자 요구는 반대입니다.

## 결정 (user-confirmed 2026-08-04)

1. `only_normal` 과 `mother_normal` 은 **같은 oper_desc 필터**를 씁니다 —
   스텝명 끝 토큰이 정확히 `CD` 인 것만 (`ends_with_pure_cd`).
2. `mother_normal` 은 거기서 **한 단계 더** 들어갑니다 — mother 파라가 1개
   이상인 recipe 만 남기고, `para_*` 집계도 **mother 파라만** 셉니다 (둘 다).
3. `skip_yn != "Y"` 는 **두 버킷 모두**에 적용합니다.
4. `mother_normal` 의 health / violations / 판정범위도 **mother 파라만** 룰
   검증합니다.
5. `중앙값 / outlier` 는 **bucket 을 따라갑니다**.

### 새 버킷 규칙

| bucket | 규칙 |
| --- | --- |
| `all` | 모든 Step |
| `only_normal` | `is_measuring(skip_yn)` ∧ `ends_with_pure_cd(oper_desc)` |
| `mother_normal` | `only_normal` ∧ mother 파라 ≥1 · `para_*` 는 mother 파라만 |
| `only_sample` | `is_sample_recipe(recipe_id)` (변경 없음) |

`is_normal_step()` (CD 토큰 아무 위치) 은 소비처가 사라지므로 mock·office
어댑터·테스트에서 **삭제**합니다. 안 쓰는 판정 함수를 남기는 것이 두 정의가
다시 갈라지는 경로입니다.

수용된 부작용: `only_normal` / `mother_normal` 은 `avail_recipe ==
total_recipe` 가 됩니다 (skip 이 멤버십에 들어갔으므로).

## 설계

### mother 플래그의 단일 진실 원천

요약의 `para_*` 와 health 가 읽는 `parameters[]` 는 **서로 다른 모듈이 각자
난수로** 만듭니다 (`recipe_population.RecipeIdentity` vs
`recipe_params._build_parameters`). "이 recipe 에 mother 가 있는가" 를 두 곳에서
따로 정하면 *para 합계는 줄었는데 health 는 그대로*인, 오류 없이 조용히
어긋나는 화면이 됩니다.

그래서 `RecipeIdentity` 하나가 정합니다:

```
RecipeIdentity + mother_para_16 / 13 / 9 / 5
  mother_para_all == 0  ⟺  mother 없음  ⟺  mother_normal 에서 제외
      ├── statistics.py     mother_normal 버킷의 para_* 로 사용
      └── recipe_params.py  같은 identity 를 보고 parameters[].mother 표시
```

계약: `ParameterRow` 에 `mother: bool` 추가. 원천은
`idp_image_info.Mother_Para` (`docs/datatables/recipe_idp.txt:182`,
office 확인 2026-07-28) — parameter 1개당 bool 입니다.

### rng 순서 보존 (필수)

mother 카운트는 `_identity_pool` 루프 **안에서 굴리지 않습니다**. 완성된 풀을
한 번 더 훑는 **별도 rng** (`_identity_seed(lot_cd) ^ _MOTHER_SALT`) 로
만듭니다. 그 모듈 docstring 이 경고하듯 기존 루프에 난수 호출을 하나라도
끼우면 풀 뒷부분 recipe 가 전부 다른 값으로 다시 태어나 `recipe_id` ·
`oper_desc` 까지 바뀝니다. 별도 rng 면 기존 값이 한 바이트도 안 움직입니다.

### 프론트엔드 — 필터 하나, 소비처 둘

`buildLotVerdicts` 와 `detectDeviceOutliers` 는 둘 다 `RecipeInput[]` 을
받습니다. 입력을 한 번만 좁히면 health 와 중앙값/outlier 가 자동으로 같은
bucket 을 봅니다.

```
scopeRecipesToBucket(recipeParams, bucketKeys, motherOnly)
  └─ bucketRecipes ─┬─ buildLotVerdicts  → health / violations / 판정범위
                    └─ groupRecipesByLot → 중앙값 / outlier / drill
```

`ruleEngine.ts` · `outlierDetect.ts` · `lotHealth.buildLotVerdicts` 의 로직은
무수정. `Parameter` 에 `mother?: boolean` 만 추가됩니다.

`scopeRecipesToBucket` 은 `comparison.vue` 안이 아니라 `lotHealth.ts` 의 pure
함수로 둡니다 — `.vue` 안에 있으면 `npm test` 가 볼 수 없습니다.

### 이번 변경으로 거짓이 되는 기존 주석

- `deviceProfile.ts:6-9` — "버킷을 바꿔도 중앙값이 움직이면 안 된다". 정반대로
  다시 씁니다.
- `comparison.vue:591-597` — "outlier drill 은 일부러 안 닫는다, 버킷이 바뀌어도
  보여줄 게 안 변하므로". 이제 변하므로 **drill 도 닫아야** 합니다.

## 영향 범위

백엔드: `contracts.py`, `providers/recipe_population.py`,
`providers/statistics.py`, `providers/recipe_params.py`,
`providers/office_example.py`, `tests/test_recipe_population.py`

프론트: `utils/ruleEngine.ts`, `utils/lotHealth.ts`, `utils/deviceProfile.ts`,
`pages/ebeam/cd-sem/device-statistics/comparison.vue`

문서: `CONTEXT.md`, `docs/datatables/planstep_r3.txt`,
`docs/datatables/recipe_params.txt`, `docs/datatables/recipe_idp.txt`,
`back_dev_home/ebeam/cdsem/device_statistics/MIGRATION.md`

## 테스트

- 버킷 predicate 재작성, `is_normal_step` 대조 삭제
- 서열 `all > only_normal > mother_normal > only_sample` 유지
  (계산상 R000 에서 `189 > 79 > 67 > 48`)
- **신규** 버킷 멤버십 ⟺ `recipe_params` 의 mother 파라 존재 일치 (드리프트 방지)
- **신규** `scopeRecipesToBucket` 의 `node --test`

## OFFICE-VERIFY

- mother 파라 발생률(이 mock 은 recipe 의 약 85%가 mother 보유, 보유 시 각 bin
  의 25~45%가 mother). 실물 비율은 확인된 바 없습니다.
- office 어댑터가 `Mother_Para` 를 어느 index 에서 읽어 recipe 단위로 굴릴지 —
  `cdsem_idp_ver` 의 parameters blob 내부 구조가 아직 미확인
  (`recipe_params.txt` 의 세분도 경고와 같은 항목).
