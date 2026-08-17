# DCAL repository instructions

These instructions apply to every coding agent and contributor.

## Required reading

Before changing implementation, read in this order:

1. `docs/AI_HANDOFF.md` — current deployed state, code map, recent work, known technical debt, and continuation checklist
2. `docs/ROADMAP.md`
3. `docs/DECISIONS.md`
4. `docs/ARCHITECTURE.md`
5. `docs/DATA_CONTRACT.md`
6. `docs/GOOGLE_DRIVE_RUNBOOK.md` for ingestion, storage, or deployment work
7. `docs/WORKBENCH_RUNBOOK.md` for annotation UI, API, export, or workbench deployment work
8. `docs/TABLE_ENTRY_V2.md` for investigation-table annotation or navigation work
9. `docs/DEPLOYMENT_RUNBOOK.md` for hosted Vercel, Supabase, user, secret, or worker setup
10. `docs/CHALLENGER_PLAYBOOK.md` for experiment, model, OCR, VLM, Claude, OpenAI, RunPod, or promotion work
11. `docs/WINNING_COMPONENTS.md` before proposing or changing any challenger
12. Relevant code and tests

After reading the documentation, verify the current `main` HEAD, recent pull requests, CI status, and hosted deployment before assuming the snapshot is still current.

If these artifacts conflict, stop and report the conflict. Authority is roadmap, then decisions, then architecture/data contract, then current-state handoff, then task wording, then existing code. The handoff records current state but does not override accepted architecture decisions.

## Hard boundaries

- DCAL remains operationally and data-model independent of DCRP.
- Do not add a DCRP database dependency. Future integration is through a versioned inference API only.
- Never commit PHI, patient images, real annotations, real transcripts, credentials, signed URLs, or storage identifiers that expose patients.
- Source images are immutable. Identity is the byte-level SHA-256 plus an opaque source object ID.
- Never log or commit Google Drive object IDs, source filenames, folder names, OAuth credentials, service-account credentials, or the grouping HMAC key.
- The Drive inbox depth is patient folder, encounter folder, then files. Do not invent fallback grouping when the structure is invalid.
- Machine output never becomes human ground truth automatically.
- `unknown_document`, `unknown_region`, and `illegible` are valid outcomes. Do not force certainty.
- Never tune on the sealed test set. Split by patient and writer before model development.
- Static printed template text should come from registered templates where possible; do not repeatedly OCR known boilerplate and count it as model accuracy.
- Claude, OpenAI, local OCR, and future providers participate through the same challenger contracts, dataset snapshots, scoring, and promotion gates.
- Winning components from losing challengers should be harvested into `docs/WINNING_COMPONENTS.md` when they are reusable and evidence backed.
- Do not treat browser pilot uploads as dataset-ready pages. Gold eligibility requires complete ingestion provenance.
- Do not treat a completed task as a frozen training release. Dataset release/split governance belongs to M2.

## Hosted workbench caution

The current hosted client is intentionally layered:

- `web/public/app.js` is the base browser client.
- `web/public/ux-v2.js` and `web/public/ux-v2.css` add table-first entry and trackpad-friendly navigation.
- `web/app/page.tsx` loads the base script before the enhancement script.

Do not remove or reorder the UX v2 layer as a casual cleanup. A future consolidation must be a dedicated, behavior-preserving refactor with full tests.

Taxonomy changes normally require synchronization across:

- `config/taxonomy/bmch-document-taxonomy.v1.json`
- `web/data/taxonomy.json`
- compatibility aliases in `config/label-studio/bmch-page-annotation.v1.xml`

CI checks this parity.

## Change workflow

- One focused implementation block per branch and pull request.
- Prefer `agent/<short-description>` branches for AI-driven work.
- Keep Label Studio adapters behind repository-owned contracts. Do not let Label Studio export shape become the permanent dataset schema.
- Add or update tests for every contract or parser change.
- Run `python -m unittest discover -s tests -v` and relevant validation commands.
- For hosted work, also run `cd web && npm test && npm run typecheck && npm run build`.
- Run `docker compose config` and relevant ingestion-profile checks when Docker is available.
- Update docs and `docs/DECISIONS.md` when behavior or architecture changes.
- Update `docs/WINNING_COMPONENTS.md` when a challenger discovers a reusable preprocessing, prompt, parser, calibration, extraction, or cost/latency improvement.
- A repository-authorized AI may open and merge its own focused PR after relevant CI and deployment checks pass. Never merge through a failing contract check, unresolved migration state, or unsafe clinical-data change.

## Definition of done

A coding block is complete only when scope is documented, tests pass, generated artifacts contain synthetic data only, the branch is pushed, the PR reports exact checks and known limitations, and any hosted change has a healthy preview. After merge, verify the production deployment before declaring the change live.
