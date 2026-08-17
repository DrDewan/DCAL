import {
  ANNOTATION_SCHEMA,
  NON_REGION_DOCUMENTS,
  taxonomySets,
} from "@/lib/contracts";
import { HttpError } from "@/lib/http";

const REGION_ID = /^reg_[a-f0-9]{12,32}$/;
const FIELD_CODE = /^[a-z][a-z0-9_]*$/;
const TABLE_MAX_ROWS = 100;
const TABLE_MAX_COLUMNS = 12;
const TABLE_MAX_CELL_LENGTH = 10_000;
const TABLE_MAX_TEXT_LENGTH = 100_000;

function invalid(message: string): never {
  throw new HttpError(400, "invalid_annotation", message);
}

function optionalString(value: unknown, label: string) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string") invalid(`${label} must be text.`);
  return value;
}

function normalizeTableData(value: unknown, regionNumber: number) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    invalid(`Region ${regionNumber} needs table data.`);
  }
  const input = value as Record<string, unknown>;
  const rows = input.rows;
  const columns = input.columns;
  const headerRows = input.header_rows ?? 0;
  if (!Number.isInteger(rows) || (rows as number) < 1 || (rows as number) > TABLE_MAX_ROWS) {
    invalid(`Region ${regionNumber} table rows must be between 1 and ${TABLE_MAX_ROWS}.`);
  }
  if (!Number.isInteger(columns) || (columns as number) < 1 || (columns as number) > TABLE_MAX_COLUMNS) {
    invalid(`Region ${regionNumber} table columns must be between 1 and ${TABLE_MAX_COLUMNS}.`);
  }
  if (!Number.isInteger(headerRows) || (headerRows as number) < 0 || (headerRows as number) > (rows as number)) {
    invalid(`Region ${regionNumber} has invalid table header rows.`);
  }

  const columnLabels = input.column_labels;
  if (!Array.isArray(columnLabels) || columnLabels.length !== columns) {
    invalid(`Region ${regionNumber} table column types must match the column count.`);
  }
  const normalizedColumnLabels = columnLabels.map((label, offset) => {
    const contract = typeof label === "string" ? taxonomySets.regionLabels.get(label) : undefined;
    if (!contract || contract.textual !== true) {
      invalid(`Region ${regionNumber} table column ${offset + 1} needs a textual content type.`);
    }
    return label as string;
  });

  const rawCells = input.cells;
  if (!Array.isArray(rawCells) || rawCells.length !== rows) {
    invalid(`Region ${regionNumber} table cells must match the row count.`);
  }
  let totalLength = 0;
  const cells = rawCells.map((rawRow, rowIndex) => {
    if (!Array.isArray(rawRow) || rawRow.length !== columns) {
      invalid(`Region ${regionNumber} table row ${rowIndex + 1} must match the column count.`);
    }
    return rawRow.map((cell, columnIndex) => {
      if (typeof cell !== "string" || cell.length > TABLE_MAX_CELL_LENGTH) {
        invalid(`Region ${regionNumber} table cell ${rowIndex + 1},${columnIndex + 1} is invalid.`);
      }
      totalLength += cell.length;
      if (totalLength > TABLE_MAX_TEXT_LENGTH) {
        invalid(`Region ${regionNumber} table text is too large.`);
      }
      return cell;
    });
  });

  return {
    rows: rows as number,
    columns: columns as number,
    header_rows: headerRows as number,
    column_labels: normalizedColumnLabels,
    cells,
  };
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

    const tableData = structure === "table"
      ? normalizeTableData(region.table_data, number)
      : null;
    if (structure !== "table" && region.table_data !== null && region.table_data !== undefined) {
      invalid(`Region ${number} has table data but is not marked as a table.`);
    }
    if (completing && tableData && !tableData.cells.some((row) => row.some((cell) => cell.trim()))) {
      invalid(`Region ${number} table needs at least one transcribed cell.`);
    }

    return {
      id,
      label: label as string,
      structure_role: structure,
      legibility,
      reading_order: readingOrder as number,
      field_code: fieldCode || null,
      transcription,
      table_data: tableData,
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
