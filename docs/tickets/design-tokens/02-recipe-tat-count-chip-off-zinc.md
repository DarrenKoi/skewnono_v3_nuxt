# 02 — Recipe-TAT count chips come off zinc utilities

**What to build:** the "N / M" count chip ships with `bg-zinc-100` / `text-zinc-600` / `dark:` zinc variants in three sibling components — `RecipeTatFleetTable`, `RecipeTatEquipmentCompare`, `RecipeTatView`. This is a new instance of the zinc-on-chrome pattern DESIGN.md bans (zinc survives only in table hovers and empty-state messages); commit d48d592b deferred it knowingly. Replace the zinc utilities with `--sk-*` tokens or a role class in all three places.

**Why:** review Standards axis, hard violation. DESIGN.md explicitly narrows where zinc survives (table hovers, empty-state messages); this chip is chrome. Commit d48d592b swept exactly this class of drift out of the same three files and deferred only the count chip — so the deferral is acknowledged, but every day it stands it reads as precedent for the next zinc usage.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] All three count chips use `--sk-*` tokens / role classes, no zinc utilities
- [ ] Light and dark appearance verified visually in the recipe-tat views
- [ ] No new zinc-on-chrome instances remain in the recipe-tat tables
