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


def test_walker_does_not_match_global_default_as_project(tmp_path, monkeypatch):
    """Regression: when the global default location (e.g. ~/.dks) sits on the
    walker's upward path and no closer .dks/ exists, auto-discovery used to
    return the global path as the project, causing both layers to resolve to
    the same directory. The walker must skip the configured global base.
    """
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    # Pretend ~/.dks exists at tmp_path/home/.dks AND that's the global base
    home_like = tmp_path / "home"
    global_at_home = home_like / ".dks"
    global_at_home.mkdir(parents=True)
    monkeypatch.setenv("DKS_GLOBAL", str(global_at_home))

    # CWD is a "repo" inside the home, with no .dks/ of its own
    repo = home_like / "development" / "some-product"
    repo.mkdir(parents=True)

    layers = resolve_layers(cwd=repo)
    assert layers.global_layer is not None
    assert layers.global_layer.base == global_at_home
    # The walker MUST NOT have returned global_at_home as the project layer
    assert layers.project is None, (
        f"Auto-discovery returned the global location as project: {layers.project}"
    )


def test_walker_still_finds_closer_dotdks_even_under_home(tmp_path, monkeypatch):
    """When the project has its own .dks/ closer to CWD than the global, the
    walker finds the project (the skip only suppresses matches AT the global
    location, not closer ones).
    """
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    home_like = tmp_path / "home"
    global_at_home = home_like / ".dks"
    global_at_home.mkdir(parents=True)
    monkeypatch.setenv("DKS_GLOBAL", str(global_at_home))

    repo = home_like / "development" / "some-product"
    (repo / ".dks").mkdir(parents=True)
    nested = repo / "apps" / "web"
    nested.mkdir(parents=True)

    layers = resolve_layers(cwd=nested)
    assert layers.project is not None
    assert layers.project.base == repo / ".dks"


# --- resolution provenance tests -------------------------------------------


def test_resolve_records_source_explicit_for_project(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "g"))
    layers = resolve_layers(project=tmp_path / "p", cwd=tmp_path)
    assert layers.resolution["project"] == "explicit"


def test_resolve_records_source_env_for_project(tmp_path, monkeypatch):
    monkeypatch.setenv("DKS_PROJECT", str(tmp_path / "env-proj"))
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "g"))
    layers = resolve_layers(cwd=tmp_path)
    assert layers.resolution["project"] == "env"


def test_resolve_records_source_auto_for_project(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "g"))
    repo = tmp_path / "repo"
    (repo / ".dks").mkdir(parents=True)
    layers = resolve_layers(cwd=repo)
    assert layers.resolution["project"] == "auto-discover"


def test_resolve_records_source_explicit_for_global(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_GLOBAL", raising=False)
    layers = resolve_layers(project=tmp_path / "p", global_base=tmp_path / "g", cwd=tmp_path)
    assert layers.resolution["global"] == "explicit"


def test_resolve_records_source_env_for_global(tmp_path, monkeypatch):
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "g-env"))
    layers = resolve_layers(project=tmp_path / "p", cwd=tmp_path)
    assert layers.resolution["global"] == "env"


def test_resolve_records_source_default_for_global(tmp_path, monkeypatch):
    monkeypatch.delenv("DKS_GLOBAL", raising=False)
    layers = resolve_layers(project=tmp_path / "p", cwd=tmp_path)
    assert layers.resolution["global"] == "default"


def test_resolve_records_source_suppressed_for_global(tmp_path, monkeypatch):
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "g"))
    layers = resolve_layers(project=tmp_path / "p", include_global=False, cwd=tmp_path)
    assert layers.resolution.get("global") == "suppressed"
    assert layers.global_layer is None
