# oc-review — align 기준 이미지 404 수정 (align-image-404)

실행 2026-08-22. 대상은 `main..work/align-404` (커밋 `8a5d7fcf`) 이며, 9 files /
+468 −52 입니다. `providers/` 와 `docs/datatables/` 를 건드리므로 overlay 의
escalation surface 에 해당하여 `heavy` (glm-5.3, variant high) 로 두 축을 병렬
실행했습니다. 두 축 모두 exit 0 입니다.

- Standards 기준 문서: `CLAUDE.md`, `DESIGN.md`,
  `docs/back-end/provider-selection.md`,
  `back_dev_home/ebeam/recipe_search/MIGRATION.md`,
  `docs/datatables/recipe_idp.txt`
- Spec: `.scratch/align-image-404/spec.md`

## Standards (exit 0) — 모델 원문

> Now let me read the documented standards files.
> ## Review: 8a5d7fcf (align images discovered from folder listing)
>
> **Positives first:** the mock/office formula-drift smell is *avoided* — both providers route through one `rawfiles.align_reference_images(listing)`; the fabricated 1-in-4 OM-only ratio is marked `OFFICE-VERIFY`; `docs/datatables/recipe_idp.txt` and `mock.py` changed together; no vendor path, no inline hex, `usePersistedState` untouched.
>
> ### HARD
>
> 1. **`back_dev_home/ebeam/recipe_search/MIGRATION.md` not updated.** Its endpoint table still reads `` `/align-images` | Redis recipe registry (fallback: meas_hist) — resolution only, no FTP | wired`` and its narrative says "No FTP happens in this endpoint. Align image names are computable … so the tool is only dialed when `/recipe-image` is asked for the bytes." The change makes `/align-images` perform an NLST round trip via `_list_raw_dirs` (office_example.py:1891). CLAUDE.md defers per-feature specifics to MIGRATION.md; it now states the opposite of the code. `recipe_idp.txt` was rewritten but this doc was left contradicting it.
>
> ### JUDGEMENT
>
> 2. **Duplicated Code** — `align_point_of` (rawfiles.py:280–285) re-hand-rolls the basename/extension extraction `image_variants` already owns, and its own docstring admits it ("on the same rule `image_variants` matches by"):
>    ```python
>    base = str(entry).replace("\\", "/").rsplit("/", 1)[-1]
>    dot = base.rfind(".")
>    if dot < 0 or base[dot:].lower() not in IMAGE_EXTENSIONS:
>    ```
>    Extract a shared `_basename_ext(entry)` helper. Likewise `{p_no:04d}` now appears in both `align_names` and `align_reference_images` — the `ALIGN_IMAGE_PREFIX` constants were extracted precisely to keep derivation in one place, but the padding rule still lives in two.
>
> 3. **Malformed docstring** — office_example.py `get_align_images`: the diff consumed the second `Raises:` header, so the `LookupError:` entry (line ~1879) now dangles inside the `eqp_id` prose paragraph instead of a Raises section.
>
> 4. **Stale contract comment** — contracts.py:203 still says `optic: str  # "OM" (P.No 1) or "SEM" (P.No 2)`, but the change introduces `optic: ""` for unknown points (documented in `useRecipeParamDetail.ts`, emitted by the office adapter). CLAUDE.md: office adapters normalize to `contracts.py` — the contract now misdescribes its own value domain.
>
> No other baseline smells found; nothing ruff/eslint would catch.

## Spec (exit 0) — 모델 원문

> **(a) Missing / partly done**
>
> 1. **"listing 을 못 한 경우와 이미지가 없는 경우를 구분한다"** — done on the office side (`SourceUnavailable` → 503) and in the modal's new empty branch, but the distinction is unreachable at home. `_mock_align_listing` (providers/mock.py) always yields ≥1 point, and mock `get_align_images` can neither fail a listing nor return an empty set, so the frontend's "이 레시피에는 정렬 기준 이미지가 없습니다" branch (AlignImagesModal.vue) is dead code in Phase 1. The spec's rationale — "엔지니어가 있지도 않은 recipe 결함을 찾게 됩니다" — applies to the empty case too, and home can't exercise it.
>
> **(b) Scope creep**
>
> 2. **Suffix-split align images.** The spec asks only "align 이미지 이름도 `param-detail` 과 같이 폴더 listing 에서 찾습니다." The diff additionally invents `-U`/`-L` split discovery (`image_variants` in `align_reference_images`, `test_a_split_align_image_is_found_rather_than_missed`, docs claiming "suffix 확장이 실제로 존재한다면 그대로 찾아냅니다"). Spec scope: "범위는 'production 에서 다수 발생하는 404 를 없앤다' 이며, 그 이상은 요구되지 않았습니다."
>
> 3. **P.No ≥ 3 with blank optic.** `(p_no, align_optics(p_no) or "", name)` plus the modal's `v-if="image.optic"` badge suppression handle a case the spec explicitly leaves as OFFICE-VERIFY and never asked to render.
>
> **(c) Implemented but wrong-looking**
>
> 4. **test_align_images.py module docstring contradicts the code it sits above:** "a tool that cannot be listed still falls back to the derived pair so a dead tool reports itself as dead rather than as empty." The implementation has no such fallback — it raises `SourceUnavailable` — and the file's own `test_an_unlistable_tool_is_reported_as_unavailable_not_as_empty` asserts the raise. The docstring describes the old bug as the new behavior.
>
> 5. **routes.py:443 docstring is now false:** "Resolution only; the tool is dialed by ``recipe-image``." With this change the office adapter dials the tool (NLST) inside `align-images`. Untouched by the diff, but the change makes a documented claim wrong — and it was the claim the 404 fix had to overturn.
>
> Spec items 1 (verified names only) and 3–4 (home reproduces the 404; HTTP round-trip regression test in test_raw_routes.py) are correctly and thoroughly done.

## Claude 의 판단

인용된 줄을 전부 열어 확인한 뒤 처리했습니다.

### 인정하고 고친 것 (6건)

| 지적 | 축 | 확인 결과 |
| --- | --- | --- |
| `MIGRATION.md` 미갱신 | Standards HARD | 사실입니다. 52행 표와 73행 본문이 "resolution only, no FTP" 라고 코드와 정반대를 말하고 있었습니다. `recipe_idp.txt` 만 고치고 이 파일을 빠뜨린 것은 overlay 가 이름 붙인 **doc/mock split** 과 같은 종류의 누락입니다. |
| `contracts.py` optic 주석 | Standards JUDGEMENT | 사실입니다. TS 쪽 타입 주석만 갱신하고 Python contract 는 그대로 두었습니다. office adapter 가 `""` 를 내보내는데 contract 는 여전히 `"OM" 또는 "SEM"` 이라고 적혀 있었습니다. |
| `get_align_images` docstring 파손 | Standards JUDGEMENT | 사실이며 이번 diff 가 만든 것입니다. `Raises:` 헤더를 하나 지우는 과정에서 `LookupError:` 항목이 산문 문단 아래 고아로 남았습니다. |
| 중복 파싱 (`align_point_of` ↔ `image_variants`) | Standards JUDGEMENT | 사실입니다. `_image_file()` 로 뽑아 두 곳이 같은 규칙을 공유하게 했습니다. `{p_no:04d}` 중복도 `align_image_stem()` 으로 모았습니다. |
| `test_align_images.py` 모듈 docstring | Spec (c) | 사실이며 이번 diff 가 만든 것입니다. 도중에 폴백을 없애고 503 으로 바꾸면서 테스트는 고쳤는데 모듈 docstring 은 옛 동작을 새 동작으로 설명하고 있었습니다. |
| `routes.py` align-images docstring | Spec (c) | 사실입니다. diff 가 건드리지 않은 줄이지만, 이번 변경이 그 주장을 거짓으로 만들었습니다. |

`_mock_align_listing` 이 빈 폴더를 못 만들어 modal 의 "정렬 기준 이미지가
없습니다" 분기가 home 에서 죽은 코드라는 Spec (a) 1번도 인정하고 고쳤습니다.
"home 에서 렌더링되지 않는 화면 경로는 아무도 개발하지 않는다" 는 이 저장소가
스스로 적어 둔 원칙이며, 검토 과정에서 한 번 고려했다가 범위를 이유로 접었던
항목입니다. 다만 "align point 가 0 개인 recipe" 는 확인된 사실이 아니므로
비율을 OM-only 보다 낮추고 `OFFICE-VERIFY` 로 명시했습니다.

### 동의하지 않는 것 (2건)

**Spec (b) 2 — suffix 분할 발견이 범위 초과라는 지적.** 동의하지 않습니다.
spec 은 "align 이미지 이름도 param-detail 과 같이 폴더 listing 에서 찾습니다"
라고 적혀 있고, `param-detail` 이 쓰는 도구가 바로 `image_variants` 입니다.
분할 파일을 일부러 무시하는 구현은 코드가 더 길어지고(`image_variants` 대신
`f"{stem}.jpeg" in entries`), 없앤 추측을 한 겹 되살립니다. 즉 분할 지원은
추가된 기능이 아니라 기존 도구를 재사용한 결과입니다. 다만 그것을 굳이
테스트와 문서로 강조한 부분은 지적대로 부가물이 맞습니다.

**Spec (b) 3 — P.No ≥ 3 의 빈 optic 이 범위 초과라는 지적.** 동의하지
않습니다. `contracts.py` 의 `optic` 은 `str` 이므로 `align_optics()` 가 돌려주는
`None` 을 그대로 실을 수 없습니다. `or ""` 는 요청되지 않은 기능이 아니라
contract 를 지키기 위한 최소 조치입니다. modal 의 `v-if` 한 줄은 그 값을 화면에
그대로 찍지 않기 위한 짝입니다.

### 두 축이 놓친 것

`param-detail` 의 listing 실패 폴백은 여전히 HV-SEM 에서 404 를 냅니다
(`{stem}.jpeg` 는 분할된 폴더에 없습니다). spec 의 "범위 밖" 에 적어 둔 대로
실제로 발생 중이라는 증거가 아직 없어 이번 변경에 포함하지 않았습니다. 확인
방법은 `/admin-logs` 에서 status 404 · path 에 `recipe-image` 인 행의
`query_string` 을 읽어 `name` 이 bare stem 인지 보는 것입니다.

## 결과

| 축 | 건수 | 가장 무거운 것 |
| --- | --- | --- |
| Standards | 4 (HARD 1, JUDGEMENT 3) | `MIGRATION.md` 가 코드와 정반대를 말하고 있던 것 |
| Spec | 5 (누락 1, 범위 2, 구현 2) | 모듈 docstring 이 옛 동작을 새 동작으로 설명한 것 |
