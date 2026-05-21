"""Shared parser → normalizer contract.

`TypedContentItem` is the slim shape every parser must emit. The normalizer
turns a list of these (plus source metadata) into `NormalizedBlock`s.
"""

from typing import Literal

from pydantic import BaseModel, Field

from dks.locators import Locator

BlockType = Literal["text", "heading", "table", "list", "code"]


class TypedContentItem(BaseModel):
    content: str = Field(min_length=1)
    block_type: BlockType = "text"
    locator: Locator
