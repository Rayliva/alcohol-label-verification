---
description: Execute the project's chosen build loop
---

1. Read `docs/build-loop.md`. If it does not exist, halt and tell the user to run `/pick-loop` first.
2. Read `docs/PRD.md` and `docs/tech-spec.md` for context.
3. Read every file in `.claude/rules/`.
4. Read `.claude/skills/INDEX.md` (and any individual skill files relevant to the next iteration).
5. Execute the build loop as specified in `docs/build-loop.md`, iteration by iteration, until its stopping condition is met.
6. Between iterations, briefly report progress to the user.

If the loop's specification is ambiguous mid-run, halt and ask. Do not paper over the ambiguity by guessing.
