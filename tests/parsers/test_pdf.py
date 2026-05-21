from pathlib import Path

from dks.locators import PdfLocator
from dks.parsers.pdf import parse_pdf_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_pdf_extracts_text_with_page_locator():
    items = parse_pdf_file(FIXTURES / "sample.pdf")
    assert len(items) >= 2, f"expected at least 2 items, got {len(items)}"
    pages = {i.locator.page for i in items if isinstance(i.locator, PdfLocator)}
    assert 1 in pages
    assert 2 in pages


def test_parse_pdf_content_includes_known_text():
    items = parse_pdf_file(FIXTURES / "sample.pdf")
    blob = " ".join(i.content for i in items)
    assert "Claims must be filed" in blob
    assert "Filing Window" in blob
