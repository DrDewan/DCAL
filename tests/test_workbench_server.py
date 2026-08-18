from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

from dcal_workbench.server import create_server
from dcal_workbench.store import WorkbenchStore




def synthetic_png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (100, 140), "white").save(output, format="PNG")
    return output.getvalue()


class WorkbenchServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        store = WorkbenchStore(root / "state.sqlite3", root / "images")
        self.server = create_server("127.0.0.1", 0, store, "synthetic-ingestion-token")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path: str, **kwargs):
        with urlopen(Request(f"{self.base_url}{path}", **kwargs), timeout=3) as response:
            return response, response.read()

    def test_health_and_security_headers(self) -> None:
        response, body = self.request("/api/health")
        self.assertEqual({"status": "ok"}, json.loads(body))
        self.assertEqual("no-store", response.headers["Cache-Control"])
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

    def test_annotation_surface_is_not_served_locally(self) -> None:
        # Annotation, taxonomy, and gold export live only in the hosted
        # workbench, which enforces named identity and reviewer/admin roles.
        for path in ("/", "/app.js", "/api/taxonomy", "/api/export/gold.jsonl"):
            with self.assertRaises(HTTPError) as raised:
                self.request(path)
            self.assertEqual(404, raised.exception.code)

    def test_browser_upload_creates_a_pilot_task(self) -> None:
        boundary = "dcal-synthetic-boundary"
        content = synthetic_png()
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="files"; filename="synthetic.png"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("ascii") + content + f"\r\n--{boundary}--\r\n".encode("ascii")
        _, raw = self.request(
            "/api/uploads",
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        payload = json.loads(raw)
        self.assertEqual(1, len(payload["tasks"]))
        self.assertFalse(payload["tasks"][0]["dataset_eligible"])
        task_id = payload["tasks"][0]["id"]
        response, image = self.request(f"/api/tasks/{task_id}/image")
        self.assertEqual("image/png", response.headers["Content-Type"])
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
        _, raw_task = self.request(f"/api/tasks/{task_id}")
        task = json.loads(raw_task)
        self.assertEqual("unassigned", task["status"])
        self.assertEqual([], task["annotation"]["regions"])
        _, queue = self.request("/api/tasks")
        self.assertEqual(1, json.loads(queue)["total"])

    def test_ingestion_index_requires_token(self) -> None:
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/ingestion/tasks")
        self.assertEqual(401, caught.exception.code)
        _, body = self.request(
            "/api/ingestion/tasks",
            headers={"Authorization": "Bearer synthetic-ingestion-token"},
        )
        self.assertEqual({}, json.loads(body)["tasks"])


if __name__ == "__main__":
    unittest.main()
