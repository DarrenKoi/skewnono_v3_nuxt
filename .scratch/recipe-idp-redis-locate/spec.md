# Redis-first IDP location for recipe open

Status: approved
Date: 2026-07-29
Feature: `back_dev_home/ebeam/hitachi/recipe_search`
Surface: `providers/office_example.py` (template; `office.py` is the gitignored copy)

## Problem

`get_recipe_open_data` locates a recipe's `.idp` file by querying OpenSearch
`meas_hist_{cdsem,hvsem}` for the newest document naming that recipe, then
assembling an FTP path from four of its fields. That works, but it makes recipe
open depend on the recipe having been **measured** — a recipe that exists in the
catalog and has never run has no locatable `.idp` at all — and it spends an
OpenSearch round trip on what is really a registry lookup.

Two Redis hashes now hold that registry directly (user-confirmed 2026-07-29):

```text
v3_{cdsem|hvsem}_rcp_loc_{fab}        field = full_name, value = [idw_name, idp_name]
v3_{cdsem|hvsem}_tools_in_rcp_{fab}   field = full_name, value = [eqp_id, ...]
```

`{fab}` is the lowercase fab name, matching the existing
`v3_{cdsem|hvsem}_unique_rcp_list` hash-field convention.

## Goal

Resolve the `.idp` location from Redis when it can, fall back to the existing
OpenSearch path when it cannot, and use the tool list Redis provides to survive
a single unreachable tool.

Non-goals: the batched `/compare` FTP work (`tools_in_rcp` is its missing input,
but it stays a separate job); any change to `data.py`, `routes.py`,
`contracts.py`, or mock behavior.

## What the FTP fetch needs

```text
host = eqp_ip
path = /HITACHI/DEVICE/HD/{class_name}/data/{idw_stem}/{idp_stem}.idp
```

Redis supplies `idw_name` and `idp_name` directly. The other two are derived:

- `class_name` — the prefix of the `full_name` key being looked up.
  `full_name = f"{class_name}/{recipe_name}"` is documented in
  `docs/datatables/meas_hist.txt`, so `recipe_id.split("/", 1)[0]` is the class.
- `eqp_ip` — Redis gives `eqp_id`, so the roster resolves it. This is the
  `eqp_id -> eqp_ip` join through `sem_list.data.get_sem_list()` that
  `lateral_recipe` already performs, and that `docs/datatables/recipe_idp.txt`
  currently claims recipe open does not need. That claim becomes true only of
  the fallback path and must be corrected.

## Design

### Locate returns candidates, not a location

Retrying down a tool list means the resolver cannot return exactly one answer.
Both strategies produce an ordered `list[_IdpLocation]` and feed one shared
download loop. `_IdpLocation` itself is unchanged.

```text
get_recipe_open_data
  ├─ _locate_idp(tool_type, recipe_id, fab_name) -> list[_IdpLocation]
  │    ├─ _locate_via_redis(...)      -> list | None   NEW, tried first
  │    └─ _locate_via_meas_hist(...)  -> list          today's code, lightly changed
  ├─ _download_first(candidates, tmp) -> Path          NEW retry loop
  ├─ _parse_idp                                        unchanged
  └─ _to_detail_response                               unchanged
```

Everything below the download is untouched, so `tests/test_idp_mapping.py`
keeps passing without edits.

### Redis strategy

```python
_FAMILY: dict[ToolType, str] = {"cd-sem": "cdsem", "hv-sem": "hvsem"}

def _fab_hash(kind: str, tool_type: ToolType, fab_name: str) -> str:
    """kind is "rcp_loc" or "tools_in_rcp"."""
    return f"v3_{_FAMILY[tool_type]}_{kind}_{fab_name.strip().lower()}"
```

Lowercasing happens at the Redis boundary and never leaks upward — the same
rule the catalog path already follows.

| Step | Action | Returns `None` when |
| --- | --- | --- |
| 1 | check `fab_name` | blank — no key can be built |
| 2 | `hget(rcp_loc, recipe_id)` -> `[idw_name, idp_name]` | field missing, or fewer than 2 entries |
| 3 | `hget(tools_in_rcp, recipe_id)` -> eqp_id list | field missing or empty |
| 4 | resolve each eqp_id against the roster | none resolves |
| 5 | order `available == "On"` first, input order kept within group | — |
| 6 | derive `class_name`, stems via existing `_stem()` | — |

Values parse through the existing `_parse_recipe_list`, which already tolerates
JSON, Python `repr`, and comma-CSV — the same ambiguity the loader jobs have for
the catalog hash. It is renamed `_parse_str_list` since it now serves three
hashes.

Every `None` is logged at INFO naming the step that bailed, so an office-side
fallback is diagnosable rather than mysterious.

### Fallback is all-or-nothing on lookup

```text
rcp_loc HIT  + tools HIT   -> redis        (0 OpenSearch calls)
rcp_loc MISS + tools HIT   -> opensearch
rcp_loc HIT  + tools MISS  -> opensearch
rcp_loc MISS + tools MISS  -> opensearch
fac_id blank               -> opensearch
```

A download failure after a successful Redis lookup does **not** retry against
OpenSearch. The path came from the recipe registry, so an unreachable tool is a
tool problem, not a lookup problem.

### OpenSearch strategy

Today's `_locate_idp` body becomes `_locate_via_meas_hist` with one behavioral
change: it returns **all** complete hits (still newest-first, still capped at
`_LOCATE_CANDIDATES = 5`) instead of the first one, feeding the same retry loop.
Error text and the "recipe never measured" `LookupError` are unchanged. Net
effect on the existing path: a recipe whose newest tool is unreachable now falls
through to the previous run's tool instead of returning 502.

### Download retry and the SSRF guard

```python
for location in candidates:
    try:
        return _download_idp(location, dest_dir)
    except InvalidToolIp:   # skipped, WARNING logged, remembered
    except LookupError:     # refused / no such file, remembered
```

A single stale IP in the roster must not fail every recipe on that tool, so an
out-of-subnet candidate is skipped with a WARNING rather than propagated. If
**every** candidate was rejected by the guard, the original `InvalidToolIp` is
re-raised — preserving the behavior `MIGRATION.md` documents for the case that
actually indicates misconfiguration. Mixed failures raise `LookupError` naming
each tool and its reason.

### Roster caching

`get_sem_list()` reads two parquet blobs from Redis and merges them office-side,
which is too heavy to repeat per recipe open. The derived
`eqp_id -> (eqp_ip, available)` index is wrapped in `ttl_cache` (900 s, already
imported from `_office_search`). Cost: a re-IP'd tool takes up to 15 minutes to
appear.

## Documentation

Per the two-places rule in `CLAUDE.md`, office DB facts land in both the schema
of record and the mock docstring:

- `docs/datatables/recipe_name_list.txt` — both new hash schemas, marked
  `user-confirmed 2026-07-29`
- `docs/datatables/recipe_idp.txt` — redraw the source chain Redis-first, and
  correct the passage asserting the `sem_list` join is unnecessary
- `providers/mock.py` docstring — name the new office source
- `MIGRATION.md` — `/recipe-detail` source and error tables
- `providers/office_example.py` module docstring

## Tests

New `tests/test_idp_locate.py`, importing `providers.office_example` (never the
gitignored `office.py`), requiring no Redis, OpenSearch, or FTP:

- key building: fab lowercased, family resolved from `tool_type`
- `class_name` split, including a name with no `/` and one with two
- value parsing for both JSON and `repr` shapes
- candidate ordering: `On` first, input order stable, unresolvable eqp_id dropped
- `_download_first` retry against a stubbed downloader, including the
  all-candidates-rejected `InvalidToolIp` re-raise

## Verify

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q
npm run lint:md
```

Office-side (Phase 2), after `cp office_example.py office.py`:

```bash
SKEWNONO_RECIPE_SEARCH_PROVIDER=office \
  .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search
```

## Open at the office

- Confirm the real `rcp_loc` values are 2-entry lists in `[idw, idp]` order —
  the adapter reads them positionally.
- Confirm `class_name` as the `full_name` prefix produces a directory that
  exists on the FTP tree for a catalog name like `1/AC_M2_TAT`.
The eqp_id spelling in `tools_in_rcp` matches the `sem_list` roster
(user-confirmed 2026-07-29), so no normalization belongs on that join — an
unresolvable eqp_id means the roster is missing the tool, not that the two
sources disagree about how to write its name.
