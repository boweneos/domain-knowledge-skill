from pathlib import Path

from dks.locators import MarkdownLocator
from dks.parsers.markdown import parse_markdown_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_simple_markdown() -> None:
    items = parse_markdown_file(FIXTURES / "sample_simple.md")
    assert len(items) == 1
    assert items[0].content == "This is a single paragraph with no headings."
    assert items[0].locator.kind == "md"
    assert isinstance(items[0].locator, MarkdownLocator)
    assert items[0].locator.heading_path == []
    assert items[0].block_type == "text"


def test_parse_markdown_with_headings() -> None:
    items = parse_markdown_file(FIXTURES / "sample_with_headings.md")

    # We expect:
    #   heading "Claims Handling"
    #   paragraph "Claims must be filed..."
    #   heading "Filing Window"
    #   paragraph "Subject to subsection..."
    #   heading "Extensions"
    #   paragraph "Only the regulator..."
    assert len(items) == 6
    headings = [i for i in items if i.block_type == "heading"]
    paragraphs = [i for i in items if i.block_type == "text"]
    assert len(headings) == 3
    assert len(paragraphs) == 3

    # The paragraph under H2 should have a heading_path of length 2
    filing_paragraph = next(p for p in paragraphs if "Subject to subsection" in p.content)
    assert isinstance(filing_paragraph.locator, MarkdownLocator)
    assert filing_paragraph.locator.heading_path == ["Claims Handling", "Filing Window"]

    # The paragraph under H3 should have a heading_path of length 3
    ext_paragraph = next(p for p in paragraphs if "Only the regulator" in p.content)
    assert isinstance(ext_paragraph.locator, MarkdownLocator)
    assert ext_paragraph.locator.heading_path == ["Claims Handling", "Filing Window", "Extensions"]


def test_parse_markdown_line_ranges_are_one_indexed_and_inclusive(tmp_path: Path) -> None:
    src = tmp_path / "x.md"
    src.write_text("alpha\nbeta\n\ngamma\n")
    items = parse_markdown_file(src)
    # "alpha\nbeta" is the first paragraph (lines 1-2); "gamma" is the second (line 4)
    assert isinstance(items[0].locator, MarkdownLocator)
    assert isinstance(items[1].locator, MarkdownLocator)
    assert items[0].locator.line_start == 1
    assert items[0].locator.line_end == 2
    assert items[1].locator.line_start == 4
    assert items[1].locator.line_end == 4
