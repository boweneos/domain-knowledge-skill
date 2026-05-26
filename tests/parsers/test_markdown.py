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


def test_parse_markdown_strips_utf8_bom(tmp_path):
    src = tmp_path / "bom.md"
    # Write with explicit UTF-8 BOM (﻿ encoded as utf-8 = b'\xef\xbb\xbf')
    src.write_bytes("﻿# Heading\n\nA paragraph.\n".encode())
    items = parse_markdown_file(src)
    headings = [i for i in items if i.block_type == "heading"]
    assert len(headings) == 1
    # The BOM should be stripped from the heading content
    assert "﻿" not in headings[0].content
    assert "# Heading" in headings[0].content


def test_parse_markdown_detects_code_fences(tmp_path):
    src = tmp_path / "x.md"
    src.write_text(
        "Some prose.\n\n"
        "```python\n"
        "def foo():\n"
        "    return 42\n"
        "```\n\n"
        "More prose.\n"
    )
    items = parse_markdown_file(src)
    code_items = [i for i in items if i.block_type == "code"]
    assert len(code_items) == 1
    assert "def foo()" in code_items[0].content
    assert "return 42" in code_items[0].content
    # Fence lines themselves should NOT be in the code content
    assert "```" not in code_items[0].content
    # Surrounding prose should be separate text blocks
    text_items = [i for i in items if i.block_type == "text"]
    bodies = " ".join(t.content for t in text_items)
    assert "Some prose" in bodies
    assert "More prose" in bodies


def test_parse_markdown_handles_tilde_fences(tmp_path):
    src = tmp_path / "x.md"
    src.write_text("~~~\nplain code\n~~~\n")
    items = parse_markdown_file(src)
    code_items = [i for i in items if i.block_type == "code"]
    assert len(code_items) == 1
    assert code_items[0].content == "plain code"


def test_parse_markdown_unterminated_fence_emits_code_to_eof(tmp_path):
    src = tmp_path / "x.md"
    src.write_text("```\nleft open\nstill open\n")
    items = parse_markdown_file(src)
    code_items = [i for i in items if i.block_type == "code"]
    assert len(code_items) == 1
    assert "left open" in code_items[0].content
    assert "still open" in code_items[0].content
