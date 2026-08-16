import {
  ANNOTATION_SCHEMA,
  NON_REGION_DOCUMENTS,
  taxonomySets,
} from "@/lib/contracts";
import { HttpError } from "@/lib/http";

const REGION_ID = /^reg_[a-f0-9]{12,32}$/;
const FIELD_CODE = /^[a-z][a-z0-9_]*$/;

function invalid(message: string): never {
  throw new HttpError(400, "invalid_annotation", message);
}

function optionalString(value: unknown, label: string) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string") invalid(`${label} must be text.`);
  return value;
}

export type NormalizedAnnotation = ReturnType<typeof validateAnnotation>;

export function validateAnnotation(value: unknown, completing: boolean) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    invalid("Annotation must be an object.");
  }
  const input = value as Record<string, unknown>;
  const documentType = optionalString(input.document_type, "Document type");
  if (documentType && !taxonomySets.documentTypes.has(documentType)) {
    invalid("Unknown physical document type.");
  }
  const variant = optionalString(input.document_variant, "Document variant");
  if (variant) {
    const contract = taxonomySets.variants.get(variant);
    if (!contract) invalid("Unknown physical document variant.");
    if (documentType && contract!.physical_document_type !== documentType) {
      invalid("Document variant does not belong to the selected type.");
    }
  }
  const contentProfile = optionalString(input.content_profile, "Content profile");
  if (contentProfile && !taxonomySets.contentProfiles.has(contentProfile)) {
    invalid("Unknown page content profile.");
  }
  const quality = input.image_quality ?? [];
  if (!Array.isArray(quality) || !quality.every((item) => typeof item === "string")) {
    invalid("Image quality must be an array.");
  }
  if (new Set(quality).size !== quality.length) invalid("Image quality values must be unique.");
  if (quality.some((item) => !taxonomySets.quality.has(item))) invalid("Unknown image quality flag.");
  if (quality.includes("clear") && quality.length > 1) {
    invalid("Clear cannot be combined with an image defect.");
  }
  const notes = input.notes ?? "";
  if (typeof notes !== "string" || notes.length > 4000) {
    invalid("Notes must contain at most 4,000 characters.");
  }
  const rawRegions = input.regions ?? [];
  if (!Array.isArray(rawRegions)) invalid("Regions must be an array.");
  const ids = new Set<string>();
  const orders = new Set<number>();
  const regions = rawRegions.map((raw, offset) => {
    const number = offset + 1;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) invalid(`Region ${number} must be an object.`);
    const region = raw as Record<string, unknown>;
    const id = region.id;
    if (typeof id !== "string" || !REGION_ID.test(id)) invalid(`Region ${number} has an invalid ID.`);
    if (ids.has(id)) invalid("Region IDs must be unique.");
    ids.add(id);
    const label = region.label;
    const labelContract = typeof label === "string" ? taxonomySets.regionLabels.get(label) : undefined;
    if (!labelContract) invalid(`Region ${number} has an unknown label.`);
    const structure = region.structure_role ?? "none";
    if (typeof structure !== "string" || !taxonomySets.structures.has(structure)) {
      invalid(`Region ${number} has an unknown structure role.`);
    }
    const legibility = region.legibility;
    if (typeof legibility !== "string" || !taxonomySets.legibility.has(legibility)) {
      invalid(`Region ${number} has unknown legibility.`);
    }
    const readingOrder = region.reading_order;
    if (!Number.isInteger(readingOrder) || (readingOrder as number) < 1) {
      invalid(`Region ${number} needs a positive reading order.`);
    }
    if (orders.has(readingOrder as number)) invalid("Reading orders must be unique.");
    orders.add(readingOrder as number);
    const geometry = Object.fromEntries(
      ["x", "y", "width", "height"].map((name) => {
        const item = region[name];
        if (typeof item !== "number" || !Number.isFinite(item)) invalid(`Region ${number} has invalid geometry.`);
        return [name, Math.round(item * 1_000_000) / 1_000_000];
      }),
    ) as Record<"x" | "y" | "width" | "height", number>;
    if (geometry.x < 0 || geometry.x >= 100 || geometry.y < 0 || geometry.y >= 100) {
      invalid(`Region ${number} starts outside the page.`);
    }
    if (geometry.width <= 0 || geometry.height <= 0) invalid(`Region ${number} has no area.`);
    if (geometry.x + geometry.width > 100.001 || geometry.y + geometry.height > 100.001) {
      invalid(`Region ${number} extends outside the page.`);
    }
    const transcription = region.transcription ?? "";
    if (typeof transcription !== "string" || transcription.length > 10_000) {
      invalid(`Region ${number} has invalid transcription.`);
    }
    const rawFieldCode = region.field_code ?? "";
    if (typeof rawFieldCode !== "string" || rawFieldCode.length > 100) {
      invalid(`Region ${number} has invalid field code.`);
    }
    const fieldCode = rawFieldCode.trim();
    if (fieldCode && !FIELD_CODE.test(fieldCode)) invalid("Field codes must use lowercase snake_case.");
    if (labelContract!.textual && legibility === "not_applicable") {
      invalid(`Region ${number} is text and needs legibility.`);
    }
    if (["illegible", "not_applicable"].includes(legibility) && transcription.trim()) {
      invalid(`Region ${number} cannot contain a transcription.`);
    }
    if (
      completing &&
      labelContract!.requires_transcription_when_readable &&
      ["legible", "partially_legible"].includes(legibility) &&
      !transcription.trim()
    ) {
      invalid(`Region ${number} needs exact transcription.`);
    }
    return {
      id,
      label: label as string,
      structure_role: structure,
      legibility,
      reading_order: readingOrder as number,
      field_code: fieldCode || null,
      transcription,
      ...geometry,
    };
  });
  if (completing) {
    if (!documentType) invalid("Select the physical document type before completing.");
    if (!contentProfile) invalid("Select the page content profile before completing.");
    if (!NON_REGION_DOCUMENTS.has(documentType!) && regions.length === 0) {
      invalid("Clinical pages need at least one annotated region.");
    }
  }
  return {
    schema_version: ANNOTATION_SCHEMA,
    document_type: documentType,
    document_variant: variant,
    content_profile: contentProfile,
    image_quality: quality,
    notes,
    regions: regions.sort((a, b) => a.reading_order - b.reading_order),
  };
}
