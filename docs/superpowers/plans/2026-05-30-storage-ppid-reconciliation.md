# Storage / PPID Page Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the storage page (backend mock + frontend table) with `docs/datatables/storage_ppid.txt`: surface "storage not available" rows in the main table, and replace the synthetic "Storage Unreachable" table with a real "PPID not available" daily IP list joined against `sem_list`.

**Architecture:** Backend stays feature-sliced (`back_dev_home/ebeam/hitachi/storage/{data,routes}.py`). The main storage df gains nullable storage fields (a tool can fail storage collection while still reporting recipe/ppid counts). The second dataset is re-grounded on the Redis shape `v3_hitachi_sem_ppid_not_avail` → `hget(key, YYYYMMDD)` → list of IPs, retained for 30 days; IPs are joined against `get_sem_list()` to enrich, with unmatched IPs surfaced as orphan rows. Frontend mirrors with nullable types, an "N/A" row state + stat + filter, and a retitled "PPID Unreachable" table that keeps a consecutive-days-unreachable streak column.

**Tech Stack:** Flask blueprints (mock data), Nuxt 4 + NuxtUI (`UTable`, `useAsyncData`), TypeScript composables.

**No test framework exists in this repo (mock-data project).** Verification is by running the data functions through `.venv/Scripts/python.exe` and by `npm run typecheck` / `npm run lint` in `front-dev-home/`.

---

## File Structure

- Modify `back_dev_home/ebeam/hitachi/storage/data.py` — nullable `StorageRow`, storage-N/A rows, replace unavailable-snapshot logic with `get_ppid_unavailable` (sem_list join, 30-day window, orphans).
- Modify `back_dev_home/ebeam/hitachi/storage/routes.py` — endpoint `/<tool_slug>/storage-unavailable` → `/<tool_slug>/ppid-unavailable`.
- Modify `front-dev-home/app/composables/useStorageApi.ts` — nullable `StorageRow`, rename types/fns to `PpidUnavailable*`, new endpoint, `isStorageUnavailable` helper.
- Modify `front-dev-home/app/components/ebeam/StorageView.vue` — cadence label, N/A cell rendering + stat + filter, retitled PPID table with streak + orphan handling.
- Modify `docs/api-contracts/cdsem-storage.yaml` and `docs/api-contracts/hvsem-storage.yaml` — nullable fields, renamed endpoint, Redis-key note.

---

## Task 0: Pre-flight — find all references to the renamed surface

**Files:** none (read-only)

- [ ] **Step 1: Grep for old endpoint / function / type names**

Run (Grep tool or rg):
- `storage-unavailable`
- `get_storage_unavailable`
- `fetchUnavailable|StorageUnavailableSnapshot|UnavailableRow`

Expected references: `StorageView.vue`, `useStorageApi.ts`, `storage/routes.py`, `storage/data.py`, the two YAML contracts, possibly `scripts/capture_fixtures.py` and `back_dev_home/README.md`. Note every hit — each must be updated by a later task. If `scripts/capture_fixtures.py` hits the old path, add its update to Task 6.

---

## Task 1: Backend — storage-not-available rows in the main df

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/storage/data.py` (the `StorageRow` TypedDict ~lines 30-43 and `_generate_rows` ~lines 61-143)

- [ ] **Step 1: Make `StorageRow` storage fields nullable**

Replace the `StorageRow` class body so storage-collection fields can be empty/None while recipe fields stay required:

```python
class StorageRow(TypedDict):
    eqp_id: str
    eqp_ip: str
    fac_id: str
    total: str            # "" when storage collection failed
    used: str             # "" when storage collection failed
    avail: str            # "" when storage collection failed
    percent: str          # "" when storage collection failed
    storage_mt: str | None  # None when storage collection failed
    rcp_counts: int
    rcp_counts_mt: str
    storage_mt_date: str  # "" when storage collection failed
    fab_name: str
    eqp_model_cd: str
```

- [ ] **Step 2: Emit ~8% storage-N/A rows in `_generate_rows`**

In `_generate_rows`, compute the sample timestamp and recipe count *before* the capacity block, then short-circuit unavailable rows. Replace the body of the `for _ in range(n_rows):` loop (from the `storage_mt = now - timedelta(...)` block through the final `rows.append(...)`) with:

```python
        # Sample timestamp drives both storage_mt and rcp_counts_mt; recipe
        # (ppid) counting is a separate collection path from storage capacity.
        sample_base = now - timedelta(
            days=rng.uniform(0, 7),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
            seconds=rng.randint(0, 59),
            microseconds=rng.randint(0, 999999),
        )

        # Tools cap at 50,000 recipes. Seed a realistic mix so the UI's
        # warning (>49,000) and critical (>49,800) tiers are exercised.
        rcp_roll = rng.random()
        if rcp_roll < 0.08:
            rcp_counts = rng.randint(49_801, 49_990)
        elif rcp_roll < 0.20:
            rcp_counts = rng.randint(49_001, 49_800)
        elif rcp_roll < 0.40:
            rcp_counts = rng.randint(35_000, 49_000)
        else:
            rcp_counts = rng.randint(2_000, 35_000)
        rcp_counts_mt = sample_base + timedelta(
            hours=rng.uniform(-0.5, 0.5),
            microseconds=rng.randint(0, 999999),
        )

        # ~8% of tools fail storage collection: storage_mt is None and the
        # capacity fields are blank, but recipe counts still report.
        if rng.random() < 0.08:
            rows.append(StorageRow(
                eqp_id=eqp_id,
                eqp_ip=eqp_ip,
                fac_id=fac_id,
                total="",
                used="",
                avail="",
                percent="",
                storage_mt=None,
                rcp_counts=rcp_counts,
                rcp_counts_mt=_iso_z(rcp_counts_mt),
                storage_mt_date="",
                fab_name=fab_name,
                eqp_model_cd=model,
            ))
            continue

        # Capacity: 70% chance GB (500-999), 30% chance TB (1.0-2.0)
        if rng.random() < 0.7:
            total_gb_value = rng.randint(500, 999)
            total_label = f"{total_gb_value}G"
            total_value = float(total_gb_value)
        else:
            total_tb_value = round(rng.uniform(1.0, 2.0), 1)
            total_label = f"{total_tb_value}T"
            total_value = total_tb_value * 1024

        used_ratio = rng.uniform(0.2, 0.9)
        used_value = total_value * used_ratio
        avail_value = total_value - used_value

        used_label = _format_size_gb(used_value)
        avail_label = _format_size_gb(avail_value)
        percent_label = f"{int(used_ratio * 100)}%"

        rows.append(StorageRow(
            eqp_id=eqp_id,
            eqp_ip=eqp_ip,
            fac_id=fac_id,
            total=total_label,
            used=used_label,
            avail=avail_label,
            percent=percent_label,
            storage_mt=_iso_z(sample_base),
            rcp_counts=rcp_counts,
            rcp_counts_mt=_iso_z(rcp_counts_mt),
            storage_mt_date=sample_base.date().isoformat(),
            fab_name=fab_name,
            eqp_model_cd=model,
        ))
```

(The `eqp_id` / `eqp_ip` / `fac_id` / `fab_name` / `model` / prefix lines earlier in the loop are unchanged.)

- [ ] **Step 3: Verify shape — has both normal and N/A rows**

Run:
```
.venv/Scripts/python.exe -c "from back_dev_home.ebeam.hitachi.storage.data import get_storage; rows=get_storage('cdsem'); na=[r for r in rows if r['storage_mt'] is None]; print('total',len(rows),'na',len(na)); print('na sample',na[0] if na else None)"
```
Expected: `total 300`, `na` between ~15–35, and the sample row has `storage_mt=None`, blank `total/used/avail/percent/storage_mt_date`, and a populated integer `rcp_counts`.

- [ ] **Step 4: Commit**

```bash
git add back_dev_home/ebeam/hitachi/storage/data.py
git commit -m "feat(storage): emit storage-not-available rows in mock df"
```

---

## Task 2: Backend — replace unavailable-snapshot with `get_ppid_unavailable`

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/storage/data.py` (imports at top; the entire `__all__` list; and everything from the `# Storage Unreachable` section comment ~line 159 to EOF)

- [ ] **Step 1: Update imports and `__all__`**

Replace the import line `from .._tool_specs import TOOL_SPECS, ToolSlug` with:

```python
from .._tool_specs import (
    SLUG_TO_TOOL_TYPE,
    TOOL_SPECS,
    ToolSlug,
    model_to_tool_type,
)
from ....sem_list.data import get_sem_list
```

Replace `__all__` with:

```python
__all__ = [
    "StorageRow",
    "PpidUnavailableRow",
    "PpidUnavailableSnapshot",
    "get_storage",
    "get_ppid_unavailable",
]
```

- [ ] **Step 2: Delete the old unavailable block and write the PPID model**

Delete everything from the line `# ---...` introducing `# Storage Unreachable:` (≈ line 159) through the end of the file (the `UnavailableSnapshotRow`, `UnavailableRow`, `StorageUnavailableSnapshot` classes, `MOCK_UNAVAILABLE_*`, `_generate_unavailable_tool_pool`, `_generate_unavailable_snapshots`, `_missing_days_streak`, and `get_storage_unavailable`). Replace with:

```python
# ---------------------------------------------------------------------------
# PPID not available: tools whose recipe/ppid endpoint could not be reached.
# Office source: Redis hash 'v3_hitachi_sem_ppid_not_avail',
#   hget(key, "%Y%m%d") -> not_avail_ip_list (list[str] of eqp_ip), kept 30 days.
# Only IPs are stored, so each IP is joined against sem_list to enrich; IPs with
# no sem_list match surface as orphan rows (IP only).
# ---------------------------------------------------------------------------


class PpidUnavailableRow(TypedDict):
    eqp_id: str
    eqp_ip: str
    fac_id: str
    fab_name: str
    eqp_model_cd: str
    missing_days_streak: int


class PpidUnavailableSnapshot(TypedDict):
    latest_date: str
    rows: list[PpidUnavailableRow]


MOCK_PPID_LATEST_DATE = date(2026, 5, 26)
MOCK_PPID_WINDOW_DAYS = 30


def _ymd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _generate_ppid_snapshots(tool_slug: ToolSlug, seed: int = 43) -> dict[str, list[str]]:
    """Redis-shaped mock: {"YYYYMMDD": [eqp_ip, ...]} for the last 30 days."""
    rng = random.Random(seed)
    tool_type = SLUG_TO_TOOL_TYPE[tool_slug]
    sem_rows = [
        row for row in get_sem_list()
        if model_to_tool_type(row["eqp_model_cd"]) == tool_type
    ]

    latest = MOCK_PPID_LATEST_DATE
    snapshots: dict[str, list[str]] = {
        _ymd(latest - timedelta(days=offset)): []
        for offset in range(MOCK_PPID_WINDOW_DAYS)
    }

    if sem_rows:
        failing = rng.sample(sem_rows, max(1, int(len(sem_rows) * 0.4)))
    else:
        failing = []
    n_current = len(failing) // 2

    # Currently unreachable: a streak ending at the latest date.
    for row in failing[:n_current]:
        streak = rng.randint(1, MOCK_PPID_WINDOW_DAYS)
        for offset in range(streak):
            snapshots[_ymd(latest - timedelta(days=offset))].append(row["eqp_ip"])

    # Failed earlier in the window then recovered (absent from the latest date).
    for row in failing[n_current:]:
        start = rng.randint(1, MOCK_PPID_WINDOW_DAYS - 1)
        duration = rng.randint(1, min(4, MOCK_PPID_WINDOW_DAYS - start))
        for offset in range(start, start + duration):
            snapshots[_ymd(latest - timedelta(days=offset))].append(row["eqp_ip"])

    # A few orphan IPs absent from sem_list (e.g. decommissioned but still failing).
    for idx in range(3):
        orphan_ip = f"177.{200 + idx}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"
        streak = rng.randint(1, 6)
        for offset in range(streak):
            snapshots[_ymd(latest - timedelta(days=offset))].append(orphan_ip)

    return snapshots


def _ppid_streak(eqp_ip: str, latest_date: date, ip_by_date: dict[str, set[str]]) -> int:
    streak = 0
    cursor = latest_date
    while eqp_ip in ip_by_date.get(_ymd(cursor), set()):
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def get_ppid_unavailable(
    tool_slug: ToolSlug,
    fac_ids: list[str] | None = None,
) -> PpidUnavailableSnapshot:
    snapshots = _generate_ppid_snapshots(tool_slug)
    latest_key = max(snapshots)  # compact YYYYMMDD sorts chronologically
    latest_date = datetime.strptime(latest_key, "%Y%m%d").date()

    ip_by_date = {key: set(ips) for key, ips in snapshots.items()}
    sem_by_ip = {row["eqp_ip"]: row for row in get_sem_list()}

    normalized = {
        fac_id.strip().upper()
        for fac_id in (fac_ids or [])
        if fac_id.strip()
    }

    rows: list[PpidUnavailableRow] = []
    for eqp_ip in snapshots[latest_key]:
        match = sem_by_ip.get(eqp_ip)
        fac_id = match["fac_id"] if match else ""
        fab_name = match["fab_name"] if match else ""
        eqp_id = match["eqp_id"] if match else ""
        eqp_model_cd = match["eqp_model_cd"] if match else ""

        # A fac filter drops orphan rows (they have no fac_id to match).
        if normalized and fac_id not in normalized:
            continue

        rows.append(PpidUnavailableRow(
            eqp_id=eqp_id,
            eqp_ip=eqp_ip,
            fac_id=fac_id,
            fab_name=fab_name,
            eqp_model_cd=eqp_model_cd,
            missing_days_streak=_ppid_streak(eqp_ip, latest_date, ip_by_date),
        ))

    rows.sort(key=lambda row: (-row["missing_days_streak"], row["eqp_ip"]))

    return {
        "latest_date": latest_date.isoformat(),
        "rows": rows,
    }
```

- [ ] **Step 3: Verify PPID join, orphans, and streak**

Run:
```
.venv/Scripts/python.exe -c "from back_dev_home.ebeam.hitachi.storage.data import get_ppid_unavailable; snap=get_ppid_unavailable('cdsem'); rows=snap['rows']; print('latest',snap['latest_date'],'rows',len(rows)); print('orphans',sum(1 for r in rows if not r['eqp_id'])); print('max streak',max((r['missing_days_streak'] for r in rows), default=0)); print(rows[0])"
```
Expected: `latest 2026-05-26`, `rows` > 0, `orphans` ≈ 1–3, `max streak` up to 30, first row has the largest streak and a populated `eqp_id`/`fab_name` (matched) or blanks (orphan).

- [ ] **Step 4: Commit**

```bash
git add back_dev_home/ebeam/hitachi/storage/data.py
git commit -m "feat(storage): model ppid-not-available daily IP list joined to sem_list"
```

---

## Task 3: Backend — rename route to `/ppid-unavailable`

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/storage/routes.py`

- [ ] **Step 1: Update import and handler**

Change the import:
```python
from .data import get_storage, get_ppid_unavailable
```

Replace the `storage_unavailable` handler with:
```python
@bp.get("/<tool_slug>/ppid-unavailable")
def ppid_unavailable(tool_slug: str):
    slug = _validate_slug(tool_slug)
    if not slug:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    rows = get_ppid_unavailable(slug, _parse_fac_ids())
    return jsonify(rows)
```

- [ ] **Step 2: Verify the blueprint imports and the route is registered**

Run:
```
.venv/Scripts/python.exe -c "from back_dev_home import create_app; app=create_app(); print([str(r) for r in app.url_map.iter_rules() if 'ppid' in str(r) or 'storage' in str(r)])"
```
Expected: a list including `/api/<tool_slug>/storage` and `/api/<tool_slug>/ppid-unavailable`, and **no** `/storage-unavailable`.

- [ ] **Step 3: Commit**

```bash
git add back_dev_home/ebeam/hitachi/storage/routes.py
git commit -m "feat(storage): rename storage-unavailable route to ppid-unavailable"
```

---

## Task 4: Frontend — `useStorageApi.ts` types, endpoint, helper

**Files:**
- Modify: `front-dev-home/app/composables/useStorageApi.ts`

- [ ] **Step 1: Nullable `StorageRow` + `isStorageUnavailable` helper**

Update the `StorageRow` interface so storage fields can be empty/null (leave `eqp_id`, `eqp_ip`, `fac_id`, `rcp_counts`, `rcp_counts_mt`, `fab_name`, `eqp_model_cd` as-is):

```typescript
export interface StorageRow {
  eqp_id: string
  eqp_ip: string
  fac_id: string
  total: string
  used: string
  avail: string
  percent: string
  storage_mt: string | null
  rcp_counts: number
  rcp_counts_mt: string
  storage_mt_date: string
  fab_name: string
  eqp_model_cd: string
}

// A tool whose storage collection failed: no sample timestamp or no avail value.
// Mirrors back_dev_home storage data.py (storage_mt is None / avail is "").
export const isStorageUnavailable = (row: StorageRow): boolean =>
  !row.storage_mt || !row.avail
```

- [ ] **Step 2: Rename the unavailable types to PPID**

Replace `UnavailableRow` and `StorageUnavailableSnapshot` with:

```typescript
export interface PpidUnavailableRow {
  eqp_id: string
  eqp_ip: string
  fac_id: string
  fab_name: string
  eqp_model_cd: string
  missing_days_streak: number
}

export interface PpidUnavailableSnapshot {
  latest_date: string
  rows: PpidUnavailableRow[]
}
```

- [ ] **Step 3: Point fetchers at `/ppid-unavailable` and rename them**

In `useStorageApi`, replace the `unavailableUrl` const and the two unavailable fetchers + the return object so the names read as PPID:

```typescript
  const ppidUnavailableUrl = joinApiPath(config.public.apiBase, `/${slug}/ppid-unavailable`)
```

```typescript
  const fetchPpidUnavailableRows = async (facIds: string[] = [], signal?: AbortSignal): Promise<PpidUnavailableSnapshot> => {
    const query = facIds.length > 0 ? { fac_id: facIds.join(',') } : undefined

    return await $fetch<PpidUnavailableSnapshot>(ppidUnavailableUrl, { query, signal })
  }
```

```typescript
  const fetchPpidUnavailableByUrlFab = async (urlFab: string, signal?: AbortSignal): Promise<PpidUnavailableSnapshot> => {
    const facId = fabNameToFacId(urlFab)
    return await fetchPpidUnavailableRows([facId], signal)
  }
```

Return object:
```typescript
  return {
    fetchStorageRows,
    fetchByUrlFab,
    fetchPpidUnavailableRows,
    fetchPpidUnavailableByUrlFab
  }
```

- [ ] **Step 4: Verify (deferred to Task 5's typecheck)**

No standalone check; `StorageView.vue` is the only consumer and is updated next. Do not commit yet — commit together with Task 5 so the rename stays atomic.

---

## Task 5: Frontend — `StorageView.vue` N/A state, stat, filter, PPID table

**Files:**
- Modify: `front-dev-home/app/components/ebeam/StorageView.vue`

- [ ] **Step 1: Fix the cadence label**

In the `<EbeamMetaBar>` tag, change `cadence="매일 08:30"` to `cadence="매일 04:30"`.

- [ ] **Step 2: Update type imports and composable destructure**

Change the type import line:
```typescript
import type { StorageRow, StorageTool, PpidUnavailableSnapshot, PpidUnavailableRow } from '~/composables/useStorageApi'
import { isStorageUnavailable } from '~/composables/useStorageApi'
```

Change the composable destructure:
```typescript
const { fetchByUrlFab, fetchPpidUnavailableByUrlFab } = useStorageApi(storageTool)
```

- [ ] **Step 3: Rename the second `useAsyncData` block to PPID**

Replace the `unavailableData` block with PPID-named bindings and fetcher:

```typescript
const {
  data: ppidUnavailableData,
  pending: ppidUnavailablePending,
  error: ppidUnavailableError
} = await useAsyncData(
  () => `ppid-unavailable:${storageTool}:${props.fab}`,
  () => fetchPpidUnavailableByUrlFab(props.fab, abortController.signal),
  {
    watch: [() => props.fab],
    default: (): PpidUnavailableSnapshot => ({ latest_date: '', rows: [] }),
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const ppidLatestDate = computed(() => ppidUnavailableData.value?.latest_date ?? '')

const ppidUnavailableRows = computed(() => (ppidUnavailableData.value?.rows ?? []).filter(row => row.eqp_model_cd === '' || classifyToolType(row.eqp_model_cd) === props.toolType))
```

(Orphan rows have `eqp_model_cd === ''`; keep them so data-quality gaps stay visible.)

- [ ] **Step 4: Add the storage-N/A helper and exclude N/A from usage buckets**

After `parsePercent`/`parseSizeGb`, add:
```typescript
const storageNa = (row: StorageRow): boolean => isStorageUnavailable(row)
```

Replace the `usageFilterOptions` array to add the new option:
```typescript
const usageFilterOptions = [
  { label: 'All Usage', value: 'all' },
  { label: 'Critical (>=80%)', value: 'critical' },
  { label: 'Warning (60-79%)', value: 'warning' },
  { label: 'Healthy (<60%)', value: 'healthy' },
  { label: 'Not available', value: 'unavailable' }
]
```

Widen the `usageFilter` ref type:
```typescript
const usageFilter = ref<'all' | 'critical' | 'warning' | 'healthy' | 'unavailable'>('all')
```

- [ ] **Step 5: Update `filteredRows` — usage logic + push N/A to the bottom**

Replace the `usage !== 'all'` branch inside the `.filter` and the trailing sort so N/A rows are filtered correctly and always sorted last:

Filter branch (inside the `matched` filter callback, replacing the existing `if (usage !== 'all') { ... }`):
```typescript
    const na = storageNa(row)
    if (usage === 'unavailable') {
      if (!na) return false
    } else if (usage !== 'all') {
      if (na) return false
      const pct = parsePercent(row.percent)
      if (usage === 'critical' && pct < 80) return false
      if (usage === 'warning' && (pct < 60 || pct >= 80)) return false
      if (usage === 'healthy' && pct >= 60) return false
    }
```

Replace the final sort block (from `const currentSort = storageSorting.value[0]` to the end of the computed) with a partitioned sort:
```typescript
  const currentSort = storageSorting.value[0]

  const available = matched.filter(row => !storageNa(row))
  const unavailable = matched.filter(row => storageNa(row))

  if (currentSort) {
    const key = currentSort.id as keyof StorageRow
    const direction = currentSort.desc ? -1 : 1
    available.sort((a, b) => {
      const sortResult = compareStorageRows(a, b, key)
      if (sortResult !== 0) return sortResult * direction
      return sortCollator.compare(a.eqp_id, b.eqp_id)
    })
  }

  unavailable.sort((a, b) => sortCollator.compare(a.eqp_id, b.eqp_id))

  return [...available, ...unavailable]
```

- [ ] **Step 6: Add the Storage N/A count to `summary` and `metaStats`**

Replace the `summary` computed so N/A rows are counted separately (not folded into "healthy"):
```typescript
const summary = computed(() => {
  let critical = 0
  let warning = 0
  let healthy = 0
  let na = 0
  for (const row of rows.value) {
    if (storageNa(row)) {
      na++
      continue
    }
    const pct = parsePercent(row.percent)
    if (pct >= 80) critical++
    else if (pct >= 60) warning++
    else healthy++
  }

  return {
    total: rows.value.length,
    critical,
    warning,
    healthy,
    na
  }
})
```

Add an `na` stat to `metaStats`:
```typescript
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'total', label: 'Total Tools', value: summary.value.total, tone: 'neutral' },
  { key: 'critical', label: 'Critical', value: summary.value.critical, tone: 'bad' },
  { key: 'warning', label: 'Warning', value: summary.value.warning, tone: 'warn' },
  { key: 'healthy', label: 'Healthy', value: summary.value.healthy, tone: 'ok' },
  { key: 'na', label: 'Storage N/A', value: summary.value.na, tone: 'neutral' }
])
```

- [ ] **Step 7: Render N/A in the capacity/usage/timestamp cells**

Replace the `total`, `used`, `avail`, `percent`, and `storage_mt` cell templates with N/A-aware versions:

```vue
        <template #total-cell="{ row }">
          <span
            class="font-mono tabular-nums text-[12.5px]"
            :class="storageNa(row.original) ? 'text-(--sk-ink-muted) italic' : ''"
          >{{ storageNa(row.original) ? 'N/A' : row.original.total }}</span>
        </template>
        <template #used-cell="{ row }">
          <span
            class="font-mono tabular-nums text-[12.5px]"
            :class="storageNa(row.original) ? 'text-(--sk-ink-muted) italic' : ''"
          >{{ storageNa(row.original) ? 'N/A' : row.original.used }}</span>
        </template>
        <template #avail-cell="{ row }">
          <span
            class="font-mono tabular-nums text-[12.5px] text-(--sk-ink)"
            :class="storageNa(row.original) ? 'text-(--sk-ink-muted) italic' : ''"
          >{{ storageNa(row.original) ? 'N/A' : row.original.avail }}</span>
        </template>
        <template #percent-cell="{ row }">
          <div
            v-if="storageNa(row.original)"
            class="flex items-center gap-1.5 min-w-[10rem] text-(--sk-ink-muted)"
          >
            <UIcon
              name="i-lucide-circle-slash"
              class="h-3.5 w-3.5 shrink-0"
            />
            <span class="text-[12px] italic">Storage N/A</span>
          </div>
          <div
            v-else
            class="flex items-center gap-2 min-w-[10rem]"
          >
            <div class="flex-1 h-1.5 rounded-full bg-zinc-200/70 dark:bg-zinc-800/70 overflow-hidden">
              <div
                class="h-full rounded-full transition-all"
                :class="usageBarClass(parsePercent(row.original.percent))"
                :style="{ width: `${parsePercent(row.original.percent)}%` }"
              />
            </div>
            <span
              class="text-[12px] font-semibold tabular-nums w-10 text-right"
              :class="usageTextClass(parsePercent(row.original.percent))"
            >{{ row.original.percent }}</span>
          </div>
        </template>
        <template #storage_mt-cell="{ row }">
          <span class="text-[12px] text-(--sk-ink) tabular-nums">{{ row.original.storage_mt ? formatTimestamp(row.original.storage_mt) : '—' }}</span>
        </template>
```

- [ ] **Step 8: Retitle the second card and update its states**

In the second `<UCard>`:
- Change the `<h2>` text `Storage Unreachable` → `PPID Unreachable`.
- Change the "Latest date" paragraph to bind `ppidLatestDate`.
- Change the count paragraph to `{{ filteredPpidUnavailable.length }} of {{ ppidUnavailableRows.length }} tools`.
- Change the search `v-model` to `ppidUnavailableFilter`, the loading/error/empty bindings to `ppidUnavailablePending` / `ppidUnavailableError` / `ppidUnavailableRows`, the reset button `:disabled` to `!hasActivePpidControls` and `@click` to `resetPpidFilters`.
- Empty-state copy: replace "No tools missing from the latest storage snapshot." with "No tools failed PPID access on the latest date." and the sub-line `{{ props.fab }} {{ props.toolLabel }} on {{ ppidLatestDate || 'the latest date' }}.`
- The filtered-empty state and `<UTable>` bind to `filteredPpidUnavailable`, `v-model:sorting="ppidSorting"`, `:columns="ppidColumns"`, `:meta="ppidTableMeta"`, and iterate `ppidSortableHeaders`.

The full replacement second-card `<UTable>` and its header loop:
```vue
      <UTable
        v-else
        v-model:sorting="ppidSorting"
        class="max-h-[22rem] font-mono-ids"
        :columns="ppidColumns"
        :data="filteredPpidUnavailable"
        :meta="ppidTableMeta"
        :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false, manualSorting: true }"
        sticky="header"
      >
        <template
          v-for="head in ppidSortableHeaders"
          :key="head.id"
          #[`${head.id}-header`]="{ column }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-zinc-900 dark:hover:text-zinc-100"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ head.label }}
          </UButton>
        </template>

        <template #fab_name-cell="{ row }">
          <span class="text-(--sk-ink) font-medium">{{ row.original.fab_name || '—' }}</span>
        </template>
        <template #eqp_id-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px]">{{ row.original.eqp_id || '—' }}</span>
        </template>
        <template #eqp_model_cd-cell="{ row }">
          <span class="font-mono text-[12.5px]">{{ row.original.eqp_model_cd || '—' }}</span>
        </template>
        <template #eqp_ip-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px] text-(--sk-ink)">{{ row.original.eqp_ip }}</span>
        </template>
        <template #missing_days_streak-cell="{ row }">
          <span
            class="inline-flex items-center justify-center min-w-[2rem] rounded-md px-1.5 py-0.5 text-[11.5px] font-semibold tabular-nums"
            :class="row.original.missing_days_streak >= 7 ? 'bg-rose-500/10 text-rose-600 dark:text-rose-300' : 'bg-zinc-500/10 text-(--sk-ink-muted)'"
          >{{ row.original.missing_days_streak }}d</span>
        </template>
      </UTable>
```

- [ ] **Step 9: Rename the second table's script state and add the streak column**

Replace the `unavailableFilter` / `unavailableSorting` / `compareUnavailableRows` / `filteredUnavailable` / `hasActiveUnavailableControls` / `resetUnavailableFilters` / `unavailableTableMeta` / `unavailableColumnConfigs` / `unavailableColumns` / `unavailableSortableHeaders` block (≈ lines 667-765) with PPID-named equivalents, adding the streak column and defaulting the sort to streak-desc:

```typescript
const ppidUnavailableFilter = ref('')
const defaultPpidSort = {
  id: 'missing_days_streak',
  desc: true
}
const ppidSorting = ref<SortingState>([
  defaultPpidSort
])

const comparePpidRows = (left: PpidUnavailableRow, right: PpidUnavailableRow, key: keyof PpidUnavailableRow) => {
  const leftValue = left[key]
  const rightValue = right[key]

  if (typeof leftValue === 'number' && typeof rightValue === 'number') {
    return leftValue - rightValue
  }

  return sortCollator.compare(String(leftValue), String(rightValue))
}

const filteredPpidUnavailable = computed(() => {
  const term = ppidUnavailableFilter.value.trim().toLowerCase()

  const matched = ppidUnavailableRows.value.filter((row) => {
    if (!term) return true
    const hay = [
      row.eqp_id,
      row.eqp_ip,
      row.fab_name,
      row.eqp_model_cd
    ]
    return hay.some(v => v.toLowerCase().includes(term))
  })

  const currentSort = ppidSorting.value[0]

  if (!currentSort) {
    return matched
  }

  const key = currentSort.id as keyof PpidUnavailableRow
  const direction = currentSort.desc ? -1 : 1

  return [...matched].sort((a, b) => {
    const sortResult = comparePpidRows(a, b, key)

    if (sortResult !== 0) {
      return sortResult * direction
    }

    return sortCollator.compare(a.eqp_ip, b.eqp_ip)
  })
})

const hasActivePpidControls = computed(() => {
  const currentSort = ppidSorting.value[0]

  return ppidUnavailableFilter.value.length > 0
    || currentSort?.id !== defaultPpidSort.id
    || currentSort?.desc !== defaultPpidSort.desc
})

const resetPpidFilters = () => {
  ppidUnavailableFilter.value = ''
  ppidSorting.value = [
    defaultPpidSort
  ]
}

const ppidTableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50/60 dark:hover:bg-zinc-800/40',
    td: 'py-1.5 px-3 text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis',
    th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}

type PpidColumnConfig = {
  id: keyof PpidUnavailableRow
  header: string
  size: number
}

const ppidColumnConfigs: PpidColumnConfig[] = [
  { id: 'missing_days_streak', header: 'Days Down', size: 88 },
  { id: 'fab_name', header: 'Fab', size: 64 },
  { id: 'eqp_id', header: 'Equipment ID', size: 130 },
  { id: 'eqp_model_cd', header: 'Model', size: 130 },
  { id: 'eqp_ip', header: 'IP Address', size: 140 }
]

const ppidColumns: TableColumn<PpidUnavailableRow>[] = ppidColumnConfigs.map(({ id, ...column }) => ({
  accessorKey: id,
  ...column
}))

const ppidSortableHeaders = ppidColumnConfigs.map(column => ({
  id: column.id,
  label: column.header
}))
```

- [ ] **Step 10: Typecheck and lint**

Run (from `front-dev-home/`):
```
npm run typecheck
npm run lint
```
Expected: no type errors referencing `StorageView.vue` / `useStorageApi.ts`; lint clean (or only pre-existing unrelated warnings).

- [ ] **Step 11: Commit (frontend rename atomic with Task 4)**

```bash
git add front-dev-home/app/composables/useStorageApi.ts front-dev-home/app/components/ebeam/StorageView.vue
git commit -m "feat(storage): surface storage-N/A rows and ppid-unreachable table in StorageView"
```

---

## Task 6: Docs — API contracts

**Files:**
- Modify: `docs/api-contracts/cdsem-storage.yaml`
- Modify: `docs/api-contracts/hvsem-storage.yaml`
- Modify (only if Task 0 flagged it): `scripts/capture_fixtures.py`, `back_dev_home/README.md`

- [ ] **Step 1: Update `cdsem-storage.yaml`**

For `total`, `used`, `avail`, `percent`: append to each `description:` (or add one) the note `Empty string when storage collection failed (storage not available).` For `storage_mt`: change type note to `ISO 8601 UTC ending in Z, or null when storage collection failed`. For `storage_mt_date`: note `Empty string when storage collection failed`.

Rename the `UnavailableRow` type to `PpidUnavailableRow` and `StorageUnavailableSnapshot` to `PpidUnavailableSnapshot`, and update `missing_days_streak` description to `Consecutive days the tool's PPID endpoint has been unreachable, ending at latest_date`. Add to `PpidUnavailableRow` a note that `eqp_id`/`fac_id`/`fab_name`/`eqp_model_cd` are empty for orphan IPs with no sem_list match.

Replace the `/api/cdsem/storage-unavailable` endpoint with:
```yaml
  - path: /api/cdsem/ppid-unavailable
    method: GET
    description: >-
      Latest daily snapshot of CD-SEM tools whose PPID (recipe) endpoint was
      unreachable, with consecutive-days-unreachable streak. Source: Redis hash
      'v3_hitachi_sem_ppid_not_avail', hget(key, "%Y%m%d") -> list of eqp_ip,
      retained 30 days; IPs are joined against sem-list to enrich. Unmatched
      (orphan) IPs appear with eqp_ip only.
    query_params:
      fac_id:
        type: string
        required: false
        description: Comma-separated fac_ids; orphan rows (no fac_id) are dropped when set.
    response:
      status: 200
      body: PpidUnavailableSnapshot
```

Update the `notes:` section: replace the 8-day unavailable note with `Phase 1 ppid-unavailable generator uses random.Random(seed=43) over a 30-day window and joins IPs against get_sem_list().` and add `storage-not-available rows (storage_mt null, blank capacity fields) are ~8% of the main df; rcp_counts still reports since recipe counting is a separate collection path.`

- [ ] **Step 2: Mirror the edits into `hvsem-storage.yaml`**

Apply the identical structural changes (nullable storage fields, `PpidUnavailable*` rename, `/api/hvsem/ppid-unavailable` endpoint, notes). Keep HV-SEM-specific values (resource name, AMAT TP model enum, `/api/hvsem` base path) unchanged.

- [ ] **Step 3: Markdown/doc lint not required for YAML; verify YAML parses**

Run:
```
.venv/Scripts/python.exe -c "import yaml; [yaml.safe_load(open(f, encoding='utf-8')) for f in ['docs/api-contracts/cdsem-storage.yaml','docs/api-contracts/hvsem-storage.yaml']]; print('yaml ok')"
```
Expected: `yaml ok`.

- [ ] **Step 4: Commit**

```bash
git add docs/api-contracts/cdsem-storage.yaml docs/api-contracts/hvsem-storage.yaml
git commit -m "docs(storage): update contracts for nullable storage fields and ppid-unavailable"
```

---

## Final verification

- [ ] Backend: re-run the Task 1 + Task 2 + Task 3 verification one-liners; all pass.
- [ ] Frontend: `npm run typecheck` and `npm run lint` clean.
- [ ] Optional end-to-end (if Flask :5050 + Nuxt :3000 are running in PyCharm): load a CD-SEM storage page, confirm the meta bar shows a "Storage N/A" count, the "Not available" usage filter works, N/A rows render "Storage N/A" and sit at the bottom, and the "PPID Unreachable" card shows a "Days Down" column with orphan rows rendering "—" for eqp_id/model.
