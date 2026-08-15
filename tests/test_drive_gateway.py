from __future__ import annotations

import re
import unittest
from typing import Any

from dcal_ingestion.drive import FOLDER_MIME_TYPE, GoogleDriveGateway


class FakeRequest:
    def __init__(self, payload: Any):
        self.payload = payload

    def execute(self) -> Any:
        return self.payload


class FakeFilesResource:
    def __init__(self):
        self.items: dict[str, dict[str, Any]] = {
            "root": {
                "id": "root",
                "name": "DCAL",
                "mimeType": FOLDER_MIME_TYPE,
                "parents": [],
                "appProperties": {},
            }
        }
        self.next_id = 1
        self.list_calls: list[dict[str, Any]] = []

    def list(self, **kwargs: Any) -> FakeRequest:
        self.list_calls.append(kwargs)
        query = kwargs["q"]
        parent_match = re.search(r"'([^']+)' in parents", query)
        parent = parent_match.group(1) if parent_match else ""
        matches = [
            dict(item)
            for item in self.items.values()
            if parent in item.get("parents", [])
        ]
        sha_match = re.search(r"key='dcal_sha256' and value='([^']+)'", query)
        if sha_match:
            matches = [
                item
                for item in matches
                if item.get("appProperties", {}).get("dcal_sha256")
                == sha_match.group(1)
            ]
        return FakeRequest({"files": matches})

    def create(self, **kwargs: Any) -> FakeRequest:
        body = dict(kwargs["body"])
        file_id = f"created-{self.next_id}"
        self.next_id += 1
        item = {
            "id": file_id,
            "size": None,
            "contentRestrictions": [],
            **body,
        }
        self.items[file_id] = item
        return FakeRequest(dict(item))

    def update(self, **kwargs: Any) -> FakeRequest:
        item = self.items[kwargs["fileId"]]
        body = kwargs.get("body", {})
        if "appProperties" in body:
            item["appProperties"] = dict(body["appProperties"])
        for key in ("name", "contentRestrictions"):
            if key in body:
                item[key] = body[key]
        if kwargs.get("addParents"):
            item["parents"] = [kwargs["addParents"]]
        return FakeRequest(dict(item))


class FakeDriveService:
    def __init__(self):
        self.files_resource = FakeFilesResource()

    def files(self) -> FakeFilesResource:
        return self.files_resource


class GoogleDriveGatewayTests(unittest.TestCase):
    def test_bootstrap_is_idempotent_and_shared_drive_aware(self) -> None:
        service = FakeDriveService()
        gateway = GoogleDriveGateway(service)
        first = gateway.bootstrap_layout("root")
        second = gateway.bootstrap_layout("root")
        self.assertEqual(first, second)
        folders = [
            item
            for item in service.files_resource.items.values()
            if item.get("id") != "root"
        ]
        self.assertEqual(6, len(folders))
        self.assertEqual(
            {
                "inbox",
                "source_archive",
                "page_store",
                "quarantine",
                "dataset_exports",
                "manifests",
            },
            {item["appProperties"]["dcal_role"] for item in folders},
        )
        self.assertTrue(
            all(call["supportsAllDrives"] for call in service.files_resource.list_calls)
        )
        self.assertTrue(
            all(call["includeItemsFromAllDrives"] for call in service.files_resource.list_calls)
        )

    def test_scan_requires_patient_and_encounter_folder_depth(self) -> None:
        service = FakeDriveService()
        gateway = GoogleDriveGateway(service)
        layout = gateway.bootstrap_layout("root")
        items = service.files_resource.items
        items["patient"] = {
            "id": "patient",
            "name": "Patient folder",
            "mimeType": FOLDER_MIME_TYPE,
            "parents": [layout.inbox],
            "appProperties": {},
        }
        items["encounter"] = {
            "id": "encounter",
            "name": "Encounter folder",
            "mimeType": FOLDER_MIME_TYPE,
            "parents": ["patient"],
            "appProperties": {},
        }
        items["source"] = {
            "id": "source",
            "name": "page.jpg",
            "mimeType": "image/jpeg",
            "size": "1234",
            "parents": ["encounter"],
            "appProperties": {},
        }
        items["misplaced"] = {
            "id": "misplaced",
            "name": "wrong-level.jpg",
            "mimeType": "image/jpeg",
            "size": "10",
            "parents": [layout.inbox],
            "appProperties": {},
        }
        candidates, errors = gateway.scan_inbox(layout)
        self.assertEqual(1, len(candidates))
        self.assertEqual("source", candidates[0].file_id)
        self.assertEqual("patient", candidates[0].patient_folder_id)
        self.assertEqual("encounter", candidates[0].encounter_folder_id)
        self.assertEqual(1, errors)


if __name__ == "__main__":
    unittest.main()
