from dks.block import NormalizedBlock, parse_markdown, to_markdown
from dks.locators import MarkdownLocator


def test_normalized_block_default_classification_is_internal():
    block = NormalizedBlock(
        source_file="a.md",
        block_id="a.md#L1-1",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        block_type="text",
        content="x",
    )
    assert block.classification == "internal"


def test_normalized_block_accepts_all_classification_levels():
    for level in ("public", "internal", "confidential", "restricted"):
        block = NormalizedBlock(
            source_file="a.md",
            block_id="a.md#L1-1",
            locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
            block_type="text",
            content="x",
            classification=level,
        )
        assert block.classification == level


def test_normalized_block_roundtrip_preserves_classification():
    original = NormalizedBlock(
        source_file="a.md",
        block_id="a.md#L1-1",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        block_type="text",
        content="x",
        classification="confidential",
    )
    md = to_markdown(original)
    parsed = parse_markdown(md)
    assert parsed.classification == "confidential"


def _make_block() -> NormalizedBlock:
    return NormalizedBlock(
        source_file="notes/handling.md",
        block_id="notes/handling.md#L5-7",
        locator=MarkdownLocator(heading_path=["Claims", "Filing"], line_start=5, line_end=7),
        block_type="text",
        content="Claims must be filed within 30 days.",
    )


def test_to_markdown_includes_frontmatter_and_content():
    md = to_markdown(_make_block())
    assert md.startswith("---\n")
    assert '"block_id":' in md
    assert '"source_file":' in md
    assert "Claims must be filed within 30 days." in md


def test_to_markdown_roundtrip():
    original = _make_block()
    md = to_markdown(original)
    parsed = parse_markdown(md)
    assert parsed == original


def test_parse_markdown_rejects_missing_frontmatter():
    import pytest

    with pytest.raises(ValueError, match="frontmatter"):
        parse_markdown("just some plain text\n")


def test_parse_markdown_rejects_unterminated_frontmatter():
    import pytest

    with pytest.raises(ValueError, match="frontmatter"):
        parse_markdown("---\nblock_id: x\nstill in frontmatter\n")


def test_normalized_block_default_redacted_is_false():
    block = NormalizedBlock(
        source_file="a.md",
        block_id="a.md#L1-1",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        block_type="text",
        content="x",
    )
    assert block.redacted is False


def test_normalized_block_redacted_persists_through_roundtrip():
    original = NormalizedBlock(
        source_file="a.md",
        block_id="a.md#L1-1",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        block_type="text",
        content="[REDACTED:PERSON] phoned in",
        classification="confidential",
        redacted=True,
    )
    md = to_markdown(original)
    parsed = parse_markdown(md)
    assert parsed.redacted is True
    assert parsed.content.startswith("[REDACTED:")
