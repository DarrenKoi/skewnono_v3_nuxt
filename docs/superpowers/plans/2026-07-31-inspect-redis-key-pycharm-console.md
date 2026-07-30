# Redis Key Inspector PyCharm Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `scripts/inspect_redis_key.py` from an argparse-driven `main()` function into a PyCharm-console worksheet whose Redis and DataFrame objects remain available as module variables.

**Architecture:** Keep the existing Redis formatting and inspection helpers import-safe. Put editable inspection settings at module scope and execute the read-only inspection inside the existing `__main__` guard, where assignments still create module globals visible to PyCharm.

**Tech Stack:** Python 3.14, pytest, Redis client helpers from `back_dev_home._runtime.office_redis`

## Global Constraints

- Redis inspection remains read-only: no write, expiry, or delete commands.
- `scripts.inspect_device_info_keys` must still import `_human_bytes` and `describe_dataframe` without opening a Redis connection.
- `client`, `key`, `kind`, `raw`, and `df` must remain available after PyCharm runs the file in its Python console.
- Do not add dependencies or restore command-line argument parsing.

---

### Task 1: Convert the Redis inspector into an interactive worksheet

**Files:**

- Create: `tests/test_inspect_redis_key_script.py`
- Modify: `scripts/inspect_redis_key.py:1-290`

**Interfaces:**

- Consumes: `redis_client()`, `read_dataframe(raw: bytes, key: str)`, `redis_text(value)`, and `STORE_ERRORS` from `back_dev_home._runtime.office_redis`
- Produces: editable module settings `KEY_NAME: str`, `ROWS: int`, and `UNIQUE_COLUMNS: list[str]`; console variables `client`, `key`, `kind`, `raw`, and `df`

- [ ] **Step 1: Write the failing console-execution tests**

Create `tests/test_inspect_redis_key_script.py`. Load the script with
`runpy.run_path(..., run_name="__main__")` while replacing
`back_dev_home._runtime.office_redis` with a complete in-memory module double.
Use a string-key fixture whose `get()` returns `b"parquet"` and whose
`read_dataframe()` returns a sentinel DataFrame-like object. Assert that the
returned namespace exposes:

```python
assert namespace["client"] is fake_client
assert namespace["key"] == namespace["KEY_NAME"].encode()
assert namespace["kind"] == "string"
assert namespace["raw"] == b"parquet"
assert namespace["df"] is sentinel_dataframe
```

Add a second test that imports the script with a non-main run name and asserts
the fake `redis_client()` was not called. This catches accidental Redis access
when `scripts.inspect_device_info_keys` imports the formatting helpers.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_inspect_redis_key_script.py -q
```

Expected: the console-execution test fails because the current namespace only
contains `main`, while `client`, `key`, `kind`, `raw`, and `df` are local to
that function.

- [ ] **Step 3: Implement the minimal worksheet behavior**

In `scripts/inspect_redis_key.py`:

1. Remove `argparse`, `sys`, `main()`, and all CLI parsing.
2. Add editable settings near the imports:

```python
KEY_NAME = "v3_df_sem_list"
ROWS = 5
UNIQUE_COLUMNS: list[str] = []
```

3. Keep all existing helper functions used by this file or
   `scripts.inspect_device_info_keys`.
4. Inside `if __name__ == "__main__":`, assign `client`, `key`, `kind`,
   `raw = None`, and `df = None` at module scope.
5. For a string key, fetch into `raw`, deserialize into `df`, and call
   `describe_dataframe(df, KEY_NAME, ROWS, UNIQUE_COLUMNS)`.
6. For non-DataFrame text and collection keys, retain the current bounded
   display behavior.
7. Raise clear `RuntimeError`, `KeyError`, or Redis client exceptions instead
   of converting them to integer CLI exit codes.
8. Rewrite the module docstring with PyCharm **Run File in Python Console**
   instructions and example console expressions such as `df.columns`,
   `df.dtypes`, and `df.head()`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_inspect_redis_key_script.py -q
```

Expected: both tests pass.

- [ ] **Step 5: Run compatibility and static verification**

Run:

```bash
.venv/bin/python -m py_compile scripts/inspect_redis_key.py
.venv/bin/python -c "from scripts.inspect_device_info_keys import _human_bytes, describe_dataframe"
.venv/bin/python -m pytest tests/test_inspect_redis_key_script.py -q
git diff --check
```

Expected: every command exits with status 0 and the pytest summary reports no
failures.

- [ ] **Step 6: Commit the implementation**

```bash
git add scripts/inspect_redis_key.py tests/test_inspect_redis_key_script.py
git commit -m "refactor(scripts): expose Redis inspection variables"
```
