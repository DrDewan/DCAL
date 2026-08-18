from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from .models import AnnotationGatewayError, RenderedPage


class WorkbenchClient:
    def __init__(self, base_url: str, token: str, *, timeout_seconds: int = 30):
        if not base_url or not token:
            raise ValueError("workbench URL and ingestion token are required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
    ) -> Any:
        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise AnnotationGatewayError(
                f"workbench request failed with HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise AnnotationGatewayError("workbench request did not complete") from error

    def task_index(self) -> dict[str, int]:
        payload = self._request("/api/ingestion/tasks")
        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        if not isinstance(tasks, dict):
            raise AnnotationGatewayError("workbench returned an invalid task index")
        result: dict[str, int] = {}
        for key, task_id in tasks.items():
            if not isinstance(key, str) or not isinstance(task_id, int) or task_id < 1:
                raise AnnotationGatewayError("workbench returned an invalid task index")
            result[key] = task_id
        return result

    def _upload_signed_page(self, signed_url: str, page: RenderedPage) -> None:
        parsed = urlparse(signed_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".supabase.co")
            or "/storage/v1/object/upload/sign/dcal-pages/" not in parsed.path
        ):
            raise AnnotationGatewayError("workbench returned an invalid upload destination")
        request = Request(
            signed_url,
            data=page.content,
            headers={
                "Content-Type": "image/png",
                "Cache-Control": "max-age=0",
                "X-Upsert": "true",
            },
            method="PUT",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response.read()
        except HTTPError as error:
            raise AnnotationGatewayError(
                f"private page upload failed with HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise AnnotationGatewayError("private page upload did not complete") from error

    def create_task(
        self,
        data: dict[str, object],
        page: RenderedPage | None = None,
    ) -> int:
        if page is None:
            raise AnnotationGatewayError("workbench task creation requires rendered page bytes")
        signed = self._request(
            "/api/ingestion/upload-url",
            method="POST",
            body={
                "source_sha256": page.sha256,
                "mime_type": page.mime_type,
                "size_bytes": len(page.content),
            },
        )
        signed_url = signed.get("signed_url") if isinstance(signed, dict) else None
        storage_path = signed.get("storage_path") if isinstance(signed, dict) else None
        expected_path = f"pages/{page.sha256[:2]}/{page.sha256}.png"
        if not isinstance(signed_url, str) or storage_path != expected_path:
            raise AnnotationGatewayError("workbench returned an invalid upload contract")
        self._upload_signed_page(signed_url, page)
        task_data = {
            **data,
            "storage_path": storage_path,
            "image_width": page.width,
            "image_height": page.height,
        }
        payload = self._request("/api/ingestion/tasks", method="POST", body=task_data)
        task_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(task_id, int) or task_id < 1:
            raise AnnotationGatewayError("workbench did not return a task ID")
        return task_id
