"""Wiki entry storage — one Markdown file per topic, layer-aware."""

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from dks.layers import KbLayer, KbLayers
from dks.types import Classification

_FENCE = "---"


class WikiEntry(BaseModel):
    topic: str
    slug: str
    source_refs: list[str]
    body: str
    compiled_at: str | None = None
    classification: Classification = "internal"


@dataclass(frozen=True)
class WikiSlugHit:
    slug: str
    layer: str


def write_wiki_entry(layer: KbLayer, entry: WikiEntry) -> Path:
    """Persist a WikiEntry to the given layer. Sets compiled_at if unset."""
    layer.wiki_dir.mkdir(parents=True, exist_ok=True)
    if not entry.compiled_at:
        entry.compiled_at = _dt.datetime.now(_dt.UTC).isoformat()
    frontmatter = entry.model_dump_json(exclude={"body"}, indent=2)
    target = layer.wiki_dir / f"{entry.slug}.md"
    target.write_text(f"{_FENCE}\n{frontmatter}\n{_FENCE}\n{entry.body}\n")
    return target


def _read_from(wiki_dir: Path, slug: str) -> WikiEntry:
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
            return _read_from(layer.wiki_dir, slug), layer.name
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
