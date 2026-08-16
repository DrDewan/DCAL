# DCAL architecture

## Purpose

DCAL builds institution-specific page classification and document-reading models from human-reviewed BMCH material. It is an experimental and dataset-governance system, not a clinical record application.

## Boundary

DCAL and DCRP have separate repositories, deployments, databases, credentials, and release cycles. No DCAL experiment may write into DCRP. A future promoted model may be exposed behind a versioned inference API that DCRP calls explicitly.

## Components

1. **Ingestion service** — a separate long-lived worker scans a dedicated Drive, renders pages, calculates checksums, generates opaque grouping IDs, archives originals/pages under content restrictions, uploads a private workbench copy, and creates idempotent tasks. It is not a Vercel function.
2. **DCAL workbench** — a first-party Next.js human annotation interface on Vercel. A DCAL-only Supabase project provides named authentication, operational PostgreSQL state, append-only revisions, and a private working-copy page bucket. The original local SQLite interface remains a compatibility/development path.
3. **Dataset adapter/export** — validates completed workbench state and converts provenance-complete pages into stable `dcal.gold.v1`. The prior Label Studio adapter remains for compatibility.
4. **Dataset registry** — freezes releases and patient/writer-separated train, validation, and sealed-test splits. Planned.
5. **Experiment runner** — launches reproducible CPU/GPU challengers and records code, container, configuration, cost, latency, and metrics. Planned.
6. **Model registry** — promotes a challenger only after regression gates pass. Planned.
7. **Inference gateway** — serves only promoted models with versioned requests and responses. Planned.

## Champion/challenger architecture

The experiment system is provider-neutral. OpenAI, Claude, local OCR, Gemini, rules-based preprocessing, and hybrid systems all participate as challengers behind the same DCAL contracts.

```mermaid
flowchart TD
    A["Frozen dataset release"] --> B["Provider-neutral challenger spec"]
    B --> C["OpenAI / Claude / local / hybrid runner"]
    C --> D["Normalized prediction contract"]
    D --> E["Scoring and regression gates"]
    E --> F["Champion or harvested component"]
```

Claude participation is expected, but Claude is not a privileged code path. Claude challengers must use the same dataset snapshots, output contract, scoring, cost reporting, and promotion gates as every other provider.

Reusable improvements from all challengers are recorded in `docs/WINNING_COMPONENTS.md`. A losing challenger can still contribute a winning component such as a better preprocessing step, prompt fragment, parser rule, confidence rule, or template-drift detector.

## Data flow

```mermaid
flowchart TD
    A["Dedicated Drive inbox"] --> C["Ingestion worker"]
    C --> B["Locked source and page store"]
    C --> D["Private Supabase page and task"]
    D --> E["Vercel workbench annotation"]
    E --> F["Contract validation and eligibility gate"]
    F --> G["Versioned gold dataset"]
    G --> H["CPU/GPU experiment"]
    H --> I{"Regression gates"}
    I -->|Fail| H
    I -->|Pass| J["Promoted model"]
    J -. "future versioned API" .-> K["DCRP"]
```

## Why operational annotation state is not canonical

The workbench Supabase database, local SQLite database, and optional Label Studio database are mutable collaboration state. DCAL therefore stores immutable normalized dataset releases outside every interface. Only completed pages with opaque patient/encounter provenance may enter a gold release.

## Security baseline

- Hosted users authenticate with named Supabase Auth accounts. New accounts are inactive until explicitly activated; task/revision tables have deny-all browser policies.
- Vercel server routes revalidate every session and mediate all database and private-image access with a server-only secret key. Reviewer/admin roles alone can export gold.
- The ingestion route requires a separate bearer secret. The worker receives a short-lived signed page-upload URL, never the Supabase secret key.
- Browser upload is excluded from dataset export until Drive provenance upgrades the checksum-addressed page.
- Raw images and canonical rendered pages live in the dedicated Drive. Supabase Storage and the local checksum-addressed cache are operational copies.
- The optional Label Studio compatibility profile retains disabled public signup, SSRF protection, and disabled product analytics.
- Drive objects are content restricted and audited, but Drive is not represented as true write-once storage.
- Vercel supplies HTTPS, but hosting does not by itself establish clinical compliance. Real material still requires institutional approval, documented access review, backup/restore tests, incident response, retention rules, and confirmation that the selected Vercel/Supabase plans and regions meet policy.

## Accuracy layers

Metrics are never collapsed into one headline number:

- Page classification: per-class precision, recall, F1, confusion, abstention, and false-acceptance rate.
- Text: character error rate and word error rate, separated into printed and handwritten content.
- Fields: exact-field accuracy and clinically critical token errors.
- Automation: accepted-result precision at defined confidence thresholds and human-review coverage.
- Operations: latency, cost, failure rate, and image-quality strata.
