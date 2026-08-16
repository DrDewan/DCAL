import { createHash } from "node:crypto";

import { GOLD_SCHEMA, PAGE_BUCKET, taxonomyPayload } from "@/lib/contracts";
import { HttpError } from "@/lib/http";
import { validateAnnotation } from "@/lib/validation";

export type TaskRow = {
  id: number;
  ingestion_key: string;
  source_origin: "manual_upload" | "google_drive";
  dataset_eligible: boolean;
  source_object_id: string;
  source_sha256: string;
  raw_source_sha256: string | null;
  patient_group_id: string | null;
  encounter_group_id: string | null;
  writer_group_ids: unknown;
  source_page_index: number;
  ingestion_schema_version: string | null;
  render_profile: string;
  storage_bucket: string;
  storage_path: string;
  image_width: number;
  image_height: number;
  status: string;
  assigned_to: string | null;
  assigned_to_name: string | null;
  annotation: unknown;
  version: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

export function publicTaskId(id: number) {
  return `page_${String(id).padStart(6, "0")}`;
}

export function parseTaskId(value: string) {
  const match = /^page_([0-9]{6,})$/.exec(value);
  if (!match) throw new HttpError(404, "task_not_found", "Task not found.");
  const id = Number(match[1]);
  if (!Number.isSafeInteger(id) || id < 1) {
    throw new HttpError(404, "task_not_found", "Task not found.");
  }
  return id;
}

export function taskSummary(row: TaskRow) {
  const annotation = row.annotation as Record<string, unknown>;
  const regions = Array.isArray(annotation?.regions) ? annotation.regions : [];
  return {
    id: publicTaskId(row.id),
    status: row.status,
    assigned_to: row.assigned_to_name,
    document_type: annotation?.document_type ?? null,
    content_profile: annotation?.content_profile ?? null,
    region_count: regions.length,
    dataset_eligible: row.dataset_eligible,
    source_origin: row.source_origin,
    updated_at: row.updated_at,
    version: row.version,
  };
}

export function taskDetail(row: TaskRow) {
  return {
    ...taskSummary(row),
    image: {
      url: `/api/tasks/${publicTaskId(row.id)}/image`,
      width: row.image_width,
      height: row.image_height,
    },
    annotation: row.annotation,
    created_at: row.created_at,
    completed_at: row.completed_at,
  };
}

export function stableJson(value: unknown): string {
  if (value === undefined) return "null";
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableJson(object[key])}`)
    .join(",")}}`;
}

export function goldRecord(row: TaskRow) {
  const annotation = validateAnnotation(row.annotation, true);
  const writers = Array.isArray(row.writer_group_ids) ? row.writer_group_ids : [];
  const record: Record<string, unknown> = {
    schema_version: GOLD_SCHEMA,
    taxonomy_version: taxonomyPayload.schema_version,
    source: {
      object_id: row.source_object_id,
      sha256: row.source_sha256,
      patient_group_id: row.patient_group_id,
      encounter_group_id: row.encounter_group_id,
      writer_group_ids: writers,
      page_index: row.source_page_index,
      ingestion: {
        raw_sha256: row.raw_source_sha256,
        schema_version: row.ingestion_schema_version,
        render_profile: row.render_profile,
        task_key: row.ingestion_key,
      },
    },
    annotation: {
      source: "dcal_workbench",
      workbench_task_id: publicTaskId(row.id),
      annotator: row.assigned_to_name,
      created_at: row.created_at,
      updated_at: row.updated_at,
    },
    classification: {
      physical_document_type: annotation.document_type,
      physical_document_variant: annotation.document_variant,
      content_profile: annotation.content_profile,
    },
    image_quality: annotation.image_quality,
    regions: annotation.regions.map((region) => ({
      region_id: region.id,
      reading_order: region.reading_order,
      label: region.label,
      structure_role: region.structure_role,
      legibility: region.legibility,
      semantic_region_type: null,
      field_code: region.field_code,
      transcription: region.transcription || null,
      geometry: {
        x: region.x,
        y: region.y,
        width: region.width,
        height: region.height,
        rotation: 0,
        original_width: row.image_width,
        original_height: row.image_height,
        image_rotation: 0,
      },
    })),
  };
  record.record_sha256 = createHash("sha256").update(stableJson(record)).digest("hex");
  return record;
}

export const taskColumns = [
  "id",
  "ingestion_key",
  "source_origin",
  "dataset_eligible",
  "source_object_id",
  "source_sha256",
  "raw_source_sha256",
  "patient_group_id",
  "encounter_group_id",
  "writer_group_ids",
  "source_page_index",
  "ingestion_schema_version",
  "render_profile",
  "storage_bucket",
  "storage_path",
  "image_width",
  "image_height",
  "status",
  "assigned_to",
  "assigned_to_name",
  "annotation",
  "version",
  "created_at",
  "updated_at",
  "completed_at",
].join(",");

export function assertPrivatePage(row: Pick<TaskRow, "storage_bucket" | "storage_path">) {
  if (row.storage_bucket !== PAGE_BUCKET || row.storage_path.includes("..")) {
    throw new HttpError(404, "image_unavailable", "Page image is unavailable.");
  }
}
