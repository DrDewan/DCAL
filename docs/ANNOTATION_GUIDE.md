# BMCH page annotation guide v1

## Unit of work

Annotate one page image at a time. Use the physical page itself—not its Drive folder, filename, neighboring pages, or expected clinical family—to choose the page type.

## Workflow

1. Inspect the full page and select its physical document type.
2. Select a known visual variant only when the layout genuinely matches that registered variant.
3. Mark every applicable image-quality problem.
4. Draw a tight rectangle around each meaningful variable region or text line.
5. Select the region label.
6. Enter its top-to-bottom, left-to-right reading-order number.
7. Select legibility and, where applicable, the semantic clinical region.
8. Transcribe exactly what is visible. Do not correct spelling, expand abbreviations, normalize dates, or infer missing words.
9. Add an optional stable field code only when one has been defined by the project lead.
10. Review the page, then submit.

## Region granularity

- Prefer one bounding box per handwriting line or meaningful fixed-form field.
- Keep a multi-line phrase together when splitting it would destroy meaning.
- Do not draw one box per individual character or word unless a later specialist protocol explicitly requires it.
- Do not include static printed boilerplate in every annotation when it is represented by a registered template; annotate variable printed content and any boilerplate that materially differs from the template.

## Labels

| Label | Use |
|---|---|
| `printed_static` | Registered or potentially registerable boilerplate printed on the form |
| `printed_variable` | Patient- or event-specific machine-printed value |
| `handwriting` | Handwritten letters, words, numbers, or marks intended as text |
| `checkbox_mark` | Tick, cross, filled circle, or equivalent selection mark |
| `stamp_or_seal` | Institutional or clinician stamp/seal |
| `signature` | Signature or initials functioning as authentication |
| `drawing_or_tracing` | ECG tracing, plotted chart, diagram, or non-text graphic |
| `other_region` | Meaningful content that fits no current label; explain in notes |

Use the separate structure-role control for `form_field`, `free_text_block`, `table_header`, `table_cell`, or `chart_axis_or_label`. This preserves whether the content itself is printed, handwritten, or non-text.

## Legibility

- `legible`: confidently visible without reconstruction.
- `partially_legible`: some exact characters are visible; transcribe only those and use `[?]` for a local unresolved fragment.
- `illegible`: no defensible transcription; leave transcription blank.
- `not_applicable`: non-text content such as a signature or tracing.

Never replace an unreadable word with a medically plausible guess.

## Quality flags

Use all that apply: blur, rotation, skew, perspective distortion, crop loss, glare/shadow, low contrast, compression artifact, obstruction, or other. Use `clear` only when none of the defects materially affect reading.

## Privacy

The annotation system necessarily displays clinical information. Do not copy it into tickets, chat, GitHub, screenshots, test fixtures, or developer logs. Use synthetic examples when reporting software defects.
