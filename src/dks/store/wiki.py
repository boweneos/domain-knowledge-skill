"""Wiki entry storage — one Markdown file per topic, with JSON frontmatter."""

import datetime as _dt
import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

_FENCE = "---"


class WikiEntry(BaseModel):
    topic: str
    slug: str
    source_refs: list[str]
    body: str
    compiled_at: str | None = None


def write_wiki_entry(wiki_dir: Path, entry: WikiEntry) -> Path:
    """Persist a WikiEntry. Sets `compiled_at` to now() if unset."""
    wiki_dir.mkdir(parents=True, exist_ok=True)
    if not entry.compiled_at:
        entry.compiled_at = _dt.datetime.now(_dt.UTC).isoformat()
    frontmatter = entry.model_dump_json(exclude={"body"}, indent=2)
    target = wiki_dir / f"{entry.slug}.md"
    target.write_text(f"{_FENCE}\n{frontmatter}\n{_FENCE}\n{entry.body}\n")
    return target


def read_wiki_entry(wiki_dir: Path, slug: str) -> WikiEntry:
    """Load and return the WikiEntry with the given slug."""
    target = wiki_dir / f"{slug}.md"
    if not target.exists():
        raise FileNotFoundError(f"no wiki entry for slug {slug!r}")
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


def list_wiki_entries(wiki_dir: Path) -> list[str]:
    """Return all slugs (stems of .md files) under wiki_dir."""
    if not wiki_dir.is_dir():
        return []
    return [p.stem for p in wiki_dir.glob("*.md")]
