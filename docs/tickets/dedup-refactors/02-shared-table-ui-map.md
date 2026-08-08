# 02 — One shared `tableUi` class map for the recipe-tat tables

**What to build:** the `tableUi` class map is verbatim in three components — `RecipeTatFleetTable`, `RecipeTatEquipmentCompare`, `RecipeTatView`. The cost is already proven: the d48d592b DESIGN.md sweep (drop header background, take `.sk-label`) had to make the identical edit in all three. Extract the map to one shared source (a small module or role classes) and import it from all three tables.

**Why:** review Standards axis, judgement call (Duplicated Code / Shotgun Surgery) with the cost already paid once: the d48d592b DESIGN.md sweep had to make the identical header/label edit in all three files. DESIGN.md sweeps are a recurring event in this repo, so the triplication is a guaranteed recurring tax — and a guaranteed partial sweep the first time someone forgets one file.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 8469edca — analyticsTableUi (실제 사본은 3개가 아니라 4개였음)

- [ ] A single shared `tableUi` source is imported by all three recipe-tat tables
- [ ] Rendered classes are unchanged at every table (visual check)
- [ ] The next DESIGN.md table sweep touches one file, not three
