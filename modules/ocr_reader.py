"""
Label photo -> ingredient text (REAL if an OCR engine is installed, STUB otherwise).

Engine order:
  1. EasyOCR   (pip install easyocr; downloads ~100 MB of models on first use)
  2. Tesseract (pip install pytesseract + `brew install tesseract tesseract-lang`)
  3. Stub      - returns a documented demo label so the skeleton still runs end to end.

The UI always shows the extracted text in an editable box, so a parent (or the
demo presenter) can correct OCR mistakes before analysis - a human-in-the-loop
safety step.
"""

from __future__ import annotations

import io
import re

STUB_TEXT = (
    "Ingredientes: harina de trigo, azúcar, aceite de girasol, suero lácteo en polvo, "
    "huevo, lecitina de soja, gasificante (E500), sal, aromas. "
    "Puede contener trazas de frutos de cáscara y sésamo."
)

_easyocr_reader = None


def available_engines() -> list[str]:
    engines = []
    try:
        import easyocr  # noqa: F401
        engines.append("easyocr")
    except Exception:
        pass
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        engines.append("tesseract")
    except Exception:
        pass
    return engines


def _load_image(image_bytes: bytes):
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    # Upscale small phone crops - OCR works better on ~2000 px wide images
    if img.width < 1200:
        scale = 1200 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    return img


def _run_easyocr(image_bytes: bytes) -> str:
    global _easyocr_reader
    import numpy as np
    import easyocr
    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(["es", "en"], gpu=False, verbose=False)
    img = np.array(_load_image(image_bytes))
    lines = _easyocr_reader.readtext(img, detail=0, paragraph=True)
    return " ".join(lines)


def _run_tesseract(image_bytes: bytes) -> str:
    import pytesseract
    from PIL import ImageOps
    img = ImageOps.grayscale(_load_image(image_bytes))
    try:
        return pytesseract.image_to_string(img, lang="spa+eng")
    except pytesseract.TesseractError:
        return pytesseract.image_to_string(img)


def extract_ingredients_section(text: str) -> str:
    """Keep the part of the label after 'Ingredientes:' / 'Ingredients:' if present."""
    m = re.search(r"(ingredientes|ingredients|ingrédients)\s*[:\-]?", text, flags=re.I)
    return text[m.end():].strip() if m else text.strip()


def read_label(image_bytes: bytes | None) -> dict:
    """
    Returns {"text", "engine", "is_stub", "error"}.
    Never raises: on any failure, falls back to the stub text and says so.
    """
    if not image_bytes:
        return {"text": STUB_TEXT, "engine": "stub", "is_stub": True,
                "error": "No image provided - using demo label text."}

    errors = []
    for engine in available_engines():
        try:
            raw = _run_easyocr(image_bytes) if engine == "easyocr" else _run_tesseract(image_bytes)
            text = re.sub(r"\s+", " ", extract_ingredients_section(raw)).strip()
            if len(text) >= 8:
                return {"text": text, "engine": engine, "is_stub": False, "error": None}
            errors.append(f"{engine}: no readable text found")
        except Exception as exc:  # OCR libs raise many exception types
            errors.append(f"{engine}: {exc.__class__.__name__}: {exc}")

    reason = "; ".join(errors) if errors else "No OCR engine installed (EasyOCR / Tesseract)."
    return {"text": STUB_TEXT, "engine": "stub", "is_stub": True,
            "error": f"{reason} Using demo label text - edit it to match your photo."}
