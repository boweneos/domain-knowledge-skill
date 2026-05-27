"""Per-source metadata — supersedes links + ingest provenance.

Stored as a `.meta.json` sidecar inside each source's normalized directory:
`<layer>/normalized/<source_basename>/.meta.json`. Co-located with the blocks
so `rm -rf` of a source removes both blocks and metadata cleanly.
"""

import datetime as _dt
import json
from pathlib import Path

from pydantic import BaseModel

from dks.layers import KbLayer, KbLayers


class SourceMeta(BaseModel):
    """Metadata attached to one ingested source.

    `supersedes` names other source_files (by basename) that this source
    replaces. A wiki entry citing a superseded source becomes a candidate for
    re-compile against the superseding source.
    """

    supersedes: list[str] = []
    ingested_at: str | None = None


def _target(layer: KbLayer, source_file: str) -> Path:
    basename = Path(source_file).name
    return layer.normalized_dir / basename / ".meta.json"


def write_meta(layer: KbLayer, source_file: str, meta: SourceMeta) -> Path:
    """Persist meta to the given layer. Sets `ingested_at` if unset."""
    target = _target(layer, source_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not meta.ingested_at:
        meta.ingested_at = _dt.datetime.now(_dt.UTC).isoformat()
    target.write_text(meta.model_dump_json(indent=2))
    return target


def read_meta(layers: KbLayers, source_file: str) -> tuple[SourceMeta, str] | None:
    """Read meta + which layer served it. Project first, fall back to global.

    Returns None if no meta sidecar exists in any layer (sources without meta
    are the common case and are not errors).
    """
    for layer in layers.for_read():
        target = _target(layer, source_file)
        if target.exists():
            return SourceMeta.model_validate_json(target.read_text()), layer.name
    return None


def compute_superseded_by(layers: KbLayers) -> dict[str, list[tuple[str, str]]]:
    """Walk all sources in active layers, return the inverse supersedes map.

    Returns `{old_source: [(new_source, new_layer), ...]}` — for each source
    that was superseded by something, the list of superseding (source, layer)
    pairs. Multiple ingestions can supersede the same old source; the map
    captures all of them.

    A source with no meta, or meta with empty `supersedes`, contributes
    nothing to the map.
    """
    inverse: dict[str, list[tuple[str, str]]] = {}
    for layer in layers.for_read():
        if not layer.normalized_dir.is_dir():
            continue
        for source_dir in layer.normalized_dir.iterdir():
            if not source_dir.is_dir():
                continue
            meta_path = source_dir / ".meta.json"
            if not meta_path.exists():
                continue
            try:
                meta = SourceMeta.model_validate_json(meta_path.read_text())
            except (json.JSONDecodeError, ValueError, OSError):
                continue
            for old in meta.supersedes:
                inverse.setdefault(old, []).append((source_dir.name, layer.name))
    return inverse
