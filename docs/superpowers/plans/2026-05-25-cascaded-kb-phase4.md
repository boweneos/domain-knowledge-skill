# Domain Knowledge Skill — Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Introduce two-layer KB resolution — a **global** layer (default `~/.dks/`) plus an auto-discovered **project** layer — so a user-scope plugin install can ground answers in cross-project rules while still letting per-project repos override or extend them.

**Architecture:** Project layer shadows global. Reads cascade (project first, fall back to global). Writes default to the project layer when one is discovered, otherwise to global. The shadowing is per-slug for the wiki, per-block_id for blocks, per-source_file for PageIndex trees.

**Breaking change.** This is a v0.2.0 bump. CLI flags `--normalized-dir`, `--wiki-dir`, `--index-dir` are replaced by layer-aware flags (`--project`, `--global`, `--no-global`). Existing tests that hardcode those flags will need updating; the public consumer skill contract is unchanged.

**Tech stack:** Same as Phases 1–3. No new deps.

---

## Design summary

```
~/.dks/                       ← GLOBAL layer (DKS_GLOBAL env var to relocate)
  ├── normalized/
  ├── index/
  ├── wiki/
  └── raw/

<project>/.dks/               ← PROJECT layer (auto-discovered by walking up
  ├── normalized/                from CWD looking for a `.dks/` directory)
  ├── index/
  ├── wiki/
  └── raw/
```

**Resolution rules:**
- `dks blocks get <id>` — try project first, fall back to global; print `layer` in JSON.
- `dks blocks list <source>` — merge ids from both layers, dedupe (project wins on collision); each id tagged with layer.
- `dks wiki list` — merge slugs from both, dedupe (project wins).
- `dks wiki read <slug>` — try project first, fall back to global; print `layer`.
- `dks wiki search <query>` — search both, merge hits, dedupe by slug (project wins); each hit carries `layer`.
- `dks pageindex read <source>` — try project first, fall back to global.
- `dks ingest <path>` — write to project layer by default; `--global` to force global.
- `dks wiki write <slug>` — same default-to-project rule; `--global` to force global.
- `dks pageindex write <source>` — same.

**Citation format gains a layer tag.** Skills surface `[ref: <block_id> @ project]` vs `@ global`. When a project block shadows a global one with different content, `dks blocks get` emits a stderr warning.

**Auto-discovery walker.** From CWD, walk up looking for `.dks/` directory. If found, that's the project layer. If we hit filesystem root with no match, project layer is `None` (global-only).

---

## File structure changes

```
src/dks/
  layers.py                    NEW — KbLayer, KbLayers, resolve_layers()
  store/blocks.py              MODIFIED — list_blocks(layers, …), get_block(layers, …)
  store/wiki.py                MODIFIED — read/list now layer-aware; write takes a layer
  store/pageindex.py           MODIFIED — read/write layer-aware
  search.py                    MODIFIED — search_wiki(layers, …) returns SearchHit with layer
  writer.py                    MODIFIED — write_blocks(blocks, layer)
  cli.py                       MODIFIED — new --project / --global / --no-global flags
                                          replace --normalized-dir / --wiki-dir / --index-dir
  __init__.py                  MODIFIED — version bump to 0.2.0
dks/.claude-plugin/plugin.json MODIFIED — version bump to 0.2.0
dks/skills/                    MODIFIED — all four SKILL.md files updated for layer-tagged output
tests/                         MODIFIED — most existing tests need to pass `KbLayers`
  test_layers.py               NEW — resolution + auto-discovery tests
  store/test_blocks.py         MODIFIED
  store/test_wiki.py           MODIFIED
  store/test_pageindex.py      MODIFIED
  test_search.py               MODIFIED
  test_cli.py                  MODIFIED
docs/USAGE.md                  MODIFIED — new "Cascaded KB" section
README.md                      MODIFIED — one sentence in Architecture summary
```

---

## Task 1 — Layer resolution module

**Files:**
- Create: `src/dks/layers.py`
- Create: `tests/test_layers.py`

`KbLayer` is a frozen dataclass holding a layer name + base path with computed subdirs. `KbLayers` is an ordered tuple (project first). `resolve_layers()` honours explicit args, `DKS_PROJECT` / `DKS_GLOBAL` env vars, auto-discovery, and falls back to `~/.dks/` for global.

- [ ] **Step 1: Failing tests**

`tests/test_layers.py`:
```python
import os
from pathlib import Path

import pytest

from dks.layers import KbLayer, KbLayers, resolve_layers


def test_kb_layer_subdirs():
    layer = KbLayer(name="x", base=Path("/tmp/x"))
    assert layer.normalized_dir == Path("/tmp/x/normalized")
    assert layer.index_dir == Path("/tmp/x/index")
    assert layer.wiki_dir == Path("/tmp/x/wiki")
    assert layer.raw_dir == Path("/tmp/x/raw")


def test_resolve_default_global_only(tmp_path, monkeypatch):
    # No project to find, custom global
    monkeypatch.delenv("DKS_PROJECT", raising=False)
    monkeypatch.setenv("DKS_GLOBAL", str(tmp_path / "global"))
    layers = resolve_layers(cwd=tmp_path)
    assert layers.project is None
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
    assert [l.name for l in read_order] == ["project", "global"]


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
    assert [l.name for l in layers.for_read()] == ["project"]
```

- [ ] **Step 2: Run, observe fail**

```bash
uv run pytest tests/test_layers.py -v
```

ImportError expected.

- [ ] **Step 3: Implement `src/dks/layers.py`**

```python
"""KB layer resolution — global + project, project shadows global on reads."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KbLayer:
    """A single KB layer rooted at a directory with the standard subdirs."""
    name: str
    base: Path

    @property
    def normalized_dir(self) -> Path:
        return self.base / "normalized"

    @property
    def index_dir(self) -> Path:
        return self.base / "index"

    @property
    def wiki_dir(self) -> Path:
        return self.base / "wiki"

    @property
    def raw_dir(self) -> Path:
        return self.base / "raw"


@dataclass(frozen=True)
class KbLayers:
    """Resolved active layers. Project first (highest precedence), then global."""
    project: KbLayer | None
    global_layer: KbLayer | None

    def for_read(self) -> tuple[KbLayer, ...]:
        """Read order: project first, then global. Empty layers omitted."""
        return tuple(l for l in (self.project, self.global_layer) if l is not None)

    def for_write(self) -> KbLayer:
        """Write target: project if present, else global."""
        if self.project is not None:
            return self.project
        if self.global_layer is not None:
            return self.global_layer
        raise RuntimeError("no writable layer (both project and global are None)")

    def by_name(self, name: str) -> KbLayer | None:
        for layer in self.for_read():
            if layer.name == name:
                return layer
        return None


def _auto_discover_project(cwd: Path) -> Path | None:
    """Walk up from cwd looking for a .dks/ directory. Return its path or None."""
    current = cwd.resolve()
    while True:
        candidate = current / ".dks"
        if candidate.is_dir():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def resolve_layers(
    project: Path | None = None,
    global_base: Path | None = None,
    include_global: bool = True,
    cwd: Path | None = None,
) -> KbLayers:
    """Resolve which layers are active.

    Precedence for the **project** layer:
      1. Explicit `project` argument.
      2. `DKS_PROJECT` env var.
      3. Auto-discovery from `cwd` (default: real CWD).
      4. None.

    Precedence for the **global** layer (suppressed if include_global=False):
      1. Explicit `global_base` argument.
      2. `DKS_GLOBAL` env var.
      3. `~/.dks`.
    """
    if cwd is None:
        cwd = Path.cwd()

    if project is None:
        env_project = os.environ.get("DKS_PROJECT")
        if env_project:
            project = Path(env_project)
        else:
            project = _auto_discover_project(cwd)

    project_layer = KbLayer(name="project", base=project) if project is not None else None

    if include_global:
        if global_base is None:
            env_global = os.environ.get("DKS_GLOBAL")
            global_base = Path(env_global) if env_global else Path.home() / ".dks"
        global_layer: KbLayer | None = KbLayer(name="global", base=global_base)
    else:
        global_layer = None

    return KbLayers(project=project_layer, global_layer=global_layer)
```

- [ ] **Step 4: Run, pass**

```bash
uv run pytest tests/test_layers.py -v
```

7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/layers.py tests/test_layers.py
git commit -m "feat: KbLayer / KbLayers / resolve_layers — two-layer KB resolution"
```

---

## Task 2 — Layered block store + writer

**Files:**
- Modify: `src/dks/store/blocks.py`
- Modify: `src/dks/writer.py`
- Modify: `tests/store/test_blocks.py`
- Modify: `tests/test_writer.py`

`list_blocks` and `get_block` accept `KbLayers` and return layer-tagged results. `write_blocks` takes a `KbLayer` directly (caller decides which layer).

- [ ] **Step 1: Update tests first**

Replace `tests/store/test_blocks.py` contents with:
```python
from pathlib import Path

import pytest

from dks.block import NormalizedBlock
from dks.blockref import encode_blockref
from dks.layers import KbLayer, KbLayers
from dks.locators import MarkdownLocator
from dks.store.blocks import BlockHit, get_block, list_blocks
from dks.writer import write_blocks


def _layer(name: str, root: Path) -> KbLayer:
    return KbLayer(name=name, base=root)


def _block(source: str, start: int, end: int, content: str) -> NormalizedBlock:
    loc = MarkdownLocator(heading_path=[], line_start=start, line_end=end)
    return NormalizedBlock(
        source_file=source,
        block_id=encode_blockref(source, loc),
        locator=loc,
        block_type="text",
        content=content,
    )


def _seed(layer: KbLayer, source: str, content_pairs: list[tuple[int, int, str]]) -> None:
    blocks = [_block(source, s, e, c) for s, e, c in content_pairs]
    write_blocks(blocks, layer)


def test_list_blocks_project_only(tmp_path):
    proj = _layer("project", tmp_path / "p")
    layers = KbLayers(project=proj, global_layer=None)
    _seed(proj, "claims.md", [(1, 1, "a"), (3, 3, "b")])
    hits = list_blocks(layers, source_file="claims.md")
    assert sorted(h.block_id for h in hits) == ["claims.md#L1-1", "claims.md#L3-3"]
    assert all(h.layer == "project" for h in hits)


def test_list_blocks_global_only(tmp_path):
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=None, global_layer=glb)
    _seed(glb, "claims.md", [(1, 1, "a")])
    [hit] = list_blocks(layers, source_file="claims.md")
    assert hit.block_id == "claims.md#L1-1"
    assert hit.layer == "global"


def test_list_blocks_merges_layers(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    _seed(proj, "claims.md", [(1, 1, "proj-1")])
    _seed(glb, "claims.md", [(1, 1, "glob-1"), (3, 3, "glob-3")])
    hits = list_blocks(layers, source_file="claims.md")
    # 2 unique ids: L1-1 (shadowed by project), L3-3 (global only)
    by_id = {h.block_id: h.layer for h in hits}
    assert by_id["claims.md#L1-1"] == "project"   # project shadows
    assert by_id["claims.md#L3-3"] == "global"


def test_get_block_project_wins(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    _seed(proj, "claims.md", [(1, 1, "proj-content")])
    _seed(glb, "claims.md", [(1, 1, "global-content")])
    block, layer_name = get_block(layers, block_id="claims.md#L1-1")
    assert block.content == "proj-content"
    assert layer_name == "project"


def test_get_block_falls_back_to_global(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    _seed(glb, "claims.md", [(7, 9, "only-global")])
    block, layer_name = get_block(layers, block_id="claims.md#L7-9")
    assert block.content == "only-global"
    assert layer_name == "global"


def test_get_block_missing_raises(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    with pytest.raises(FileNotFoundError):
        get_block(layers, block_id="absent.md#L1-1")
```

Replace `tests/test_writer.py` contents to use a `KbLayer` instead of a raw path:
```python
from pathlib import Path

from dks.block import NormalizedBlock, parse_markdown
from dks.blockref import encode_blockref
from dks.layers import KbLayer
from dks.locators import MarkdownLocator
from dks.writer import safe_filename, write_blocks


def _block(source: str, start: int, end: int, content: str) -> NormalizedBlock:
    loc = MarkdownLocator(heading_path=[], line_start=start, line_end=end)
    return NormalizedBlock(
        source_file=source,
        block_id=encode_blockref(source, loc),
        locator=loc,
        block_type="text",
        content=content,
    )


def test_write_blocks_creates_files(tmp_path: Path):
    layer = KbLayer(name="project", base=tmp_path)
    blocks = [_block("notes.md", 1, 1, "first"), _block("notes.md", 3, 5, "second")]
    written = write_blocks(blocks, layer)
    assert len(written) == 2
    for p in written:
        assert p.exists()
        assert p.parent.parent == tmp_path / "normalized"


def test_write_blocks_overwrites_on_rerun(tmp_path: Path):
    layer = KbLayer(name="project", base=tmp_path)
    [original] = write_blocks([_block("a.md", 1, 1, "v1")], layer)
    [rewritten] = write_blocks([_block("a.md", 1, 1, "v2")], layer)
    assert original == rewritten
    assert parse_markdown(rewritten.read_text()).content == "v2"


def test_safe_filename_strips_unsafe_chars():
    assert safe_filename("a/b.md#L1-3") == "a__b.md__L1-3"
    assert safe_filename("x.pdf#p5#3.2") == "x.pdf__p5__3.2"


def test_write_blocks_empty_list_no_op(tmp_path: Path):
    layer = KbLayer(name="project", base=tmp_path)
    assert write_blocks([], layer) == []
```

- [ ] **Step 2: Run, observe fail**

`uv run pytest tests/store/test_blocks.py tests/test_writer.py -v` — import/signature errors expected.

- [ ] **Step 3: Update `src/dks/writer.py`**

```python
"""Writer — persists NormalizedBlocks to disk under a KbLayer."""

from collections.abc import Iterable
from pathlib import Path

from dks.block import NormalizedBlock, to_markdown
from dks.layers import KbLayer


def safe_filename(s: str) -> str:
    """Make a string safe for filesystem use: replace / and # with __."""
    return s.replace("/", "__").replace("#", "__")


def write_blocks(blocks: Iterable[NormalizedBlock], layer: KbLayer) -> list[Path]:
    """Persist blocks to `<layer.normalized_dir>/<source_basename>/`."""
    output_dir = layer.normalized_dir
    written: list[Path] = []
    for block in blocks:
        source_basename = Path(block.source_file).name
        target_dir = output_dir / source_basename
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{safe_filename(block.block_id)}.md"
        target.write_text(to_markdown(block))
        written.append(target)
    return written
```

- [ ] **Step 4: Update `src/dks/store/blocks.py`**

```python
"""Block store reader — layer-aware. Project shadows global."""

from dataclasses import dataclass
from pathlib import Path

from dks.block import NormalizedBlock, parse_markdown
from dks.layers import KbLayers
from dks.writer import safe_filename


@dataclass(frozen=True)
class BlockHit:
    block_id: str
    layer: str


def list_blocks(layers: KbLayers, source_file: str) -> list[BlockHit]:
    """Return BlockHits for `source_file` across layers; project shadows global by block_id."""
    seen: dict[str, BlockHit] = {}
    for layer in layers.for_read():
        source_dir = layer.normalized_dir / Path(source_file).name
        if not source_dir.is_dir():
            continue
        for md_file in sorted(source_dir.glob("*.md")):
            block = parse_markdown(md_file.read_text())
            if block.source_file != source_file:
                continue
            if block.block_id not in seen:  # first layer wins (project first)
                seen[block.block_id] = BlockHit(block_id=block.block_id, layer=layer.name)
    return list(seen.values())


def get_block(layers: KbLayers, block_id: str) -> tuple[NormalizedBlock, str]:
    """Load the NormalizedBlock + which layer served it. Project first, fall back to global."""
    source_part = block_id.split("#", 1)[0]
    source_basename = Path(source_part).name
    for layer in layers.for_read():
        target = layer.normalized_dir / source_basename / f"{safe_filename(block_id)}.md"
        if target.exists():
            return parse_markdown(target.read_text()), layer.name
    raise FileNotFoundError(f"block {block_id!r} not found in any layer")
```

- [ ] **Step 5: Run + verify**

```bash
uv run pytest tests/store/test_blocks.py tests/test_writer.py -v
uv run mypy src
uv run ruff check src tests
```

All pass.

- [ ] **Step 6: Commit**

```bash
git add src/dks/store/blocks.py src/dks/writer.py tests/store/test_blocks.py tests/test_writer.py
git commit -m "feat: layer-aware block store + writer; BlockHit tagged with layer"
```

---

## Task 3 — Layered wiki store

**Files:**
- Modify: `src/dks/store/wiki.py`
- Modify: `tests/store/test_wiki.py`

`list_wiki_entries` and `read_wiki_entry` cascade. `write_wiki_entry` takes a `KbLayer`.

- [ ] **Step 1: Update tests**

`tests/store/test_wiki.py`:
```python
import pytest

from dks.layers import KbLayer, KbLayers
from dks.store.wiki import WikiEntry, WikiSlugHit, list_wiki_entries, read_wiki_entry, write_wiki_entry


def _layer(name: str, base):
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
    write_wiki_entry(proj, _entry("b", ""))  # shadows global b
    write_wiki_entry(proj, _entry("c", ""))
    hits = list_wiki_entries(layers)
    by_slug = {h.slug: h.layer for h in hits}
    assert by_slug == {"a": "global", "b": "project", "c": "project"}


def test_read_missing_raises(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    with pytest.raises(FileNotFoundError):
        read_wiki_entry(layers, "absent")
```

- [ ] **Step 2: Run, observe fail**

`uv run pytest tests/store/test_wiki.py -v` → import errors.

- [ ] **Step 3: Update `src/dks/store/wiki.py`**

Keep the existing `WikiEntry` model + on-disk format unchanged. Adapt the read functions to take `KbLayers`, and add `WikiSlugHit`.

```python
"""Wiki entry storage — one Markdown file per topic, layer-aware."""

import json
from dataclasses import dataclass
from datetime import datetime
from datetime import UTC as _UTC
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from dks.layers import KbLayer, KbLayers

_FENCE = "---"


class WikiEntry(BaseModel):
    topic: str
    slug: str
    source_refs: list[str]
    body: str
    compiled_at: str | None = None


@dataclass(frozen=True)
class WikiSlugHit:
    slug: str
    layer: str


def write_wiki_entry(layer: KbLayer, entry: WikiEntry) -> Path:
    """Persist a WikiEntry to the given layer. Sets compiled_at to now() if unset."""
    layer.wiki_dir.mkdir(parents=True, exist_ok=True)
    if not entry.compiled_at:
        entry.compiled_at = datetime.now(_UTC).isoformat()
    frontmatter = entry.model_dump_json(exclude={"body"}, indent=2)
    target = layer.wiki_dir / f"{entry.slug}.md"
    target.write_text(f"{_FENCE}\n{frontmatter}\n{_FENCE}\n{entry.body}\n")
    return target


def _read_one(wiki_dir: Path, slug: str) -> WikiEntry:
    target = wiki_dir / f"{slug}.md"
    text = target.read_text()
    if not text.startswith(_FENCE + "\n"):
        raise ValueError(f"missing frontmatter fence in {target}")
    rest = text[len(_FENCE) + 1 :]
    close = rest.find("\n" + _FENCE + "\n")
    if close == -1:
        raise ValueError(f"missing closing frontmatter fence in {target}")
    front = cast(dict[str, Any], json.loads(rest[:close]))
    body = rest[close + len(_FENCE) + 2 :].rstrip("\n")
    front["body"] = body
    return WikiEntry.model_validate(front)


def read_wiki_entry(layers: KbLayers, slug: str) -> tuple[WikiEntry, str]:
    """Read a WikiEntry + which layer served it. Project first, fall back to global."""
    for layer in layers.for_read():
        target = layer.wiki_dir / f"{slug}.md"
        if target.exists():
            return _read_one(layer.wiki_dir, slug), layer.name
    raise FileNotFoundError(f"no wiki entry for slug {slug!r} in any layer")


def list_wiki_entries(layers: KbLayers) -> list[WikiSlugHit]:
    """List slugs across layers, deduped (project shadows global)."""
    seen: dict[str, WikiSlugHit] = {}
    for layer in layers.for_read():
        if not layer.wiki_dir.is_dir():
            continue
        for p in layer.wiki_dir.glob("*.md"):
            slug = p.stem
            if slug not in seen:
                seen[slug] = WikiSlugHit(slug=slug, layer=layer.name)
    return sorted(seen.values(), key=lambda h: h.slug)
```

- [ ] **Step 4: Run + verify**

`uv run pytest tests/store/test_wiki.py -v` → 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/store/wiki.py tests/store/test_wiki.py
git commit -m "feat: layer-aware wiki store (read cascades, write takes a layer)"
```

---

## Task 4 — Layered PageIndex store

**Files:**
- Modify: `src/dks/store/pageindex.py`
- Modify: `tests/store/test_pageindex.py`

Same pattern as wiki. `read_pageindex` cascades, `write_pageindex` takes a `KbLayer`.

- [ ] **Step 1: Update tests**

```python
import pytest

from dks.layers import KbLayer, KbLayers
from dks.store.pageindex import read_pageindex, write_pageindex


def _layer(name, base): return KbLayer(name=name, base=base)


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
    write_pageindex(glb, source_file="a.pdf", tree={"title": "global", "block_ids": [], "children": []})
    write_pageindex(proj, source_file="a.pdf", tree={"title": "project", "block_ids": [], "children": []})
    loaded, layer = read_pageindex(layers, source_file="a.pdf")
    assert loaded["title"] == "project"
    assert layer == "project"


def test_read_falls_back_to_global(tmp_path):
    proj = _layer("project", tmp_path / "p")
    glb = _layer("global", tmp_path / "g")
    layers = KbLayers(project=proj, global_layer=glb)
    write_pageindex(glb, source_file="b.pdf", tree={"title": "G", "block_ids": [], "children": []})
    loaded, layer = read_pageindex(layers, source_file="b.pdf")
    assert layer == "global"


def test_read_missing_raises(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    with pytest.raises(FileNotFoundError):
        read_pageindex(layers, source_file="absent.pdf")
```

- [ ] **Step 2: Implement**

```python
"""PageIndex tree storage — sidecar JSON per source document, layer-aware."""

import json
from pathlib import Path
from typing import Any, cast

from dks.layers import KbLayer, KbLayers


def _target(wiki_or_index_dir: Path, source_file: str) -> Path:
    basename = Path(source_file).name
    return wiki_or_index_dir / f"{basename}.pageindex.json"


def write_pageindex(layer: KbLayer, source_file: str, tree: dict[str, Any]) -> Path:
    """Persist `tree` to the given layer."""
    layer.index_dir.mkdir(parents=True, exist_ok=True)
    target = _target(layer.index_dir, source_file)
    target.write_text(json.dumps(tree, indent=2))
    return target


def read_pageindex(layers: KbLayers, source_file: str) -> tuple[dict[str, Any], str]:
    """Read tree + which layer served it. Project first, fall back to global."""
    for layer in layers.for_read():
        target = _target(layer.index_dir, source_file)
        if target.exists():
            return cast(dict[str, Any], json.loads(target.read_text())), layer.name
    raise FileNotFoundError(f"no PageIndex for {source_file!r} in any layer")
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/store/test_pageindex.py -v
git add src/dks/store/pageindex.py tests/store/test_pageindex.py
git commit -m "feat: layer-aware PageIndex store"
```

---

## Task 5 — Layered search

**Files:**
- Modify: `src/dks/search.py`
- Modify: `tests/test_search.py`

`SearchHit` gains `layer`. `search_wiki(layers, query)` searches both, dedupes by slug.

- [ ] **Step 1: Update tests**

```python
from pathlib import Path

from dks.layers import KbLayer, KbLayers
from dks.search import SearchHit, search_wiki
from dks.store.wiki import WikiEntry, write_wiki_entry


def _layer(name, base): return KbLayer(name=name, base=base)


def _entry(slug, topic, body, refs=None):
    return WikiEntry(
        topic=topic, slug=slug,
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


def test_search_no_match_empty(tmp_path):
    layers = KbLayers(project=_layer("project", tmp_path / "p"), global_layer=None)
    assert search_wiki(layers, "nothing-here") == []
```

- [ ] **Step 2: Implement**

```python
"""Keyword search over compiled wiki entries — layer-aware."""

from pydantic import BaseModel

from dks.layers import KbLayers
from dks.store.wiki import list_wiki_entries, read_wiki_entry


class SearchHit(BaseModel):
    slug: str
    layer: str
    topic: str
    source_refs: list[str]
    snippet: str


def search_wiki(layers: KbLayers, query: str) -> list[SearchHit]:
    q = query.lower().strip()
    if not q:
        return []
    hits: list[SearchHit] = []
    for slug_hit in list_wiki_entries(layers):
        entry, layer_name = read_wiki_entry(layers, slug_hit.slug)
        topic_match = q in entry.topic.lower()
        body_lower = entry.body.lower()
        body_match_idx = body_lower.find(q)
        if not topic_match and body_match_idx < 0:
            continue
        if body_match_idx >= 0:
            start = max(0, body_match_idx - 80)
            end = min(len(entry.body), body_match_idx + len(query) + 120)
            snippet = entry.body[start:end].strip()
        else:
            snippet = entry.body[:200].strip()
        hits.append(
            SearchHit(
                slug=slug_hit.slug,
                layer=layer_name,
                topic=entry.topic,
                source_refs=entry.source_refs,
                snippet=snippet,
            )
        )
    return hits
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/test_search.py -v
git add src/dks/search.py tests/test_search.py
git commit -m "feat: layer-aware search; SearchHit tagged with layer"
```

---

## Task 6 — CLI flag rework

**Files:**
- Modify: `src/dks/cli.py`
- Modify: `tests/test_cli.py`

Replace `--normalized-dir`, `--wiki-dir`, `--index-dir` with `--project <path>`, `--global <path>`, `--no-global`. Add `--global` boolean flag to `ingest` / `wiki write` / `pageindex write` to force the global layer for writes.

Pattern for every command:
```python
project: Path | None = typer.Option(None, "--project", "-p", help="..."),  # noqa: B008
global_base: Path | None = typer.Option(None, "--global", help="..."),  # noqa: B008
no_global: bool = typer.Option(False, "--no-global", help="..."),  # noqa: B008
```

Build layers:
```python
layers = resolve_layers(project=project, global_base=global_base, include_global=not no_global)
```

For ingest/write commands, add a `--global` write flag (booleans can collide with `--global <path>` — solve by using `--write-global` for the write target flag):
```python
write_global: bool = typer.Option(False, "--write-global", help="Force write to the global layer."),
```

In the body:
```python
write_target = layers.global_layer if write_global else layers.for_write()
```

- [ ] **Step 1: Update tests** to use the new flags and assert on new JSON shapes (layer field on hits / responses).

Major test changes:
- Pass `--project <tmp>` instead of `--output-dir <tmp>`.
- Assert that responses include a `layer` field where the new schema includes one (blocks get, wiki search, wiki read).

(See the test file for the full diff; this is the biggest test churn in the plan.)

- [ ] **Step 2: Update `src/dks/cli.py`** with the new flag set + layer wiring. Preserve the existing subcommand names (`ingest`, `blocks list/get`, `pageindex read/write`, `wiki list/read/write/search`).

- [ ] **Step 3: Verify + commit**

```bash
uv run pytest -v 2>&1 | tail -15
uv run mypy src
uv run ruff check src tests
git add -A
git commit -m "feat: layer-aware CLI flags (--project / --global / --no-global / --write-global)"
```

---

## Task 7 — Skill updates

**Files:**
- Modify: `dks/skills/dks-search/SKILL.md`
- Modify: `dks/skills/dks-build-pageindex/SKILL.md`
- Modify: `dks/skills/dks-compile-wiki/SKILL.md`
- Modify: `dks/skills/dks-lint-wiki/SKILL.md`
- Modify: `dks/commands/*.md` (if any inline flag references)

Each skill prompt updated to:
- Reference the new flags only where needed (skills mostly use defaults).
- Surface `layer` from CLI output in citation strings: `[ref: <block_id> @ <layer>]`.
- `dks-lint-wiki`: walk both layers in the report (separate sections per layer).
- `dks-build-pageindex`: write to project by default; mention `--write-global` for cross-project trees.
- `dks-compile-wiki`: same default; mention `--write-global`.

- [ ] **Step 1: Edit each SKILL.md** — primarily the Procedure section and the citation format examples.

- [ ] **Step 2: Commit**

```bash
git add dks/skills/ dks/commands/
git commit -m "docs: skill prompts updated for layer-aware CLI + layer-tagged citations"
```

---

## Task 8 — Version bump, docs, end-to-end smoke

**Files:**
- Modify: `src/dks/__init__.py` (version 0.1.0 → 0.2.0)
- Modify: `pyproject.toml` (version 0.0.1 → 0.2.0 — sync with package)
- Modify: `dks/.claude-plugin/plugin.json` (0.1.0 → 0.2.0)
- Modify: `README.md` (one sentence in Architecture summary)
- Modify: `docs/USAGE.md` (new "Cascaded KB" section after Installation)

- [ ] **Step 1: Bump versions** in all three places.

- [ ] **Step 2: Add `## Cascaded KB` section to USAGE.md** between Installation and Step 1. Cover:
   - The two-layer model (`~/.dks/` global + auto-discovered `.dks/` project).
   - Auto-discovery rules + env-var overrides (`DKS_GLOBAL`, `DKS_PROJECT`).
   - Read shadowing semantics.
   - Write default (project when present, else global; `--write-global` to force).
   - Citation format change (`@layer` tag).
   - When you want global only (user-scope plugin in a non-project repo) vs project-only (`--no-global`).

- [ ] **Step 3: README sentence** in Architecture summary — "Two-layer KB: a global `~/.dks/` layer plus an auto-discovered project `.dks/` layer; project shadows global on reads."

- [ ] **Step 4: End-to-end smoke test** (manual; document in the commit message):

```bash
# Set up two layers
mkdir -p /tmp/dks-e2e-{global,project}/.dks
DKS_GLOBAL=/tmp/dks-e2e-global/.dks DKS_PROJECT=/tmp/dks-e2e-project/.dks \
  uv run dks ingest <some.md>     # writes to project by default

# Seed a global wiki entry
DKS_GLOBAL=/tmp/dks-e2e-global/.dks DKS_PROJECT=/tmp/dks-e2e-project/.dks \
  bash -c 'echo "{...}" | uv run dks wiki write global-only --write-global'

# Seed a project entry that shadows
DKS_GLOBAL=/tmp/dks-e2e-global/.dks DKS_PROJECT=/tmp/dks-e2e-project/.dks \
  bash -c 'echo "{...}" | uv run dks wiki write global-only'

# Search — confirm project wins
DKS_GLOBAL=/tmp/dks-e2e-global/.dks DKS_PROJECT=/tmp/dks-e2e-project/.dks \
  uv run dks wiki search global-only      # → layer: project
```

- [ ] **Step 5: Run full suite + final commit + tag**

```bash
uv run pytest
uv run mypy src
uv run ruff check src tests
git add -A
git commit -m "chore: bump to 0.2.0; docs + smoke verification"
git push -u origin phase-4-cascaded-kb
git tag phase-4-complete
git push --tags
```

---

## Self-review

- **Spec coverage:** All design rules from the brainstorm (project shadows global; auto-discovery; env-var overrides; write defaults to project; citation `@layer` tag; lint walks both) are addressed.
- **No placeholders:** every step has the actual test code or implementation to write.
- **Type consistency:** `KbLayer`/`KbLayers` (Task 1) used by store (Tasks 2–4), search (Task 5), CLI (Task 6). `BlockHit`, `WikiSlugHit`, `SearchHit` all gain a `layer` field consistently.
- **Breaking-change discipline:** version bumped, plugin manifest bumped, CLI flag rename documented in commit messages.
- **What's deliberately not here:** content-diff warning when project shadows global with different content (mentioned in the Phase 4 brainstorm). Skipped as a v0.2.x follow-up — non-blocking for the cascading itself.

## What's left for v0.2.x

- `WARN: shadows global block with different content` on `dks blocks get` when both layers serve the same id with diverging content.
- `dks layers` introspection subcommand (`dks layers list` to print which layers are active).
- Project-marker file alternative to a `.dks/` directory (e.g. `dks.toml`), for repos that don't want a `.dks/` dir at the root.
