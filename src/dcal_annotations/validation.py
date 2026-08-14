from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from .taxonomy import Taxonomy


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FIELD_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ANNOTATION_SCHEMA_VERSION = "dcal.annotation.v1"
GOLD_SCHEMA_VERSION = "dcal.gold.v1"


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class ExportValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("\n".join(str(issue) for issue in self.issues))


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _require_positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a positive integer")
    if int(value) != value or value < 1:
        raise ValueError(f"{path} must be a positive integer")
    return int(value)


def _as_tasks(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        tasks = payload
    elif isinstance(payload, dict) and isinstance(payload.get("tasks"), list):
        tasks = payload["tasks"]
    else:
        raise ValueError("export root must be a task array or an object with a tasks array")
    if not all(isinstance(task, dict) for task in tasks):
        raise ValueError("every exported task must be a JSON object")
    return tasks


def _select_annotation(task: dict[str, Any]) -> dict[str, Any]:
    annotations = task.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("annotations must be an array")
    active = [
        annotation
        for annotation in annotations
        if isinstance(annotation, dict)
        and annotation.get("was_cancelled") is not True
        and isinstance(annotation.get("result"), list)
        and annotation["result"]
    ]
    ground_truth = [annotation for annotation in active if annotation.get("ground_truth") is True]
    if len(ground_truth) == 1:
        return ground_truth[0]
    if len(ground_truth) > 1:
        raise ValueError("multiple active annotations are marked as ground truth")
    if len(active) != 1:
        raise ValueError(
            "task must have exactly one active annotation or exactly one explicit ground truth"
        )
    return active[0]


def _items(results: list[dict[str, Any]], from_name: str) -> list[dict[str, Any]]:
    return [item for item in results if item.get("from_name") == from_name]


def _single_choice(
    results: list[dict[str, Any]], from_name: str, *, required: bool
) -> str | None:
    matches = _items(results, from_name)
    if not matches:
        if required:
            raise ValueError(f"missing required {from_name} choice")
        return None
    if len(matches) != 1:
        raise ValueError(f"{from_name} must contain exactly one result item")
    choices = matches[0].get("value", {}).get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], str):
        raise ValueError(f"{from_name} must contain exactly one choice")
    return choices[0]


def _multiple_choices(results: list[dict[str, Any]], from_name: str) -> list[str]:
    matches = _items(results, from_name)
    if not matches:
        return []
    if len(matches) != 1:
        raise ValueError(f"{from_name} must contain at most one result item")
    choices = matches[0].get("value", {}).get("choices")
    if not isinstance(choices, list) or not all(isinstance(value, str) for value in choices):
        raise ValueError(f"{from_name} choices must be an array of strings")
    if len(set(choices)) != len(choices):
        raise ValueError(f"{from_name} contains duplicate choices")
    return choices


def _single_text(results: list[dict[str, Any]], from_name: str) -> str | None:
    matches = _items(results, from_name)
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"{from_name} must contain at most one result item")
    value = matches[0].get("value", {}).get("text")
    if isinstance(value, str):
        return value
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        return value[0]
    raise ValueError(f"{from_name} must contain exactly one text value")


def _single_number(results: list[dict[str, Any]], from_name: str) -> int:
    matches = _items(results, from_name)
    if len(matches) != 1:
        raise ValueError(f"{from_name} must contain exactly one result item")
    return _require_positive_int(matches[0].get("value", {}).get("number"), from_name)


def _annotation_actor(annotation: dict[str, Any]) -> int | str | None:
    actor = annotation.get("completed_by")
    if isinstance(actor, dict):
        actor = actor.get("id")
    if isinstance(actor, (int, str)) and not isinstance(actor, bool):
        return actor
    return None


def _validate_geometry(result: dict[str, Any]) -> dict[str, Any]:
    value = result.get("value")
    if not isinstance(value, dict):
        raise ValueError("region geometry value must be an object")

    geometry: dict[str, float] = {}
    for name in ("x", "y", "width", "height"):
        raw = value.get(name)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"region {name} must be numeric")
        geometry[name] = float(raw)

    if not 0 <= geometry["x"] <= 100 or not 0 <= geometry["y"] <= 100:
        raise ValueError("region x and y must be between 0 and 100")
    if not 0 < geometry["width"] <= 100 or not 0 < geometry["height"] <= 100:
        raise ValueError("region width and height must be greater than 0 and at most 100")
    if geometry["x"] + geometry["width"] > 100.001:
        raise ValueError("region extends beyond the right page boundary")
    if geometry["y"] + geometry["height"] > 100.001:
        raise ValueError("region extends beyond the bottom page boundary")

    rotation = value.get("rotation", 0)
    if isinstance(rotation, bool) or not isinstance(rotation, (int, float)):
        raise ValueError("region rotation must be numeric")
    if not -360 <= rotation <= 360:
        raise ValueError("region rotation must be between -360 and 360 degrees")

    original_width = _require_positive_int(result.get("original_width"), "original_width")
    original_height = _require_positive_int(result.get("original_height"), "original_height")
    image_rotation = result.get("image_rotation", 0)
    if isinstance(image_rotation, bool) or not isinstance(image_rotation, (int, float)):
        raise ValueError("image_rotation must be numeric")

    return {
        **geometry,
        "rotation": float(rotation),
        "original_width": original_width,
        "original_height": original_height,
        "image_rotation": float(image_rotation),
    }


def _normalize_region(
    geometry_result: dict[str, Any],
    all_results: list[dict[str, Any]],
    taxonomy: Taxonomy,
) -> dict[str, Any]:
    region_id = _require_string(geometry_result.get("id"), "region id")
    labels = geometry_result.get("value", {}).get("rectanglelabels")
    if not isinstance(labels, list) or len(labels) != 1 or not isinstance(labels[0], str):
        raise ValueError(f"region {region_id} must have exactly one region label")
    label = labels[0]
    if label not in taxonomy.region_labels:
        raise ValueError(f"region {region_id} uses unknown label {label!r}")

    scoped = [item for item in all_results if item.get("id") == region_id]
    legibility = _single_choice(scoped, "legibility", required=True)
    assert legibility is not None
    if legibility not in taxonomy.legibility_states:
        raise ValueError(f"region {region_id} uses unknown legibility {legibility!r}")

    structure_role = _single_choice(scoped, "structure_role", required=False) or "none"
    if structure_role not in taxonomy.structure_roles:
        raise ValueError(f"region {region_id} uses unknown structure role {structure_role!r}")

    semantic_type = _single_choice(scoped, "semantic_region_type", required=False)
    if semantic_type is not None and semantic_type not in taxonomy.semantic_region_types:
        raise ValueError(f"region {region_id} uses unknown semantic type {semantic_type!r}")

    reading_order = _single_number(scoped, "reading_order")
    transcription = _single_text(scoped, "transcription")
    field_code = _single_text(scoped, "field_code")
    if field_code is not None:
        field_code = field_code.strip()
        if not field_code:
            field_code = None
        elif not FIELD_CODE_RE.fullmatch(field_code):
            raise ValueError(
                f"region {region_id} field_code must use lowercase snake_case"
            )

    label_contract = taxonomy.region_labels[label]
    if label_contract.get("textual") is True and legibility == "not_applicable":
        raise ValueError(f"region {region_id} is textual and cannot be not_applicable")
    if legibility in {"illegible", "not_applicable"} and transcription is not None:
        if transcription.strip():
            raise ValueError(
                f"region {region_id} must not contain transcription when {legibility}"
            )
        transcription = None
    if (
        label_contract.get("requires_transcription_when_readable") is True
        and legibility in {"legible", "partially_legible"}
        and (transcription is None or not transcription.strip())
    ):
        raise ValueError(f"region {region_id} requires exact transcription")

    return {
        "region_id": region_id,
        "reading_order": reading_order,
        "label": label,
        "structure_role": structure_role,
        "legibility": legibility,
        "semantic_region_type": semantic_type,
        "field_code": field_code,
        "transcription": transcription,
        "geometry": _validate_geometry(geometry_result),
    }


def _normalize_task(task: dict[str, Any], taxonomy: Taxonomy) -> dict[str, Any]:
    data = task.get("data")
    if not isinstance(data, dict):
        raise ValueError("data must be an object")
    _require_string(data.get("image"), "data.image")
    object_id = _require_string(data.get("source_object_id"), "data.source_object_id")
    source_sha256 = _require_string(data.get("source_sha256"), "data.source_sha256")
    if not SHA256_RE.fullmatch(source_sha256):
        raise ValueError("data.source_sha256 must be 64 lowercase hexadecimal characters")
    patient_group_id = _require_string(
        data.get("patient_group_id"), "data.patient_group_id"
    )
    encounter_group_id = _require_string(
        data.get("encounter_group_id"), "data.encounter_group_id"
    )
    page_index = _require_positive_int(data.get("source_page_index"), "data.source_page_index")
    schema_version = _require_string(
        data.get("annotation_schema_version"), "data.annotation_schema_version"
    )
    if schema_version != ANNOTATION_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported annotation schema {schema_version!r}; expected {ANNOTATION_SCHEMA_VERSION!r}"
        )

    writer_group_ids = data.get("writer_group_ids", [])
    if not isinstance(writer_group_ids, list) or not all(
        isinstance(value, str) and value.strip() for value in writer_group_ids
    ):
        raise ValueError("data.writer_group_ids must be an array of non-empty opaque IDs")
    if len(set(writer_group_ids)) != len(writer_group_ids):
        raise ValueError("data.writer_group_ids contains duplicates")

    annotation = _select_annotation(task)
    raw_results = annotation["result"]
    if not all(isinstance(item, dict) for item in raw_results):
        raise ValueError("annotation results must all be objects")
    results: list[dict[str, Any]] = raw_results

    physical_type = _single_choice(results, "physical_document_type", required=True)
    assert physical_type is not None
    if physical_type not in taxonomy.physical_document_types:
        raise ValueError(f"unknown physical document type {physical_type!r}")

    variant = _single_choice(results, "physical_document_variant", required=False)
    if variant is not None:
        variant_contract = taxonomy.physical_document_variants.get(variant)
        if variant_contract is None:
            raise ValueError(f"unknown physical document variant {variant!r}")
        if variant_contract["physical_document_type"] != physical_type:
            raise ValueError(
                f"variant {variant!r} does not belong to physical type {physical_type!r}"
            )

    quality = _multiple_choices(results, "image_quality")
    unknown_quality = sorted(set(quality) - set(taxonomy.image_quality_flags))
    if unknown_quality:
        raise ValueError(f"unknown image quality flags: {unknown_quality!r}")
    if "clear" in quality and len(quality) > 1:
        raise ValueError("image quality 'clear' cannot be combined with defect flags")

    geometry_results = _items(results, "region_label")
    geometry_ids = {
        item.get("id")
        for item in geometry_results
        if isinstance(item.get("id"), str) and item.get("id")
    }
    region_control_names = {
        "reading_order",
        "legibility",
        "structure_role",
        "semantic_region_type",
        "transcription",
        "field_code",
    }
    orphaned_controls = sorted(
        {
            str(item.get("id"))
            for item in results
            if item.get("from_name") in region_control_names
            and item.get("id") not in geometry_ids
        }
    )
    if orphaned_controls:
        raise ValueError(
            "region controls reference missing geometry IDs: "
            f"{orphaned_controls!r}"
        )

    seen_region_ids: set[str] = set()
    regions: list[dict[str, Any]] = []
    for geometry_result in geometry_results:
        if geometry_result.get("type") != "rectanglelabels":
            raise ValueError("region_label results must use rectanglelabels geometry")
        region_id = _require_string(geometry_result.get("id"), "region id")
        if region_id in seen_region_ids:
            raise ValueError(f"duplicate region geometry id {region_id!r}")
        seen_region_ids.add(region_id)
        regions.append(_normalize_region(geometry_result, results, taxonomy))

    if physical_type not in taxonomy.non_catalog_types and not regions:
        raise ValueError("clinical physical pages require at least one annotated region")

    reading_orders = [region["reading_order"] for region in regions]
    if len(reading_orders) != len(set(reading_orders)):
        raise ValueError("region reading_order values must be unique within a page")
    regions.sort(key=lambda region: region["reading_order"])

    notes = _single_text(results, "annotator_notes")
    if notes is not None and not notes.strip():
        notes = None

    record: dict[str, Any] = {
        "schema_version": GOLD_SCHEMA_VERSION,
        "taxonomy_version": taxonomy.version,
        "source": {
            "object_id": object_id,
            "sha256": source_sha256,
            "patient_group_id": patient_group_id,
            "encounter_group_id": encounter_group_id,
            "writer_group_ids": writer_group_ids,
            "page_index": page_index,
        },
        "annotation": {
            "label_studio_task_id": task.get("id"),
            "label_studio_annotation_id": annotation.get("id"),
            "annotator_id": _annotation_actor(annotation),
            "created_at": annotation.get("created_at"),
            "updated_at": annotation.get("updated_at"),
        },
        "classification": {
            "physical_document_type": physical_type,
            "physical_document_variant": variant,
        },
        "image_quality": sorted(quality),
        "annotator_notes": notes,
        "regions": regions,
    }
    canonical = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    record["record_sha256"] = hashlib.sha256(canonical).hexdigest()
    return record


def normalize_export(payload: Any, taxonomy: Taxonomy) -> list[dict[str, Any]]:
    try:
        tasks = _as_tasks(payload)
    except ValueError as error:
        raise ExportValidationError([ValidationIssue("export", str(error))]) from error

    issues: list[ValidationIssue] = []
    records: list[dict[str, Any]] = []
    for index, task in enumerate(tasks):
        task_id = task.get("id", "unknown")
        try:
            records.append(_normalize_task(task, taxonomy))
        except (AssertionError, KeyError, TypeError, ValueError) as error:
            issues.append(ValidationIssue(f"tasks[{index}] (id={task_id})", str(error)))

    if issues:
        raise ExportValidationError(issues)

    source_hashes = [record["source"]["sha256"] for record in records]
    duplicates = sorted(
        value for value, count in Counter(source_hashes).items() if count > 1
    )
    if duplicates:
        raise ExportValidationError(
            [
                ValidationIssue(
                    "export",
                    f"contains duplicate source SHA-256 values: {duplicates!r}",
                )
            ]
        )
    return records
