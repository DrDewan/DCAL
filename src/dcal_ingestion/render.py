from __future__ import annotations

import hashlib
import io
import warnings
from pathlib import Path
from typing import Iterable

import pymupdf
from PIL import Image, ImageOps, ImageSequence

from .models import RENDER_PROFILE, RenderedPage, SourceRejected


MAX_SOURCE_BYTES = 250 * 1024 * 1024
MAX_SOURCE_PAGES = 500
MAX_PAGE_PIXELS = 150_000_000
PDF_DPI = 300

SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "image/bmp",
}


def _check_source_size(content: bytes) -> None:
    if not content:
        raise SourceRejected("empty_source", "source file is empty")
    if len(content) > MAX_SOURCE_BYTES:
        raise SourceRejected(
            "source_too_large",
            f"source exceeds the {MAX_SOURCE_BYTES // (1024 * 1024)} MiB safety limit",
        )


def _rgb(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")


def _png_page(image: Image.Image, page_index: int) -> RenderedPage:
    width, height = image.size
    if width < 1 or height < 1:
        raise SourceRejected("invalid_dimensions", "page has invalid dimensions")
    if width * height > MAX_PAGE_PIXELS:
        raise SourceRejected(
            "page_too_large",
            f"page exceeds the {MAX_PAGE_PIXELS:,}-pixel safety limit",
        )
    output = io.BytesIO()
    _rgb(image).save(output, format="PNG", optimize=False, compress_level=6)
    content = output.getvalue()
    return RenderedPage(
        page_index=page_index,
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        width=width,
        height=height,
        render_profile=RENDER_PROFILE,
    )


def _render_image(content: bytes) -> list[RenderedPage]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                pages: list[RenderedPage] = []
                for index, frame in enumerate(ImageSequence.Iterator(source), start=1):
                    if index > MAX_SOURCE_PAGES:
                        raise SourceRejected(
                            "too_many_pages",
                            f"source exceeds the {MAX_SOURCE_PAGES}-page safety limit",
                        )
                    frame.load()
                    pages.append(_png_page(frame.copy(), index))
                return pages
    except SourceRejected:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise SourceRejected("decompression_bomb", "image dimensions are unsafe") from error
    except (OSError, ValueError) as error:
        raise SourceRejected("invalid_image", "image could not be decoded") from error


def _render_pdf(content: bytes) -> list[RenderedPage]:
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as error:
        raise SourceRejected("invalid_pdf", "PDF could not be decoded") from error
    try:
        if document.needs_pass:
            raise SourceRejected("encrypted_pdf", "encrypted PDFs are not accepted")
        if document.page_count < 1:
            raise SourceRejected("empty_pdf", "PDF contains no pages")
        if document.page_count > MAX_SOURCE_PAGES:
            raise SourceRejected(
                "too_many_pages",
                f"source exceeds the {MAX_SOURCE_PAGES}-page safety limit",
            )

        pages: list[RenderedPage] = []
        matrix = pymupdf.Matrix(PDF_DPI / 72, PDF_DPI / 72)
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(
                matrix=matrix, colorspace=pymupdf.csRGB, alpha=False
            )
            if pixmap.width * pixmap.height > MAX_PAGE_PIXELS:
                raise SourceRejected(
                    "page_too_large",
                    f"page exceeds the {MAX_PAGE_PIXELS:,}-pixel safety limit",
                )
            rendered = pixmap.tobytes("png")
            pages.append(
                RenderedPage(
                    page_index=index,
                    content=rendered,
                    sha256=hashlib.sha256(rendered).hexdigest(),
                    width=pixmap.width,
                    height=pixmap.height,
                    render_profile=RENDER_PROFILE,
                )
            )
        return pages
    finally:
        document.close()


def render_source(content: bytes, mime_type: str) -> list[RenderedPage]:
    _check_source_size(content)
    if mime_type == "application/pdf":
        return _render_pdf(content)
    if mime_type in SUPPORTED_IMAGE_MIME_TYPES:
        return _render_image(content)
    raise SourceRejected(
        "unsupported_media_type",
        "only PDF, JPEG, PNG, TIFF, WebP, and BMP sources are accepted",
    )


def render_local_file(path: str | Path, mime_type: str) -> Iterable[RenderedPage]:
    return render_source(Path(path).read_bytes(), mime_type)
