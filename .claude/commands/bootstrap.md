---
description: Walk the user through the full greenfield bootstrap workflow
---

Run the greenfield bootstrap workflow in order. Between phases, summarize what you produced and ask the user to approve before moving on.

For each phase below, read the named slash-command file and follow its instructions exactly:

1. **PRD** — if `docs/PRD.md` does not exist, follow `.claude/commands/prd.md`.
2. **Tech spec** — if `docs/tech-spec.md` does not exist, follow `.claude/commands/tech-interview.md`.
3. **Skills** — follow `.claude/commands/scaffold-skills.md` to populate `.claude/skills/`.
4. **Rules** — follow `.claude/commands/scaffold-rules.md` to populate `.claude/rules/` beyond the defaults.
5. **Required rules check** — confirm `.claude/rules/spec-driven-development.md` and `.claude/rules/test-driven-development.md` exist. They ship with the template; if missing, halt and tell the user the template is broken.
6. **Build loop** — follow `.claude/commands/pick-loop.md` to choose a build loop and write `docs/build-loop.md`.

Stop after step 6. Tell the user that bootstrap is complete and they can run `/build` when ready.

Do not skip phases unless the produced artifact already exists. If the user wants to redo a phase, run that phase's command directly.
