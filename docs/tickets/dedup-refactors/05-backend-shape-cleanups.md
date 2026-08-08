# 05 — Backend shape cleanups: shared suffix constant, NamedTuples, derived image field

**What to build:** three backend/contract shape items. First, the HV-SEM image-suffix tuple `("U", "T", "M", "L")` is defined three times — `msr_file` mock, `msr_image` mock, and `recipe_search/rawfiles.py`; give it one shared home (rawfiles already imports across features, so a shared module is feasible). Second, the positional tuples are growing hazardous: `EquipmentGridRow` is a 6-tuple threaded mock → shape → office (the office template itself admits a fab/model swap "집에서는 테스트로 잡히지 않는 종류"), and `_transport()` now returns a 4-tuple that call sites half-discard — make both NamedTuples so fields are named at every hand-off. Third, the frontend `ReviewEntry` carries both `image` and `images` with a hand-maintained `image === images[0]` invariant; derive the singular from the list instead.

**Why:** review Standards axis, judgement calls bundled by theme. The suffix constant is a *protocol* fact — if the office ever adds a fifth suffix, three backends must learn it together or `recipe_search` discovers images the other two refuse to name. The positional tuples are already admitted hazardous: the office template's own comment warns a fab/model swap "집에서는 테스트로 잡히지 않는 종류" — a failure mode a NamedTuple deletes at the type level. And a hand-maintained `image === images[0]` invariant holds only until the first consumer that forgets it.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] The image-suffix constant has one home, imported by all three backends
- [ ] `EquipmentGridRow` and `_transport()` results are NamedTuples; no positional unpacking remains
- [ ] `ReviewEntry.image` is derived (or removed) with consumers updated; the hand-maintained invariant is gone
- [ ] Provider contract suites stay green (`pytest back_dev_home/msr_file back_dev_home/ebeam/hitachi/recipe_search -q`)
