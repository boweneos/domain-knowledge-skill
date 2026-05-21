"""PageIndex tree storage — sidecar JSON per source document.

Schema is intentionally loose; the producer (the `dks-build-pageindex` skill)
owns the tree shape. Storage just persists/reads.
"""

import json
from pathlib import Path
from typing import Any, cast


def _target(index_dir: Path, source_file: str) -> Path:
    basename = Path(source_file).name
    return index_dir / f"{basename}.pageindex.json"


def write_pageindex(index_dir: Path, source_file: str, tree: dict[str, Any]) -> Path:
    """Persist `tree` as a sidecar JSON file. Returns the path written."""
    index_dir.mkdir(parents=True, exist_ok=True)
    target = _target(index_dir, source_file)
    target.write_text(json.dumps(tree, indent=2))
    return target


def read_pageindex(index_dir: Path, source_file: str) -> dict[str, Any]:
    """Load and return the JSON tree for `source_file`."""
    target = _target(index_dir, source_file)
    if not target.exists():
        raise FileNotFoundError(f"no PageIndex for {source_file!r} at {target}")
    return cast(dict[str, Any], json.loads(target.read_text()))
