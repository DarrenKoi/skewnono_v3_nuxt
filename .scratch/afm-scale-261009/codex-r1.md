# AFM scale-up review, round 1

The feature can grow without an application rewrite. Tool routing, provider separation and reusable analytics are adequate for 10–20 tools and tens of users. The limits are concentrated in whole-history reads, full-list rendering and synchronous, memory-backed downloads. Retention bounds history by time, not by bytes or measurement count.

This is a review of the current tracked code, especially `office_example.py`, against the deployment facts in BRIEF.md. The running office copy and cloud configuration were not inspected. Every path below is relative to the repository root.

## Verdict by axis

| Axis | Verdict | Concrete limit | Smallest change that lifts it |
| --- | --- | --- | --- |
| Data volume | Fine until one tool's retained history becomes expensive to transmit, render or decode. No defensible measurement-count cutoff is available. | `backend/afm/providers/office_example.py:117` reads the entire blob; `:120` converts all rows to Python dictionaries; `:361` normalizes all rows; `backend/afm/routes.py:36` returns everything; `frontend/app/components/afm/SearchBar.vue:196` renders every matching row. | First page the displayed results. Then offer a compact list response and query filters without changing the existing default contract. If decoding the history itself becomes the limit, ask the loader for time-partitioned history and a compact per-measurement object index. |
| Tool count | Fine for 10–20 after small catalog updates; adding a fourth tool to Redis alone does not expose it in navigation. Cache behavior becomes worse when users actively visit more than eight distinct cache keys per worker. | `frontend/app/composables/useAfmToolData.ts:12` contains only three tools; `backend/afm/providers/office_example.py:87` contains the fallback fab mapping; `:115` caches only eight entries including the minute tick. | For occasional additions, update the existing frontend catalog, fab mapping and mock fixtures. If onboarding becomes routine, make this same composable consume the existing `/api/afm/tools` endpoint. Replace tick-key accumulation with one expiring entry per tool before increasing cache capacity. |
| Feature count | Fine for further pages using list metadata or bounded selected-measurement detail. Fine until an analysis requires details from the whole retained history. | `frontend/app/composables/useAfmDetailApi.ts:171` is shared by tips, usage and recipes; `frontend/app/pages/afm/[tool]/see-together.vue:244` fetches detail per selection; `backend/afm/providers/office_example.py:402`, `:420`, `:421` read three detail objects per measurement when present. | Reuse existing pure utilities and shared reads. For a specific history-wide detail statistic, request that statistic in the loader's measurement metadata and update its contract/mock/schema, rather than making every page fetch all details. |
| Concurrency | Fine until active object reads fill worker slots or concurrent ZIP/profile allocations exhaust the 8 GB host. Tens of registered users do not establish how many expensive requests overlap. | `backend/afm/routes.py:235`, `:249` build and materialize whole original ZIPs in RAM; `backend/afm/providers/office_example.py:144` performs synchronous object reads; `:115` has independent caches per process. | Move ZIP construction to a disk-backed temporary file and serve it as a file with cleanup. Bound simultaneous ZIP builders if necessary. Limit detail-fetch concurrency in the comparison page before adding workers. |

There is no evidence for a statement such as "breaks at 10,000 measurements" or "supports 20 simultaneous users." The missing inputs are retained row count, decoded history size, original image sizes, object latency and actual cloud worker configuration.

## Findings ranked by likely practical impact

### 1. Whole-history list transfer and rendering grow even when the user wants a narrow search

`office_example.py:306` derives seven basename lists for every row. Those lists are sent with every list response, although the frontend list type uses availability flags and metadata rather than those file arrays (`useAfmDetailApi.ts:3`). The route has no date filter or pagination (`routes.py:32`). Search filters run after download (`SearchBar.vue:280`, `:323`), and the 620px scrolling container still mounts every matching row (`:194`, `:196`). A small viewport is not a DOM bound.

The first likely symptom is a slow list/search view, before storage capacity itself becomes a problem. Even a three-month history can grow sharply as throughput rises. The raw path arrays make payload growth depend on image/file count as well as measurement count.

The smallest local improvement is ordinary result pagination while keeping search/count/group-selection semantics explicit. It bounds DOM work, not transfer or Redis decoding. Next, add an opt-in compact list representation that omits file arrays, preserving the legacy/default response and originals/detail lookup. Update the frontend list consumers and route tests together; do not silently remove required fields from `AfmMeasurementRow` (`contracts.py:38`).

Server-side date filtering can bound returned rows, but the current Redis layout still requires reading the whole tool blob. If that cold decode becomes the measured bottleneck, the external loader must split history into time partitions. Keep a separate compact mapping from measurement identity to its MinIO keys so an image/detail lookup need not deserialize all partitions. This changes the loader and office adapter, not page routing or `data.py`.

### 2. Original ZIPs can exhaust memory with surprisingly few overlapping downloads

`routes.py:237` compresses originals sequentially into a `BytesIO`; `:249` materializes the archive for the response. During construction the current original is also resident because `office_example.py:528` returns the complete object bytes. The maximum is driven by archive bytes plus the current original, compression work and response lifetime, not simply by the number of measurements.

The comment at `routes.py:231` assumes 36 originals and argues that 36 × 50 MB fits an 8 GB machine. BRIEF permits up to 133 images across a measurement; it does not establish 133 originals of one type or their sizes. The comment therefore cannot justify the concurrent-download budget. As an illustrative scenario, 36 poorly compressible 50 MB originals create an archive near 1.8 GB; several overlapping archives can consume most of the host before accounting for history caches and other features. This is arithmetic, not an observed office workload.

Use a disk-backed temporary file for the archive and file-based response delivery. Replacing `BytesIO` with a spool but then calling `read()`/`getvalue()` for `_attachment` would recreate the memory problem. Preserve missing-object handling, download names and cleanup when the response closes. This can remain entirely in the route and preserve the current provider contract. A small ZIP concurrency gate is appropriate if CPU, disk or request occupancy remains a problem. A task queue is unnecessary unless users need asynchronous download jobs.

### 3. The minute-key LRU wastes history memory and becomes ineffective under a broader active tool set

`office_example.py:125` uses `(hash, field, minute)` as the cache key. The 60-second interval is a freshness rule, not an expiration rule: old-minute entries stay until eviction. Three tools used across two minutes occupy six history entries, and an idle worker can retain obsolete histories indefinitely. Up to eight entries remain per process, with temporary raw bytes, DataFrames and JSON during a miss. Worker processes duplicate this memory.

With ten tools visited in round-robin order in the same minute, an eight-entry LRU misses every access on the second pass. This is conditional on active access patterns, not a failure caused merely by having ten tools registered. The tools-list entry also consumes capacity if used. Threaded simultaneous misses can decode the same key more than once because `lru_cache` does not coalesce in-flight loads.

A small standard-library self-check reproduced both the ten-tool thrash and the six retained entries across two ticks. It did not use Redis or measure throughput.

Replace the tick-key cache with one expiring snapshot per tool, retain the existing freshness interval initially, and coordinate concurrent refreshes per key. Size the bounded cache from measured decoded bytes and the active working set. Simply changing eight to twenty increases retained memory and still keeps duplicate generations. For large histories, build filename/unique-key lookup maps once per snapshot: `_find` currently scans history on every image/profile/original request (`office_example.py:275`), even on a cache hit. Reuse the existing normalization and first-match behavior.

### 4. New tools require catalog edits, not new feature implementations

Backend tool discovery is already data-driven (`office_example.py:290`), and detail/list requests use the normalized tool name as the Redis field. Frontend routes are generic `[tool]` routes. Tools are never combined on a page, so twenty registered tools do not multiply one page's data volume by twenty.

The actual onboarding limit is the static frontend catalog and fallback fab table. `ToolList.vue:33` and the list/tips/usage/recipes tool navigation all use the same composable, which is a useful existing centralization. For one new tool, adding entries and matching mock coverage is smaller than building a registry system. If ten tools are arriving together, use the already-existing tools API through that composable and supply confirmed fab metadata. Do not infer fab from the current alias field. Wrapping navigation pills can remain until FHD inspection shows a usability problem.

### 5. Bounded comparison is reasonable, but its requests still arrive as a burst

`useAfmCart.ts:40` caps comparison at twenty measurements and `:61` trims older stored groups. That is a useful bound. `see-together.vue:244` nevertheless starts all twenty detail fetches together. At three MinIO parquet reads per complete detail, one comparison can perform sixty object reads over the request lifetime.

The checked-in uWSGI configuration has four processes and four threads (`wsgi.ini:11`, `:15`), hence sixteen request slots. It is not proof of the cloud's permanent configuration. More overlapping comparisons or galleries can queue requests even with tens of users. AFM is exempt from the global rate limit (`backend/__init__.py:79`, `:117`), so the cart comment attributing its bound to 50 requests per five seconds is stale. Keep the bound, but do not count the global limiter as protection.

If comparison bursts are measured to delay other work, fetch a few details concurrently rather than all twenty. Preserve partial-failure reporting. A batched endpoint that still synchronously reads sixty objects does not by itself reduce storage work. Reintroducing the global 50-request limit across all AFM routes would break legitimate gallery loads; any concurrency gate should target expensive operations.

## Leave these parts alone

- Keep `data.py`, the provider seam, generic routes and the tool-scoped persisted cart. None needs a rewrite for twenty tools.
- Tips, usage and recipes already share `afm-tip-rows:<tool>` (`useAfmDetailApi.ts:171` and their page callers). The search list has a separate transformed cache key (`:163`), so visiting both paths can download the list twice. Sharing one raw list read is a small future improvement, not a reason to introduce another state library.
- Image types load on demand (`AnalysisImages.vue:387`, `:396`); thumbnails use native lazy loading (`:76`, `:239`); office webps get a private one-hour browser cache (`routes.py:289`). Keep these before considering an image proxy service or server-side image cache.
- Profile responses are already thinned to at most 65,536 samples (`profile_sampling.py:16`, `routes.py:93`). This bounds browser transfer/rendering, but `office_example.py:447` still constructs all profile dictionaries first, and `full=1` deliberately bypasses thinning. If dense simultaneous profiles are a measured memory problem, sample the DataFrame before dictionary conversion for display requests while preserving full export. Current dataset scale does not justify a separate profile service.
- Pure analytics utilities and dedicated chart components let more metadata-based pages reuse the same data. New infrastructure, distributed caches, database replacement and cross-fab aggregation are more than this user base currently needs.

A practical sequence is to measure a retained tool blob and list response, bound rendered search rows, remove unnecessary list payload, and protect large ZIP downloads. Fix catalog onboarding when adding tools. Change loader storage only when whole-history decoding remains the measured limit after local improvements.

## Evidence and limits

Read the current AFM routes, contracts, dispatcher, tracked office adapter, migration/schema notes, relevant frontend consumers and worker configuration. No product files were changed. The only executed check was the standalone standard-library cache self-check described above. Prior review memory was used only to preserve the requested read-only scope; earlier defects were not carried forward as current findings.

Skipped browser, office, cloud load/RSS tests and the full test suite. Scratch Markdown is outside the repository's Markdown lint glob.
Risk: peak memory and latency remain unmeasured; the verdicts identify code-level limits, not verified production capacity.

<oai-mem-citation>
<citation_entries>
MEMORY.md:18-19|note=[preserved report-only read-only review scope]
</citation_entries>
<rollout_ids>
01a113cc-2a60-7f62-b621-286ceeee259c
</rollout_ids>
</oai-mem-citation>
