import pytest
from pydantic import ValidationError

from dks.locators import (
    DocxLocator,
    ExcelLocator,
    Locator,
    MarkdownLocator,
    PdfLocator,
)


def test_pdf_locator_minimal():
    loc = PdfLocator(page=14)
    assert loc.kind == "pdf"
    assert loc.page == 14
    assert loc.section is None
    assert loc.clause is None


def test_pdf_locator_with_section_and_clause():
    loc = PdfLocator(page=14, section="3.2", clause="3.2.1")
    assert loc.section == "3.2"
    assert loc.clause == "3.2.1"


def test_pdf_locator_rejects_zero_page():
    with pytest.raises(ValidationError):
        PdfLocator(page=0)


def test_docx_locator():
    loc = DocxLocator(section="Introduction", paragraph_idx=3)
    assert loc.kind == "docx"


def test_excel_locator():
    loc = ExcelLocator(sheet="Assumptions", cells="B2:D40")
    assert loc.kind == "excel"
    assert loc.cells == "B2:D40"


def test_markdown_locator():
    loc = MarkdownLocator(
        heading_path=["Claims Handling", "Filing Window"], line_start=5, line_end=7
    )
    assert loc.kind == "md"
    assert loc.heading_path == ["Claims Handling", "Filing Window"]


def test_markdown_locator_rejects_zero_line():
    with pytest.raises(ValidationError):
        MarkdownLocator(heading_path=[], line_start=0, line_end=1)


def test_locator_discriminated_union_roundtrip():
    """Pydantic should discriminate by `kind` when parsing dicts into Locator."""
    from pydantic import TypeAdapter

    adapter = TypeAdapter(Locator)
    parsed = adapter.validate_python({"kind": "pdf", "page": 1, "section": "1.0"})
    assert isinstance(parsed, PdfLocator)
    assert parsed.section == "1.0"


def test_markdown_locator_rejects_line_end_lt_line_start():
    with pytest.raises(ValidationError):
        MarkdownLocator(heading_path=[], line_start=5, line_end=3)


def test_markdown_locator_allows_equal_line_start_and_end():
    loc = MarkdownLocator(heading_path=[], line_start=5, line_end=5)
    assert loc.line_start == 5
    assert loc.line_end == 5
