from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from dcal_ingestion.models import AnnotationGatewayError, RenderedPage
from dcal_ingestion.workbench import WorkbenchClient


class FakeResponse:
    def __init__(self, payload: object):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class WorkbenchClientTests(unittest.TestCase):
    def test_index_and_create_use_private_bearer_contract(self) -> None:
        requests = []
        sha256 = "a" * 64
        storage_path = f"pages/aa/{sha256}.png"
        responses = [
            FakeResponse({"tasks": {"task_key": 7}}),
            FakeResponse(
                {
                    "storage_path": storage_path,
                    "signed_url": (
                        "https://example.supabase.co/storage/v1/object/upload/sign/"
                        f"dcal-pages/{storage_path}?token=signed"
                    ),
                }
            ),
            FakeResponse({"Key": f"dcal-pages/{storage_path}"}),
            FakeResponse({"id": 8}),
        ]

        def fake_urlopen(request, timeout):
            requests.append(request)
            return responses.pop(0)

        client = WorkbenchClient("http://workbench:8090", "secret-token")
        with patch("dcal_ingestion.workbench.urlopen", side_effect=fake_urlopen):
            self.assertEqual({"task_key": 7}, client.task_index())
            self.assertEqual(
                8,
                client.create_task(
                    {"dcal_ingestion_key": "task_new"},
                    RenderedPage(
                        page_index=1,
                        content=b"synthetic-page",
                        sha256=sha256,
                        width=100,
                        height=200,
                    ),
                ),
            )
        self.assertEqual("Bearer secret-token", requests[0].get_header("Authorization"))
        self.assertEqual("POST", requests[1].method)
        self.assertIsNone(requests[2].get_header("Authorization"))
        self.assertEqual("PUT", requests[2].method)
        posted = json.loads(requests[3].data.decode("utf-8"))
        self.assertEqual(storage_path, posted["storage_path"])
        self.assertEqual(100, posted["image_width"])
        self.assertEqual(200, posted["image_height"])

    def test_invalid_task_index_is_rejected(self) -> None:
        client = WorkbenchClient("http://workbench:8090", "secret-token")
        with patch(
            "dcal_ingestion.workbench.urlopen",
            return_value=FakeResponse({"tasks": {"bad": "not-an-integer"}}),
        ):
            with self.assertRaises(AnnotationGatewayError):
                client.task_index()


if __name__ == "__main__":
    unittest.main()
