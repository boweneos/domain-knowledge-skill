"""PDF parser via pypdf — text extraction with page-level PdfLocator.

Library chosen: pypdf>=4.0 (pure Python, no ML, no network I/O). It handles
clean, text-extractable PDFs (the Phase 2 v0 fixture is a 2-page reportlab PDF
with no images or complex layout). pdfplumber, pymupdf, or docling are
reasonable escalation paths if OCR or complex column layout is needed.

Phase 2 v0 scope: each page contributes one TypedContentItem per non-empty
paragraph block. Section detection is deferred to Phase 3.
"""

from pathlib import Path

from pypdf import PdfReader

from dks.locators import PdfLocator
from dks.types import TypedContentItem


def parse_pdf_file(path: Path) -> list[TypedContentItem]:
    """Parse a PDF file using pypdf and return typed content items.

    Each non-empty text block on a page becomes one TypedContentItem with a
    PdfLocator carrying the 1-based page number. Blank-line boundaries are used
    as paragraph delimiters within a page. block_type is always "text" for now.
    """
    reader = PdfReader(str(path))
    items: list[TypedContentItem] = []
    for page_idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        # Split on blank-line boundaries to get paragraph-like blocks
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]
        for para in paragraphs:
            items.append(
                TypedContentItem(
                    content=para,
                    block_type="text",
                    locator=PdfLocator(page=page_idx),
                )
            )
    return items
