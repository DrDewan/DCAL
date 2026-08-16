# DCAL hosted workbench

This directory is the Vercel/Supabase implementation of the first-party DCAL annotation workbench. It is independent of DCRP.

## Local synthetic verification

Copy `.env.example` to `.env.local` and supply a DCAL-only Supabase project. Never use production clinical secrets on an untrusted developer machine.

```bash
npm ci
npm test
npm run typecheck
npm run dev
```

The Vercel project root must be this `web/` directory. Required runtime variables are documented in `../docs/DEPLOYMENT_RUNBOOK.md`.

## Trust boundary

- Browser code receives only the Supabase URL, publishable key, and HttpOnly session cookies.
- Every task, image, upload, mutation, and export route revalidates a named active member.
- `SUPABASE_SECRET_KEY` is server-only and must never be prefixed with `NEXT_PUBLIC_`.
- The Drive worker uses only `DCAL_WORKBENCH_INGEST_TOKEN` and short-lived signed page-upload URLs.
- Direct browser roles have no task/revision table access and the page bucket is private.
- Browser uploads are pilot-only; Google Drive ingestion supplies dataset eligibility.

The server API intentionally retains the local workbench response shapes so the annotation UI and dataset contract stay provider-neutral.
