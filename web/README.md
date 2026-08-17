# DCAL hosted workbench

This directory is the Vercel/Supabase implementation of the first-party DCAL annotation workbench. It is independent of DCRP.

Current stable production URL:

`https://dcal-bm7i.vercel.app`

Before editing this application, read `../docs/AI_HANDOFF.md`, `../AGENTS.md`, `../docs/WORKBENCH_RUNBOOK.md`, and the relevant data/deployment documents.

## Current browser architecture

The hosted annotation client is currently layered for incremental safety:

- `public/app.js` — base browser client: queue, canvas, drawing, selection, move/resize, autosave, base keyboard handling.
- `public/ux-v2.js` — enhancement layer: Table/Pan tools, spreadsheet table entry, trackpad panning, pointer-centred zoom, inspector reordering/scroll isolation, multiline enhancements.
- `public/ux-v2.css` — styles for those enhancements.
- `app/page.tsx` — loads the base client before UX v2.
- `lib/workbench-markup.ts` — server-generated workbench HTML structure.

Do not remove or reorder `ux-v2.js` merely because it appears to overlap with the base client. It wraps/intercepts existing global behavior and depends on loading after `app.js`. Consolidating it into the base client should be a dedicated behavior-preserving refactor, not an incidental cleanup during feature work.

## Structured table annotation

Investigation reports can use one parent region with `structure_role: "table"` and a structured `table_data` cell matrix. Server validation is in `lib/validation.ts`; browser entry logic is in `public/ux-v2.js`. See `../docs/TABLE_ENTRY_V2.md` and `../docs/DATA_CONTRACT.md`.

## Local synthetic verification

Copy `.env.example` to `.env.local` and supply a DCAL-only Supabase project. Never use production clinical secrets on an untrusted developer machine.

```bash
npm ci
npm test
npm run typecheck
npm run build
npm run dev
```

This project currently requires Node `>=22` and uses Next.js 16.3.1. Read the Next.js agent guidance in `AGENTS.md` before assuming older Next.js APIs or conventions.

The Vercel project root must be this `web/` directory. Required runtime variables are documented in `../docs/DEPLOYMENT_RUNBOOK.md`.

## Trust boundary

- Browser code receives only Supabase URL/publishable key and HttpOnly session cookies.
- Every task, image, upload, mutation, and export route revalidates a named active member.
- `SUPABASE_SECRET_KEY` is server-only and must never be prefixed with `NEXT_PUBLIC_`.
- Drive worker uses only `DCAL_WORKBENCH_INGEST_TOKEN` and short-lived signed page-upload URLs.
- Direct browser roles have no task/revision table access and the page bucket is private.
- Browser uploads are pilot-only; Google Drive ingestion supplies dataset eligibility.
- Never add request-body logging containing annotation text, filenames, storage IDs, or signed URLs.

## Taxonomy synchronization

The web bundle contains `data/taxonomy.json`, but the repository also has canonical/compatibility copies outside this directory. Taxonomy changes must be checked against:

- `../config/taxonomy/bmch-document-taxonomy.v1.json`
- `data/taxonomy.json`
- `../config/label-studio/bmch-page-annotation.v1.xml`

CI checks compatibility aliases; PR #8 initially failed because a new `table` structure role was not added to the Label Studio alias list.

The server API intentionally retains stable workbench response shapes so the annotation UI and dataset contract stay provider-neutral.
