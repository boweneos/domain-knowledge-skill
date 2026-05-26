from pathlib import Path

from dks.locators import DocxLocator
from dks.parsers.docx import _block_type_from_label, parse_docx_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_docx_yields_headings_and_paragraphs():
    items = parse_docx_file(FIXTURES / "sample.docx")
    headings = [i for i in items if i.block_type == "heading"]
    paragraphs = [i for i in items if i.block_type == "text"]
    assert len(headings) == 2
    assert len(paragraphs) == 2
    assert any("Claims Handling" in h.content for h in headings)


def test_parse_docx_locator_carries_section_and_index():
    items = parse_docx_file(FIXTURES / "sample.docx")
    paragraphs = [i for i in items if i.block_type == "text"]
    assert paragraphs, "expected at least one paragraph block"
    p = paragraphs[0]
    assert isinstance(p.locator, DocxLocator)
    assert p.locator.section
    assert p.locator.paragraph_idx >= 0


def test_block_type_from_label_maps_header():
    assert _block_type_from_label("section_header") == "heading"
    assert _block_type_from_label("HEADER") == "heading"


def test_block_type_from_label_maps_list():
    assert _block_type_from_label("list_item") == "list"
    assert _block_type_from_label("enumeration") == "list"


def test_block_type_from_label_maps_table():
    assert _block_type_from_label("table") == "table"


def test_block_type_from_label_maps_code():
    assert _block_type_from_label("code") == "code"
    assert _block_type_from_label("code_block") == "code"


def test_block_type_from_label_defaults_text():
    assert _block_type_from_label("paragraph") == "text"
    assert _block_type_from_label("") == "text"
    assert _block_type_from_label(None) == "text"
