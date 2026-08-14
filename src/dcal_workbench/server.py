from __future__ import annotations

import json
import mimetypes
import re
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from dcal_ingestion.render import MAX_SOURCE_BYTES
from dcal_ingestion.models import SourceRejected

from .store import (
    TaskNotFound,
    UploadItem,
    VersionConflict,
    WorkbenchError,
    WorkbenchStore,
)


MAX_REQUEST_BYTES = MAX_SOURCE_BYTES + 2 * 1024 * 1024
STATIC_ROOT = Path(__file__).with_name("static")
TASK_PATH = re.compile(r"^/api/tasks/(page_[0-9]{6,})(?:/(image))?$")


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _sniff_mime(content: bytes, declared: str) -> str:
    if declared != "application/octet-stream":
        return declared
    signatures = (
        (b"%PDF-", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"II*\x00", "image/tiff"),
        (b"MM\x00*", "image/tiff"),
        (b"BM", "image/bmp"),
    )
    for signature, mime_type in signatures:
        if content.startswith(signature):
            return mime_type
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return declared


def _multipart_files(content_type: str, body: bytes) -> list[UploadItem]:
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
        + body
    )
    if not message.is_multipart():
        raise WorkbenchError("upload must use multipart form data")
    files: list[UploadItem] = []
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data" or part.get_param(
            "name", header="content-disposition"
        ) != "files":
            continue
        content = part.get_payload(decode=True)
        mime_type = part.get_content_type().lower()
        if not isinstance(content, bytes) or not content:
            continue
        if len(content) > MAX_SOURCE_BYTES:
            raise WorkbenchError("an uploaded source exceeds the 250 MiB safety limit")
        files.append(UploadItem(content=content, mime_type=_sniff_mime(content, mime_type)))
    if not files:
        raise WorkbenchError("choose at least one image or PDF")
    return files


def handler_factory(store: WorkbenchStore, ingestion_token: str) -> type[BaseHTTPRequestHandler]:
    class WorkbenchHandler(BaseHTTPRequestHandler):
        server_version = "DCALWorkbench/0.1"

        def log_message(self, _format: str, *_args: object) -> None:
            # File names, source IDs, transcripts, and query strings must not reach logs.
            return

        def _headers(self, status: int, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' blob:; style-src 'self'; "
                "script-src 'self'; connect-src 'self'; object-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()

        def _send_json(self, status: int, payload: Any) -> None:
            body = _json_bytes(payload)
            self._headers(status, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)

        def _error(self, status: int, code: str, message: str) -> None:
            self._send_json(status, {"error": {"code": code, "message": message}})

        def _read_body(self) -> bytes:
            raw_length = self.headers.get("Content-Length")
            if not raw_length:
                raise WorkbenchError("request body is required")
            try:
                length = int(raw_length)
            except ValueError as error:
                raise WorkbenchError("invalid content length") from error
            if length < 1 or length > MAX_REQUEST_BYTES:
                raise WorkbenchError("request body exceeds the safety limit")
            body = self.rfile.read(length)
            if len(body) != length:
                raise WorkbenchError("request body ended early")
            return body

        def _read_json(self) -> dict[str, Any]:
            if self.headers.get_content_type() != "application/json":
                raise WorkbenchError("request must use application/json")
            try:
                payload = json.loads(self._read_body().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise WorkbenchError("request contains invalid JSON") from error
            if not isinstance(payload, dict):
                raise WorkbenchError("JSON request must be an object")
            return payload

        def _authorized_ingestion(self) -> bool:
            expected = f"Bearer {ingestion_token}"
            return bool(ingestion_token) and self.headers.get("Authorization") == expected

        def _serve_static(self, route: str) -> None:
            names = {
                "/": "index.html",
                "/index.html": "index.html",
                "/app.js": "app.js",
                "/styles.css": "styles.css",
            }
            name = names.get(route)
            if name is None:
                self._error(HTTPStatus.NOT_FOUND, "not_found", "resource not found")
                return
            path = STATIC_ROOT / name
            try:
                body = path.read_bytes()
            except OSError:
                self._error(HTTPStatus.NOT_FOUND, "not_found", "resource not found")
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type == "application/javascript":
                content_type += "; charset=utf-8"
            self._headers(HTTPStatus.OK, content_type, len(body))
            self.wfile.write(body)

        def _handle_error(self, error: Exception) -> None:
            if isinstance(error, TaskNotFound):
                self._error(HTTPStatus.NOT_FOUND, "task_not_found", str(error))
            elif isinstance(error, VersionConflict):
                self._error(HTTPStatus.CONFLICT, "version_conflict", str(error))
            elif isinstance(error, (WorkbenchError, SourceRejected)):
                self._error(HTTPStatus.BAD_REQUEST, "invalid_request", str(error))
            else:
                self._error(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "internal_error",
                    "the request could not be completed",
                )

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
            try:
                parsed = urlparse(self.path)
                route = parsed.path
                if route == "/api/health":
                    self._send_json(HTTPStatus.OK, {"status": "ok"})
                    return
                if route == "/api/taxonomy":
                    self._send_json(HTTPStatus.OK, store.taxonomy_payload())
                    return
                if route == "/api/tasks":
                    query = parse_qs(parsed.query)
                    payload = store.list_tasks(
                        status=query.get("status", [None])[0],
                        document_type=query.get("document_type", [None])[0],
                        query=query.get("q", [None])[0],
                    )
                    self._send_json(HTTPStatus.OK, payload)
                    return
                if route == "/api/ingestion/tasks":
                    if not self._authorized_ingestion():
                        self._error(HTTPStatus.UNAUTHORIZED, "unauthorized", "ingestion token required")
                        return
                    self._send_json(HTTPStatus.OK, {"tasks": store.task_index()})
                    return
                if route == "/api/export/gold.jsonl":
                    content, summary = store.export_gold()
                    body = content.encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                    self.send_header("Content-Disposition", "attachment; filename=dcal-gold.jsonl")
                    self.send_header("X-DCAL-Exported", str(summary["exported"]))
                    self.send_header(
                        "X-DCAL-Skipped-Manual",
                        str(summary["skipped_manual_without_grouping"]),
                    )
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                match = TASK_PATH.fullmatch(route)
                if match:
                    task_id, image = match.groups()
                    if image:
                        path = store.image_path(task_id)
                        body = path.read_bytes()
                        self._headers(HTTPStatus.OK, "image/png", len(body))
                        self.wfile.write(body)
                    else:
                        self._send_json(HTTPStatus.OK, store.get_task(task_id))
                    return
                self._serve_static(route)
            except Exception as error:  # safe boundary; never echo raw external errors
                self._handle_error(error)

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
            try:
                route = urlparse(self.path).path
                if route == "/api/uploads":
                    body = self._read_body()
                    files = _multipart_files(self.headers.get("Content-Type", ""), body)
                    results = store.upload_sources(files)
                    self._send_json(HTTPStatus.CREATED, {"tasks": results})
                    return
                if route == "/api/ingestion/tasks":
                    if not self._authorized_ingestion():
                        self._error(HTTPStatus.UNAUTHORIZED, "unauthorized", "ingestion token required")
                        return
                    task_id, created = store.import_ingestion_task(self._read_json())
                    self._send_json(
                        HTTPStatus.CREATED if created else HTTPStatus.OK,
                        {"id": task_id, "created": created},
                    )
                    return
                self._error(HTTPStatus.NOT_FOUND, "not_found", "resource not found")
            except Exception as error:
                self._handle_error(error)

        def do_PUT(self) -> None:  # noqa: N802 - stdlib handler contract
            try:
                route = urlparse(self.path).path
                match = TASK_PATH.fullmatch(route)
                if not match or match.group(2):
                    self._error(HTTPStatus.NOT_FOUND, "not_found", "resource not found")
                    return
                payload = self._read_json()
                task = store.save_task(
                    match.group(1),
                    annotation=payload.get("annotation"),
                    expected_version=payload.get("expected_version"),
                    actor=payload.get("actor", ""),
                    status=payload.get("status"),
                )
                self._send_json(HTTPStatus.OK, task)
            except Exception as error:
                self._handle_error(error)

    return WorkbenchHandler


def create_server(
    host: str,
    port: int,
    store: WorkbenchStore,
    ingestion_token: str,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), handler_factory(store, ingestion_token))
