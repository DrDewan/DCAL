from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import LabelStudioError


class LabelStudioClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        project_id: int,
        *,
        timeout_seconds: int = 30,
    ):
        if not base_url or not token or project_id < 1:
            raise ValueError("Label Studio URL, token, and positive project ID are required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project_id = project_id
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = None
        headers = {
            "Authorization": f"Token {self.token}",
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise LabelStudioError(
                f"Label Studio request failed with HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise LabelStudioError("Label Studio request did not complete") from error

    def task_index(self) -> dict[str, int]:
        index: dict[str, int] = {}
        page = 1
        while True:
            payload = self._request(
                "/api/tasks/",
                query={
                    "project": self.project_id,
                    "page": page,
                    "page_size": 100,
                    "fields": "task_only",
                },
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
                raise LabelStudioError("Label Studio returned an invalid task list")
            tasks = payload["tasks"]
            for task in tasks:
                if not isinstance(task, dict) or not isinstance(task.get("data"), dict):
                    continue
                ingestion_key = task["data"].get("dcal_ingestion_key")
                task_id = task.get("id")
                if not isinstance(ingestion_key, str) or not isinstance(task_id, int):
                    continue
                if ingestion_key in index and index[ingestion_key] != task_id:
                    raise LabelStudioError(
                        "Label Studio contains duplicate DCAL ingestion keys"
                    )
                index[ingestion_key] = task_id
            total = payload.get("total")
            if not tasks or not isinstance(total, int) or page * 100 >= total:
                return index
            page += 1

    def create_task(self, data: dict[str, object]) -> int:
        payload = self._request(
            "/api/tasks/",
            method="POST",
            body={"project": self.project_id, "data": data, "allow_skip": True},
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), int):
            raise LabelStudioError("Label Studio did not return a task ID")
        return payload["id"]
