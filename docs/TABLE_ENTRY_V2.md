# DCAL Table Entry v2

The hosted workbench supports a table as one annotated parent region with `structure_role: "table"` and an optional structured `table_data` payload.

## Why

Hospital investigation reports and charts are relational. Flattening an entire table into one text string loses row/column meaning, while drawing and transcribing every cell as an independent rectangle is too slow for the initial human annotation workflow.

## Region shape

```json
{
  "label": "other_region",
  "structure_role": "table",
  "legibility": "not_applicable",
  "field_code": "cbc_results",
  "table_data": {
    "rows": 3,
    "columns": 4,
    "header_rows": 1,
    "column_labels": [
      "printed_static",
      "printed_variable",
      "printed_static",
      "printed_static"
    ],
    "cells": [
      ["Test", "Result", "Unit", "Reference"],
      ["White Blood Cells", "07.50", "10^9/L", "4.00 - 11.00"],
      ["Haemoglobin", "13.40", "g/dL", "13 - 18"]
    ]
  }
}
```

`column_labels` describe the default content class for non-header cells in that column. Header rows are treated as printed static content by the workbench.

## Workbench interaction

1. Choose **Table** or press `T`.
2. Draw one box around the complete visible table.
3. Set the row and column count.
4. Enter values in the spreadsheet-style editor.
5. `Tab` moves across cells.
6. `Enter` moves to the cell below.
7. `Shift+Enter` inserts a line break inside a cell.
8. Pasting tab/newline-separated text fills a block of cells and expands the grid within configured limits.

The table payload is additive to `dcal.annotation.v2`; existing non-table annotations remain valid and unchanged.

## Navigation changes

- Two-finger wheel/trackpad movement pans the page instead of always zooming.
- Pinch or Ctrl/Cmd + wheel zooms around the pointer position.
- **Pan** / `P` provides explicit drag-to-pan mode.
- `Space` + drag and middle-button pan continue to work.
- The selected-region editor is moved to the top of the independently scrolling inspector.
- Standard text transcription remains multiline and preserves line breaks.
