# sem_list — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/sem-list

- Handler: `routes.py` → `data.get_sem_list()`
- Contract: `SemListRow` —

  ```python
  class SemListRow(TypedDict):
      fac_id: str
      eqp_id: str
      eqp_model_cd: str
      eqp_grp_id: str
      vendor_nm: Literal["HITACHI", "AMAT"]
      eqp_ip: str
      fab_name: str
      updt_dt: str
      available: Literal["On", "Off"]
      version: int
  ```

- Mock behavior: generates a deterministic 300-row fleet (`random.Random(42)`)
  spanning six `fac_id` values (`M11, M12, M14, M15, M16, R3`). `R3`-class
  facilities only ever produce `fab_name` of `R3` or `R4` (no letter suffix);
  every other `fac_id` gets a single `A`/`B`/`C` suffix appended
  (`fab_name = f"{fac_id}{suffix}"`). `vendor_nm` is a coin flip between
  `HITACHI` and `AMAT`, and `eqp_model_cd`/`eqp_id` prefixes are drawn from
  vendor-specific pools so the model code and equipment id prefix always
  agree with `vendor_nm`. `updt_dt` is an ISO-8601 UTC timestamp with a
  literal `Z` suffix, anchored at `2026-04-19T00:00:00Z` minus a random
  0–90 day offset. `available` is `"On"` 90% of the time.
- Office data source: <!-- OFFICE: equipment master table / OpenSearch sem-fleet index -->
- Notes: the full list is unfiltered and unpaginated — the route returns
  every row every call. There is no empty-result case in the mock (always
  300 rows); the office adapter should still return `[]` gracefully if the
  fleet table is empty rather than erroring, since the contract test only
  requires "not empty" as a mock-mode sanity check, not a hard invariant of
  the contract itself.

## Verify

    SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/pytest back_dev_home/sem_list
