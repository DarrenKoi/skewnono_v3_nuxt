# Open Jobs

_Updated: 2026-07-07 · branch: main_

## In progress
- [ ] Validate the new `/leave-office` ↔ `/back-to-office` loop — next: next session run `/back-to-office` and confirm it surfaces this file and proposes a resume (`~/.claude/skills/back-to-office/SKILL.md`) · since 2026-06-30

## Blocked
- (none)

## Backlog / soon
- [ ] Optional: run skill-creator description eval on `/leave-office` + `/back-to-office` to tune auto-triggering, then package the two skills · since 2026-06-30
- [ ] Commit the pending `.remember/` consolidation changes (archive/recent roll + today-2026-07-07) as the usual `chore(remember)` — left out of f9c56c0 on purpose · since 2026-07-07

## Closed today
- Measurement-rules display simplification — shipped & pushed (f9c56c0): WAFER/LEVEL fixed strip, EV/TV vehicle labels, accent on expanded EDGE/EDGE_EX, Sample rules split into own table.

## Context to remember
- These two skills ride the `.remember/` rails by design; pickup is the explicit `/back-to-office` command, NOT the SessionStart hook (hook untouched).
- Skewvoir `Fdc*` cluster is staged WIP — keep it, don't prune as dead code.
- Rules matrix emphasis is selector-derived (`isExpandedCell` in `ruleMatrix.ts`), so the step-3 inline cap editor will inherit highlighting for free; `mfab` prop is gone from `rules/Matrix.vue` (D22).
