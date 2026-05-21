"""Block store reader — load NormalizedBlocks from disk by source or by id."""

from pathlib import Path

from dks.block import NormalizedBlock, parse_markdown
from dks.writer import safe_filename


def list_blocks(normalized_dir: Path, source_file: str) -> list[str]:
    """Return all block_ids written for the given source_file."""
    source_dir = normalized_dir / Path(source_file).name
    if not source_dir.is_dir():
        return []
    ids: list[str] = []
    for md_file in sorted(source_dir.glob("*.md")):
        block = parse_markdown(md_file.read_text())
        if block.source_file == source_file:
            ids.append(block.block_id)
    return ids


def get_block(normalized_dir: Path, block_id: str) -> NormalizedBlock:
    """Load and return the NormalizedBlock with the given block_id."""
    source_part = block_id.split("#", 1)[0]
    source_basename = Path(source_part).name
    target = normalized_dir / source_basename / f"{safe_filename(block_id)}.md"
    if not target.exists():
        raise FileNotFoundError(f"block {block_id!r} not found at {target}")
    return parse_markdown(target.read_text())
