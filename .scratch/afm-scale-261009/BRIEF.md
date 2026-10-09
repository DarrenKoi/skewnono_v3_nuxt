# AFM scale-up review — brief (round 1)

Read-only review. Do **not** edit code. Write your answer to
`.scratch/afm-scale-261009/codex-r1.md` (that file only), in English.

## Question

Is the AFM feature structured so that it can scale up without a rewrite?
Judge each axis separately, because the answer may differ:

1. **Data volume** — more measurements per tool, longer history.
2. **Tool count** — today 3 AFM tools (MAP608, MAPC01, 5EAP1501); what if 10–20?
3. **Feature count** — more pages/analytics on top of the same data
   (today: list, detail, see-together/trend, tips, usage, recipes).
4. **Concurrency** — more simultaneous users on the cloud host.

## Where the code is

- Backend: `backend/afm/` — `routes.py`, `data.py` (dispatcher, do not propose
  editing it), `contracts.py`, `providers/mock.py` (home),
  `providers/office_example.py` (the real adapter; `office.py` is a gitignored
  copy of it), `MIGRATION.md`.
- Schema of record: `docs/datatables/afm/`.
- Frontend: `frontend/app/pages/afm/[tool]/*.vue`,
  `frontend/app/components/afm/**`, `frontend/app/composables/useAfm*.ts`,
  `frontend/app/utils/afm*.ts`.
- Repo rules: `CLAUDE.md` (root).

## Facts you cannot infer from the code

- Office storage: Redis hash `afm_d2_measurements`, one field per tool, the
  value is that tool's **whole history as one parquet DataFrame**; an external
  loader (not ours, but we can send it requests) rewrites it every 30 min.
  Bodies (detail parquet, profiles, webp images, originals) are in MinIO.
- Retention is 3 months. One measurement holds up to 133 images.
- Production is Flask under uWSGI with several worker processes, 8 GB RAM,
  internal network, HTTP only. `/api/*` is rate-limited to 50 req / 5 s per
  user; the `afm` blueprint is exempt.
- AFM tools are in different fabs and are never combined on one page: every
  page is one tool.
- Users are on FHD desktop monitors; user base is one company's metrology team
  (tens of users, not thousands).
- The office is unreachable from here; only the mock runs at home.

## What I want back

For each axis: verdict (fine / fine until X / breaks at X), the specific
file:line that is the limit, and the *smallest* change that lifts it. Rank the
findings by how soon they would actually bite. Call out anything that is
over-built for this user base as well — "leave it alone" is a valid finding.
Be concrete; no generic best-practice lists.
