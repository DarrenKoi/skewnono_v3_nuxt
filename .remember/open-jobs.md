# Open Jobs

_Updated: 2026-06-30 · branch: main_

## In progress
- [ ] Validate the new `/leave-office` ↔ `/back-to-office` loop — next: tomorrow morning run `/back-to-office` and confirm it surfaces this file and proposes a resume (`~/.claude/skills/back-to-office/SKILL.md`) · since 2026-06-30

## Blocked
- (none)

## Backlog / soon
- [ ] Optional: run skill-creator description eval on `/leave-office` + `/back-to-office` to tune auto-triggering, then package the two skills · since 2026-06-30

## Context to remember
- These two skills ride the `.remember/` rails by design; pickup is the explicit `/back-to-office` command, NOT the SessionStart hook (hook untouched).
- Skewvoir `Fdc*` cluster is staged WIP — keep it, don't prune as dead code.
