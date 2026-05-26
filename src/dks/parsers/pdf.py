"""PDF parser via pypdf — text extraction with page-level PdfLocator.

Phase 2 v0 only handles clean, text-extractable PDFs (no OCR, no complex
layout). Heuristics: each page contributes one TypedContentItem per
non-empty extracted block, with page index recorded in the locator.

**Limitation — block_type is always 'text' for PDFs.** pypdf extracts a flat
text stream per page with no preserved structure markers, so we can't
reliably detect tables, lists, headings, or code blocks. Section / clause
detection would require a layout-aware parser (MinerU, pdfplumber with
custom heuristics, etc.) and is a deferred upgrade — see the Phase 2
carryover notes for context.
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
