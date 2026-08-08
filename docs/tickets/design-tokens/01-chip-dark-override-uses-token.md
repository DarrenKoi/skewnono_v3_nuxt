# 01 — Chip dark override consumes the `--sk-ink-fg` token

**What to build:** `components/sk/Chip.vue`'s `.dark` override hardcodes `rgba(21, 17, 13, 0.18)` / `rgba(21, 17, 13, 0.9)` — the resolved dark value of `--sk-ink-fg` written out by hand, which the DESIGN.md token rule bans ("colors come from `--sk-*` tokens only, never inline hex"). Replace the literals with `color-mix` on `--sk-ink-fg` so future retones track the token. The identical pair is already byte-for-byte in `NavPill.vue`: extract one shared dark-chip/pill rule (a role class in `main.css`'s components layer) and make both components consume it.

**Why:** review Standards axis, hard violation. CLAUDE.md makes DESIGN.md the visual source of truth — "colors come from `--sk-*` tokens only, never inline hex". A hand-resolved literal of a token's current value is worse than an arbitrary hex: it looks deliberate, but freezes today's value, so the next dark-mode retone silently leaves the chip stale. The byte-identical pair in `NavPill.vue` means that retone already shotguns across two design-system components.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — ba4926c9 — .sk-count-on-ink 로 .dark 오버라이드 자체를 제거(--sk-ink-fg 가 반전하므로)

- [ ] No inline color literals remain in `Chip.vue`'s dark override
- [ ] `NavPill.vue` and `Chip.vue` consume the same shared rule instead of two copies
- [ ] Dark-mode appearance is visually unchanged in both components
