from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from dcal_ingestion.label_studio import LabelStudioClient
from dcal_ingestion.models import LabelStudioError


class FakeResponse:
    def __init__(self, payload: object):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class LabelStudioClientTests(unittest.TestCase):
    def test_task_index_and_create_task_use_documented_api_shapes(self) -> None:
        requests = []
        responses = [
            FakeResponse(
                {
                    "tasks": [
                        {
                            "id": 41,
                            "data": {"dcal_ingestion_key": "task_existing"},
                        }
                    ],
                    "total": 1,
                }
            ),
            FakeResponse({"id": 42, "data": {}}),
        ]

        def fake_urlopen(request, timeout):
            requests.append(request)
            return responses.pop(0)

        client = LabelStudioClient("http://label-studio:8080", "secret-token", 7)
        with patch("dcal_ingestion.label_studio.urlopen", side_effect=fake_urlopen):
            self.assertEqual({"task_existing": 41}, client.task_index())
            task_id = client.create_task(
                {"image": "/data/local-files/?d=pages/a.png", "dcal_ingestion_key": "task_new"}
            )
        self.assertEqual(42, task_id)
        self.assertIn("project=7", requests[0].full_url)
        self.assertEqual("Token secret-token", requests[0].get_header("Authorization"))
        created = json.loads(requests[1].data.decode("utf-8"))
        self.assertEqual(7, created["project"])
        self.assertEqual("task_new", created["data"]["dcal_ingestion_key"])

    def test_duplicate_ingestion_keys_are_rejected(self) -> None:
        response = FakeResponse(
            {
                "tasks": [
                    {"id": 1, "data": {"dcal_ingestion_key": "same"}},
                    {"id": 2, "data": {"dcal_ingestion_key": "same"}},
                ],
                "total": 2,
            }
        )
        client = LabelStudioClient("http://label-studio:8080", "token", 1)
        with patch("dcal_ingestion.label_studio.urlopen", return_value=response):
            with self.assertRaisesRegex(LabelStudioError, "duplicate"):
                client.task_index()


if __name__ == "__main__":
    unittest.main()
