import pytest

from dks.layers import KbLayer, KbLayers
from dks.store.pageindex import read_pageindex, search_pageindex, write_pageindex


def _layer(name, base):
    return KbLayer(name=name, base=base)


def test_write_and_read_one_layer(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    tree = {"title": "T", "block_ids": [], "children": []}
    write_pageindex(proj, source_file="a.pdf", tree=tree)
    loaded, layer = read_pageindex(layers, source_file="a.pdf")
    assert loaded == tree
    assert layer == "project"


def test_project_shadows_global(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_pageindex(glb, source_file="a.pdf", tree={"title": "global", "block_ids": [], "children": []})  # noqa: E501
    write_pageindex(proj, source_file="a.pdf", tree={"title": "project", "block_ids": [], "children": []})  # noqa: E501
    loaded, layer = read_pageindex(layers, source_file="a.pdf")
    assert loaded["title"] == "project"
    assert layer == "project"


def test_read_falls_back_to_global(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_pageindex(glb, source_file="b.pdf", tree={"title": "G", "block_ids": [], "children": []})
    loaded, layer = read_pageindex(layers, source_file="b.pdf")
    assert loaded["title"] == "G"
    assert layer == "global"


def test_read_missing_raises(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    with pytest.raises(FileNotFoundError):
        read_pageindex(layers, source_file="absent.pdf")


# --- search_pageindex ----------------------------------------------------

def _tree(title, children=None, block_ids=None):
    return {
        "title": title,
        "block_ids": list(block_ids or []),
        "children": children or [],
    }


def test_search_empty_when_no_pageindex_files(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    assert search_pageindex(layers, "sleep") == []


def test_search_returns_case_insensitive_title_match(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    write_pageindex(proj, "x.pdf", _tree("Sleep Apnoea Management"))
    hits = search_pageindex(layers, "sleep")
    assert len(hits) == 1
    assert hits[0].title == "Sleep Apnoea Management"
    assert hits[0].source == "x.pdf"
    assert hits[0].layer == "project"
    assert hits[0].path == ["Sleep Apnoea Management"]


def test_search_returns_nested_node_with_full_path(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    tree = _tree(
        "Root",
        children=[
            _tree(
                "Chapter 3",
                children=[_tree("3.2 Family History Cancer Rules", block_ids=["a.pdf#p10"])],
            )
        ],
    )
    write_pageindex(proj, "a.pdf", tree)
    hits = search_pageindex(layers, "family history")
    assert len(hits) == 1
    assert hits[0].path == ["Root", "Chapter 3", "3.2 Family History Cancer Rules"]
    assert hits[0].block_ids == ["a.pdf#p10"]


def test_search_project_hits_precede_global_hits(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_pageindex(glb, "g.pdf", _tree("Sleep — global"))
    write_pageindex(proj, "p.pdf", _tree("Sleep — project"))
    hits = search_pageindex(layers, "sleep")
    assert [h.layer for h in hits] == ["project", "global"]


def test_search_no_match_returns_empty(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    write_pageindex(proj, "x.pdf", _tree("Unrelated content"))
    assert search_pageindex(layers, "sleep") == []


def test_search_handles_malformed_pageindex_json(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    # First create a valid file so the index dir exists
    write_pageindex(proj, "ok.pdf", _tree("Sleep ok"))
    # Then drop a bad file alongside
    proj.index_dir.mkdir(parents=True, exist_ok=True)
    (proj.index_dir / "broken.pdf.pageindex.json").write_text("{not valid json")
    hits = search_pageindex(layers, "sleep")
    assert len(hits) == 1
    assert hits[0].source == "ok.pdf"
