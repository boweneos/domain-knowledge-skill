import pytest

from dks.layers import KbLayer, KbLayers
from dks.store.pageindex import read_pageindex, write_pageindex


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
