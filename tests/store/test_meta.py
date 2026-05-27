from dks.layers import KbLayer, KbLayers
from dks.store.meta import SourceMeta, compute_superseded_by, read_meta, write_meta


def _layer(name, base):
    base.mkdir(parents=True, exist_ok=True)
    (base / "normalized").mkdir()
    return KbLayer(name=name, base=base)


def test_write_and_read_one_layer(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    meta = SourceMeta(supersedes=["old.docx"])
    write_meta(proj, "new.docx", meta)
    loaded = read_meta(layers, "new.docx")
    assert loaded is not None
    loaded_meta, layer_name = loaded
    assert loaded_meta.supersedes == ["old.docx"]
    assert loaded_meta.ingested_at  # auto-set
    assert layer_name == "project"


def test_read_missing_returns_none(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    assert read_meta(layers, "absent.docx") is None


def test_project_shadows_global(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_meta(glb, "a.docx", SourceMeta(supersedes=["global-old.docx"]))
    write_meta(proj, "a.docx", SourceMeta(supersedes=["project-old.docx"]))
    loaded = read_meta(layers, "a.docx")
    assert loaded is not None
    meta, layer = loaded
    assert meta.supersedes == ["project-old.docx"]
    assert layer == "project"


def test_compute_superseded_by_empty_corpus(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    assert compute_superseded_by(layers) == {}


def test_compute_superseded_by_single_link(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    write_meta(proj, "amendment.docx", SourceMeta(supersedes=["original.docx"]))
    result = compute_superseded_by(layers)
    assert result == {"original.docx": [("amendment.docx", "project")]}


def test_compute_superseded_by_multiple_amendments_of_same_source(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_meta(glb, "amend-v1.docx", SourceMeta(supersedes=["base.docx"]))
    write_meta(proj, "amend-v2.docx", SourceMeta(supersedes=["base.docx"]))
    result = compute_superseded_by(layers)
    successors = result["base.docx"]
    successor_names = {s for s, _ in successors}
    assert successor_names == {"amend-v1.docx", "amend-v2.docx"}


def test_compute_superseded_by_skips_corrupt_meta(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    # Valid meta
    write_meta(proj, "good.docx", SourceMeta(supersedes=["base.docx"]))
    # Corrupt sidecar
    (proj.normalized_dir / "broken.docx").mkdir(parents=True, exist_ok=True)
    (proj.normalized_dir / "broken.docx" / ".meta.json").write_text("{not valid json")
    result = compute_superseded_by(layers)
    assert result == {"base.docx": [("good.docx", "project")]}
