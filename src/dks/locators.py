"""Locator types — the citation primitive per document format.

A `Locator` carries the minimum information required to point back to a specific
span of a source document. The shape varies by document type but every variant
provides enough detail to reconstruct an audit-grade citation.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PdfLocator(BaseModel):
    kind: Literal["pdf"] = "pdf"
    page: int = Field(ge=1)
    section: str | None = None
    clause: str | None = None


class DocxLocator(BaseModel):
    kind: Literal["docx"] = "docx"
    section: str
    paragraph_idx: int = Field(ge=0)


class ExcelLocator(BaseModel):
    kind: Literal["excel"] = "excel"
    sheet: str
    cells: str  # "A1" or "A1:C12"


class MarkdownLocator(BaseModel):
    kind: Literal["md"] = "md"
    heading_path: list[str]
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


Locator = Annotated[
    PdfLocator | DocxLocator | ExcelLocator | MarkdownLocator,
    Field(discriminator="kind"),
]
