# Hosted DCAL deployment runbook

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

The deployment branch contains:

- timestamped Supabase migrations for the hosted schema, private bucket, RLS policies, membership trigger, optimistic save function, and manual-upload function;
- a Next.js 16 application in `web/`;
- server-only task, image, upload, ingestion, and export routes;
- a Drive worker adapter that uploads rendered pages through short-lived signed URLs;
- TypeScript contract tests and the existing Python suite;
- an authenticated-by-design access model in which new users are inactive and direct browser access to tasks/revisions is denied.

A DCAL Supabase project has been created in `ap-south-1` and the migrations have been applied. Its security advisor must remain clear before production use.

## Secrets and public configuration

Generate both random values on a trusted administrator machine. Do not paste them into Git, a PR, chat, a ticket, or a screenshot.

```bash
openssl rand -hex 32  # DCAL_WORKBENCH_INGEST_TOKEN: copy to Vercel and the worker
openssl rand -hex 32  # DCAL_GROUP_HMAC_KEY: worker only; preserve permanently
```

The values have different purposes and must not be reused.

| Variable | Vercel | Worker | Secret | Rotation rule |
|---|---:|---:|---:|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | No | No | Change only when moving the project |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Yes | No | No | Rotate in Supabase if required |
| `SUPABASE_SECRET_KEY` | Yes | No | **Yes** | Rotate after exposure; never prefix with `NEXT_PUBLIC_` |
| `DCAL_WORKBENCH_INGEST_TOKEN` | Yes | Yes | **Yes** | Rotate both ends together |
| `DCAL_GROUP_HMAC_KEY` | No | Yes | **Yes, identity-critical** | Do not rotate after ingestion without an identity migration |
| `DCAL_DRIVE_ROOT_FOLDER_ID` | No | Yes | Sensitive operational metadata | Change only with an explicit Drive migration |
| Google credential JSON | No | Yes | **Yes** | Rotate through Google Cloud/Workspace |

## Step 1 — Merge the deployment pull request

The pull request is the code-review boundary. It does not contain patient data or production secrets. Review the checks and merge it into `main`. Vercel production should track `main`; branch previews are optional.

Do not connect an unprotected preview deployment to a Supabase project containing clinical pages. Use either a separate synthetic Supabase project for previews or production-only environment variables with previews disabled/protected.

## Step 2 — Lock down Supabase Auth

In the DCAL Supabase dashboard:

1. Open **Authentication → Providers → Email**.
2. Turn off **Allow new users to sign up**. The workbench has no signup UI, but the backend setting is still required.
3. Require confirmed email for any non-administrative invitation flow. For dashboard-created pilot users, create and confirm them administratively.
4. Open **Project Settings → API Keys**.
5. Copy the active project URL and modern `sb_publishable_...` key.
6. Create or reveal a modern `sb_secret_...` key for Vercel. Do not use it in a browser variable and do not store it on the Drive worker.

Keep the old JWT-style `service_role` key unused when a modern secret key is available.

## Step 3 — Import DCAL into Vercel

In Vercel:

1. Choose **Add New → Project** and import `DrDewan/DCAL`.
2. Set **Root Directory** to `web`.
3. Keep the detected framework as **Next.js**.
4. Keep the install command as `npm install`, build command as `next build`, and output settings at their Next.js defaults.
5. Add these variables to the **Production** environment:

   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_SECRET_KEY`
   - `DCAL_WORKBENCH_INGEST_TOKEN`

6. Deploy production from `main`.
7. Record the stable production URL, for example `https://dcal.example.vercel.app`.

The application must never emit the secret key or ingestion token. Vercel logs should contain route/status diagnostics only; do not add request-body logging.

## Step 4 — Configure Supabase URLs

In **Authentication → URL Configuration**:

1. Set **Site URL** to the stable Vercel production URL.
2. Add only approved redirect URLs. Email/password sign-in does not need a wildcard preview redirect.
3. Do not add broad `*.vercel.app` clinical redirect patterns.

Redeploy after changing Vercel variables. A successful build alone does not prove that runtime secrets are correct.

## Step 5 — Create and activate the first administrator

1. In **Authentication → Users**, choose **Add user**.
2. Enter the administrator's real work email and a unique temporary password. Do not send the password through the repository or a public channel.
3. Auto-confirm the dashboard-created user if the dashboard offers that option.
4. In the Supabase SQL editor, replace both placeholders and run:

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

The query must return exactly one row. If it returns none, stop and verify the Auth user instead of inserting a profile manually.

For later users, create the Auth user first and activate it with one of these roles:

- `annotator`: view pages and save/complete annotations;
- `reviewer`: annotator capabilities plus gold export;
- `admin`: reviewer capabilities plus operational administration performed in the dashboard.

There is intentionally no self-service activation or browser-side role mutation.

## Step 6 — Verify the hosted workbench with synthetic data

Before connecting Drive or uploading patient material:

1. Open `/api/health`; expect `{"status":"ok",...}`.
2. Open `/` in a signed-out browser; expect a redirect to `/login`.
3. Request `/api/tasks` while signed out; expect HTTP 401.
4. Sign in as the activated administrator.
5. Upload one synthetic JPEG/PNG/WebP page smaller than 4 MiB.
6. Confirm it is labelled **Pilot upload**, create a box, transcribe synthetic text, save, reload, and complete it.
7. Confirm the same upload is deduplicated.
8. Confirm an annotator account does not see the export control and receives HTTP 403 from the export endpoint.
9. Confirm a reviewer/admin export skips the pilot page and reports it in `X-DCAL-Skipped-Manual`.

Do not proceed if the browser exposes a Supabase secret key, a storage object is public, a signed-out request reads task data, or a stale-version save overwrites a newer revision.

## Step 7 — Create the separate Google Drive

Preferred path:

1. Create a Google Workspace Shared Drive used only for DCAL.
2. Create a dedicated Google Cloud service account and enable the Drive API.
3. Add that service account to the Shared Drive as **Manager** because DCAL applies owner-restricted content restrictions.
4. Download its JSON key to the worker host at `secrets/google-drive-credentials.json`; set owner-only file permissions.
5. Choose the Shared Drive root or an empty folder inside it as `DCAL_DRIVE_ROOT_FOLDER_ID`.

If a Shared Drive is unavailable, use the separate-account OAuth flow in `GOOGLE_DRIVE_RUNBOOK.md`. Do not use a personal account that contains unrelated material.

## Step 8 — Configure the long-lived ingestion worker

On one private Docker-capable machine or existing private CPU worker:

```bash
cp .env.example .env
```

Set at least:

```dotenv
DCAL_WORKBENCH_URL=https://your-production-dcal-url
DCAL_WORKBENCH_INGEST_TOKEN=<the exact Vercel ingestion token>
DCAL_DRIVE_ROOT_FOLDER_ID=<dedicated Drive root ID>
DCAL_GOOGLE_CREDENTIALS_FILE=./secrets/google-drive-credentials.json
DCAL_GROUP_HMAC_KEY=<the permanent worker-only HMAC key>
DCAL_INGESTION_INTERVAL_SECONDS=60
```

Then bootstrap and verify the Drive:

```bash
docker compose --profile ingestion build dcal-ingest
docker compose --profile ingestion run --rm --no-deps dcal-ingest bootstrap-drive
docker compose --profile ingestion run --rm --no-deps dcal-ingest doctor
```

Upload one synthetic source through the required patient/encounter folder hierarchy and run:

```bash
docker compose --profile ingestion run --rm --no-deps dcal-ingest sync-once
```

Confirm that the task appears as **Dataset-ready**, then start the single continuous worker:

```bash
docker compose --profile ingestion up -d --build dcal-ingest
docker compose logs --tail=100 dcal-ingest
```

Routine logs must contain aggregate counts only. They must not contain filenames, Drive IDs, folder names, transcripts, tokens, or signed URLs.

## Step 9 — Complete the clinical-data gate

Before the first real page, the responsible institution must explicitly approve:

- use of the selected Vercel, Supabase, and Google Workspace accounts/plans and their data regions;
- named-user lifecycle, password/reset policy, session revocation, and periodic access review;
- least-privilege Drive roles and who may remove content restrictions;
- database/export backup schedule and a witnessed restore drill;
- retention/deletion rules, incident response, and breach notification ownership;
- storage-capacity monitoring and the threshold for leaving free plans;
- whether an additional VPN, identity-aware proxy, or network restriction is required.

The technical login and private bucket are necessary controls, not a declaration of regulatory compliance.

## Routine operations

### Add a user

Create the user in Supabase Auth, then activate the generated profile through reviewed SQL. Never authorize from `user_metadata`; only `public.profiles.role` and `active` are authoritative.

### Disable a user

Set `active=false`, then sign the user out/revoke sessions in Supabase Auth. Disabling the profile makes subsequent API authorization fail even if an old session cookie still exists.

### Audit Drive

```bash
docker compose --profile ingestion run --rm --no-deps dcal-ingest audit-drive
```

Run this before every frozen dataset release and on a regular schedule.

### Monitor capacity

Watch Supabase database size and `dcal-pages` bucket usage. The free project is a pilot constraint, not a target architecture for an unlimited corpus. Because canonical pages remain in Drive, capacity changes do not change page identity, but the hosted workbench still needs an accessible private copy for active tasks.

### Rotate the ingestion token

1. Stop the Drive worker.
2. Generate a new token.
3. replace `DCAL_WORKBENCH_INGEST_TOKEN` in Vercel Production and redeploy.
4. Replace it in the worker secret file/store.
5. Start the worker and run `sync-once`.

Never rotate `DCAL_GROUP_HMAC_KEY` through this procedure.

## Release verification commands

Run before every deployment PR is marked ready:

```bash
python -m unittest discover -s tests -v
cd web
npm ci
npm test
npm run typecheck
npm run build
```

Also confirm that the latest Supabase security advisor has no findings and that no real image, annotation, export, credential, signed URL, Drive ID, or HMAC value appears in the Git diff.
