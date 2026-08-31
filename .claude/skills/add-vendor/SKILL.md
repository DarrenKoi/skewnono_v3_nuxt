---
name: add-vendor
description: Use when adding a new e-beam tool family (VeritySEM, Provision, or a future one) to an existing backend feature — scaffolds providers/<family>/, the datatables entry, MIGRATION.md, and the contract tests in the required order. Triggers on "VeritySEM 붙이기", "Provision 연결", "새 계열 추가", "add a tool family".
argument-hint: <feature> <family> (e.g. storage veritysem)
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

# Add a tool family to a feature

**Read [`docs/back-end/vendor-onboarding.md`](../../../docs/back-end/vendor-onboarding.md)
first.** It holds every rule and the reason behind it; this file is only the
running order. Do not restate the rules here — two copies drift apart.

## Scope check

- Target must be an existing feature under `back_dev_home/ebeam/<feature>/`.
- Family name must already be in `back_dev_home/ebeam/_tool_specs.py`
  (`SLUG_TO_ADAPTER`). If it is not, that registry entry comes first — the
  adapter folder name is read from there, never invented here.
- `afm`, `skew`, `chat` are deferred: skip them.

## The eight steps, in order

Do them in order. The order is the convention — a mock written before the
contract makes the contract follow the mock.

- [ ] **1. 계약 확인** — read `<feature>/contracts.py`. Do NOT add a
      family-specific TypedDict. If the new family cannot fill a field, write
      the null convention (`""` / `None`) into the contract's docstring.
- [ ] **2. 스키마 기록** — add or extend `docs/datatables/<source>.txt`. The
      office key/index name is decided here. Nothing is known about AMAT
      sources yet, so mark every line `OFFICE-VERIFY` until a real office run
      confirms it. Add the file→source→feature row in
      `docs/datatables/README.md`.
- [ ] **3. mock 작성** — `<feature>/providers/<family>/mock.py`. Derive the
      tool list from `sem_list` (`vendor_nm` row), never generate it
      independently. The docstring records the same office facts as step 2.
- [ ] **4. 템플릿 작성** — `<feature>/providers/<family>/office_example.py`,
      tracked, `NotImplementedError` bodies, same public functions as the
      family mock. Never create `office.py` at home.
- [ ] **5. 디스패처 배선** — add `_adapter()` to
      `<feature>/providers/{mock,office_example}.py` (keep both files at the
      feature level). The 501 policy belongs to the `office_example.py`
      dispatcher alone — the `mock.py` one just resolves the
      `<family>/mock.py` written in step 3. `AdapterNotWired` lives in
      `back_dev_home/ebeam/_adapters.py`, created with the first family and
      never per feature. Keep the `exc.name` guard. Copy the shape from
      `back_dev_home/ebeam/hardware/providers/office_example.py`'s `_tab()`,
      then change the fallback policy.
- [ ] **6. 문서 갱신** — `<feature>/MIGRATION.md`: endpoint, contract, mock
      behaviour, office source. Four items, one block per endpoint.
- [ ] **7. 테스트** — parametrize `<feature>/tests/test_contract.py` and
      `test_office_template.py` over the new family. Add a case for the
      unwired-adapter 501 path.
- [ ] **8. 사무실 연결** — office side only:
      `python -m scripts.adapters.sync_office_adapters <feature>/<family>`, then verify
      with `GET /api/health/providers`. At home, stop after step 7 and say so.

## Gates before reporting done

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/<feature> -q
npm run lint:md          # from the repo root, if any Markdown changed
```

Then run the `home-to-office` skill on the feature and report its verdict.

## Report

State which of the eight steps landed, which are office-only, and every
`OFFICE-VERIFY` line you added — those are the open questions for the next
office session.
