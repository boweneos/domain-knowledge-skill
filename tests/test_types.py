import pytest
from pydantic import ValidationError

from dks.locators import MarkdownLocator
from dks.types import TypedContentItem, classification_rank


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


def test_classification_rank_ordering():
    assert classification_rank("public") == 0
    assert classification_rank("internal") == 1
    assert classification_rank("confidential") == 2
    assert classification_rank("restricted") == 3


def test_classification_rank_relative_ordering():
    assert classification_rank("internal") > classification_rank("public")
    assert classification_rank("confidential") > classification_rank("internal")
    assert classification_rank("restricted") > classification_rank("confidential")
