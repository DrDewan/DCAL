from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from dcal_ingestion.models import AnnotationGatewayError
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
        responses = [FakeResponse({"tasks": {"task_key": 7}}), FakeResponse({"id": 8})]

        def fake_urlopen(request, timeout):
            requests.append(request)
            return responses.pop(0)

        client = WorkbenchClient("http://workbench:8090", "secret-token")
        with patch("dcal_ingestion.workbench.urlopen", side_effect=fake_urlopen):
            self.assertEqual({"task_key": 7}, client.task_index())
            self.assertEqual(8, client.create_task({"dcal_ingestion_key": "task_new"}))
        self.assertEqual("Bearer secret-token", requests[0].get_header("Authorization"))
        self.assertEqual("POST", requests[1].method)

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

