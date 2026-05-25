"""Block store reader — layer-aware. Project shadows global on collision."""

from dataclasses import dataclass
from pathlib import Path

from dks.block import NormalizedBlock, parse_markdown
from dks.layers import KbLayers
from dks.writer import safe_filename


@dataclass(frozen=True)
class BlockHit:
    block_id: str
    layer: str


def list_blocks(layers: KbLayers, source_file: str) -> list[BlockHit]:
    """Return BlockHits for `source_file` across layers; project shadows global by block_id."""
    seen: dict[str, BlockHit] = {}
    for layer in layers.for_read():
        source_dir = layer.normalized_dir / Path(source_file).name
        if not source_dir.is_dir():
            continue
        for md_file in sorted(source_dir.glob("*.md")):
            block = parse_markdown(md_file.read_text())
            if block.source_file != source_file:
                continue
            if block.block_id not in seen:  # first-layer-wins == project shadows global
                seen[block.block_id] = BlockHit(block_id=block.block_id, layer=layer.name)
    return list(seen.values())


def get_block(layers: KbLayers, block_id: str) -> tuple[NormalizedBlock, str]:
    """Load the NormalizedBlock + which layer served it. Project first, fall back to global."""
    source_part = block_id.split("#", 1)[0]
    source_basename = Path(source_part).name
    for layer in layers.for_read():
        target = layer.normalized_dir / source_basename / f"{safe_filename(block_id)}.md"
        if target.exists():
            return parse_markdown(target.read_text()), layer.name
    raise FileNotFoundError(f"block {block_id!r} not found in any layer")
