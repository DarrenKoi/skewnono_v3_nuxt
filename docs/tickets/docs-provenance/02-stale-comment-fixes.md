# 02 — Fix two stale comments

**What to build:** two comment/docstring corrections. First, the device-statistics fab-store fix (03ddfcf9) left a comment claiming "only a key bump clears the copies already written" — in fact nothing is cleared; the old localStorage keys are simply orphaned. Correct the comment so the next session doesn't believe cleanup happened. Second, the HV-SEM `_mock_raw_listing` synthesizes only files that match the expected stems, so the `image_variants` filtering path never runs end-to-end at home; the mock docstring discloses shape fabrication but not this omission — disclose it, so nobody trusts a green home run as coverage of the filter.

**Why:** review Standards axis, judgement calls. Both comments are load-bearing explanations of non-obvious behavior, and both currently teach something false: one claims orphaned localStorage copies get "cleared" (they are abandoned, and a reader may wait forever for a cleanup that never runs); the other omits that the mock listing synthesizes only matching files, so a green home run looks like end-to-end coverage of the variant filter that it never provided. In a repo where docstrings are the office-knowledge carrier, false comments are worse than none.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 841d024a

- [ ] The key-bump comment no longer claims orphaned localStorage copies are cleared
- [ ] The mock raw-listing docstring states that only matching files are synthesized and the filter path is therefore unexercised at home
