from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import AnnotationGatewayError


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

    def create_task(self, data: dict[str, object]) -> int:
        payload = self._request("/api/ingestion/tasks", method="POST", body=data)
        task_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(task_id, int) or task_id < 1:
            raise AnnotationGatewayError("workbench did not return a task ID")
        return task_id

