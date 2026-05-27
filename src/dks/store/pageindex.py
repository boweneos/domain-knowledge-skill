"""PageIndex tree storage — sidecar JSON per source document, layer-aware."""

import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from dks.layers import KbLayer, KbLayers


def _target(index_dir: Path, source_file: str) -> Path:
    basename = Path(source_file).name
    return index_dir / f"{basename}.pageindex.json"


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


class PageIndexHit(BaseModel):
    """A node match from `search_pageindex`.

    `path` is the chain of ancestor titles ending in the matching node's title,
    so the LLM consumer can see context (e.g. ["root", "Section 3", "3.2 X"]).
    `block_ids` are the ids attached *directly* to the matching node; children
    are not flattened in — the consumer can recurse via `read_pageindex` if it
    wants the full subtree.
    """

    source: str
    layer: str
    title: str
    path: list[str]
    block_ids: list[str]


def _walk_tree_for_query(
    node: dict[str, Any],
    *,
    needle: str,
    ancestors: tuple[str, ...],
    source: str,
    layer: str,
    out: list[PageIndexHit],
) -> None:
    title = str(node.get("title", ""))
    path = (*ancestors, title)
    if needle in title.casefold():
        out.append(
            PageIndexHit(
                source=source,
                layer=layer,
                title=title,
                path=list(path),
                block_ids=list(node.get("block_ids", [])),
            )
        )
    for child in node.get("children", []) or []:
        if isinstance(child, dict):
            _walk_tree_for_query(
                child,
                needle=needle,
                ancestors=path,
                source=source,
                layer=layer,
                out=out,
            )


def search_pageindex(layers: KbLayers, query: str) -> list[PageIndexHit]:
    """Return nodes whose `title` contains `query` (case-insensitive) across
    every `<source>.pageindex.json` in active layers.

    Project-layer hits appear before global-layer hits. Within a layer, hits
    are grouped by source in lexicographic filename order; tree traversal is
    depth-first.

    Returns an empty list when no pageindex files exist or no node matches.
    """
    needle = query.casefold()
    hits: list[PageIndexHit] = []
    for layer in layers.for_read():
        if not layer.index_dir.exists():
            continue
        for path in sorted(layer.index_dir.glob("*.pageindex.json")):
            try:
                tree = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(tree, dict):
                continue
            source = path.name.removesuffix(".pageindex.json")
            _walk_tree_for_query(
                tree,
                needle=needle,
                ancestors=(),
                source=source,
                layer=layer.name,
                out=hits,
            )
    return hits
