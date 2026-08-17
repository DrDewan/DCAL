# Hosted DCAL deployment runbook

Read `AI_HANDOFF.md` first for the current implementation/deployment snapshot.

## Current live state — 17 August 2026

The hosted workbench is deployed from `main` with Vercel project root `web/`.

Stable production URL:

`https://dcal-bm7i.vercel.app`

PR #8 (`3cb80fc9ffbe81472d32dd97fe7bc67e18440125`) deployed successfully to production. The production deployment reached READY and `/api/health` returned HTTP 200 afterward.

A DCAL-only Supabase project exists in `ap-south-1`; repository migrations have been applied. Named authentication and hosted annotation are operational.

**Do not infer from this that the long-lived Google Drive worker is currently running.** The Drive integration is implemented and tested, but runtime worker status must be verified separately before claiming dataset-ready ingestion is active.

## Outcome

This runbook deploys the DCAL annotation workbench independently of DCRP:

| Component | Location | Responsibility |
|---|---|---|
| Web application and private API | Vercel project rooted at `web/` | Login, queue, annotation UI, validation, image delivery, ingestion API, export |
| Authentication and work state | DCAL-only Supabase project | Named users, roles, tasks, append-only revisions |
| Browser page working copy | Private Supabase Storage bucket `dcal-pages` | Page bytes used by the hosted annotation canvas |
| Canonical source and page archive | Separate DCAL Google Drive/Shared Drive | Inbox, originals, 300-DPI rendered PNGs, quarantine, future exports |
| Ingestion process | One long-lived Docker worker outside Vercel | Drive polling, rendering, checksums, opaque grouping, signed page upload, task creation |

Google Drive is the canonical source/page archive. Supabase Storage is a private operational copy so the browser does not need Google credentials. The database and gold exports require their own backups.

## Current repository-provisioned state

The repository contains:

- timestamped Supabase migrations for hosted schema, private bucket, RLS policies, membership trigger, optimistic save, and manual-upload functions;
- a Next.js 16 application under `web/`;
- server-only task, image, upload, ingestion, and export routes;
- Drive worker adapter using short-lived signed page uploads;
- TypeScript contract tests and Python suite;
- inactive-by-default memberships and deny-direct-browser task/revision access;
- table-first investigation annotation and trackpad-friendly navigation layered through `web/public/ux-v2.js` / `ux-v2.css`.

Current Supabase migrations:

- `20260816040711_vercel_supabase_foundation.sql`
- `20260816041807_align_completion_exceptions.sql`

Never rewrite an already-applied migration to make history look different. Add a new timestamped migration for any database change.

## Secrets and public configuration

Generate random values only on a trusted administrator machine. Never paste real values into Git, PRs, chats, tickets, screenshots, or documentation.

```bash
openssl rand -hex 32  # DCAL_WORKBENCH_INGEST_TOKEN: Vercel + worker
openssl rand -hex 32  # DCAL_GROUP_HMAC_KEY: worker only; preserve permanently
```

The values have different purposes and must not be reused.

| Variable | Vercel | Worker | Secret | Rotation rule |
|---|---:|---:|---:|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | No | No | Change only when moving project |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Yes | No | No | Rotate in Supabase if required |
| `SUPABASE_SECRET_KEY` | Yes | No | **Yes** | Rotate after exposure; never prefix `NEXT_PUBLIC_` |
| `DCAL_WORKBENCH_INGEST_TOKEN` | Yes | Yes | **Yes** | Rotate both ends together |
| `DCAL_GROUP_HMAC_KEY` | No | Yes | **Yes, identity-critical** | Do not rotate after ingestion without identity migration |
| `DCAL_DRIVE_ROOT_FOLDER_ID` | No | Yes | Sensitive operational metadata | Change only with explicit Drive migration |
| Google credential JSON | No | Yes | **Yes** | Rotate through Google Cloud/Workspace |

## Vercel deployment configuration

Repository: `DrDewan/DCAL`

Required configuration:

1. Root directory: `web`.
2. Framework: Next.js.
3. Production branch: `main`.
4. Production variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_SECRET_KEY`
   - `DCAL_WORKBENCH_INGEST_TOKEN`
5. Stable production alias: `https://dcal-bm7i.vercel.app`.

The application must never emit secret key or ingestion token values. Logs should contain route/status diagnostics only; do not add request-body logging.

For previews, do not connect an unprotected preview to clinical production data. Use protected previews or synthetic-only configuration.

## Supabase Auth configuration

In the DCAL Supabase project:

1. Public signup must remain disabled.
2. Pilot users are created administratively.
3. New profiles remain inactive until explicitly activated.
4. Role authority is `public.profiles.role`, not browser metadata.
5. Allowed roles:
   - `annotator`
   - `reviewer`
   - `admin`
6. Reviewer/admin roles may export gold; annotators may not.

The browser receives only project URL/publishable key plus session cookies. Server routes use `SUPABASE_SECRET_KEY` and revalidate active membership.

## Supabase URL configuration

Set **Site URL** to:

`https://dcal-bm7i.vercel.app`

Add only approved redirects. Avoid broad clinical `*.vercel.app` redirect patterns.

## Create or activate a user

Create the Auth user first, then activate the generated profile through reviewed SQL.

Example:

```sql
update public.profiles as p
set display_name = 'Administrator display name',
    role = 'admin',
    active = true,
    updated_at = now()
from auth.users as u
where p.id = u.id
  and lower(u.email) = lower('administrator@example.org')
returning p.id, p.display_name, p.role, p.active;
```

The query must return exactly one row. If it returns none, stop and verify Auth state instead of inventing a second profile.

There is intentionally no self-service browser role mutation.

## Verify hosted workbench with synthetic data

Before connecting Drive or adding patient material:

1. `GET /api/health` → HTTP 200 with `status: ok`.
2. Signed-out `/` redirects to `/login`.
3. Signed-out `/api/tasks` returns HTTP 401.
4. Activated user can sign in.
5. Synthetic JPEG/PNG/WebP can be uploaded.
6. Upload is visibly **Pilot upload**.
7. Create/select/move/resize a region, transcribe, save, reload, complete.
8. Test Table (`T`) by drawing one structured table and entering cells.
9. Test Pan (`P`), trackpad pan, and pinch/Ctrl/Cmd-wheel zoom.
10. Confirm duplicate pilot upload behavior.
11. Confirm annotator cannot export.
12. Confirm reviewer/admin export skips provenance-incomplete pilot page.

Stop if browser exposes secret credentials, storage is public, signed-out access reads task data, or stale writes overwrite newer revisions.

## Create the separate Google Drive

Preferred path:

1. DCAL-only Google Workspace Shared Drive.
2. Dedicated service account with Drive API enabled.
3. Add service account as Manager if required for content restrictions.
4. Store credential JSON only on worker host under restricted permissions.
5. Configure `DCAL_DRIVE_ROOT_FOLDER_ID` to dedicated root/folder.

If Shared Drive is unavailable, use separate-account OAuth from `GOOGLE_DRIVE_RUNBOOK.md`. Do not use a personal account containing unrelated files.

## Configure the long-lived ingestion worker

On a private Docker-capable machine:

```bash
cp .env.example .env
```

Set:

```dotenv
DCAL_WORKBENCH_URL=https://dcal-bm7i.vercel.app
DCAL_WORKBENCH_INGEST_TOKEN=<exact Vercel ingestion token>
DCAL_DRIVE_ROOT_FOLDER_ID=<dedicated Drive root ID>
DCAL_GOOGLE_CREDENTIALS_FILE=./secrets/google-drive-credentials.json
DCAL_GROUP_HMAC_KEY=<permanent worker-only HMAC key>
DCAL_INGESTION_INTERVAL_SECONDS=60
```

Bootstrap and verify:

```bash
docker compose --profile ingestion build dcal-ingest
docker compose --profile ingestion run --rm --no-deps dcal-ingest bootstrap-drive
docker compose --profile ingestion run --rm --no-deps dcal-ingest doctor
```

Upload one synthetic source in the required patient/encounter hierarchy and run:

```bash
docker compose --profile ingestion run --rm --no-deps dcal-ingest sync-once
```

Confirm task appears **Dataset-ready** before starting continuous worker:

```bash
docker compose --profile ingestion up -d --build dcal-ingest
docker compose logs --tail=100 dcal-ingest
```

Routine logs must not contain filenames, raw Drive IDs, folder names, transcripts, tokens, or signed URLs.

## Clinical-data operational gate

Before expanding real clinical use, responsible institutional owners must approve:

- Vercel/Supabase/Google account, plan, and data-region choices;
- named-user lifecycle and periodic access review;
- least-privilege Drive roles;
- database/export backup schedule;
- witnessed restore drill;
- retention/deletion rules;
- incident response/session revocation;
- storage capacity monitoring and paid-tier thresholds;
- whether VPN/IAP/network restrictions are required.

Technical authentication/private storage are necessary controls, not a declaration of regulatory compliance.

## Routine operations

### Disable a user

Set `active=false`, then revoke/sign out sessions in Supabase Auth. API authorization should fail on subsequent requests even if an old cookie existed.

### Audit Drive

```bash
docker compose --profile ingestion run --rm --no-deps dcal-ingest audit-drive
```

Run before every frozen dataset release and on a regular schedule.

### Monitor capacity

Monitor Supabase database and `dcal-pages` storage. Free tier is a pilot constraint, not unlimited target architecture.

### Rotate ingestion token

1. Stop worker.
2. Generate new token.
3. Replace Vercel Production `DCAL_WORKBENCH_INGEST_TOKEN` and redeploy.
4. Replace worker copy.
5. Start worker and run `sync-once`.

Never rotate `DCAL_GROUP_HMAC_KEY` using this procedure.

## Release verification

Before hosted PR merge:

```bash
python -m unittest discover -s tests -v
cd web
npm ci
npm test
npm run typecheck
npm run build
```

When relevant:

```bash
docker compose config
docker compose --profile ingestion config
docker compose --profile ingestion build dcal-ingest
```

Also verify:

- GitHub `annotation-contract` passes;
- GitHub `compose-contract` passes;
- Vercel preview is READY;
- preview build logs show no actual error/fatal exit;
- `/api/health` returns 200;
- after merge, production deployment reaches READY and stable alias points to it.

Finally inspect the diff for accidental PHI, credentials, signed URLs, Drive IDs, HMAC values, or real annotation content.
