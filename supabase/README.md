# DCAL Supabase migrations

Apply the SQL files in `migrations/` in timestamp order to a DCAL-only Supabase project. Do not point these migrations at DCRP.

The foundation creates inactive-by-default profiles, mutable task state, append-only revisions, a private `dcal-pages` bucket, deny-all direct browser policies for task data, and server-only RPCs for optimistic saves and pilot task creation.

After every migration:

1. run the Supabase security advisor and resolve every security finding;
2. confirm `dcal-pages` remains private;
3. confirm `anon` and `authenticated` cannot select or mutate `tasks` or `revisions` directly;
4. run the web build and contract tests;
5. never seed real users, images, transcripts, exports, Drive IDs, or credentials through Git migrations.

Human account creation and activation are operational steps in `../docs/DEPLOYMENT_RUNBOOK.md`, not seed data.
