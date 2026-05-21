"""Writer — persists NormalizedBlocks to disk.

Layout: <output_dir>/<source_basename>/<safe_block_filename>.md
where source_basename is the relative source path with separators preserved as
folder structure under output_dir.
"""

from collections.abc import Iterable
from pathlib import Path

from dks.block import NormalizedBlock, to_markdown


def safe_filename(s: str) -> str:
    """Make a string safe for filesystem use: replace / and # with __."""
    return s.replace("/", "__").replace("#", "__")


def write_blocks(blocks: Iterable[NormalizedBlock], output_dir: Path) -> list[Path]:
    output_dir = Path(output_dir)
    written: list[Path] = []
    for block in blocks:
        source_basename = Path(block.source_file).name
        target_dir = output_dir / source_basename
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{safe_filename(block.block_id)}.md"
        target.write_text(to_markdown(block))
        written.append(target)
    return written
