# Challenger playbook

This document defines how OpenAI, Claude, local OCR, Gemini, and future systems participate in DCAL experiments. It is written for both human developers and agentic challenger builders.

DCAL challengers do not operate inside DCRP. They run inside this standalone repository against frozen DCAL dataset releases. DCRP may later consume only a promoted champion through a versioned inference API.

## Required reading for challenger builders

Before proposing or running a challenger, read:

1. `AGENTS.md`
2. `docs/ROADMAP.md`
3. `docs/DECISIONS.md`
4. `docs/ARCHITECTURE.md`
5. `docs/DATA_CONTRACT.md`
6. `docs/CHALLENGER_PLAYBOOK.md`
7. `docs/WINNING_COMPONENTS.md`

The winning-components document is deliberately shared across all challenger builders. If Claude finds a better preprocessing step and OpenAI finds a better extraction prompt, later challengers should be able to combine both rather than rediscover them separately.

## Challenger roles

A challenger is any reproducible attempt to improve page classification, full-page transcription, layout extraction, field extraction, confidence calibration, or cost/latency while preserving safety gates.

Examples:

- OpenAI vision or text model challenger.
- Claude vision or text model challenger.
- Local OCR challenger.
- Hybrid challenger using template registration plus a VLM.
- Preprocessing challenger that improves image normalization before OCR.
- Parser challenger that converts model output into the DCAL contract more reliably.

Claude is welcome as a first-class challenger provider. Claude must participate through the same contracts, dataset snapshots, scoring, and promotion gates as every other provider.

## Where challengers run

Use the cheapest environment that can honestly run the test:

| Workload | Preferred runtime | Notes |
| --- | --- | --- |
| Dataset discovery, snapshotting, scoring, orchestration | CPU VM or RunPod CPU worker | Runs continuously or on schedule. Does not need a GPU. |
| OCR/VLM inference over real page images | RunPod GPU | Use for heavy model inference or batched image processing. |
| API-based OpenAI or Claude challenger | CPU worker | The API provider does the model compute. GPU is unnecessary unless local preprocessing needs it. |
| Local OCR or local multimodal model | RunPod GPU | Record GPU type, image, runtime, and cost. |
| Static validation, parsers, contract tests | GitHub Actions or CPU worker | Must run before promotion. |

The orchestration service should wake on schedule, detect new dataset snapshots or queued challenger specs, launch jobs, collect outputs, score them, and write results to the experiment registry.

## Wake/check cadence

Recommended default:

| Phase | Wake/check interval | Promotion behavior |
| --- | ---: | --- |
| Pipeline debugging | 15-30 minutes | No promotion; inspect failures quickly. |
| Active challenger development | 1 hour | Run smoke set first, then validation if improved. |
| Larger provider comparisons | 2-4 hours | Compare OpenAI, Claude, local OCR, and hybrids on the same frozen snapshot. |
| Overnight sweeps | 6-8 hours | Run larger batches and cost/latency analysis. |
| Stable production monitoring | Daily plus failure alerts | Track drift, failures, and new annotation volume. |

The orchestrator may poll long-running jobs internally every few minutes, but humans and coding agents should normally review and build the next challenger at the cadence above.

## Dataset discipline

Never tune on the sealed test set.

Dataset releases must be split by patient and writer where possible:

- **Training/iteration set:** used for prompt/code/model development.
- **Validation set:** used to decide whether a challenger is better than the champion.
- **Sealed test set:** used only before promotion or major claims.

No challenger may promote itself because it improved on the pages it was designed around. A result that wins only on the training/iteration set is not a win.

## Challenger specification

Every challenger must be defined by a machine-readable spec before it runs. The future implementation should store this spec in Git and copy it into the experiment registry.

Minimum fields:

```yaml
challenger_id: "anthropic-printed-followup-v001"
provider: "anthropic" # openai | anthropic | google | local | hybrid | rules
model: "claude-sonnet-x"
purpose: "full_page_transcription"
dataset_release: "dcal.dataset.bmch.v001"
input_contract: "dcal.page.v1"
output_contract: "dcal.prediction.v1"
prompt_version: "prompt.followup.transcribe.v003"
preprocessing_version: "preprocess.deskew-denoise.v002"
parser_version: "parser.strict-json.v001"
scoring_version: "score.page-text-fields.v001"
runtime_target: "cpu-api"
max_cost_usd: 25
max_latency_seconds_per_page: 30
reads_winning_components: true
sealed_test_allowed: false
```

The `reads_winning_components` flag should be true only when the challenger builder has read `docs/WINNING_COMPONENTS.md` for the current branch.

## Output contract

All challengers must emit the same prediction shape, regardless of provider.

Minimum conceptual fields:

- source page ID
- dataset release ID
- challenger ID
- predicted physical document type
- abstention or unknown flag
- full-page transcription when requested
- region predictions when requested
- extracted structured fields when requested
- confidence values and uncertainty reasons
- model/provider metadata
- runtime, latency, and cost metadata
- errors and refusal/illegibility reasons

Provider-specific raw responses may be retained as private debugging artifacts, but promotion scoring must use the normalized prediction contract.

## Claude participation

Claude can participate in two ways.

First, Claude can run as a document-reading challenger. In this mode it receives page images or rendered text context and emits normalized predictions. It must not receive raw patient names, Drive object IDs, folder names, credentials, or unnecessary PHI beyond what is already present on the page image being evaluated in the controlled DCAL environment.

Second, Claude can propose code, prompt, preprocessing, parser, or scoring changes. In this mode, Claude's proposal should enter as a branch, pull request, config file, or challenger spec. It must still pass the same tests and validation gates before any component is adopted.

Claude must not:

- overwrite the champion automatically
- tune against the sealed test set
- write into DCRP
- create ground truth from its own output
- treat chat history as canonical documentation
- bypass the shared output contract

## Promotion gates

A challenger becomes the champion only if it satisfies all relevant gates:

- beats the current champion on the validation set
- does not regress on sealed test when sealed testing is authorized
- improves or preserves critical-field error rates
- preserves explicit unknown/illegible behavior
- reports cost and latency
- emits valid normalized predictions
- has reproducible code/config/prompt versions
- records what it learned in `docs/WINNING_COMPONENTS.md` if any reusable component was discovered

Promotion is component-based when possible. If a challenger loses overall but contains a better preprocessing step, prompt fragment, parser rule, or calibration method, that component can be recorded and reused later without promoting the entire challenger.

## Scoring

Do not collapse performance into a single headline accuracy.

Track at least:

- page-type precision, recall, F1, confusion, false acceptance, and abstention
- character error rate and word error rate
- printed-text performance separate from handwritten performance
- structured field exact match and clinically critical token error rate
- table/region extraction quality where relevant
- latency per page
- cost per page
- failure rate by image-quality stratum
- performance by physical document type and variant

A claimed 98% target is meaningful only after the metric is named. For example, 98% page classification is different from 98% exact field extraction or 98% handwritten word accuracy.

## Cost control

Use progressive evaluation:

1. Run a tiny smoke set on every candidate.
2. Run the validation set only if smoke results are promising.
3. Run sealed test only for serious promotion candidates.
4. Run the full dataset nightly or manually.

API challengers such as OpenAI and Claude should not run on every page every hour unless a specific experiment requires it and the cost cap allows it.

## Required experiment report

Every completed challenger should produce a short report with:

- challenger ID
- dataset release
- provider/model/runtime
- commit SHA and container image if applicable
- prompt/config/parser/preprocessing versions
- metrics compared with champion
- cost and latency
- top failure modes
- reusable winning components discovered
- whether the challenger should be promoted, rejected, revised, or partially harvested

Reports should be stored with experiment metadata and summarized in pull requests when code or docs change.

## Failure handling

Failures are useful if captured cleanly.

Use these outcomes:

- **Promote:** challenger beats champion and passes gates.
- **Reject:** challenger is worse or unsafe.
- **Revise:** promising but incomplete, unstable, or too expensive.
- **Harvest:** challenger loses overall but contains a reusable winning component.
- **Quarantine:** output invalid, data leak risk, broken contract, or unsafe behavior.

Do not keep vague "interesting result" notes without enough detail for another challenger builder to reproduce or falsify them.
