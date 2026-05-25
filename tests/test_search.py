from dks.layers import KbLayer, KbLayers
from dks.search import SearchHit, search_wiki
from dks.store.wiki import WikiEntry, write_wiki_entry


def _layer(name, base):
    return KbLayer(name=name, base=base)


def _entry(slug, topic, body, refs=None):
    return WikiEntry(
        topic=topic,
        slug=slug,
        source_refs=refs or ["a.md#L1-1"],
        body=body,
    )


def test_search_returns_hits_with_layer(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_wiki_entry(glb, _entry("g1", "Global topic", "encrypted at rest"))
    write_wiki_entry(proj, _entry("p1", "Project topic", "claim filing"))
    hits = search_wiki(layers, "encrypted")
    assert len(hits) == 1
    assert hits[0].slug == "g1"
    assert hits[0].layer == "global"
    assert isinstance(hits[0], SearchHit)


def test_search_project_shadows_on_same_slug(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_wiki_entry(glb, _entry("retention", "Global retention", "retain seven years"))
    write_wiki_entry(proj, _entry("retention", "Project retention", "retain ten years"))
    hits = search_wiki(layers, "retain")
    assert len(hits) == 1
    assert hits[0].slug == "retention"
    assert hits[0].layer == "project"
    assert "ten years" in hits[0].snippet


def test_search_matches_topic_too(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    write_wiki_entry(proj, _entry("pii", "PII handling rules", "body unrelated"))
    hits = search_wiki(layers, "PII")
    assert len(hits) == 1
    assert hits[0].slug == "pii"


def test_search_no_match_empty(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    assert search_wiki(layers, "nothing-here") == []


def test_search_empty_query_empty(tmp_path):
    proj = _layer("project", tmp_path / "p")
    write_wiki_entry(proj, _entry("a", "topic", "body with stuff"))
    layers = KbLayers(project=proj, global_layer=None)
    assert search_wiki(layers, "") == []
