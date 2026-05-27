from pathlib import Path

from dks.block import NormalizedBlock
from dks.hints import pageindex_hint
from dks.layers import KbLayer
from dks.locators import DocxLocator, MarkdownLocator, PdfLocator


def _docx_block(section: str, idx: int) -> NormalizedBlock:
    return NormalizedBlock(
        source_file="x.docx",
        block_id=f"x.docx#§{section}#p{idx}",
        locator=DocxLocator(section=section, paragraph_idx=idx),
        block_type="text",
        content="x",
    )


def _pdf_block(page: int, section: str | None = None) -> NormalizedBlock:
    return NormalizedBlock(
        source_file="x.pdf",
        block_id=f"x.pdf#p{page}" + (f"#{section}" if section else ""),
        locator=PdfLocator(page=page, section=section),
        block_type="text",
        content="x",
    )


def _layer(tmp_path: Path) -> KbLayer:
    base = tmp_path / "kb"
    base.mkdir()
    (base / "index").mkdir()
    return KbLayer(name="test", base=base)


def test_no_hint_below_both_thresholds(tmp_path):
    layer = _layer(tmp_path)
    blocks = [_docx_block("body", i) for i in range(10)]
    assert pageindex_hint(layer, "x.docx", blocks) is None


def test_hint_fires_on_block_count(tmp_path):
    layer = _layer(tmp_path)
    blocks = [_docx_block("body", i) for i in range(80)]
    hint = pageindex_hint(layer, "x.docx", blocks)
    assert hint is not None
    assert "x.docx" in hint
    assert "80 blocks" in hint
    assert "dks-build-pageindex" in hint


def test_hint_fires_on_section_count(tmp_path):
    layer = _layer(tmp_path)
    # 8 distinct sections, well under 80 blocks
    blocks = [_docx_block(f"section-{i}", 0) for i in range(8)]
    hint = pageindex_hint(layer, "x.docx", blocks)
    assert hint is not None
    assert "8 sections" in hint


def test_no_hint_when_pageindex_already_exists(tmp_path):
    layer = _layer(tmp_path)
    (layer.index_dir / "x.docx.pageindex.json").write_text("{}")
    blocks = [_docx_block("body", i) for i in range(80)]
    assert pageindex_hint(layer, "x.docx", blocks) is None


def test_headerless_pdf_only_trips_on_block_count(tmp_path):
    """Headerless PDFs (no section per locator) shouldn't trip section threshold."""
    layer = _layer(tmp_path)
    # 30 pages, no section info each → distinct sections = 0
    blocks = [_pdf_block(p) for p in range(1, 31)]
    assert pageindex_hint(layer, "x.pdf", blocks) is None


def test_pdf_with_explicit_sections_trips_on_section_count(tmp_path):
    layer = _layer(tmp_path)
    blocks = [_pdf_block(p, section=f"§{p}") for p in range(1, 10)]
    hint = pageindex_hint(layer, "x.pdf", blocks)
    assert hint is not None


def test_env_override_lowers_block_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("DKS_PAGEINDEX_HINT_BLOCKS", "5")
    layer = _layer(tmp_path)
    blocks = [_docx_block("body", i) for i in range(5)]
    assert pageindex_hint(layer, "x.docx", blocks) is not None


def test_env_override_raises_block_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("DKS_PAGEINDEX_HINT_BLOCKS", "200")
    monkeypatch.setenv("DKS_PAGEINDEX_HINT_SECTIONS", "100")
    layer = _layer(tmp_path)
    blocks = [_docx_block(f"section-{i}", 0) for i in range(80)]
    # 80 blocks, 80 sections — but thresholds are 200 / 100. Hint suppressed.
    assert pageindex_hint(layer, "x.docx", blocks) is None


def test_markdown_heading_path_counts_as_section(tmp_path):
    layer = _layer(tmp_path)
    blocks = [
        NormalizedBlock(
            source_file="x.md",
            block_id=f"x.md#L{i}-{i}",
            locator=MarkdownLocator(heading_path=[f"H{i}"], line_start=i, line_end=i),
            block_type="text",
            content="x",
        )
        for i in range(1, 10)
    ]
    hint = pageindex_hint(layer, "x.md", blocks)
    assert hint is not None
