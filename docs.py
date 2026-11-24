"""Turn an invoice file into what a model can read: a text layer, or page images."""
from __future__ import annotations

import base64
import io
import pathlib

from PIL import Image

MAX_EDGE = 1568  # longest side sent to the vision model


class NoTextLayer(Exception):
    """The file is a scan or photo: there is no text to read without vision."""


def pdf_text(path: str) -> str:
    if pathlib.Path(path).suffix.lower() != ".pdf":
        raise NoTextLayer(f"{pathlib.Path(path).name} is an image, so it has no text layer.")
    from pypdf import PdfReader
    text = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages).strip()
    if len(text) < 20:
        raise NoTextLayer(f"{pathlib.Path(path).name} has no usable text layer (likely a scan).")
    return text


def page_images(path: str) -> list[Image.Image]:
    if pathlib.Path(path).suffix.lower() == ".pdf":
        import pypdfium2 as pdfium
        return [p.render(scale=150 / 72).to_pil() for p in pdfium.PdfDocument(path)]
    return [Image.open(path)]


def to_data_url(img: Image.Image) -> str:
    img = img.convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)  # ~5x smaller than PNG, still sharp enough to read
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
