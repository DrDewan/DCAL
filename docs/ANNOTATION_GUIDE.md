# BMCH page annotation guide v1

## Unit of work

Annotate one page image at a time. Use the physical page itself—not its Drive folder, filename, neighboring pages, or expected clinical family—to choose the page type.

## Workflow

1. Open a page from the work queue and inspect the whole page at **Fit** zoom.
2. Select its physical document type and page content profile. Select a visual variant only when the layout genuinely matches a registered variant.
3. Mark every applicable image-quality problem.
4. Choose **Fixed**, **Variable**, **Writing**, **Choice**, or **Grid**, then draw a tight rectangle around one meaningful region. Drag inside a selected box to move it; drag a corner to resize it.
5. Confirm the region type, top-to-bottom/left-to-right reading order, legibility, and structure.
6. Transcribe exactly what is visible. Do not correct spelling, expand abbreviations, normalize dates, or infer missing words.
7. Add an optional stable field code only when one has been defined by the project lead.
8. Repeat until the meaningful page content is represented, review the region list, then select **Complete page**.

Drafts autosave after a short pause. `Ctrl/Cmd+S` saves immediately. `F` selects fixed printed text, `D` variable printed text, `H` handwriting, `C` choice marks, `G` grid/other, and `V` selection mode. Hold Space while dragging to pan.

## Region granularity

- Prefer one bounding box per handwriting line or meaningful fixed-form field.
- Keep a multi-line phrase together when splitting it would destroy meaning.
- Do not draw one box per individual character or word unless a later specialist protocol explicitly requires it.
- During template discovery, annotate representative static printed labels and every variable field location. After a template variant is registered, do not repeatedly box unchanged boilerplate on every sample; annotate variable content and material template drift.

For a fully printed document with no handwritten content, choose one of:

- `printed_blank_form` when it is an unfilled reusable form; mark fixed labels and empty variable field locations.
- `printed_filled_form` when machine-printed values fill a form; mark fixed template anchors and each variable typed value.
- `printed_document` when the page is not a fillable form; mark meaningful printed blocks in reading order.

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
