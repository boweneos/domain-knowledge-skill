from pathlib import Path

import pytest

from dks.block import NormalizedBlock
from dks.blockref import encode_blockref
from dks.locators import MarkdownLocator
from dks.store.blocks import get_block, list_blocks
from dks.writer import write_blocks


def _seed(tmp_path: Path) -> Path:
    loc1 = MarkdownLocator(heading_path=[], line_start=1, line_end=1)
    loc2 = MarkdownLocator(heading_path=[], line_start=3, line_end=3)
    blocks = [
        NormalizedBlock(
            source_file="claims.md",
            block_id=encode_blockref("claims.md", loc1),
            locator=loc1,
            block_type="text",
            content="first",
        ),
        NormalizedBlock(
            source_file="claims.md",
            block_id=encode_blockref("claims.md", loc2),
            locator=loc2,
            block_type="text",
            content="second",
        ),
    ]
    write_blocks(blocks, output_dir=tmp_path)
    return tmp_path


def test_list_blocks_for_source(tmp_path):
    _seed(tmp_path)
    ids = list_blocks(normalized_dir=tmp_path, source_file="claims.md")
    assert sorted(ids) == ["claims.md#L1-1", "claims.md#L3-3"]


def test_list_blocks_for_unknown_source(tmp_path):
    _seed(tmp_path)
    assert list_blocks(normalized_dir=tmp_path, source_file="nope.md") == []


def test_get_block_returns_full_block(tmp_path):
    _seed(tmp_path)
    block = get_block(normalized_dir=tmp_path, block_id="claims.md#L1-1")
    assert block.content == "first"
    assert isinstance(block.locator, MarkdownLocator)
    assert block.locator.line_start == 1


def test_get_block_missing_raises(tmp_path):
    _seed(tmp_path)
    with pytest.raises(FileNotFoundError):
        get_block(normalized_dir=tmp_path, block_id="claims.md#L99-99")
