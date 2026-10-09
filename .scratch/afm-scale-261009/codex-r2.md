# Round 2 response

I revise the order to compact list response first, cache generation fix second, and search DOM pagination only after browser measurement. I withdraw ZIP streaming as an immediate recommendation. I still dispute an undocumented default-response change and an unrestricted cache dictionary.

## Fact verification

- Throughput: `docs/datatables/afm/afm_redis.txt:243–245` records the stated daily rates, maxima and three-month retention. At 90 days, 16/21/11 per day gives 1,440/1,890/990 rows; sustaining MAPC01's observed maximum gives 5,580. These are projections, not measured retained histories. The same note records 67/108/28 rows over 7/7/6 days, whose arithmetic averages differ from the stated daily rates. Use the reported rates as planning scenarios rather than claiming a consistent measured daily average. The dated sample does not verify Redis's size today.
- Payload: reproduced using current mock rows and Flask JSON serialization. Your 4.0–8.2 KB values match tool-level mean row sizes, not the minimum/maximum of individual rows. Individual full rows ranged from 1.1 to 31.1 KB; slim rows ranged from 0.714 to 0.830 KB. The mock counts are 36/28/30 (`mock.py:426`, `:446`, `:472`).
- With 1,900 rows made by repeating each tool's current mock mix through the real route, full/slim response sizes were MAP608 15.384/1.334 MB, MAPC01 10.284/1.304 MB, and 5EAP1501 7.442/1.427 MB. Reductions were 91.3%, 87.3% and 80.8%. These are synthetic contract-shaped responses, not office payload measurements. The route test returned no Content-Encoding; no Flask response-compression setup was found. Cloud ingress compression was not inspected.
- Frontend: `rg dir_list frontend/app` has no matches. `afmSearch.ts:25–36` reads metadata and availability flags only. `SearchBar.vue:288` defaults to all dates; `:196` mounts all matches. Tips, usage and recipes share `useAfmTipRows` (`useAfmDetailApi.ts:171`), so compact responses benefit all four pages.
- Originals: `afm_redis.txt:206–209` confirms a particular tip PNG is approximately 2.5 MB, and `:216` confirms 133 webps/189 objects across the measurement. It does not establish 2.5 MB as the maximum of all originals. `docs/datatables/afm/afm_raw_files.txt:367` explicitly lists Result-original size as unknown. Thus 133 × 2.5 MB is a hypothetical estimate, not a verified worst-case archive bound.

## D1. Compact response before pagination: concede

The reproduced byte reduction and coverage of four consumers justify doing this first. My DOM-first ordering was too aggressive without browser timing. Strip the arrays at the route boundary while retaining provider rows and `has_*` flags. This reduces JSON serialization, transfer and frontend parsing; it does not reduce Redis decoding or `_row`'s basename construction (`office_example.py:306`, `:361`).

At approximately 2,000 retained rows, leave storage partitioning alone unless cold decode/RSS measurements demand it. Check all-date search on FHD after the payload change; 5,580 rows is a useful stress case, not an established break point.

## D2. Slim default with files=1: rebut the compatibility claim

No current frontend consumer breaks. But the list is also a documented token-accessible API: `frontend/app/data/apiCatalog.ts:606–611` advertises image file lists; `docs/api-contracts/afm.yaml:63–78`, `:180–195` declares the arrays in the response. `backend/afm/MIGRATION.md:57–65` documents both canonical and legacy list URLs as full rows. This is concrete compatibility scope, although I found no proof of a deployed external caller.

Adding `files=1` does not preserve existing callers that omit it. A script reading `response['data'][0]['raw_dir_list']` or `profile_dir_list` would break. `/images/<type>` replaces image listing, not raw/data/profile filename lists. Provider-contract tests (`test_contract.py:83–87`) would still pass because they test the dispatcher rather than the slim HTTP response.

My smallest compatible choice remains compact opt-in, selected centrally for both list reads in `useAfmDetailApi.ts:163–172`, rather than remembered by each page. A route projection, central query selection and focused route test solve today's payload problem. Keep provider contracts and `data.py` unchanged; document the compact HTTP variant.

Slim-default is reasonable if the owner explicitly accepts the API migration. Then update the HTTP contract, catalog, migration notes and tests with the new default and full-row option. Do not call it a three-line compatible change. I am not insisting on permanent full defaults after an intentional migration.

## D3. ZIP severity: concede the lower priority, reject the asserted bound

Nothing measured supports ranking ZIP ahead of the cache. My 50 MB scenario came from the existing comment, not office evidence; using it to drive immediate engineering was unjustified. Leave memory-backed ZIPs and omit streaming, queues and gates for now.

However, the default ZIP downloads TIFF originals (`routes.py:219`), whose sizes remain undocumented. Do not replace the old arithmetic with a claim that all archives are at most 330 MB. `routes.py:225–228` also restricts each archive to one type, so 133 total webps is not its actual original count. Revise the comment to state that original ZIP size and overlapping-download memory are unmeasured, and retain the upgrade trigger for observed large archives or overlapping downloads. The reported low button usage is an operational assertion, not something the code verifies.

## D4. One-generation dictionary and per-key lock: accept with one condition

The replacement shape is sufficient for 10–20 real tools. A bounded cache size is not needed if the key population is itself bounded by the registered tool catalog. Keep one tick and snapshot per key; take the per-key lock, recheck freshness inside it, and replace only after a successful read. That removes duplicate generations and coalesces same-worker refreshes. It does not share snapshots across uWSGI processes.

The proposed unrestricted dictionary has a concrete problem: `routes.py:309–310` accepts tool from the query, `office_example.py:286–287` only normalizes it, and `:117–119` reads any field and returns an empty tuple for missing fields. Distinct unknown tool strings can therefore accumulate cache entries and locks indefinitely. Cache/allocate per-key locks only for catalog-approved fields, with the fixed tools-list key handled separately; alternatively retain a capacity bound. Merely skipping empty snapshots is insufficient if unknown-key locks are retained.

Do not add `_find` indexes now. I extracted the actual `_find`, `_stem`, `_text` and `normalize_tool` functions from the current adapter and timed last-row/missing lookups over 1,900 distinct synthetic records with realistic mock filename lengths. Best of five repeats of 100 calls was 0.301/0.292 ms per lookup on this Mac. That is hundreds of microseconds, not evidence of a bottleneck relative to unmeasured office I/O. Across 133 calls it is roughly 40 ms of aggregate lookup CPU in this synthetic case. Revisit only if profiling shows lookup matters; preserve first-match semantics if indexing later.

## The 2,000-row test: useful only through the real route

A test that constructs already-slim rows and checks their size would miss the actual regression: accidentally restoring file arrays in the response. Instead patch the route's list provider with 2,000 realistic full rows containing populated arrays, request the compact variant through Flask, and assert that arrays are omitted while flags, count and metadata remain correct. If providing a full-row variant, assert that it preserves the arrays and that the provider input was not mutated.

A generous 2 MiB response budget can be an extra assertion justified by the reproduced slim sizes. It is a fixture payload guard, not a throughput or browser-capacity test. Do not add a mock environment knob, timing gate or large new suite. The omission/preservation assertions are the essential regression test.

## Revised decision

Compact list first; one-generation cache with bounded key population second; catalog edits when onboarding tools. Defer DOM pagination until FHD measurement warrants it. Leave `_find`, ZIP infrastructure and loader storage alone at the documented scale. The provider separation and reusable page structure still support expansion without a rewrite.

Skipped office/cloud verification, browser timing and the full suite; only synthetic Flask payload and extracted-function lookup checks ran. No product files were changed.
Risk: Result-original sizes, retained-history RAM and actual concurrent usage remain unmeasured; neither the 330 MB ZIP ceiling nor a production capacity guarantee is established.
