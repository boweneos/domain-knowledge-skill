from pathlib import Path

from dks.locators import DocxLocator
from dks.parsers.docx import parse_docx_file

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
