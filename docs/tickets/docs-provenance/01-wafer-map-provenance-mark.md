# 01 — Wafer-map fact carries its OFFICE-VERIFY mark in mock.py

**What to build:** today's wafer-map change (bc588419) recorded the site_layout_hash / wafer-map-as-recipe-property fact in `docs/datatables/hitachi/msr_file_pickle.txt` with the correct provenance mark (`OFFICE-VERIFY (2026-08-08): 도메인 추론입니다`), but `msr_file/providers/mock.py`'s module docstring asserts the same fact as settled office truth — "The office says so structurally…" — with no provenance mark. CLAUDE.md's two-places rule exists precisely for this: mock.py is the file every home session actually runs against, so an unverified inference must not read as verified there. Add the matching provenance mark to the mock.py docstring.

**Why:** review Standards axis, hard violation of CLAUDE.md's two-places rule — and the rule's own words name this exact failure mode: "A fact recorded in one and not the other is a fact the next home session will contradict." The datatables txt says the fact is unverified domain inference; the mock docstring — the file every home session actually runs against — asserts it as office-confirmed. Whoever writes the office adapter will trust the stronger claim.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 841d024a

- [ ] The wafer-map / site_layout_hash paragraph in the mock.py docstring carries the `OFFICE-VERIFY` mark matching the datatables txt
- [ ] Both locations tell the same provenance story; wording stays honest about what is inference vs verified
