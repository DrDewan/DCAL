# BMCH page annotation guide v1

Read `AI_HANDOFF.md` for current workbench state and `TABLE_ENTRY_V2.md` for table details.

## Unit of work

Annotate one page image at a time. Use the physical page itself—not its Drive folder, filename, neighboring pages, or expected clinical family—to choose the page type.

## Workflow

1. Open a page from the work queue and inspect the whole page at **Fit** zoom.
2. Select physical document type and page content profile. Select a visual variant only when the layout genuinely matches a registered variant.
3. Mark every applicable image-quality problem.
4. Choose the natural annotation tool:
   - **Fixed** for reusable printed boilerplate;
   - **Variable** for patient/event-specific printed values;
   - **Writing** for handwriting;
   - **Choice** for checkbox/selection marks;
   - **Table** for a relational investigation/report/chart grid;
   - **Other** for meaningful content that does not fit the above.
5. Draw a tight rectangle around one meaningful region, or one parent rectangle around a whole table.
6. Confirm region type, reading order, legibility, structure, and optional stable field code.
7. Transcribe exactly what is visible. Do not correct spelling, expand abbreviations, normalize dates, or infer missing words.
8. For a table, set rows/columns and transcribe the cell grid instead of flattening it into one text block.
9. Repeat until meaningful page content is represented, review the region list, then select **Complete page**.

Drafts autosave after a short pause. `Ctrl/Cmd+S` saves immediately.

Current shortcuts:

- `F` fixed printed text;
- `D` variable printed text;
- `H` handwriting;
- `C` choice marks;
- `G` other meaningful region;
- `T` table;
- `P` explicit pan;
- `V` selection mode;
- Space + drag pans.

Trackpad/mouse navigation in the hosted workbench:

- ordinary two-finger/wheel movement pans the page;
- pinch or `Ctrl/Cmd + wheel` zooms around the pointer;
- Pan (`P`) enables drag-to-pan;
- Fit returns to fitted page view.

## Region granularity

- Prefer one bounding box per handwriting line or meaningful fixed-form field.
- Keep a multi-line phrase together when splitting would destroy meaning.
- Do not draw one box per character or word unless a later specialist protocol requires it.
- For relational tables, prefer one parent table region plus structured cells rather than one rectangle per visible cell.
- During template discovery, annotate representative static printed labels and every variable field location. After a template variant is registered, do not repeatedly box unchanged boilerplate on every sample; annotate variable content and material template drift.

For a fully printed document with no handwritten content, choose one of:

- `printed_blank_form` when it is an unfilled reusable form; mark fixed labels and empty variable field locations.
- `printed_filled_form` / printed form with typed values when machine-printed values fill a form; mark fixed anchors and variable values, using Table where a relational grid is the natural unit.
- `printed_document` when the page is not a fillable form; mark meaningful printed blocks or structured tables in reading order.

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
| `other_region` | Meaningful non-standard region; also used as the parent label for structured tables |

The separate structure-role control preserves structure independently of region content type. Important roles include:

- `form_field`
- `free_text_block`
- `table`
- `table_header`
- `table_cell`
- `chart_axis_or_label`

The hosted Table tool creates a parent `other_region` with `structure_role: "table"` and structured `table_data`.

## Table annotation

Use Table for reports such as CBC/haematology/biochemistry grids or other repeated row/column reports.

1. Press `T` or select **Table**.
2. Draw one rectangle around the complete visible grid.
3. Set row and column count.
4. Mark whether a header row exists.
5. Set each non-header column's default content type:
   - Fixed;
   - Variable;
   - Writing.
6. Enter values into the spreadsheet-style editor.

Typical investigation pattern:

| Column | Typical class |
|---|---|
| Test name | Fixed |
| Result | Variable |
| Unit | Fixed |
| Reference range | Fixed |

Table-editor keys:

- `Tab`: next cell;
- `Enter`: cell below;
- `Shift+Enter`: newline inside cell;
- paste tab/newline-separated spreadsheet content to fill a block.

Do not duplicate the entire table into the parent region transcription field.

## Legibility

- `legible`: confidently visible without reconstruction.
- `partially_legible`: some exact characters visible; transcribe only those and use `[?]` for a local unresolved fragment.
- `illegible`: no defensible transcription; leave transcription blank.
- `not_applicable`: non-text content such as signature/tracing/table parent region.

Never replace unreadable content with a medically plausible guess.

## Exact text and line breaks

Normal text transcription is multiline. Preserve visible line breaks when they carry structure. Do not rewrite the source into cleaner prose.

Examples of prohibited normalization:

- changing `07.50` to `7.5`;
- changing a misspelled patient name;
- converting a date format;
- expanding an abbreviation;
- filling an unreadable fragment from clinical context.

## Quality flags

Use all that apply: blur, rotation, skew, perspective distortion, crop loss, glare/shadow, low contrast, compression artifact, obstruction, or other. Use `clear` only when none materially affect reading.

## Privacy

The annotation system necessarily displays clinical information. Do not copy it into tickets, chat, GitHub, screenshots, test fixtures, or developer logs. Use synthetic examples when reporting software defects.
