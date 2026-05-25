from pathlib import Path

from dks.block import NormalizedBlock, parse_markdown
from dks.blockref import encode_blockref
from dks.layers import KbLayer
from dks.locators import MarkdownLocator
from dks.writer import safe_filename, write_blocks


def _block(source: str, start: int, end: int, content: str) -> NormalizedBlock:
    loc = MarkdownLocator(heading_path=[], line_start=start, line_end=end)
    return NormalizedBlock(
        source_file=source,
        block_id=encode_blockref(source, loc),
        locator=loc,
        block_type="text",
        content=content,
    )


def test_write_blocks_creates_files(tmp_path: Path):
    layer = KbLayer(name="project", base=tmp_path)
    blocks = [_block("notes.md", 1, 1, "first"), _block("notes.md", 3, 5, "second")]
    written = write_blocks(blocks, layer)
    assert len(written) == 2
    for p in written:
        assert p.exists()
        # The file lives at <base>/normalized/<source_basename>/<safe_id>.md
        assert p.parent.parent == tmp_path / "normalized"


def test_write_blocks_overwrites_on_rerun(tmp_path: Path):
    layer = KbLayer(name="project", base=tmp_path)
    [original] = write_blocks([_block("a.md", 1, 1, "v1")], layer)
    [rewritten] = write_blocks([_block("a.md", 1, 1, "v2")], layer)
    assert original == rewritten
    assert parse_markdown(rewritten.read_text()).content == "v2"


def test_safe_filename_strips_unsafe_chars():
    assert safe_filename("a/b.md#L1-3") == "a__b.md__L1-3"
    assert safe_filename("x.pdf#p5#3.2") == "x.pdf__p5__3.2"


def test_write_blocks_empty_list_no_op(tmp_path: Path):
    layer = KbLayer(name="project", base=tmp_path)
    assert write_blocks([], layer) == []
