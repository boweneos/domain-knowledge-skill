"""Citation guard — rejects NormalizedBlocks whose block_id is inconsistent
with their (source_file, locator). Structural enforcement of citation discipline.
"""

from dks.block import NormalizedBlock
from dks.blockref import decode_blockref, encode_blockref


class CitationError(ValueError):
    """Raised when a block fails the citation completeness/consistency check."""


def check_block(block: NormalizedBlock) -> None:
    """Raise CitationError if the block_id is not the canonical encoding
    of (source_file, locator). Returns None on success.
    """
    decoded_source, _ = decode_blockref(block.block_id)
    if decoded_source != block.source_file:
        raise CitationError(
            f"block_id source_file does not match block source_file: "
            f"{decoded_source!r} vs {block.source_file!r}"
        )

    expected_ref = encode_blockref(block.source_file, block.locator)
    if block.block_id != expected_ref:
        raise CitationError(
            f"block_id does not match locator: got {block.block_id!r}, expected {expected_ref!r}"
        )
