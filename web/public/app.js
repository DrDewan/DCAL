"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const labelNames = new Map();
const regionColors = {
  printed_static: "#267a5c",
  printed_variable: "#147f91",
  handwriting: "#356eb5",
  checkbox_mark: "#bd7814",
  stamp_or_seal: "#d96843",
  signature: "#8b5ca8",
  drawing_or_tracing: "#705245",
  other_region: "#7657a5",
};

const state = {
  taxonomy: null,
  writers: [],
  queue: null,
  task: null,
  member: null,
  selectedRegionId: null,
  tool: "select",
  dirty: false,
  editSequence: 0,
  saving: false,
  saveTimer: null,
  image: null,
  zoom: 1,
  panX: 0,
  panY: 0,
  spaceHeld: false,
  pointer: null,
};

function apiError(payload, fallback) {
  return payload && payload.error && payload.error.message ? payload.error.message : fallback;
}

async function api(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  const payload = response.headers.get("content-type")?.includes("application/json")
    ? await response.json()
    : null;
  if (response.status === 401) {
    location.assign("/login");
    throw new Error("Your session expired. Sign in again.");
  }
  if (response.status === 403 && payload?.error?.code === "membership_inactive") {
    location.assign("/pending");
    throw new Error("This account is awaiting activation.");
  }
  if (!response.ok) throw new Error(apiError(payload, `Request failed (${response.status})`));
  return payload;
}

function toast(message, kind = "success") {
  const item = document.createElement("div");
  item.className = `toast ${kind}`;
  item.textContent = message;
  $("#toast-stack").append(item);
  setTimeout(() => item.remove(), 4200);
}

function option(select, value, name) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = name;
  select.append(item);
}

function populateOptions(select, items, placeholder = null) {
  select.replaceChildren();
  if (placeholder !== null) option(select, "", placeholder);
  items.forEach((item) => option(select, item.code, item.name));
}

function formatStatus(status) {
  return { unassigned: "Ready", in_progress: "In progress", completed: "Completed", needs_review: "Needs review" }[status] || status;
}

function formatUpdated(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "—";
  const seconds = Math.max(0, Math.round((Date.now() - date.valueOf()) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function fillTaxonomy() {
  const typeItems = state.taxonomy.physical_document_types;
  populateOptions($("#type-filter"), typeItems, "All document types");
  populateOptions($("#document-type"), typeItems, "Select document type…");
  populateOptions($("#content-profile"), state.taxonomy.content_profiles, "Select content profile…");
  populateOptions($("#region-label"), state.taxonomy.region_labels);
  populateOptions($("#legibility"), state.taxonomy.legibility_states);
  populateOptions($("#structure-role"), state.taxonomy.structure_roles);
  [
    ...state.taxonomy.physical_document_types,
    ...state.taxonomy.physical_document_variants,
    ...state.taxonomy.region_labels,
    ...state.taxonomy.legibility_states,
    ...state.taxonomy.structure_roles,
    ...state.taxonomy.content_profiles,
  ].forEach((item) => labelNames.set(item.code, item.name));
  renderQualityFlags();
}

function renderQualityFlags() {
  const root = $("#quality-flags");
  root.replaceChildren();
  state.taxonomy.image_quality_flags.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quality-chip";
    button.dataset.value = item.code;
    button.textContent = item.name;
    button.addEventListener("click", () => toggleQuality(item.code));
    root.append(button);
  });
}

async function loadQueue() {
  const params = new URLSearchParams();
  if ($("#status-filter").value) params.set("status", $("#status-filter").value);
  if ($("#type-filter").value) params.set("document_type", $("#type-filter").value);
  if ($("#queue-search").value.trim()) params.set("q", $("#queue-search").value.trim());
  state.queue = await api(`/api/tasks?${params}`);
  renderMetrics();
  renderQueue();
}

function renderMetrics() {
  const counts = state.queue.counts;
  $("#metric-total").textContent = state.queue.total;
  $("#metric-unassigned").textContent = counts.unassigned || 0;
  $("#metric-progress").textContent = counts.in_progress || 0;
  $("#metric-completed").textContent = counts.completed || 0;
  $("#metric-eligible").textContent = state.queue.dataset_eligible;
}

function td(text, className = "") {
  const cell = document.createElement("td");
  cell.className = className;
  cell.textContent = text;
  return cell;
}

function renderQueue() {
  const body = $("#queue-body");
  body.replaceChildren();
  $("#empty-state").classList.toggle("hidden", state.queue.tasks.length > 0);
  state.queue.tasks.forEach((task) => {
    const row = document.createElement("tr");
    const pageCell = document.createElement("td");
    pageCell.className = "page-cell";
    const thumb = document.createElement("span");
    thumb.className = "page-thumb";
    const copy = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = task.id;
    const small = document.createElement("small");
    small.className = "muted";
    small.textContent = formatUpdated(task.updated_at);
    copy.append(strong, document.createElement("br"), small);
    pageCell.append(thumb, copy);
    row.append(pageCell);
    row.append(td(labelNames.get(task.document_type) || "Not identified", task.document_type ? "" : "muted"));
    row.append(td(labelNames.get(task.content_profile) || "Not set", task.content_profile ? "" : "muted"));
    const countCell = document.createElement("td");
    const count = document.createElement("span");
    count.className = "count-badge";
    count.textContent = task.region_count;
    countCell.append(count);
    row.append(countCell);
    const sourceCell = document.createElement("td");
    const source = document.createElement("span");
    source.className = `source-tag ${task.dataset_eligible ? "ready" : "pilot"}`;
    source.textContent = task.dataset_eligible ? "Dataset-ready" : "Pilot upload";
    sourceCell.append(source);
    row.append(sourceCell);
    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = `status-tag ${task.status}`;
    status.textContent = formatStatus(task.status);
    statusCell.append(status);
    row.append(statusCell);
    const actionCell = document.createElement("td");
    const button = document.createElement("button");
    button.className = "open-task";
    button.type = "button";
    button.textContent = task.status === "unassigned" ? "Start →" : "Open →";
    button.addEventListener("click", () => openTask(task.id));
    actionCell.append(button);
    row.append(actionCell);
    body.append(row);
  });
}

function imageBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => canvas.toBlob(
    (blob) => blob ? resolve(blob) : reject(new Error("The image could not be prepared.")),
    type,
    quality,
  ));
}

async function prepareUpload(file) {
  const accepted = new Set(["image/jpeg", "image/png", "image/webp"]);
  if (!accepted.has(file.type)) throw new Error("Use a JPEG, PNG, or WebP page image. Put PDFs in the DCAL Google Drive.");
  if (file.size <= 3.7 * 1024 * 1024) return file;
  if (!("createImageBitmap" in window)) throw new Error("This image is too large for browser upload. Put it in the DCAL Google Drive.");
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    let scale = Math.min(1, 3000 / Math.max(bitmap.width, bitmap.height));
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      const context = canvas.getContext("2d", { alpha: false });
      context.fillStyle = "#fff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      const blob = await imageBlob(canvas, "image/webp", Math.max(.82, .95 - attempt * .025));
      if (blob.size <= 3.7 * 1024 * 1024) {
        return new File([blob], "page.webp", { type: "image/webp" });
      }
      scale *= .82;
    }
  } finally {
    bitmap.close();
  }
  throw new Error("This image is too large for browser upload. Put it in the DCAL Google Drive.");
}

async function uploadFiles(fileList) {
  const files = [...fileList].slice(0, 10);
  if (!files.length) return;
  $("#upload-progress").classList.remove("hidden");
  $("#upload-progress-text").textContent = `Preparing ${files.length} page${files.length === 1 ? "" : "s"}…`;
  try {
    const tasks = [];
    for (let index = 0; index < files.length; index += 1) {
      $("#upload-progress-text").textContent = `Uploading page ${index + 1} of ${files.length}…`;
      const form = new FormData();
      form.append("files", await prepareUpload(files[index]));
      const result = await api("/api/uploads", { method: "POST", body: form });
      tasks.push(...result.tasks);
    }
    const created = tasks.filter((item) => item.created).length;
    const reused = tasks.length - created;
    toast(`${created} page${created === 1 ? "" : "s"} added${reused ? `; ${reused} duplicate${reused === 1 ? "" : "s"} reused` : ""}.`);
    await loadQueue();
    if (tasks.length === 1) await openTask(tasks[0].id);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    $("#upload-progress").classList.add("hidden");
    $("#file-input").value = "";
  }
}

async function loadIdentity() {
  state.member = await api("/api/me");
  $("#identity-label").textContent = state.member.display_name;
}

async function showQueue() {
  if (state.dirty) {
    try { await saveTask(); } catch (_) { return; }
  }
  $("#queue-view").classList.remove("hidden");
  $("#annotator-view").classList.add("hidden");
  $("#queue-nav").classList.add("active");
  state.task = null;
  state.image = null;
  history.replaceState(null, "", "/");
  loadQueue().catch((error) => toast(error.message, "error"));
}

async function openTask(id) {
  try {
    const task = await api(`/api/tasks/${id}`);
    state.task = task;
    state.selectedRegionId = null;
    state.dirty = false;
    state.zoom = 1;
    state.panX = 0;
    state.panY = 0;
    $("#queue-view").classList.add("hidden");
    $("#annotator-view").classList.remove("hidden");
    $("#queue-nav").classList.remove("active");
    history.replaceState(null, "", `/#${id}`);
    renderTask();
    await loadTaskImage(task.image.url);
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderTask() {
  const task = state.task;
  $("#task-title").textContent = task.id;
  $("#task-status").textContent = formatStatus(task.status);
  $("#task-provenance").textContent = task.dataset_eligible ? "Dataset-ready" : "Pilot upload";
  $("#task-provenance").className = `provenance-pill ${task.dataset_eligible ? "ready" : "pilot"}`;
  $("#document-type").value = task.annotation.document_type || "";
  renderVariantOptions();
  $("#document-variant").value = task.annotation.document_variant || "";
  $("#content-profile").value = task.annotation.content_profile || "";
  $("#page-notes").value = task.annotation.notes || "";
  renderWriters();
  $$(".quality-chip").forEach((button) => button.classList.toggle("selected", task.annotation.image_quality.includes(button.dataset.value)));
  renderInspector();
  setSaveState("saved");
  updateCompletionState();
}

function renderVariantOptions() {
  const select = $("#document-variant");
  const documentType = state.task?.annotation.document_type;
  const variants = state.taxonomy.physical_document_variants.filter((item) => item.physical_document_type === documentType);
  populateOptions(select, variants, "No confirmed variant");
  select.disabled = !variants.length;
}

function selectedRegion() {
  return state.task?.annotation.regions.find((item) => item.id === state.selectedRegionId) || null;
}

function renderInspector() {
  const region = selectedRegion();
  $("#region-inspector").classList.toggle("hidden", !region);
  if (region) {
    $("#region-heading").textContent = `Region ${region.reading_order}`;
    $("#region-label").value = region.label;
    $("#reading-order").value = region.reading_order;
    $("#legibility").value = region.legibility;
    $("#structure-role").value = region.structure_role || "none";
    $("#field-code").value = region.field_code || "";
    $("#transcription").value = region.transcription || "";
    const textual = state.taxonomy.region_labels.find((item) => item.code === region.label)?.textual;
    $("#transcription").disabled = !textual || ["illegible", "not_applicable"].includes(region.legibility);
  }
  renderRegionList();
  renderCanvas();
}

function renderRegionList() {
  const root = $("#region-list");
  const regions = [...state.task.annotation.regions].sort((a, b) => a.reading_order - b.reading_order);
  $("#region-count").textContent = regions.length;
  root.replaceChildren();
  if (!regions.length) {
    const empty = document.createElement("p");
    empty.className = "region-list-empty";
    empty.textContent = "No boxes yet. Choose Fixed or Variable, then drag on the page.";
    root.append(empty);
    return;
  }
  regions.forEach((region) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `region-list-button ${region.id === state.selectedRegionId ? "selected" : ""}`;
    const order = document.createElement("span");
    order.className = "region-order";
    order.textContent = region.reading_order;
    const copy = document.createElement("span");
    copy.className = "region-list-copy";
    const strong = document.createElement("strong");
    strong.textContent = labelNames.get(region.label) || region.label;
    const small = document.createElement("small");
    small.textContent = region.transcription || region.field_code || "No text yet";
    copy.append(strong, small);
    const swatch = document.createElement("span");
    swatch.className = "region-mini-swatch";
    swatch.style.borderColor = regionColors[region.label] || "#667";
    button.append(order, copy, swatch);
    button.addEventListener("click", () => { state.selectedRegionId = region.id; setTool("select"); renderInspector(); });
    root.append(button);
  });
}

function updateCompletionState() {
  const complete = Boolean(state.task.annotation.document_type && state.task.annotation.content_profile);
  $("#identity-complete").classList.toggle("complete", complete);
  $("#identity-complete").title = complete ? "Page identity complete" : "Document type and page content are required";
}

function setSaveState(value, message = null) {
  const element = $("#save-state");
  element.className = `save-state ${value}`;
  element.textContent = message || ({ saved: "Saved", dirty: "Unsaved changes", saving: "Saving…", error: "Save failed" }[value] || value);
}

function markDirty() {
  if (!state.task) return;
  state.dirty = true;
  state.editSequence += 1;
  setSaveState("dirty");
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(() => saveTask().catch(() => {}), 1000);
  updateCompletionState();
}

async function saveTask(status = null) {
  if (!state.task || state.saving || (!state.dirty && !status)) return state.task;
  state.saving = true;
  $("#save-button").disabled = true;
  $("#complete-button").disabled = true;
  setSaveState("saving");
  const savedSequence = state.editSequence;
  const localAnnotation = state.task.annotation;
  try {
    const task = await api(`/api/tasks/${state.task.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ annotation: state.task.annotation, expected_version: state.task.version, status }),
    });
    if (state.editSequence === savedSequence) {
      state.task = task;
      state.dirty = false;
      setSaveState("saved");
      renderTask();
    } else {
      state.task = { ...task, annotation: localAnnotation };
      state.dirty = true;
      setSaveState("dirty");
      clearTimeout(state.saveTimer);
      state.saveTimer = setTimeout(() => saveTask().catch(() => {}), 250);
    }
    return task;
  } catch (error) {
    setSaveState("error");
    toast(error.message, "error");
    throw error;
  } finally {
    state.saving = false;
    $("#save-button").disabled = false;
    $("#complete-button").disabled = false;
  }
}

async function completeTask() {
  try {
    await saveTask("completed");
    toast("Page completed and added to the reviewed set.");
    const currentIndex = state.queue?.tasks.findIndex((item) => item.id === state.task.id) ?? -1;
    await loadQueue();
    const next = state.queue.tasks.slice(Math.max(currentIndex, 0)).find((item) => item.status !== "completed");
    if (next) await openTask(next.id); else showQueue();
  } catch (_) { /* error is already shown */ }
}

function toggleQuality(code) {
  if (!state.task) return;
  const quality = state.task.annotation.image_quality;
  if (code === "clear") {
    state.task.annotation.image_quality = quality.includes("clear") ? [] : ["clear"];
  } else {
    const next = quality.filter((item) => item !== "clear");
    const index = next.indexOf(code);
    if (index >= 0) next.splice(index, 1); else next.push(code);
    state.task.annotation.image_quality = next;
  }
  $$(".quality-chip").forEach((button) => button.classList.toggle("selected", state.task.annotation.image_quality.includes(button.dataset.value)));
  markDirty();
}

function updateSelected(field, value) {
  const region = selectedRegion();
  if (!region) return;
  region[field] = value;
  if (field === "label") {
    const textual = state.taxonomy.region_labels.find((item) => item.code === value)?.textual;
    if (!textual) { region.legibility = "not_applicable"; region.transcription = ""; }
    else if (region.legibility === "not_applicable") region.legibility = "legible";
  }
  markDirty();
  if (["field_code", "transcription"].includes(field)) {
    renderRegionList();
    renderCanvas();
  } else {
    renderInspector();
  }
}

function deleteSelectedRegion() {
  if (!state.task || !state.selectedRegionId) return;
  state.task.annotation.regions = state.task.annotation.regions.filter((item) => item.id !== state.selectedRegionId);
  state.selectedRegionId = null;
  renumberRegions();
  markDirty();
  renderInspector();
}

function renumberRegions() {
  [...state.task.annotation.regions]
    .sort((a, b) => a.reading_order - b.reading_order)
    .forEach((region, index) => { region.reading_order = index + 1; });
}

function randomRegionId() {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return `reg_${[...bytes].map((item) => item.toString(16).padStart(2, "0")).join("")}`;
}

function setTool(tool) {
  state.tool = tool;
  $$(".tool-button[data-tool]").forEach((button) => button.classList.toggle("active", button.dataset.tool === tool));
  $("#annotation-canvas").classList.toggle("select-mode", tool === "select");
  const name = tool === "select" ? "Select, move, or resize a region." : `Draw a ${labelNames.get(tool)?.toLowerCase() || "region"} box.`;
  $("#canvas-hint").textContent = name;
}

const canvas = $("#annotation-canvas");
const context = canvas.getContext("2d");
const view = { width: 1, height: 1, scale: 1, fitScale: 1, offsetX: 0, offsetY: 0 };

async function loadTaskImage(url) {
  $("#canvas-loading").classList.remove("hidden");
  const image = new Image();
  image.decoding = "async";
  image.src = `${url}?v=${state.task.version}`;
  try {
    await image.decode();
    state.image = image;
    fitPage();
    $("#canvas-loading").classList.add("hidden");
  } catch (_) {
    toast("The private page image could not be loaded.", "error");
  }
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(rect.width * dpr));
  const height = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  view.width = rect.width;
  view.height = rect.height;
  renderCanvas();
}

function calculateView() {
  if (!state.image) return;
  view.fitScale = Math.min((view.width - 70) / state.image.naturalWidth, (view.height - 70) / state.image.naturalHeight);
  view.fitScale = Math.max(view.fitScale, 0.01);
  view.scale = view.fitScale * state.zoom;
  view.offsetX = (view.width - state.image.naturalWidth * view.scale) / 2 + state.panX;
  view.offsetY = (view.height - state.image.naturalHeight * view.scale) / 2 + state.panY;
}

function regionPixels(region) {
  const iw = state.image.naturalWidth;
  const ih = state.image.naturalHeight;
  return {
    x: view.offsetX + (region.x / 100) * iw * view.scale,
    y: view.offsetY + (region.y / 100) * ih * view.scale,
    width: (region.width / 100) * iw * view.scale,
    height: (region.height / 100) * ih * view.scale,
  };
}

function renderCanvas() {
  const dpr = window.devicePixelRatio || 1;
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, view.width, view.height);
  if (!state.image || !state.task) return;
  calculateView();
  context.save();
  context.shadowColor = "rgba(16,42,56,.18)";
  context.shadowBlur = 24;
  context.shadowOffsetY = 8;
  context.fillStyle = "#fff";
  context.fillRect(view.offsetX, view.offsetY, state.image.naturalWidth * view.scale, state.image.naturalHeight * view.scale);
  context.restore();
  context.drawImage(state.image, view.offsetX, view.offsetY, state.image.naturalWidth * view.scale, state.image.naturalHeight * view.scale);
  state.task.annotation.regions.forEach((region) => drawRegion(region, region.id === state.selectedRegionId));
  if (state.pointer?.mode === "draw" && state.pointer.draft) drawRegion(state.pointer.draft, true, true);
}

function drawRegion(region, selected = false, draft = false) {
  const box = regionPixels(region);
  const color = regionColors[region.label] || "#566";
  context.save();
  context.fillStyle = `${color}${selected ? "2e" : "1d"}`;
  context.strokeStyle = color;
  context.lineWidth = selected ? 2.5 : 1.6;
  if (draft) context.setLineDash([6, 4]);
  context.fillRect(box.x, box.y, box.width, box.height);
  context.strokeRect(box.x, box.y, box.width, box.height);
  const label = draft ? labelNames.get(region.label) : `${region.reading_order} · ${labelNames.get(region.label) || region.label}`;
  context.font = "700 10px Inter, sans-serif";
  const labelWidth = Math.min(Math.max(45, context.measureText(label).width + 12), Math.max(box.width, 45));
  const labelY = Math.max(view.offsetY, box.y - 18);
  context.fillStyle = color;
  context.fillRect(box.x, labelY, labelWidth, 18);
  context.fillStyle = "#fff";
  context.fillText(label, box.x + 6, labelY + 12);
  if (selected && !draft) {
    [[box.x,box.y],[box.x+box.width,box.y],[box.x+box.width,box.y+box.height],[box.x,box.y+box.height]].forEach(([x,y]) => {
      context.fillStyle = "#fff"; context.strokeStyle = color; context.lineWidth = 2;
      context.fillRect(x - 4, y - 4, 8, 8); context.strokeRect(x - 4, y - 4, 8, 8);
    });
  }
  context.restore();
}

function canvasPoint(event) {
  const rect = canvas.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

function imagePoint(point) {
  return {
    x: Math.max(0, Math.min(state.image.naturalWidth, (point.x - view.offsetX) / view.scale)),
    y: Math.max(0, Math.min(state.image.naturalHeight, (point.y - view.offsetY) / view.scale)),
  };
}

function percentRegion(start, end, label) {
  const left = Math.min(start.x, end.x), top = Math.min(start.y, end.y);
  const width = Math.abs(end.x - start.x), height = Math.abs(end.y - start.y);
  return {
    id: randomRegionId(), label,
    structure_role: ["printed_variable", "checkbox_mark"].includes(label) ? "form_field" : "none",
    legibility: ["checkbox_mark", "other_region", "signature", "drawing_or_tracing"].includes(label) ? "not_applicable" : "legible",
    reading_order: state.task.annotation.regions.reduce((max, item) => Math.max(max, item.reading_order), 0) + 1,
    field_code: null, transcription: "",
    x: left / state.image.naturalWidth * 100,
    y: top / state.image.naturalHeight * 100,
    width: width / state.image.naturalWidth * 100,
    height: height / state.image.naturalHeight * 100,
  };
}

function hitRegion(point) {
  const regions = [...state.task.annotation.regions].reverse();
  return regions.find((region) => {
    const box = regionPixels(region);
    return point.x >= box.x && point.x <= box.x + box.width && point.y >= box.y && point.y <= box.y + box.height;
  }) || null;
}

function hitHandle(point, region) {
  if (!region) return null;
  const box = regionPixels(region);
  const handles = { nw:[box.x,box.y], ne:[box.x+box.width,box.y], se:[box.x+box.width,box.y+box.height], sw:[box.x,box.y+box.height] };
  return Object.entries(handles).find(([, [x,y]]) => Math.hypot(point.x-x, point.y-y) <= 9)?.[0] || null;
}

canvas.addEventListener("pointerdown", (event) => {
  if (!state.image || !state.task) return;
  canvas.setPointerCapture(event.pointerId);
  const point = canvasPoint(event);
  if (event.button === 1 || state.spaceHeld) {
    state.pointer = { mode: "pan", start: point, panX: state.panX, panY: state.panY };
    canvas.classList.add("panning");
    return;
  }
  if (state.tool !== "select") {
    const start = imagePoint(point);
    state.pointer = { mode: "draw", start, draft: percentRegion(start, start, state.tool) };
    renderCanvas();
    return;
  }
  const region = selectedRegion();
  const handle = hitHandle(point, region);
  if (handle && region) {
    state.pointer = { mode: "resize", handle, start: imagePoint(point), original: { ...region } };
    return;
  }
  const hit = hitRegion(point);
  if (hit) {
    state.selectedRegionId = hit.id;
    state.pointer = { mode: "move", start: imagePoint(point), original: { ...hit } };
  } else {
    state.selectedRegionId = null;
    state.pointer = null;
  }
  renderInspector();
});

canvas.addEventListener("pointermove", (event) => {
  if (!state.pointer || !state.image) return;
  const point = canvasPoint(event);
  if (state.pointer.mode === "pan") {
    state.panX = state.pointer.panX + point.x - state.pointer.start.x;
    state.panY = state.pointer.panY + point.y - state.pointer.start.y;
  } else if (state.pointer.mode === "draw") {
    state.pointer.draft = percentRegion(state.pointer.start, imagePoint(point), state.tool);
  } else if (state.pointer.mode === "move") {
    const region = selectedRegion();
    const current = imagePoint(point);
    const dx = (current.x - state.pointer.start.x) / state.image.naturalWidth * 100;
    const dy = (current.y - state.pointer.start.y) / state.image.naturalHeight * 100;
    region.x = Math.max(0, Math.min(100 - region.width, state.pointer.original.x + dx));
    region.y = Math.max(0, Math.min(100 - region.height, state.pointer.original.y + dy));
  } else if (state.pointer.mode === "resize") {
    const region = selectedRegion();
    const current = imagePoint(point);
    const px = current.x / state.image.naturalWidth * 100;
    const py = current.y / state.image.naturalHeight * 100;
    const original = state.pointer.original;
    const right = original.x + original.width, bottom = original.y + original.height;
    let left = original.x, top = original.y, nextRight = right, nextBottom = bottom;
    if (state.pointer.handle.includes("w")) left = Math.min(px, right - .2);
    if (state.pointer.handle.includes("e")) nextRight = Math.max(px, original.x + .2);
    if (state.pointer.handle.includes("n")) top = Math.min(py, bottom - .2);
    if (state.pointer.handle.includes("s")) nextBottom = Math.max(py, original.y + .2);
    region.x = Math.max(0, left); region.y = Math.max(0, top);
    region.width = Math.min(100, nextRight) - region.x; region.height = Math.min(100, nextBottom) - region.y;
  }
  renderCanvas();
});

canvas.addEventListener("pointerup", () => {
  if (!state.pointer) return;
  if (state.pointer.mode === "draw") {
    const draft = state.pointer.draft;
    if (draft.width >= .2 && draft.height >= .2) {
      state.task.annotation.regions.push(draft);
      state.selectedRegionId = draft.id;
      markDirty();
      renderInspector();
    }
  } else if (["move", "resize"].includes(state.pointer.mode)) {
    markDirty();
    renderInspector();
  }
  state.pointer = null;
  canvas.classList.remove("panning");
  renderCanvas();
});

canvas.addEventListener("wheel", (event) => {
  if (!state.image) return;
  event.preventDefault();
  setZoom(state.zoom * (event.deltaY < 0 ? 1.1 : .9));
}, { passive: false });

function setZoom(value) {
  state.zoom = Math.max(.35, Math.min(6, value));
  $("#zoom-label").textContent = state.zoom === 1 ? "Fit" : `${Math.round(state.zoom * 100)}%`;
  renderCanvas();
}

function fitPage() { state.zoom = 1; state.panX = 0; state.panY = 0; $("#zoom-label").textContent = "Fit"; resizeCanvas(); }

// The writer registry stores an opaque identifier per clinician; the readable
// label is operational only and never reaches the annotation or gold export.
function writerLabel(id) {
  return state.writers.find((item) => item.id === id)?.label || id;
}

function renderWriters() {
  const chips = $("#writer-chips");
  if (!chips || !state.task) return;
  const selected = state.task.annotation.writer_group_ids || [];
  chips.replaceChildren();
  selected.forEach((id) => {
    const chip = document.createElement("span");
    chip.className = "writer-chip";
    const name = document.createElement("span");
    name.textContent = writerLabel(id);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${writerLabel(id)}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      state.task.annotation.writer_group_ids = selected.filter((item) => item !== id);
      markDirty();
      renderWriters();
    });
    chip.append(name, remove);
    chips.append(chip);
  });
}

function fillWriterOptions() {
  const list = $("#writer-options");
  if (!list) return;
  list.replaceChildren();
  state.writers.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.label;
    list.append(option);
  });
}

async function loadWriters() {
  // The registry is optional metadata. It must never be able to stop the
  // workbench loading: before its migration is applied this endpoint fails,
  // and an unguarded throw here would abort init before the queue loads.
  try {
    const payload = await api("/api/writers");
    state.writers = payload.writers || [];
  } catch {
    state.writers = [];
  }
  fillWriterOptions();
}

async function addWriter() {
  if (!state.task) return;
  const input = $("#writer-input");
  const label = input.value.trim();
  if (!label) return;
  try {
    const known = state.writers.find(
      (item) => item.label.toLowerCase() === label.toLowerCase(),
    );
    const writer = known || await api("/api/writers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label }),
    });
    if (!known) {
      state.writers = [...state.writers, { id: writer.id, label: writer.label }]
        .sort((a, b) => a.label.localeCompare(b.label));
      fillWriterOptions();
    }
    const selected = state.task.annotation.writer_group_ids || [];
    if (!selected.includes(writer.id)) {
      state.task.annotation.writer_group_ids = [...selected, writer.id];
      markDirty();
    }
    input.value = "";
    renderWriters();
  } catch (error) {
    toast(error.message, "error");
  }
}

function bindFields() {
  $("#writer-add").addEventListener("click", addWriter);
  $("#writer-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); addWriter(); }
  });
  $("#document-type").addEventListener("change", (event) => {
    state.task.annotation.document_type = event.target.value || null;
    state.task.annotation.document_variant = null;
    renderVariantOptions(); markDirty();
  });
  $("#document-variant").addEventListener("change", (event) => { state.task.annotation.document_variant = event.target.value || null; markDirty(); });
  $("#content-profile").addEventListener("change", (event) => { state.task.annotation.content_profile = event.target.value || null; markDirty(); });
  $("#page-notes").addEventListener("input", (event) => { state.task.annotation.notes = event.target.value; markDirty(); });
  $("#region-label").addEventListener("change", (event) => updateSelected("label", event.target.value));
  $("#legibility").addEventListener("change", (event) => updateSelected("legibility", event.target.value));
  $("#structure-role").addEventListener("change", (event) => updateSelected("structure_role", event.target.value));
  $("#field-code").addEventListener("input", (event) => updateSelected("field_code", event.target.value));
  $("#transcription").addEventListener("input", (event) => updateSelected("transcription", event.target.value));
  $("#reading-order").addEventListener("change", (event) => {
    const region = selectedRegion(); if (!region) return;
    const next = Math.max(1, Number.parseInt(event.target.value, 10) || 1);
    const other = state.task.annotation.regions.find((item) => item !== region && item.reading_order === next);
    if (other) other.reading_order = region.reading_order;
    region.reading_order = next; markDirty(); renderInspector();
  });
}

function bindApp() {
  $$(".upload-trigger").forEach((button) => button.addEventListener("click", () => $("#file-input").click()));
  $("#file-input").addEventListener("change", (event) => uploadFiles(event.target.files));
  const dropzone = $("#upload-dropzone");
  ["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove("dragging"); }));
  dropzone.addEventListener("drop", (event) => uploadFiles(event.dataTransfer.files));
  $("#home-button").addEventListener("click", showQueue); $("#queue-nav").addEventListener("click", showQueue); $("#back-button").addEventListener("click", showQueue);
  $$(".tool-button[data-tool]").forEach((button) => button.addEventListener("click", () => setTool(button.dataset.tool)));
  $("#fit-button").addEventListener("click", fitPage); $("#zoom-in").addEventListener("click", () => setZoom(state.zoom * 1.2)); $("#zoom-out").addEventListener("click", () => setZoom(state.zoom / 1.2));
  $("#save-button").addEventListener("click", () => saveTask().catch(() => {})); $("#complete-button").addEventListener("click", completeTask);
  $("#delete-region").addEventListener("click", deleteSelectedRegion);
  $("#clear-quality").addEventListener("click", () => { state.task.annotation.image_quality = []; $$(".quality-chip").forEach((item) => item.classList.remove("selected")); markDirty(); });
  let filterTimer;
  $("#queue-search").addEventListener("input", () => { clearTimeout(filterTimer); filterTimer = setTimeout(() => loadQueue().catch((error) => toast(error.message, "error")), 220); });
  [$("#status-filter"), $("#type-filter")].forEach((select) => select.addEventListener("change", () => loadQueue().catch((error) => toast(error.message, "error"))));
  bindFields();
  new ResizeObserver(resizeCanvas).observe($("#canvas-stage"));
  window.addEventListener("keydown", (event) => {
    const editing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
    if (event.code === "Space" && !editing) { state.spaceHeld = true; event.preventDefault(); }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") { event.preventDefault(); saveTask().catch(() => {}); return; }
    if (editing || !state.task) return;
    const tools = { v: "select", f: "printed_static", d: "printed_variable", h: "handwriting", c: "checkbox_mark", g: "other_region" };
    if (tools[event.key.toLowerCase()]) setTool(tools[event.key.toLowerCase()]);
    if (["Delete", "Backspace"].includes(event.key)) { event.preventDefault(); deleteSelectedRegion(); }
  });
  window.addEventListener("keyup", (event) => { if (event.code === "Space") state.spaceHeld = false; });
  window.addEventListener("beforeunload", (event) => { if (state.dirty) { event.preventDefault(); event.returnValue = ""; } });
}

async function init() {
  bindApp();
  try {
    await loadIdentity();
    state.taxonomy = await api("/api/taxonomy");
    fillTaxonomy();
    await loadWriters();
    await loadQueue();
    const id = location.hash.match(/^#(page_[0-9]{6,})$/)?.[1];
    if (id) await openTask(id);
  } catch (error) {
    toast(error.message, "error");
  }
}

init();
