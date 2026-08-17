<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

All repository-wide rules in `../AGENTS.md` apply.

Before changing the hosted workbench, read `../docs/AI_HANDOFF.md` and `../docs/WORKBENCH_RUNBOOK.md`.

Current hosted-client caution:

- `public/app.js` is the base client.
- `public/ux-v2.js` and `public/ux-v2.css` add table-first entry and improved navigation.
- `app/page.tsx` loads the base script before UX v2.
- Do not casually remove/reorder that enhancement layer.
- `lib/validation.ts` owns server-side table-data validation.
- Taxonomy edits must remain synchronized with `../config/taxonomy/bmch-document-taxonomy.v1.json` and Label Studio compatibility aliases.

Never add patient data, real transcripts, storage identifiers, signed URLs, or secrets to Git or tests.
