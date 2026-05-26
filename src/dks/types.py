"""Shared parser → normalizer contract.

`TypedContentItem` is the slim shape every parser must emit. The normalizer
turns a list of these (plus source metadata) into `NormalizedBlock`s.
"""

from typing import Literal

from pydantic import BaseModel, Field

from dks.locators import Locator

BlockType = Literal["text", "heading", "table", "list", "code"]

Classification = Literal["public", "internal", "confidential", "restricted"]

_CLASSIFICATION_ORDER: tuple[Classification, ...] = (
    "public",
    "internal",
    "confidential",
    "restricted",
)


def classification_rank(c: Classification) -> int:
    """Return the strictness rank: public=0, internal=1, confidential=2, restricted=3."""
    return _CLASSIFICATION_ORDER.index(c)


class TypedContentItem(BaseModel):
    content: str = Field(min_length=1)
    block_type: BlockType = "text"
    locator: Locator
