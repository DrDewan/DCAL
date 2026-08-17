@AGENTS.md

Claude contributors must follow the repository authority order and hard boundaries in `AGENTS.md`.

Before changing anything, read `docs/AI_HANDOFF.md` for the current deployed state, recent work, code map, known technical debt, and continuation checklist. Then read the normative roadmap/decisions/architecture/data-contract documents required by `AGENTS.md` and verify current GitHub/Vercel state.

For hosted workbench UI changes, specifically inspect `web/public/app.js`, `web/public/ux-v2.js`, `web/public/ux-v2.css`, and `web/app/page.tsx` before editing; UX v2 is intentionally layered after the base client.

For challenger/model work, read `docs/CHALLENGER_PLAYBOOK.md` and `docs/WINNING_COMPONENTS.md` before proposing an experiment. For hosted application or infrastructure work, read `docs/DEPLOYMENT_RUNBOOK.md`. For Drive ingestion work, read `docs/GOOGLE_DRIVE_RUNBOOK.md`.
