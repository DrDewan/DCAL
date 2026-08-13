from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TAXONOMY_PATH = (
    REPOSITORY_ROOT / "config" / "taxonomy" / "bmch-document-taxonomy.v1.json"
)


def _unique_codes(items: list[dict[str, Any]], section: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        code = item.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError(f"{section}[{index}] has no non-empty code")
        if code in result:
            raise ValueError(f"{section} contains duplicate code {code!r}")
        result[code] = item
    return result


@dataclass(frozen=True)
class Taxonomy:
    version: str
    physical_document_types: dict[str, dict[str, Any]]
    physical_document_variants: dict[str, dict[str, Any]]
    region_labels: dict[str, dict[str, Any]]
    structure_roles: dict[str, dict[str, Any]]
    legibility_states: dict[str, dict[str, Any]]
    image_quality_flags: dict[str, dict[str, Any]]
    semantic_region_types: dict[str, dict[str, Any]]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Taxonomy":
        version = payload.get("schema_version")
        if version != "dcal.taxonomy.v1":
            raise ValueError(
                f"unsupported taxonomy schema {version!r}; expected 'dcal.taxonomy.v1'"
            )

        sections = {
            name: _unique_codes(payload.get(name, []), name)
            for name in (
                "physical_document_types",
                "physical_document_variants",
                "region_labels",
                "structure_roles",
                "legibility_states",
                "image_quality_flags",
                "semantic_region_types",
            )
        }

        for code, variant in sections["physical_document_variants"].items():
            parent = variant.get("physical_document_type")
            if parent not in sections["physical_document_types"]:
                raise ValueError(
                    f"physical_document_variants[{code!r}] references unknown type {parent!r}"
                )

        return cls(version=version, **sections)

    @classmethod
    def from_path(cls, path: str | Path = DEFAULT_TAXONOMY_PATH) -> "Taxonomy":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("taxonomy root must be a JSON object")
        return cls.from_dict(payload)

    @property
    def non_catalog_types(self) -> set[str]:
        return {
            code
            for code, value in self.physical_document_types.items()
            if value.get("non_catalog") is True
        }


def load_taxonomy(path: str | Path = DEFAULT_TAXONOMY_PATH) -> Taxonomy:
    return Taxonomy.from_path(path)
