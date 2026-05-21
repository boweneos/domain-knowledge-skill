from pathlib import Path

from dks.block import NormalizedBlock, parse_markdown
from dks.locators import MarkdownLocator
from dks.writer import safe_filename, write_blocks


def _block(source: str, start: int, end: int, content: str) -> NormalizedBlock:
    loc = MarkdownLocator(heading_path=[], line_start=start, line_end=end)
    from dks.blockref import encode_blockref

    return NormalizedBlock(
        source_file=source,
        block_id=encode_blockref(source, loc),
        locator=loc,
        block_type="text",
        content=content,
    )


def test_write_blocks_creates_files(tmp_path: Path):
    blocks = [
        _block("notes.md", 1, 1, "first"),
        _block("notes.md", 3, 5, "second"),
    ]
    written = write_blocks(blocks, output_dir=tmp_path)

    assert len(written) == 2
    for path in written:
        assert path.exists()
        assert path.parent.name == "notes.md"
        # roundtrip
        parsed = parse_markdown(path.read_text())
        assert parsed.source_file == "notes.md"


def test_write_blocks_overwrites_on_rerun(tmp_path: Path):
    [original] = write_blocks([_block("a.md", 1, 1, "v1")], output_dir=tmp_path)
    [rewritten] = write_blocks([_block("a.md", 1, 1, "v2")], output_dir=tmp_path)
    assert original == rewritten
    parsed = parse_markdown(rewritten.read_text())
    assert parsed.content == "v2"


def test_safe_filename_strips_unsafe_chars():
    assert safe_filename("a/b.md#L1-3") == "a__b.md__L1-3"
    assert safe_filename("x.pdf#p5#3.2") == "x.pdf__p5__3.2"


def test_write_blocks_empty_list_no_op(tmp_path: Path):
    assert write_blocks([], output_dir=tmp_path) == []
    assert list(tmp_path.iterdir()) == []
