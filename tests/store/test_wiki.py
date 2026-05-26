import pytest

from dks.layers import KbLayer, KbLayers
from dks.store.wiki import (
    WikiEntry,
    list_wiki_entries,
    read_wiki_entry,
    write_wiki_entry,
)


def _layer(name, base):
    return KbLayer(name=name, base=base)


def _entry(slug: str, body: str) -> WikiEntry:
    return WikiEntry(
        topic=f"Topic {slug}",
        slug=slug,
        source_refs=["a.md#L1-1"],
        body=body,
    )


def test_write_and_read_in_one_layer(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    write_wiki_entry(proj, _entry("x", "hello"))
    entry, layer = read_wiki_entry(layers, "x")
    assert entry.body == "hello"
    assert layer == "project"


def test_read_falls_back_to_global(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_wiki_entry(glb, _entry("only-global", "g-body"))
    entry, layer = read_wiki_entry(layers, "only-global")
    assert entry.body == "g-body"
    assert layer == "global"


def test_project_shadows_global_on_same_slug(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_wiki_entry(glb, _entry("conflict", "global body"))
    write_wiki_entry(proj, _entry("conflict", "project body"))
    entry, layer = read_wiki_entry(layers, "conflict")
    assert entry.body == "project body"
    assert layer == "project"


def test_list_merges_and_dedupes(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_wiki_entry(glb, _entry("a", ""))
    write_wiki_entry(glb, _entry("b", ""))
    write_wiki_entry(proj, _entry("b", ""))   # shadows global b
    write_wiki_entry(proj, _entry("c", ""))
    hits = list_wiki_entries(layers)
    by_slug = {h.slug: h.layer for h in hits}
    assert by_slug == {"a": "global", "b": "project", "c": "project"}


def test_read_missing_raises(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    with pytest.raises(FileNotFoundError):
        read_wiki_entry(layers, "absent")


def test_list_empty_dirs(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    assert list_wiki_entries(layers) == []


def test_wiki_entry_default_classification_is_internal(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    entry = _entry("x", "body")
    assert entry.classification == "internal"
    write_wiki_entry(proj, entry)
    loaded, _ = read_wiki_entry(layers, "x")
    assert loaded.classification == "internal"


def test_wiki_entry_roundtrip_preserves_classification(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    entry = WikiEntry(
        topic="Sensitive topic",
        slug="sensitive",
        source_refs=["a.md#L1-1"],
        body="body",
        classification="confidential",
    )
    write_wiki_entry(proj, entry)
    loaded, _ = read_wiki_entry(layers, "sensitive")
    assert loaded.classification == "confidential"
