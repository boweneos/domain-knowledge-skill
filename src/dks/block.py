"""NormalizedBlock — the citation-preserving block that the writer persists."""

import json

from pydantic import BaseModel

from dks.locators import Locator
from dks.types import BlockType, Classification

_FENCE = "---"


class NormalizedBlock(BaseModel):
    source_file: str
    block_id: str
    locator: Locator
    block_type: BlockType = "text"
    content: str
    classification: Classification = "internal"


def to_markdown(block: NormalizedBlock) -> str:
    """Serialize a NormalizedBlock to its on-disk Markdown form."""
    frontmatter = block.model_dump_json(exclude={"content"}, indent=2)
    return f"{_FENCE}\n{frontmatter}\n{_FENCE}\n{block.content}\n"


def parse_markdown(text: str) -> NormalizedBlock:
    """Parse a Markdown file written by `to_markdown` back into a NormalizedBlock."""
    if not text.startswith(_FENCE + "\n"):
        raise ValueError("missing opening frontmatter fence ('---')")

    rest = text[len(_FENCE) + 1 :]
    close_idx = rest.find("\n" + _FENCE + "\n")
    if close_idx == -1:
        raise ValueError("missing closing frontmatter fence ('---')")

    frontmatter_str = rest[:close_idx]
    content = rest[close_idx + len(_FENCE) + 2 :].rstrip("\n")

    data = json.loads(frontmatter_str)
    data["content"] = content
    return NormalizedBlock.model_validate(data)
