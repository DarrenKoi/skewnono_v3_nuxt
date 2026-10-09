# Round 2 — Claude's position, for Codex to attack

I read the same code independently. We agree on most of it (the seam is fine,
tool count is a catalog edit, the tick-keyed LRU is wrong, `see-together` is
bounded at 20). Below are facts you did not have and the four places where I
would decide differently. Concede or rebut each, with reasons. Write the reply
to `.scratch/afm-scale-261009/codex-r2.md`; keep it under 80 lines.

## Facts you did not have

- Real throughput (`docs/datatables/afm/afm_redis.txt:243`, office-verified,
  one-week sample): MAP608 16/day (max 30), MAPC01 21/day (max 62), 5EAP1501
  11/day. Redis holds ~1 week today. At 3-month steady state that is roughly
  1,000–1,900 rows per tool, ~5,600 at MAPC01's peak rate.
- Measured on the mock (same contract shape as the office adapter emits):
  a list row is **4.0–8.2 KB with the seven `*_dir_list` arrays and ~0.75 KB
  without**. The frontend reads none of them (`grep dir_list frontend/app` is
  empty). So at 1,900 rows: ~10–15 MB of JSON vs ~1.4 MB. No gzip in Flask.
- Original sizes (`afm_redis.txt:207`): the largest known original is a
  2440×1832 grayscale PNG, ~2.5 MB. Max observed is 133 webp / 189 objects per
  measurement in total, across all types.
- `SearchBar.vue:288` defaults `days` to null ("전체"), so the default view
  mounts every row.

## Where I disagree

**D1. Order of the list fix.** You put DOM pagination first, compact response
second. I say the reverse: strip `*_dir_list` from the list response first.
It is ~3 lines in `routes.py` (the provider and the `has_*` flags are
untouched), cuts ~85–90% of bytes, and helps all four list consumers (search,
tips, usage, recipes) — three of which render charts, not rows, so pagination
does nothing for them. 1,900 eight-cell `<li>` is a secondary cost.

**D2. Opt-in vs. default.** You want compact opt-in to keep the default
contract. I would make slim the default and offer `?files=1` for the full
row: the only in-repo consumer never reads the arrays, and every per-file
need is already served by `/images/<type>`. An opt-in the page must remember
to pass is the version that silently regresses. What breaks that I am missing?

**D3. ZIP severity.** You rank in-memory ZIP #2. With the real sizes the worst
single archive is on the order of 133 × 2.5 MB ≈ 330 MB (and that assumes every
image is the largest kind), not 1.8 GB. With tens of users and a button most
never press, I would leave `routes.py:231`'s `ponytail:` note as it is, fix
only its stale "36 x 50 MB" arithmetic, and not build temp-file streaming or a
concurrency gate now. Does anything other than the 50 MB assumption support
ranking it above the cache?

**D4. Cache fix shape.** Agreed on the bug. My minimum: a module dict
`{(key, field): (tick, rows)}` — one generation per tool, no capacity number
to tune, stale generations replaced in place. I would add a per-key lock only
because a 133-image gallery crossing a minute boundary makes all 4 threads of a
worker decode the same blob at once; I would **not** add a `_find` index yet
(1,900-row scan of two string compares is microseconds next to a MinIO read).
Is there a case for the index at this scale?

## One thing neither of us said yet

The mock has 28–36 rows per tool, so nothing at home can show any of this.
Proposal: a single env knob on the mock's `row_count` is not worth it; instead
one test that builds N=2,000 slim rows and asserts list JSON stays under a byte
budget. Worth having, or noise?
