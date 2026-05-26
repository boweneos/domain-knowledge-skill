from dks.locators import MarkdownLocator
from dks.normalizer import normalize
from dks.types import TypedContentItem


def test_normalize_simple():
    items = [
        TypedContentItem(
            content="Hello world",
            locator=MarkdownLocator(heading_path=["A"], line_start=1, line_end=1),
        ),
        TypedContentItem(
            content="Goodbye",
            locator=MarkdownLocator(heading_path=["A"], line_start=3, line_end=3),
        ),
    ]
    blocks = normalize(source_file="notes.md", items=items)
    assert len(blocks) == 2
    assert blocks[0].block_id == "notes.md#L1-1"
    assert blocks[1].block_id == "notes.md#L3-3"
    assert blocks[0].content == "Hello world"
    assert blocks[0].source_file == "notes.md"


def test_normalize_empty_list_returns_empty():
    assert normalize(source_file="x.md", items=[]) == []


def test_normalize_propagates_block_type():
    items = [
        TypedContentItem(
            content="# Title",
            block_type="heading",
            locator=MarkdownLocator(heading_path=["Title"], line_start=1, line_end=1),
        ),
    ]
    [block] = normalize(source_file="x.md", items=items)
    assert block.block_type == "heading"


def test_normalize_default_classification_is_internal():
    items = [
        TypedContentItem(
            content="hello",
            locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        ),
    ]
    [block] = normalize(source_file="a.md", items=items)
    assert block.classification == "internal"


def test_normalize_propagates_explicit_classification():
    items = [
        TypedContentItem(
            content="hello",
            locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        ),
        TypedContentItem(
            content="goodbye",
            locator=MarkdownLocator(heading_path=[], line_start=3, line_end=3),
        ),
    ]
    blocks = normalize(source_file="a.md", items=items, classification="confidential")
    assert all(b.classification == "confidential" for b in blocks)
