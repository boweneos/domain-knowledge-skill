import pytest

from dks.block import NormalizedBlock
from dks.citation_guard import CitationError, check_block
from dks.locators import MarkdownLocator, PdfLocator


def _good_block() -> NormalizedBlock:
    return NormalizedBlock(
        source_file="a.md",
        block_id="a.md#L1-3",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=3),
        block_type="text",
        content="hi",
    )


def test_check_passes_on_valid_block():
    check_block(_good_block())  # must not raise


def test_check_rejects_mismatched_blockref():
    bad = _good_block().model_copy(update={"block_id": "a.md#L99-99"})
    with pytest.raises(CitationError, match="block_id does not match locator"):
        check_block(bad)


def test_check_rejects_mismatched_source_file():
    block = _good_block().model_copy(update={"source_file": "different.md"})
    with pytest.raises(CitationError, match="source_file"):
        check_block(block)


def test_check_passes_on_pdf_block():
    block = NormalizedBlock(
        source_file="x.pdf",
        block_id="x.pdf#p5#3.2",
        locator=PdfLocator(page=5, section="3.2"),
        block_type="text",
        content="hello",
    )
    check_block(block)
