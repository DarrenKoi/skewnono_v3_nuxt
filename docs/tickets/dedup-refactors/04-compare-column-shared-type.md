# 04 — One compare-column type and one spans-fabs predicate

**What to build:** the `{recipe_id, fab_name}` compare column is re-declared three times — `ParameterSelectorColumn`, inline columns in `CompareMatrix`, `compareColumns` in `RecipeCompareView` — plus the near-identical `CompareRecipeRef` that calls the same value `recipe_name`. The "spans fabs" predicate is likewise computed three different ways (`new Set(...fab_name).size > 1` twice, inside `compareRecipeLabels`, and via `fab_names.length` in the chip row). Export one `CompareColumn` type and one shared predicate; while touching it, settle the `recipe_id` vs `recipe_name` naming — the backend MIGRATION already admits they are the same string.

**Why:** review Standards axis, judgement call (Data Clump / Duplicated Code) with a visible symptom risk: three "spans fabs" predicate variants can disagree — the fab chip shows in one compare view and not another for the same data. The `recipe_id` vs `recipe_name` split for the same string (the backend MIGRATION admits they are equal) is a Mysterious Name that has already confused one reader — the reviewer had to verify equality from a migration note.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — be9c0218 — CompareColumn·spansFabs, recipe_id 를 정본으로 확정(요청 본문의 recipe_name 은 와이어 계약)

- [ ] One exported `CompareColumn` type is consumed by ParameterSelector, CompareMatrix, and RecipeCompareView
- [ ] One shared spans-fabs predicate replaces the three variants
- [ ] `recipe_id` / `recipe_name` naming is decided and applied consistently across the compare surface
