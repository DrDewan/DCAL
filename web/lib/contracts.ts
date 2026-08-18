import taxonomy from "@/data/taxonomy.json";

export const WORKBENCH_SCHEMA = "dcal.workbench.v1";
export const ANNOTATION_SCHEMA = "dcal.annotation.v2";
export const GOLD_SCHEMA = "dcal.gold.v2";
export const INGESTION_SCHEMA = "dcal.ingestion.v1";
export const PAGE_BUCKET = "dcal-pages";
export const TASK_STATUSES = [
  "unassigned",
  "in_progress",
  "completed",
  "needs_review",
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const CONTENT_PROFILES = [
  "printed_blank_form",
  "printed_filled_form",
  "printed_document",
  "printed_with_handwriting",
  "handwritten_page",
  "unknown",
] as const;

export const contentProfileOptions = [
  { code: "printed_blank_form", name: "Blank printed form" },
  { code: "printed_filled_form", name: "Printed form with typed values" },
  { code: "printed_document", name: "Fully printed document" },
  { code: "printed_with_handwriting", name: "Printed form with handwriting" },
  { code: "handwritten_page", name: "Primarily handwritten page" },
  { code: "unknown", name: "Not sure" },
];

export const taxonomyPayload = {
  ...taxonomy,
  workbench_schema_version: WORKBENCH_SCHEMA,
  annotation_schema_version: ANNOTATION_SCHEMA,
  content_profiles: contentProfileOptions,
};

export const taxonomySets = {
  documentTypes: new Set(taxonomy.physical_document_types.map((item) => item.code)),
  variants: new Map(taxonomy.physical_document_variants.map((item) => [item.code, item])),
  regionLabels: new Map(taxonomy.region_labels.map((item) => [item.code, item])),
  structures: new Set(taxonomy.structure_roles.map((item) => item.code)),
  legibility: new Set(taxonomy.legibility_states.map((item) => item.code)),
  quality: new Set(taxonomy.image_quality_flags.map((item) => item.code)),
  contentProfiles: new Set<string>(CONTENT_PROFILES),
};

export const NON_REGION_DOCUMENTS = new Set([
  "blank_or_noninformative_page",
  "duplicate_or_rephotographed_source",
  "non_clinical_cover",
  "unknown_document",
]);

export function blankAnnotation() {
  return {
    schema_version: ANNOTATION_SCHEMA,
    document_type: null,
    document_variant: null,
    content_profile: null,
    image_quality: [] as string[],
    writer_group_ids: [] as string[],
    notes: "",
    regions: [] as Record<string, unknown>[],
  };
}
