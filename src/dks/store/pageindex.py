"""PageIndex tree storage — sidecar JSON per source document, layer-aware."""

import json
from pathlib import Path
from typing import Any, cast

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
