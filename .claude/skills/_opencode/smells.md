# Smell baseline

The fixed baseline the Standards axis always carries, from Fowler,
_Refactoring_ ch.3. Paste this file into the opencode prompt verbatim.

The model *could* read it — `--agent plan` grants read access to the whole
repo — but pasting makes the baseline part of the instruction rather than one
more file it might or might not open, and keeps the axis reproducible.

Two rules bind it:

- **The repo overrides.** A documented standard in `CLAUDE.md`, `DESIGN.md`, or
  a `MIGRATION.md` always wins. Where the repo endorses something the baseline
  would flag, suppress the smell.
- **Always a judgement call.** Each entry is a labelled heuristic ("possible
  Feature Envy"), never a hard violation. Skip anything tooling already
  enforces — `ruff`, `eslint`, and `markdownlint` run in CI and do not need a
  language model's opinion.

Each smell reads *what it is* → *how to fix*:

- **Mysterious Name** — a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code** — the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy** — a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps** — the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession** — a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches** — the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery** — one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change** — one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality** — abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains** — long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man** — a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest** — a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

## Repo-specific additions

This project has failure modes the generic list does not name. Carry these too:

- **Mock/office formula drift** — a guard, clamp, or derived-value rule added to `providers/mock.py` but not to the sibling `providers/office_example.py` (or vice versa). Home tests pass; the office silently computes a different answer. → grep the sibling for the same expression.
- **Unmarked office assumption** — a value in a mock presented as fact when nobody has confirmed it against a real office DB. → mark it `OFFICE-VERIFY`, or cite `office 확인 YYYY-MM-DD` / `user-confirmed`.
- **Doc/mock split** — a new office-DB fact recorded in `docs/datatables/<source>.txt` but not in the feature's `mock.py`, or the reverse. Both must change together.
- **Value-domain narrowing** — a mock that never emits `None`, `NaN`, `NaT`, or an empty frame, so every null-handling path in the office adapter is untested at home.
