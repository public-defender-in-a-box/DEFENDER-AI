"""PDF and image text extraction service."""

import io
from pathlib import Path

from PyPDF2 import PdfReader


async def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file.

    Falls back to OCR (pytesseract) if the PDF contains scanned images.
    """
    reader = PdfReader(io.BytesIO(file_bytes))
    text_parts = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)

    text = "\n".join(text_parts)

    # If no text extracted, try OCR
    if not text.strip():
        text = await _ocr_fallback(file_bytes)

    return text


async def _ocr_fallback(file_bytes: bytes) -> str:
    """OCR fallback for scanned documents."""
    try:
        import pytesseract
        from PIL import Image
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(file_bytes)
        text_parts = []
        for image in images:
            text_parts.append(pytesseract.image_to_string(image))
        return "\n".join(text_parts)
    except ImportError:
        return "[OCR not available — install pytesseract and pdf2image]"


async def extract_text_from_image(file_bytes: bytes) -> str:
    """Extract text from an image file using OCR."""
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(file_bytes))
        return pytesseract.image_to_string(image)
    except ImportError:
        return "[OCR not available — install pytesseract]"
