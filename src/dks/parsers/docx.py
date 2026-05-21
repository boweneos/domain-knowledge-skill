"""DOCX parser via Docling — paragraphs + headings → TypedContentItem."""

from pathlib import Path

from docling.document_converter import DocumentConverter

from dks.locators import DocxLocator
from dks.types import BlockType, TypedContentItem


def parse_docx_file(path: Path) -> list[TypedContentItem]:
    """Parse a DOCX file using Docling and return typed content items.

    Headings (section_header label) map to block_type="heading".
    Paragraphs (text label) map to block_type="text".
    Each item carries a DocxLocator with the most-recent heading as section
    and a running paragraph_idx across the whole document.
    """
    converter = DocumentConverter()
    result = converter.convert(str(path))
    doc = result.document

    items: list[TypedContentItem] = []
    current_section = "body"
    paragraph_idx = 0

    # doc.texts yields SectionHeaderItem and TextItem elements in document order.
    # SectionHeaderItem has label.value == "section_header".
    # TextItem has label.value == "text".
    for element in doc.texts:
        text = (element.text or "").strip()
        if not text:
            continue

        label_value = str(getattr(element, "label", "")).lower()
        is_heading = label_value == "section_header"

        if is_heading:
            current_section = text

        block_type: BlockType = "heading" if is_heading else "text"
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
