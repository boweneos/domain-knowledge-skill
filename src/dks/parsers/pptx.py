"""PPTX parser via Docling — slide titles + body text → TypedContentItem.

PPTX semantics differ from DOCX:
- 'title' labels mark slide titles, treated as section boundaries.
- Other text (bullets, body) attaches to the most-recent slide title.
- DocxLocator is reused since the slide-title-as-section model is structurally
  the same as DOCX heading-as-section; the locator's `section` is opaque to
  downstream consumers.
"""

from pathlib import Path

from docling.document_converter import DocumentConverter

from dks.locators import DocxLocator
from dks.types import BlockType, TypedContentItem


def _block_type_from_label(label: object) -> BlockType:
    """Map a Docling PPTX element label to our BlockType.

    PPTX 'title' is the slide title — treated as a heading. Otherwise mirrors
    the DOCX label conventions.
    """
    if label is None:
        return "text"
    label_str = str(label).lower()
    if label_str == "title" or "header" in label_str:
        return "heading"
    if "list" in label_str or "enumeration" in label_str:
        return "list"
    if "table" in label_str:
        return "table"
    if "code" in label_str:
        return "code"
    return "text"


def parse_pptx_file(path: Path) -> list[TypedContentItem]:
    """Parse a PPTX file using Docling.

    Each slide's title (`label == "title"`) starts a new section; subsequent
    text elements within that slide attach to it via DocxLocator. Empty text
    elements are skipped. Paragraph index runs across the whole deck.
    """
    converter = DocumentConverter()
    result = converter.convert(str(path))
    doc = result.document

    items: list[TypedContentItem] = []
    current_section = "slide-1"
    paragraph_idx = 0

    for element in doc.texts:
        text = (element.text or "").strip()
        if not text:
            continue
        label = getattr(element, "label", None)
        block_type = _block_type_from_label(label)
        if block_type == "heading":
            current_section = text

        items.append(
            TypedContentItem(
                content=text,
                block_type=block_type,
                locator=DocxLocator(
                    section=current_section,
                    paragraph_idx=paragraph_idx,
                ),
            )
        )
        paragraph_idx += 1

    return items
