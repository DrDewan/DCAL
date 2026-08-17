"use strict";

(() => {
  const TABLE_STRUCTURE = "table";
  const TABLE_TOOL = "table";
  const PAN_TOOL = "pan";
  const TABLE_COLUMN_TYPES = [
    ["printed_static", "Fixed"],
    ["printed_variable", "Variable"],
    ["handwriting", "Writing"],
  ];
  let lastSelectedRegionId = null;

  function addStylesheet() {
    if (document.querySelector('link[href="/ux-v2.css"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/ux-v2.css";
    document.head.append(link);
  }

  function makeTool({ tool, label, title, icon }) {
    const button = document.createElement("button");
    button.className = `tool-button ${tool}-tool`;
    button.type = "button";
    button.dataset.tool = tool;
    button.title = title;
    button.innerHTML = `${icon}<span>${label}</span>`;
    button.addEventListener("click", () => setTool(tool));
    return button;
  }

  function upgradeToolRail() {
    const rail = document.querySelector(".tool-rail");
    if (!rail || rail.dataset.uxV2 === "1") return;
    rail.dataset.uxV2 = "1";

    const firstSeparator = rail.querySelector(".tool-separator");
    const panButton = makeTool({
      tool: PAN_TOOL,
      label: "Pan",
      title: "Pan image (P). Two-finger scroll also pans.",
      icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 11V7a2 2 0 0 1 4 0v3-5a2 2 0 0 1 4 0v5-3a2 2 0 0 1 4 0v7c0 4-3 7-7 7h-1c-3 0-5-1-7-4l-2-3a2 2 0 0 1 3-2l2 2"/></svg>',
    });
    rail.insertBefore(panButton, firstSeparator);

    const gridButton = rail.querySelector('[data-tool="other_region"]');
    const tableButton = makeTool({
      tool: TABLE_TOOL,
      label: "Table",
      title: "Draw a table / investigation grid (T)",
      icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 9h18M3 14h18M9 4v16M15 4v16"/></svg>',
    });
    if (gridButton) {
      gridButton.querySelector("span:last-child").textContent = "Other";
      gridButton.title = "Other meaningful region (G)";
      rail.insertBefore(tableButton, gridButton);
    } else {
      rail.append(tableButton);
    }

    const keyboardStrip = document.querySelector(".keyboard-strip");
    if (keyboardStrip) {
      const tableKey = document.createElement("span");
      tableKey.innerHTML = "<kbd>T</kbd> table";
      const panKey = document.createElement("span");
      panKey.innerHTML = "<kbd>P</kbd> pan";
      keyboardStrip.prepend(panKey, tableKey);
    }
  }

  function upgradeInspectorOrder() {
    const inspector = document.querySelector(".inspector");
    const regionSection = document.querySelector("#region-inspector");
    if (!inspector || !regionSection || inspector.dataset.uxV2 === "1") return;
    inspector.dataset.uxV2 = "1";
    inspector.prepend(regionSection);
    regionSection.classList.add("priority-region");

    const pageSections = [...inspector.querySelectorAll(":scope > .inspector-section")];
    pageSections.forEach((section) => {
      if (section !== regionSection) section.classList.add("compact-inspector-section");
    });

    const transcription = document.querySelector("#transcription");
    const transcriptionLabel = transcription?.closest("label");
    if (transcriptionLabel && !document.querySelector("#multiline-hint")) {
      const hint = document.createElement("span");
      hint.id = "multiline-hint";
      hint.className = "input-help";
      hint.textContent = "Line breaks are preserved. Press Enter for a new line.";
      transcriptionLabel.append(hint);
      transcription.rows = 7;
      transcription.placeholder = "Type exactly what is visible. Keep the visible line breaks.";
      transcription.addEventListener("input", () => autoGrow(transcription));
    }
  }

  function createTableEditor() {
    const regionSection = document.querySelector("#region-inspector");
    if (!regionSection || document.querySelector("#table-editor")) return;
    const editor = document.createElement("div");
    editor.id = "table-editor";
    editor.className = "table-editor hidden";
    editor.innerHTML = `
      <div class="table-editor-heading">
        <div>
          <strong>Table values</strong>
          <small>Spreadsheet entry for investigation tables and charts</small>
        </div>
        <span class="table-badge">TABLE</span>
      </div>
      <div class="table-size-row">
        <label>Rows<input id="table-rows" type="number" min="1" max="100" step="1"></label>
        <label>Columns<input id="table-columns" type="number" min="1" max="12" step="1"></label>
        <label class="header-toggle"><input id="table-header-row" type="checkbox"><span>Header row</span></label>
      </div>
      <div class="table-action-row" aria-label="Table dimensions">
        <button type="button" data-table-action="add-row">+ Row</button>
        <button type="button" data-table-action="remove-row">− Row</button>
        <button type="button" data-table-action="add-column">+ Column</button>
        <button type="button" data-table-action="remove-column">− Column</button>
      </div>
      <div class="table-column-types" id="table-column-types"></div>
      <div class="table-grid-scroller">
        <div class="table-entry-grid" id="table-entry-grid"></div>
      </div>
      <p class="table-key-help"><kbd>Tab</kbd> next cell · <kbd>Enter</kbd> cell below · <kbd>Shift</kbd>+<kbd>Enter</kbd> new line · paste spreadsheet rows directly</p>
    `;
    const heading = regionSection.querySelector(".section-heading");
    heading.after(editor);

    editor.querySelector("#table-rows").addEventListener("change", (event) => {
      resizeSelectedTable(Number.parseInt(event.target.value, 10), null);
    });
    editor.querySelector("#table-columns").addEventListener("change", (event) => {
      resizeSelectedTable(null, Number.parseInt(event.target.value, 10));
    });
    editor.querySelector("#table-header-row").addEventListener("change", (event) => {
      const region = selectedRegion();
      if (!isTableRegion(region)) return;
      ensureTableData(region).header_rows = event.target.checked ? 1 : 0;
      markDirty();
      renderTableEditor(region);
    });
    editor.querySelectorAll("[data-table-action]").forEach((button) => {
      button.addEventListener("click", () => changeTableSize(button.dataset.tableAction));
    });
  }

  function defaultColumnLabels(columns) {
    if (columns <= 1) return ["printed_variable"];
    const values = ["printed_static", "printed_variable"];
    while (values.length < columns) values.push(values.length <= 3 ? "printed_static" : "printed_variable");
    return values.slice(0, columns);
  }

  function blankCells(rows, columns) {
    return Array.from({ length: rows }, () => Array.from({ length: columns }, () => ""));
  }

  function makeTableData(rows = 8, columns = 4) {
    return {
      rows,
      columns,
      header_rows: 1,
      column_labels: defaultColumnLabels(columns),
      cells: blankCells(rows, columns),
    };
  }

  function isTableRegion(region) {
    return Boolean(region && region.structure_role === TABLE_STRUCTURE);
  }

  function ensureTableData(region) {
    if (!region.table_data || typeof region.table_data !== "object") {
      region.table_data = makeTableData();
    }
    const data = region.table_data;
    const rows = clampInt(data.rows, 1, 100, 8);
    const columns = clampInt(data.columns, 1, 12, 4);
    data.rows = rows;
    data.columns = columns;
    data.header_rows = clampInt(data.header_rows, 0, rows, 1);
    data.column_labels = Array.isArray(data.column_labels) ? data.column_labels.slice(0, columns) : [];
    while (data.column_labels.length < columns) {
      data.column_labels.push(defaultColumnLabels(columns)[data.column_labels.length]);
    }
    data.cells = Array.isArray(data.cells) ? data.cells.slice(0, rows) : [];
    while (data.cells.length < rows) data.cells.push([]);
    data.cells = data.cells.map((row) => {
      const next = Array.isArray(row) ? row.slice(0, columns) : [];
      while (next.length < columns) next.push("");
      return next.map((value) => typeof value === "string" ? value : "");
    });
    return data;
  }

  function clampInt(value, min, max, fallback) {
    if (!Number.isFinite(value)) return fallback;
    return Math.max(min, Math.min(max, Math.trunc(value)));
  }

  function resizeTableData(data, rows, columns) {
    rows = clampInt(rows, 1, 100, data.rows || 8);
    columns = clampInt(columns, 1, 12, data.columns || 4);
    const oldCells = data.cells || [];
    const cells = blankCells(rows, columns);
    for (let r = 0; r < Math.min(rows, oldCells.length); r += 1) {
      for (let c = 0; c < Math.min(columns, oldCells[r]?.length || 0); c += 1) {
        cells[r][c] = oldCells[r][c] || "";
      }
    }
    const oldLabels = Array.isArray(data.column_labels) ? data.column_labels : [];
    const defaults = defaultColumnLabels(columns);
    data.rows = rows;
    data.columns = columns;
    data.header_rows = Math.min(data.header_rows || 0, rows);
    data.column_labels = Array.from({ length: columns }, (_, index) => oldLabels[index] || defaults[index]);
    data.cells = cells;
  }

  function resizeSelectedTable(rows, columns) {
    const region = selectedRegion();
    if (!isTableRegion(region)) return;
    const data = ensureTableData(region);
    resizeTableData(data, rows ?? data.rows, columns ?? data.columns);
    markDirty();
    renderTableEditor(region);
  }

  function changeTableSize(action) {
    const region = selectedRegion();
    if (!isTableRegion(region)) return;
    const data = ensureTableData(region);
    const changes = {
      "add-row": [data.rows + 1, data.columns],
      "remove-row": [Math.max(1, data.rows - 1), data.columns],
      "add-column": [data.rows, data.columns + 1],
      "remove-column": [data.rows, Math.max(1, data.columns - 1)],
    };
    const next = changes[action];
    if (next) resizeSelectedTable(next[0], next[1]);
  }

  function renderColumnTypes(data) {
    const root = document.querySelector("#table-column-types");
    if (!root) return;
    root.replaceChildren();
    root.style.gridTemplateColumns = `repeat(${data.columns}, minmax(92px, 1fr))`;
    data.column_labels.forEach((value, columnIndex) => {
      const label = document.createElement("label");
      label.className = "table-column-kind";
      const caption = document.createElement("span");
      caption.textContent = `Col ${columnIndex + 1}`;
      const select = document.createElement("select");
      TABLE_COLUMN_TYPES.forEach(([code, name]) => {
        const option = document.createElement("option");
        option.value = code;
        option.textContent = name;
        select.append(option);
      });
      select.value = value;
      select.addEventListener("change", () => {
        const region = selectedRegion();
        if (!isTableRegion(region)) return;
        ensureTableData(region).column_labels[columnIndex] = select.value;
        markDirty();
      });
      label.append(caption, select);
      root.append(label);
    });
  }

  function autoGrow(textarea) {
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(160, Math.max(34, textarea.scrollHeight))}px`;
  }

  function focusTableCell(row, column) {
    const cell = document.querySelector(`.table-cell-input[data-row="${row}"][data-column="${column}"]`);
    if (cell) {
      cell.focus({ preventScroll: true });
      cell.select();
      cell.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  }

  function updateTableCell(row, column, value) {
    const region = selectedRegion();
    if (!isTableRegion(region)) return;
    const data = ensureTableData(region);
    if (!data.cells[row] || column >= data.columns) return;
    data.cells[row][column] = value;
    markDirty();
  }

  function pasteTableBlock(event, startRow, startColumn) {
    const text = event.clipboardData?.getData("text/plain") || "";
    if (!text.includes("\t") && !/[\r\n]/.test(text.trimEnd())) return false;
    event.preventDefault();
    const rows = text.replace(/\r\n?/g, "\n").replace(/\n$/, "").split("\n").map((line) => line.split("\t"));
    const region = selectedRegion();
    if (!isTableRegion(region)) return true;
    const data = ensureTableData(region);
    const requiredRows = Math.min(100, Math.max(data.rows, startRow + rows.length));
    const requiredColumns = Math.min(12, Math.max(data.columns, startColumn + Math.max(...rows.map((row) => row.length))));
    if (requiredRows !== data.rows || requiredColumns !== data.columns) resizeTableData(data, requiredRows, requiredColumns);
    rows.forEach((row, rowOffset) => row.forEach((value, columnOffset) => {
      const r = startRow + rowOffset;
      const c = startColumn + columnOffset;
      if (r < data.rows && c < data.columns) data.cells[r][c] = value;
    }));
    markDirty();
    renderTableEditor(region);
    requestAnimationFrame(() => focusTableCell(startRow, startColumn));
    return true;
  }

  function renderTableGrid(data) {
    const root = document.querySelector("#table-entry-grid");
    if (!root) return;
    root.replaceChildren();
    root.style.gridTemplateColumns = `32px repeat(${data.columns}, minmax(108px, 1fr))`;

    const corner = document.createElement("div");
    corner.className = "table-grid-corner";
    root.append(corner);
    for (let column = 0; column < data.columns; column += 1) {
      const head = document.createElement("div");
      head.className = "table-grid-column-number";
      head.textContent = `${column + 1}`;
      root.append(head);
    }

    for (let row = 0; row < data.rows; row += 1) {
      const rowNumber = document.createElement("div");
      rowNumber.className = "table-grid-row-number";
      rowNumber.textContent = `${row + 1}`;
      root.append(rowNumber);
      for (let column = 0; column < data.columns; column += 1) {
        const textarea = document.createElement("textarea");
        textarea.className = "table-cell-input";
        textarea.rows = 1;
        textarea.dataset.row = `${row}`;
        textarea.dataset.column = `${column}`;
        textarea.value = data.cells[row][column] || "";
        textarea.placeholder = row < data.header_rows ? "Header" : "…";
        textarea.classList.toggle("header-cell", row < data.header_rows);
        textarea.dataset.contentType = row < data.header_rows ? "printed_static" : data.column_labels[column];
        textarea.addEventListener("input", () => {
          updateTableCell(row, column, textarea.value);
          autoGrow(textarea);
        });
        textarea.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            const nextRow = Math.min(data.rows - 1, row + 1);
            focusTableCell(nextRow, column);
          }
        });
        textarea.addEventListener("paste", (event) => pasteTableBlock(event, row, column));
        root.append(textarea);
        requestAnimationFrame(() => autoGrow(textarea));
      }
    }
  }

  function renderTableEditor(region) {
    const editor = document.querySelector("#table-editor");
    const inspector = document.querySelector("#region-inspector");
    if (!editor || !inspector) return;
    const tableMode = isTableRegion(region);
    editor.classList.toggle("hidden", !tableMode);
    inspector.classList.toggle("table-mode", tableMode);
    if (!tableMode) return;

    const data = ensureTableData(region);
    document.querySelector("#table-rows").value = `${data.rows}`;
    document.querySelector("#table-columns").value = `${data.columns}`;
    document.querySelector("#table-header-row").checked = data.header_rows > 0;
    renderColumnTypes(data);
    renderTableGrid(data);
  }

  function installFunctionEnhancements() {
    const baseSetTool = setTool;
    setTool = function enhancedSetTool(tool) {
      if (![PAN_TOOL, TABLE_TOOL].includes(tool)) {
        baseSetTool(tool);
        canvas.classList.remove("pan-mode");
        return;
      }
      state.tool = tool;
      document.querySelectorAll(".tool-button[data-tool]").forEach((button) => {
        button.classList.toggle("active", button.dataset.tool === tool);
      });
      canvas.classList.toggle("select-mode", false);
      canvas.classList.toggle("pan-mode", tool === PAN_TOOL);
      document.querySelector("#canvas-hint").textContent = tool === PAN_TOOL
        ? "Drag the page to move it. Two-finger scroll pans; pinch zooms."
        : "Draw one box around the whole table. Then enter values in the grid on the right.";
    };

    const basePercentRegion = percentRegion;
    percentRegion = function enhancedPercentRegion(start, end, label) {
      if (label !== TABLE_TOOL) return basePercentRegion(start, end, label);
      const region = basePercentRegion(start, end, "other_region");
      region.structure_role = TABLE_STRUCTURE;
      region.legibility = "not_applicable";
      region.table_data = makeTableData();
      return region;
    };

    const baseRenderInspector = renderInspector;
    renderInspector = function enhancedRenderInspector() {
      baseRenderInspector();
      const region = selectedRegion();
      renderTableEditor(region);
      const inspector = document.querySelector(".inspector");
      if (region?.id !== lastSelectedRegionId) {
        lastSelectedRegionId = region?.id || null;
        if (region && inspector) requestAnimationFrame(() => inspector.scrollTo({ top: 0, behavior: "smooth" }));
      }
      const transcription = document.querySelector("#transcription");
      if (transcription && !transcription.disabled) requestAnimationFrame(() => autoGrow(transcription));
    };
  }

  function installPanAndZoom() {
    canvas.addEventListener("pointerdown", (event) => {
      if (!state.image || !state.task || state.tool !== PAN_TOOL || ![0, 1, 2].includes(event.button)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      canvas.setPointerCapture(event.pointerId);
      const point = canvasPoint(event);
      state.pointer = { mode: "pan", start: point, panX: state.panX, panY: state.panY };
      canvas.classList.add("panning");
    }, true);

    canvas.addEventListener("contextmenu", (event) => {
      if (state.tool === PAN_TOOL) event.preventDefault();
    });

    canvas.addEventListener("wheel", (event) => {
      if (!state.image || !state.task) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const point = canvasPoint(event);
      if (event.ctrlKey || event.metaKey) {
        calculateView();
        const imageX = (point.x - view.offsetX) / view.scale;
        const imageY = (point.y - view.offsetY) / view.scale;
        const factor = Math.exp(-event.deltaY * 0.006);
        const nextZoom = Math.max(.35, Math.min(6, state.zoom * factor));
        const nextScale = view.fitScale * nextZoom;
        const baseX = (view.width - state.image.naturalWidth * nextScale) / 2;
        const baseY = (view.height - state.image.naturalHeight * nextScale) / 2;
        state.zoom = nextZoom;
        state.panX = point.x - baseX - imageX * nextScale;
        state.panY = point.y - baseY - imageY * nextScale;
        document.querySelector("#zoom-label").textContent = state.zoom === 1 ? "Fit" : `${Math.round(state.zoom * 100)}%`;
      } else {
        const horizontal = event.shiftKey && Math.abs(event.deltaX) < 1 ? event.deltaY : event.deltaX;
        const vertical = event.shiftKey && Math.abs(event.deltaX) < 1 ? 0 : event.deltaY;
        state.panX -= horizontal;
        state.panY -= vertical;
      }
      renderCanvas();
    }, { capture: true, passive: false });

    window.addEventListener("keydown", (event) => {
      const editing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
      if (editing || !state.task) return;
      if (event.key.toLowerCase() === "p") setTool(PAN_TOOL);
      if (event.key.toLowerCase() === "t") setTool(TABLE_TOOL);
    });
  }

  function installInspectorWheelIsolation() {
    const inspector = document.querySelector(".inspector");
    if (!inspector) return;
    inspector.addEventListener("wheel", (event) => {
      event.stopPropagation();
    }, { passive: true });
  }

  function boot() {
    addStylesheet();
    upgradeToolRail();
    upgradeInspectorOrder();
    createTableEditor();
    installFunctionEnhancements();
    installPanAndZoom();
    installInspectorWheelIsolation();
    if (state.task) renderInspector();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
