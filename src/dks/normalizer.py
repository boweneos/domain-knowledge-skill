"""Normalizer — turns a parser's TypedContentItem list into NormalizedBlocks
with citation-checked block_ids.
"""

from collections.abc import Iterable

from dks.block import NormalizedBlock
from dks.blockref import encode_blockref
from dks.citation_guard import check_block
from dks.types import TypedContentItem


def normalize(source_file: str, items: Iterable[TypedContentItem]) -> list[NormalizedBlock]:
    blocks: list[NormalizedBlock] = []
    for item in items:
        block_id = encode_blockref(source_file, item.locator)
        block = NormalizedBlock(
            source_file=source_file,
            block_id=block_id,
            locator=item.locator,
            block_type=item.block_type,
            content=item.content,
        )
        check_block(block)  # raises CitationError on inconsistency
        blocks.append(block)
    return blocks
