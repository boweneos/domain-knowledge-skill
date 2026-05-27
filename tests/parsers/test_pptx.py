from pathlib import Path

from dks.locators import DocxLocator
from dks.parsers.pptx import _block_type_from_label, parse_pptx_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_pptx_yields_titles_and_body():
    items = parse_pptx_file(FIXTURES / "sample.pptx")
    headings = [i for i in items if i.block_type == "heading"]
    others = [i for i in items if i.block_type != "heading"]
    assert len(headings) == 2, f"expected 2 slide titles, got {len(headings)}"
    assert any("Claims Handling" in h.content for h in headings)
    assert any("Customer Notification" in h.content for h in headings)
    assert len(others) >= 2, "expected at least 2 body items across the deck"


def test_parse_pptx_locator_carries_slide_title_as_section():
    items = parse_pptx_file(FIXTURES / "sample.pptx")
    body_items = [i for i in items if i.block_type != "heading"]
    assert body_items, "expected at least one non-heading item"
    first = body_items[0]
    assert isinstance(first.locator, DocxLocator)
    # The body item under the first slide should carry the first slide title.
    assert "Claims Handling" in first.locator.section
    assert first.locator.paragraph_idx >= 0


def test_parse_pptx_section_changes_on_new_slide_title():
    items = parse_pptx_file(FIXTURES / "sample.pptx")
    sections = [i.locator.section for i in items if isinstance(i.locator, DocxLocator)]
    # We expect at least two distinct sections (one per slide title).
    assert len(set(sections)) >= 2


def test_block_type_from_label_maps_title_to_heading():
    assert _block_type_from_label("title") == "heading"
    assert _block_type_from_label("TITLE") == "heading"


def test_block_type_from_label_maps_list_item():
    assert _block_type_from_label("list_item") == "list"


def test_block_type_from_label_defaults_text():
    assert _block_type_from_label("paragraph") == "text"
    assert _block_type_from_label(None) == "text"
