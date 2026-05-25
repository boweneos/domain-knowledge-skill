from pathlib import Path

import pytest

from dks.block import NormalizedBlock
from dks.blockref import encode_blockref
from dks.layers import KbLayer, KbLayers
from dks.locators import MarkdownLocator
from dks.store.blocks import get_block, list_blocks
from dks.writer import write_blocks


def _layer(name: str, root: Path) -> KbLayer:
    return KbLayer(name=name, base=root)


def _block(source: str, start: int, end: int, content: str) -> NormalizedBlock:
    loc = MarkdownLocator(heading_path=[], line_start=start, line_end=end)
    return NormalizedBlock(
        source_file=source,
        block_id=encode_blockref(source, loc),
        locator=loc,
        block_type="text",
        content=content,
    )


def _seed(layer: KbLayer, source: str, content_pairs: list[tuple[int, int, str]]) -> None:
    blocks = [_block(source, s, e, c) for s, e, c in content_pairs]
    write_blocks(blocks, layer)


def test_list_blocks_project_only(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    _seed(proj, "claims.md", [(1, 1, "a"), (3, 3, "b")])
    hits = list_blocks(layers, source_file="claims.md")
    assert sorted(h.block_id for h in hits) == ["claims.md#L1-1", "claims.md#L3-3"]
    assert all(h.layer == "project" for h in hits)


def test_list_blocks_global_only(tmp_path):
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=None, global_layer=glb)
    _seed(glb, "claims.md", [(1, 1, "a")])
    [hit] = list_blocks(layers, source_file="claims.md")
    assert hit.block_id == "claims.md#L1-1"
    assert hit.layer == "global"


def test_list_blocks_merges_layers(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    _seed(proj, "claims.md", [(1, 1, "proj-1")])
    _seed(glb, "claims.md", [(1, 1, "glob-1"), (3, 3, "glob-3")])
    hits = list_blocks(layers, source_file="claims.md")
    by_id = {h.block_id: h.layer for h in hits}
    assert by_id["claims.md#L1-1"] == "project"  # project shadows
    assert by_id["claims.md#L3-3"] == "global"


def test_get_block_project_wins(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    _seed(proj, "claims.md", [(1, 1, "proj-content")])
    _seed(glb, "claims.md", [(1, 1, "global-content")])
    block, layer_name = get_block(layers, block_id="claims.md#L1-1")
    assert block.content == "proj-content"
    assert layer_name == "project"


def test_get_block_falls_back_to_global(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    _seed(glb, "claims.md", [(7, 9, "only-global")])
    block, layer_name = get_block(layers, block_id="claims.md#L7-9")
    assert block.content == "only-global"
    assert layer_name == "global"


def test_get_block_missing_raises(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    with pytest.raises(FileNotFoundError):
        get_block(layers, block_id="absent.md#L1-1")
