from pathlib import Path

from dks.layers import KbLayer, resolve_layers


def test_kb_layer_subdirs():
    layer = KbLayer(name="x", base=Path("/tmp/x"))
    assert layer.normalized_dir == Path("/tmp/x/normalized")
    assert layer.index_dir == Path("/tmp/x/index")
    assert layer.wiki_dir == Path("/tmp/x/wiki")
    assert layer.raw_dir == Path("/tmp/x/raw")


def test_resolve_default_global_only(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "global"))
    layers = resolve_layers(cwd=tmp_path)
    assert layers.project is None
    assert layers.global_layer is not None
    assert layers.global_layer.base == tmp_path / "global"
    assert layers.for_write().name == "global"


def test_resolve_explicit_project_overrides_auto(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "global"))
    explicit = tmp_path / "explicit_proj"
    layers = resolve_layers(project=explicit, cwd=tmp_path)
    assert layers.project is not None
    assert layers.project.base == explicit


def test_resolve_auto_discovers_dotdks(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "g"))
    proj = tmp_path / "myproj"
    (proj / ".dks").mkdir(parents=True)
    nested = proj / "src" / "feature"
    nested.mkdir(parents=True)
    layers = resolve_layers(cwd=nested)
    assert layers.project is not None
    assert layers.project.base == proj / ".dks"


def test_resolve_for_read_order_project_first(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "g"))
    proj = tmp_path / "p"
    layers = resolve_layers(project=proj, cwd=tmp_path)
    read_order = layers.for_read()
    assert [layer.name for layer in read_order] == ["project", "global"]


def test_resolve_for_write_prefers_project_when_present(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "g"))
    proj = tmp_path / "p"
    layers = resolve_layers(project=proj, cwd=tmp_path)
    assert layers.for_write().name == "project"


def test_resolve_no_global_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "g"))
    proj = tmp_path / "p"
    layers = resolve_layers(project=proj, include_global=False, cwd=tmp_path)
    assert layers.global_layer is None
    assert [layer.name for layer in layers.for_read()] == ["project"]
