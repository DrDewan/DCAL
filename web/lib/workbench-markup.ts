export function workbenchMarkup(canExport: boolean) {
  const exportLink = canExport
    ? '<a class="nav-button" href="/api/export/gold.jsonl" download>Export gold</a>'
    : "";
  return `
    <header class="app-header">
      <button class="brand" id="home-button" type="button" aria-label="Open annotation queue">
        <span class="brand-mark" aria-hidden="true"><span></span><span></span><span></span></span>
        <span><strong>DCAL</strong><small>Annotation workbench</small></span>
      </button>
      <nav class="header-nav" aria-label="Primary navigation">
        <button class="nav-button active" id="queue-nav" type="button">Queue</button>
        ${exportLink}
      </nav>
      <div class="member-actions">
        <span class="identity-chip"><span class="identity-dot" aria-hidden="true"></span><span id="identity-label">Loading…</span></span>
        <form action="/auth/signout" method="post"><button class="signout-button" type="submit">Sign out</button></form>
      </div>
    </header>

    <main>
      <section id="queue-view" class="queue-view">
        <div class="queue-hero">
          <div>
            <p class="eyebrow">Dataset operations</p>
            <h1>Turn pages into trustworthy training data.</h1>
            <p class="hero-copy">Identify the physical document, mark what matters, and transcribe exactly what is visible.</p>
          </div>
          <button class="primary-button upload-trigger" type="button">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4h14v-4"/></svg>
            Upload pages
          </button>
        </div>

        <div class="metrics-grid" id="metrics-grid" aria-label="Annotation progress">
          <article class="metric-card"><span>All pages</span><strong id="metric-total">—</strong><small>in this workspace</small></article>
          <article class="metric-card accent-a"><span>Ready to start</span><strong id="metric-unassigned">—</strong><small>unassigned</small></article>
          <article class="metric-card accent-b"><span>In progress</span><strong id="metric-progress">—</strong><small>drafts saved</small></article>
          <article class="metric-card accent-c"><span>Completed</span><strong id="metric-completed">—</strong><small>human annotated</small></article>
          <article class="metric-card"><span>Dataset-ready</span><strong id="metric-eligible">—</strong><small>Drive provenance</small></article>
        </div>

        <section class="upload-panel" id="upload-panel" aria-labelledby="upload-title">
          <div class="upload-dropzone" id="upload-dropzone">
            <input id="file-input" type="file" multiple accept="image/jpeg,image/png,image/webp">
            <div class="upload-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4h14v-4"/></svg>
            </div>
            <div><h2 id="upload-title">Drop page images here</h2><p>JPEG, PNG, or WebP. Browser uploads are pilot-only and are resized locally when needed. Put source images and PDFs in the separate DCAL Google Drive for dataset-ready ingestion.</p></div>
            <button class="secondary-button upload-trigger" type="button">Choose images</button>
          </div>
          <div class="upload-progress hidden" id="upload-progress" role="status">
            <span class="spinner" aria-hidden="true"></span><span id="upload-progress-text">Preparing pages…</span>
          </div>
        </section>

        <section class="queue-panel" aria-labelledby="queue-title">
          <div class="panel-heading">
            <div><p class="eyebrow">Work queue</p><h2 id="queue-title">Document pages</h2></div>
            <div class="queue-filters">
              <label class="search-field"><span class="sr-only">Search queue</span><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg><input id="queue-search" type="search" placeholder="Search page ID or annotator"></label>
              <label><span class="sr-only">Filter by status</span><select id="status-filter"><option value="">All statuses</option><option value="unassigned">Ready to start</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="needs_review">Needs review</option></select></label>
              <label><span class="sr-only">Filter by document type</span><select id="type-filter"><option value="">All document types</option></select></label>
            </div>
          </div>
          <div class="queue-table-wrap">
            <table class="queue-table">
              <thead><tr><th>Page</th><th>Document</th><th>Content</th><th>Regions</th><th>Provenance</th><th>Status</th><th></th></tr></thead>
              <tbody id="queue-body"></tbody>
            </table>
            <div class="empty-state hidden" id="empty-state"><span aria-hidden="true">□</span><h3>No pages match this view</h3><p>Change the filters or upload a pilot page image.</p></div>
          </div>
        </section>
      </section>

      <section id="annotator-view" class="annotator-view hidden" aria-label="Page annotation workspace">
        <div class="annotation-topbar">
          <button class="icon-text-button" id="back-button" type="button"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>Queue</button>
          <div class="task-heading"><strong id="task-title">Page</strong><span class="status-pill" id="task-status">Ready</span><span class="provenance-pill" id="task-provenance">Pilot upload</span></div>
          <div class="annotation-actions"><span class="save-state" id="save-state">Saved</span><button class="secondary-button" id="save-button" type="button">Save draft</button><button class="primary-button" id="complete-button" type="button">Complete page</button></div>
        </div>

        <div class="annotation-layout">
          <aside class="tool-rail" aria-label="Annotation tools">
            <button class="tool-button active" type="button" data-tool="select" title="Select and move (V)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 3 13 9-6 1 3 6-2 1-3-6-5 4Z"/></svg><span>Select</span></button>
            <div class="tool-separator"></div>
            <button class="tool-button static" type="button" data-tool="printed_static" title="Fixed printed text (F)"><span class="tool-swatch"></span><span>Fixed</span></button>
            <button class="tool-button variable" type="button" data-tool="printed_variable" title="Variable printed text (D)"><span class="tool-swatch"></span><span>Variable</span></button>
            <button class="tool-button handwriting" type="button" data-tool="handwriting" title="Handwriting (H)"><span class="tool-swatch"></span><span>Writing</span></button>
            <button class="tool-button choice" type="button" data-tool="checkbox_mark" title="Checkbox or choice (C)"><span class="tool-swatch"></span><span>Choice</span></button>
            <button class="tool-button other" type="button" data-tool="other_region" title="Table, grid, or other region (G)"><span class="tool-swatch"></span><span>Grid</span></button>
            <div class="tool-separator"></div>
            <button class="tool-button" id="fit-button" type="button" title="Fit page"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5m13-5h5v5M8 21H3v-5m13 5h5v-5"/></svg><span>Fit</span></button>
          </aside>

          <div class="canvas-column">
            <div class="canvas-toolbar">
              <p id="canvas-hint">Draw a box around a field or text area.</p>
              <div class="zoom-controls"><button id="zoom-out" type="button" aria-label="Zoom out">−</button><output id="zoom-label">Fit</output><button id="zoom-in" type="button" aria-label="Zoom in">+</button></div>
            </div>
            <div class="canvas-stage" id="canvas-stage">
              <canvas id="annotation-canvas" tabindex="0" aria-label="Document image annotation canvas"></canvas>
              <div class="canvas-loading" id="canvas-loading"><span class="spinner"></span><span>Loading page…</span></div>
            </div>
            <div class="keyboard-strip"><span><kbd>F</kbd> fixed</span><span><kbd>D</kbd> variable</span><span><kbd>V</kbd> select</span><span><kbd>Del</kbd> delete</span><span><kbd>Ctrl S</kbd> save</span><span>Hold <kbd>Space</kbd> to pan</span></div>
          </div>

          <aside class="inspector" aria-label="Annotation details">
            <section class="inspector-section">
              <div class="section-heading"><p class="eyebrow">Page identity</p><span id="identity-complete" class="completion-dot" title="Required fields incomplete"></span></div>
              <label class="field-label">Physical document type<select id="document-type"><option value="">Select document type…</option></select></label>
              <label class="field-label">Template variant<select id="document-variant"><option value="">No confirmed variant</option></select></label>
              <label class="field-label">Page content<select id="content-profile"><option value="">Select content profile…</option></select></label>
            </section>

            <section class="inspector-section">
              <div class="section-heading"><p class="eyebrow">Image quality</p><button class="text-button" id="clear-quality" type="button">Clear</button></div>
              <div class="chip-grid" id="quality-flags"></div>
            </section>

            <section class="inspector-section region-inspector hidden" id="region-inspector">
              <div class="section-heading"><div><p class="eyebrow">Selected region</p><h2 id="region-heading">Region</h2></div><button class="danger-icon" id="delete-region" type="button" aria-label="Delete selected region"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3m3 0-1 14H7L6 7m4 4v6m4-6v6"/></svg></button></div>
              <label class="field-label">Region type<select id="region-label"></select></label>
              <div class="two-fields"><label class="field-label">Reading order<input id="reading-order" type="number" min="1" step="1"></label><label class="field-label">Legibility<select id="legibility"></select></label></div>
              <label class="field-label">Structure<select id="structure-role"></select></label>
              <label class="field-label">Field code <span class="field-hint">lowercase_snake_case</span><input id="field-code" type="text" maxlength="100" placeholder="patient_name"></label>
              <label class="field-label">Exact visible text<textarea id="transcription" rows="5" maxlength="10000" placeholder="Type exactly what is visible. Use [?] only for an unreadable fragment."></textarea></label>
            </section>

            <section class="inspector-section">
              <div class="section-heading"><p class="eyebrow">Regions</p><span class="region-count" id="region-count">0</span></div>
              <div class="region-list" id="region-list"></div>
            </section>

            <section class="inspector-section">
              <div class="section-heading"><p class="eyebrow">Writer</p><span class="field-hint">optional</span></div>
              <p class="input-help">Record who signed the page, if a signature is visible and legible. Leave empty otherwise.</p>
              <div class="writer-chips" id="writer-chips"></div>
              <label class="field-label">Name as signed
                <input id="writer-input" type="text" maxlength="120" list="writer-options" placeholder="Start typing or add a new writer" autocomplete="off">
              </label>
              <datalist id="writer-options"></datalist>
              <button class="secondary-button" id="writer-add" type="button">Add writer</button>
            </section>

            <section class="inspector-section">
              <label class="field-label">Page notes<textarea id="page-notes" rows="3" maxlength="4000" placeholder="Layout uncertainty or quality explanation. Never infer clinical content."></textarea></label>
            </section>
          </aside>
        </div>
      </section>
    </main>

    <div class="toast-stack" id="toast-stack" aria-live="polite"></div>
  `;
}
