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
    """Return entries whose topic or body contains `query` (case-insensitive)."""
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
