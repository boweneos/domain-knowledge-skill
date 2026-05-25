"""Writer — persists NormalizedBlocks to disk under a KbLayer's normalized_dir."""

from collections.abc import Iterable
from pathlib import Path

from dks.block import NormalizedBlock, to_markdown
from dks.layers import KbLayer


def safe_filename(s: str) -> str:
    """Make a string safe for filesystem use: replace / and # with __."""
    return s.replace("/", "__").replace("#", "__")


def write_blocks(blocks: Iterable[NormalizedBlock], layer: KbLayer) -> list[Path]:
    """Persist blocks to `<layer.normalized_dir>/<source_basename>/<safe_id>.md`."""
    output_dir = layer.normalized_dir
    written: list[Path] = []
    for block in blocks:
        source_basename = Path(block.source_file).name
        target_dir = output_dir / source_basename
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{safe_filename(block.block_id)}.md"
        target.write_text(to_markdown(block))
        written.append(target)
    return written
