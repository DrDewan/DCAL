# DCAL repository instructions

These instructions apply to every coding agent and contributor.

## Required reading

Before changing implementation, read in this order:

1. `docs/ROADMAP.md`
2. `docs/DECISIONS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DATA_CONTRACT.md`
5. Relevant code and tests

If these artifacts conflict, stop and report the conflict. Authority is roadmap, then decisions, then architecture/data contract, then task wording, then existing code.

## Hard boundaries

- DCAL remains operationally and data-model independent of DCRP.
- Do not add a DCRP database dependency. Future integration is through a versioned inference API only.
- Never commit PHI, patient images, real annotations, real transcripts, credentials, signed URLs, or storage identifiers that expose patients.
- Source images are immutable. Identity is the byte-level SHA-256 plus an opaque source object ID.
- Machine output never becomes human ground truth automatically.
- `unknown_document`, `unknown_region`, and `illegible` are valid outcomes. Do not force certainty.
- Never tune on the sealed test set. Split by patient and writer before model development.
- Static printed template text should come from registered templates where possible; do not repeatedly OCR known boilerplate and count it as model accuracy.

## Change workflow

- One focused implementation block per branch and pull request.
- Use `agent/<short-description>` branches.
- Keep Label Studio adapters behind repository-owned contracts. Do not let Label Studio export shape become the permanent dataset schema.
- Add or update tests for every contract or parser change.
- Run `python -m unittest discover -s tests -v` and relevant validation commands.
- Run `docker compose config` when Docker is available.
- Update docs and `docs/DECISIONS.md` when behavior or architecture changes.
- Default to draft pull requests. Do not self-merge.

## Definition of done

A coding block is complete only when scope is documented, tests pass, generated artifacts contain synthetic data only, the branch is pushed, and the PR reports exact checks and known limitations.
