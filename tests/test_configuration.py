from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = (
    REPOSITORY_ROOT / "config" / "taxonomy" / "bmch-document-taxonomy.v1.json"
)
LABEL_CONFIG_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "label-studio"
    / "bmch-page-annotation.v1.xml"
)


class LabelConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        cls.root = ET.parse(LABEL_CONFIG_PATH).getroot()

    def aliases_for(self, control_name: str) -> set[str]:
        control = self.root.find(f".//*[@name='{control_name}']")
        self.assertIsNotNone(control, f"missing Label Studio control {control_name}")
        option_tags = ("Label",) if control.tag == "RectangleLabels" else ("Choice",)
        aliases = {
            option.get("alias")
            for option_tag in option_tags
            for option in control.findall(option_tag)
        }
        self.assertNotIn(None, aliases, f"{control_name} has a choice without an alias")
        return aliases  # type: ignore[return-value]

    def taxonomy_codes(self, section: str) -> set[str]:
        return {item["code"] for item in self.taxonomy[section]}

    def test_xml_is_well_formed_and_targets_one_image(self) -> None:
        images = self.root.findall(".//Image")
        rectangles = self.root.findall(".//RectangleLabels")
        self.assertEqual(1, len(images))
        self.assertEqual("page_image", images[0].get("name"))
        self.assertEqual(1, len(rectangles))
        self.assertEqual("page_image", rectangles[0].get("toName"))

    def test_page_type_aliases_match_taxonomy(self) -> None:
        self.assertEqual(
            self.taxonomy_codes("physical_document_types"),
            self.aliases_for("physical_document_type"),
        )

    def test_variant_aliases_match_taxonomy(self) -> None:
        self.assertEqual(
            self.taxonomy_codes("physical_document_variants"),
            self.aliases_for("physical_document_variant"),
        )

    def test_quality_aliases_match_taxonomy(self) -> None:
        self.assertEqual(
            self.taxonomy_codes("image_quality_flags"),
            self.aliases_for("image_quality"),
        )

    def test_region_aliases_match_taxonomy(self) -> None:
        mappings = {
            "region_label": "region_labels",
            "legibility": "legibility_states",
            "structure_role": "structure_roles",
            "semantic_region_type": "semantic_region_types",
        }
        for control, section in mappings.items():
            with self.subTest(control=control):
                self.assertEqual(
                    self.taxonomy_codes(section), self.aliases_for(control)
                )

    def test_required_region_controls_are_per_region(self) -> None:
        for name in (
            "reading_order",
            "legibility",
            "structure_role",
            "semantic_region_type",
            "transcription",
            "field_code",
        ):
            with self.subTest(control=name):
                control = self.root.find(f".//*[@name='{name}']")
                self.assertIsNotNone(control)
                self.assertEqual("true", control.get("perRegion"))


if __name__ == "__main__":
    unittest.main()
