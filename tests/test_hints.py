from pathlib import Path

from dks.block import NormalizedBlock
from dks.hints import (
    _strip_version_suffix,
    pageindex_hint,
    supersedes_candidate_hint,
    wiki_stale_hint,
)
from dks.layers import KbLayer, KbLayers
from dks.locators import DocxLocator, MarkdownLocator, PdfLocator
from dks.store.wiki import WikiEntry, write_wiki_entry


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


# --- wiki_stale_hint ----------------------------------------------------


def _make_entry(slug: str, source_refs: list[str]) -> WikiEntry:
    return WikiEntry(topic=f"Topic {slug}", slug=slug, source_refs=source_refs, body="x")


def test_wiki_stale_hint_none_when_no_entries(tmp_path):
    layers = KbLayers(project=KbLayer(name="project", base=tmp_path / "p"), global_layer=None)
    assert wiki_stale_hint(layers, "x.docx") is None


def test_wiki_stale_hint_none_when_no_entry_cites_source(tmp_path):
    proj = KbLayer(name="project", base=tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    write_wiki_entry(proj, _make_entry("unrelated", ["other.docx#§body#p1"]))
    assert wiki_stale_hint(layers, "x.docx") is None


def test_wiki_stale_hint_fires_for_citing_entry(tmp_path):
    proj = KbLayer(name="project", base=tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    write_wiki_entry(
        proj,
        _make_entry("cancer-rules", ["cancer.docx#§body#p1", "cancer.docx#§body#p2"]),
    )
    hint = wiki_stale_hint(layers, "cancer.docx")
    assert hint is not None
    assert "cancer-rules" in hint
    assert "@ project" in hint
    assert "2 citations" in hint
    assert "re-compile" in hint.lower()


def test_wiki_stale_hint_lists_multiple_entries_across_layers(tmp_path):
    proj = KbLayer(name="project", base=tmp_path / "p")
    glb = KbLayer(name="global", base=tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_wiki_entry(proj, _make_entry("project-entry", ["amend.docx#§body#p1"]))
    write_wiki_entry(
        glb,
        _make_entry("global-entry", ["amend.docx#§body#p2", "amend.docx#§body#p3"]),
    )
    hint = wiki_stale_hint(layers, "amend.docx")
    assert hint is not None
    assert "2 wiki entry(s)" in hint
    assert "project-entry @ project" in hint
    assert "global-entry @ global" in hint


def test_wiki_stale_hint_exact_source_match_not_prefix_collision(tmp_path):
    """An entry citing 'cancer-long.docx' should NOT be flagged when ingesting 'cancer.docx'."""
    proj = KbLayer(name="project", base=tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    write_wiki_entry(proj, _make_entry("entry", ["cancer-long.docx#§body#p1"]))
    assert wiki_stale_hint(layers, "cancer.docx") is None


# --- _strip_version_suffix ------------------------------------------------


def test_strip_version_suffix_handles_v_pattern():
    assert _strip_version_suffix("Futura - Mental Health v2") == "futura - mental health"
    assert _strip_version_suffix("policy_v10") == "policy"


def test_strip_version_suffix_handles_year_pattern():
    assert _strip_version_suffix("Encompass - Cannabis 2025") == "encompass - cannabis"
    assert _strip_version_suffix("rules-2026") == "rules"


def test_strip_version_suffix_handles_amendment_pattern():
    assert _strip_version_suffix("Mental Health Amendment 2026") == "mental health"
    assert _strip_version_suffix("rules - amendment") == "rules"


def test_strip_version_suffix_handles_disambiguator_pattern():
    assert _strip_version_suffix("Notes (1)") == "notes"
    assert _strip_version_suffix("file (3)") == "file"


def test_strip_version_suffix_chains_multiple_suffixes():
    assert _strip_version_suffix("policy v2 2026") == "policy"
    assert _strip_version_suffix("rules-amendment-v3") == "rules"


def test_strip_version_suffix_returns_empty_for_pure_suffix():
    assert _strip_version_suffix("v2") == ""
    assert _strip_version_suffix("2026") == ""


def test_strip_version_suffix_leaves_distinct_names_alone():
    assert _strip_version_suffix("encompass-mental-health") == "encompass-mental-health"
    assert _strip_version_suffix("Cannabis Use") == "cannabis use"


# --- supersedes_candidate_hint --------------------------------------------


def _make_source_dir(layer: KbLayer, name: str) -> None:
    (layer.normalized_dir / name).mkdir(parents=True, exist_ok=True)


def test_supersedes_hint_none_when_no_other_sources(tmp_path):
    proj = KbLayer(name="project", base=tmp_path / "p")
    proj.normalized_dir.mkdir(parents=True)
    layers = KbLayers(project=proj, global_layer=None)
    assert supersedes_candidate_hint(layers, "new.docx") is None


def test_supersedes_hint_fires_on_version_suffix_match(tmp_path):
    proj = KbLayer(name="project", base=tmp_path / "p")
    proj.normalized_dir.mkdir(parents=True)
    layers = KbLayers(project=proj, global_layer=None)
    _make_source_dir(proj, "Futura - Mental Health.docx")
    hint = supersedes_candidate_hint(layers, "Futura - Mental Health v2.docx")
    assert hint is not None
    assert "Futura - Mental Health.docx" in hint
    assert "@ project" in hint
    assert "--supersedes" in hint


def test_supersedes_hint_fires_on_year_suffix_match(tmp_path):
    proj = KbLayer(name="project", base=tmp_path / "p")
    proj.normalized_dir.mkdir(parents=True)
    layers = KbLayers(project=proj, global_layer=None)
    _make_source_dir(proj, "Encompass - Cannabis Use.pdf")
    hint = supersedes_candidate_hint(layers, "Encompass - Cannabis Use 2026.pdf")
    assert hint is not None
    assert "Encompass - Cannabis Use.pdf" in hint


def test_supersedes_hint_excludes_self(tmp_path):
    proj = KbLayer(name="project", base=tmp_path / "p")
    proj.normalized_dir.mkdir(parents=True)
    layers = KbLayers(project=proj, global_layer=None)
    _make_source_dir(proj, "same.docx")
    # Comparing a source to itself should not trip the hint
    assert supersedes_candidate_hint(layers, "same.docx") is None


def test_supersedes_hint_skips_unrelated_names(tmp_path):
    proj = KbLayer(name="project", base=tmp_path / "p")
    proj.normalized_dir.mkdir(parents=True)
    layers = KbLayers(project=proj, global_layer=None)
    _make_source_dir(proj, "Encompass - Mental Health.docx")
    # Different product line — should NOT be flagged
    assert supersedes_candidate_hint(layers, "Futura - Cancer.docx") is None


def test_supersedes_hint_lists_candidates_across_layers(tmp_path):
    proj = KbLayer(name="project", base=tmp_path / "p")
    glb = KbLayer(name="global", base=tmp_path / "g")
    proj.normalized_dir.mkdir(parents=True)
    glb.normalized_dir.mkdir(parents=True)
    layers = KbLayers(project=proj, global_layer=glb)
    _make_source_dir(proj, "rules.docx")
    _make_source_dir(glb, "rules-2024.docx")
    hint = supersedes_candidate_hint(layers, "rules-v3.docx")
    assert hint is not None
    # Both layers' candidates should appear
    assert "rules.docx @ project" in hint
    assert "rules-2024.docx @ global" in hint


def test_supersedes_hint_respects_env_threshold_override(tmp_path, monkeypatch):
    proj = KbLayer(name="project", base=tmp_path / "p")
    proj.normalized_dir.mkdir(parents=True)
    layers = KbLayers(project=proj, global_layer=None)
    _make_source_dir(proj, "Cannabis.pdf")
    # By default, these would not match (low similarity); with threshold 0.3 they would
    monkeypatch.setenv("DKS_SUPERSEDES_SIMILARITY_THRESHOLD", "0.30")
    hint = supersedes_candidate_hint(layers, "Cancer.pdf")
    assert hint is not None


def test_supersedes_hint_high_threshold_suppresses_borderline_matches(tmp_path, monkeypatch):
    proj = KbLayer(name="project", base=tmp_path / "p")
    proj.normalized_dir.mkdir(parents=True)
    layers = KbLayers(project=proj, global_layer=None)
    _make_source_dir(proj, "Futura - Mental Health Notes.docx")
    monkeypatch.setenv("DKS_SUPERSEDES_SIMILARITY_THRESHOLD", "0.99")
    # Even a v2 of nearly the same name shouldn't trip at 0.99 (post-strip names diverge)
    hint = supersedes_candidate_hint(layers, "Futura - Mental Health v2.docx")
    assert hint is None
