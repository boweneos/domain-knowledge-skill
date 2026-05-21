import pytest
from pydantic import ValidationError

from dks.locators import MarkdownLocator
from dks.types import TypedContentItem


def test_typed_content_item_basic():
    item = TypedContentItem(
        content="Hello world",
        block_type="text",
        locator=MarkdownLocator(heading_path=["A"], line_start=1, line_end=1),
    )
    assert item.content == "Hello world"
    assert item.block_type == "text"
    assert item.locator.kind == "md"


def test_typed_content_item_rejects_empty_content():
    with pytest.raises(ValidationError):
        TypedContentItem(
            content="",
            block_type="text",
            locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        )


def test_typed_content_item_default_block_type_is_text():
    item = TypedContentItem(
        content="x",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
    )
    assert item.block_type == "text"
