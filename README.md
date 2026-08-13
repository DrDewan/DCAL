# DCAL

DCAL is the standalone **Document Classification, Annotation, and Learning** laboratory for Bangladesh Medical College Hospital (BMCH) pages.

It is intentionally independent of DCRP. DCAL owns annotation, gold-dataset creation, experiments, evaluation, and model promotion. DCRP may consume a stable versioned inference API later, but it is not a dependency of this repository.

## Current foundation

- Self-hosted Label Studio Community `1.23.0` with PostgreSQL.
- A BMCH single-page annotation interface for physical page classification, image-quality flags, bounding boxes, exact transcription, legibility, reading order, and semantic region labels.
- A versioned, repository-owned physical-document taxonomy.
- Strict validation and deterministic conversion of Label Studio exports into `dcal.gold.v1` JSONL records.
- Synthetic fixtures and CI checks. No patient pages or identifiable data belong in Git.

Not implemented yet: Google Drive ingestion, private object storage, RunPod model workers, active-learning selection, experiment tracking, or DCRP integration.

## Local start

Prerequisites: Docker with Docker Compose and Python 3.11 or newer.

```bash
cp .env.example .env
# Replace every placeholder password in .env before continuing.
docker compose up -d
```

Open `http://localhost:8080`. Sign in with the administrator credentials from `.env`, create a Label Studio API token from **Account & Settings**, then create the DCAL project:

```bash
export LABEL_STUDIO_API_TOKEN="your-local-token"
python scripts/bootstrap_label_studio_project.py
```

The bootstrap command is idempotent: it returns the existing project rather than silently creating duplicates.

## Validate an annotation export

```bash
python -m dcal_annotations validate-export examples/label-studio-export.valid.json
python -m dcal_annotations normalize-export \
  examples/label-studio-export.valid.json \
  --output /tmp/dcal-gold.jsonl
```

Install the package first when running outside this checkout:

```bash
python -m pip install -e .
```

## Tests

```bash
python -m unittest discover -s tests -v
```

Docker is not required for the Python and configuration tests. CI additionally runs `docker compose config`.

## Non-negotiable data rules

- Never commit real patient images, exports, transcripts, identifiers, access tokens, or signed URLs.
- Originals are immutable and identified by SHA-256.
- `patient_group_id` and `encounter_group_id` are opaque keyed identifiers, not raw hospital IDs and not unsalted hashes.
- Unknown or unreadable content must be labelled as such; it must never be guessed into a known class or transcription.
- Test pages are separated by patient and writer and remain unavailable to model tuning.
- Label Studio is the annotation user interface, not the canonical dataset or model registry.

Read [Architecture](docs/ARCHITECTURE.md), [Data Contract](docs/DATA_CONTRACT.md), [Annotation Guide](docs/ANNOTATION_GUIDE.md), and [Roadmap](docs/ROADMAP.md) before extending the system.
