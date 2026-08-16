import { createHash } from "node:crypto";

import { INGESTION_SCHEMA } from "@/lib/contracts";
import { HttpError } from "@/lib/http";

const SHA256 = /^[0-9a-f]{64}$/;
const INGESTION_KEY = /^task_[0-9a-f]{32}$/;
const OPAQUE_ID = /^[a-z]+_[A-Za-z0-9_-]{20,64}$/;

function requireString(
  input: Record<string, unknown>,
  name: string,
  pattern?: RegExp,
) {
  const value = input[name];
  if (typeof value !== "string" || !value || (pattern && !pattern.test(value))) {
    throw new HttpError(400, "invalid_ingestion", `Ingestion task is missing or has invalid ${name}.`);
  }
  return value;
}

function positiveInteger(input: Record<string, unknown>, name: string) {
  const value = input[name];
  if (!Number.isInteger(value) || (value as number) < 1) {
    throw new HttpError(400, "invalid_ingestion", `${name} must be a positive integer.`);
  }
  return value as number;
}

export function taskIngestionKey(sha256: string) {
  return `task_${createHash("sha256")
    .update(`dcal:label-studio-task:v1:${sha256}`, "ascii")
    .digest("hex")
    .slice(0, 32)}`;
}

export function canonicalPagePath(sha256: string) {
  if (!SHA256.test(sha256)) {
    throw new HttpError(400, "invalid_checksum", "Page checksum is invalid.");
  }
  return `pages/${sha256.slice(0, 2)}/${sha256}.png`;
}

export type IngestionTask = ReturnType<typeof validateIngestionTask>;

export function validateIngestionTask(input: Record<string, unknown>) {
  const sourceSha256 = requireString(input, "source_sha256", SHA256);
  const rawSourceSha256 = requireString(input, "raw_source_sha256", SHA256);
  const ingestionKey = requireString(input, "dcal_ingestion_key", INGESTION_KEY);
  if (ingestionKey !== taskIngestionKey(sourceSha256)) {
    throw new HttpError(400, "invalid_ingestion", "Ingestion key does not match the page checksum.");
  }
  if (input.ingestion_schema_version !== INGESTION_SCHEMA) {
    throw new HttpError(400, "invalid_ingestion", "Unsupported ingestion schema.");
  }
  if (input.annotation_schema_version !== "dcal.annotation.v1") {
    throw new HttpError(400, "invalid_ingestion", "Unsupported ingestion annotation schema.");
  }
  const writerGroups = input.writer_group_ids ?? [];
  if (
    !Array.isArray(writerGroups) ||
    !writerGroups.every((item) => typeof item === "string" && OPAQUE_ID.test(item))
  ) {
    throw new HttpError(400, "invalid_ingestion", "writer_group_ids must contain opaque identifiers.");
  }
  const storagePath = requireString(input, "storage_path");
  if (storagePath !== canonicalPagePath(sourceSha256)) {
    throw new HttpError(400, "invalid_ingestion", "Storage path does not match the page checksum.");
  }
  const renderProfile = requireString(input, "render_profile");
  if (renderProfile !== "dcal.render.300dpi-rgb-png.v1") {
    throw new HttpError(400, "invalid_ingestion", "Unsupported render profile.");
  }
  return {
    sourceObjectId: requireString(input, "source_object_id", OPAQUE_ID),
    sourceSha256,
    rawSourceSha256,
    patientGroupId: requireString(input, "patient_group_id", OPAQUE_ID),
    encounterGroupId: requireString(input, "encounter_group_id", OPAQUE_ID),
    writerGroupIds: writerGroups as string[],
    sourcePageIndex: positiveInteger(input, "source_page_index"),
    imageWidth: positiveInteger(input, "image_width"),
    imageHeight: positiveInteger(input, "image_height"),
    storagePath,
    ingestionKey,
    renderProfile,
  };
}
