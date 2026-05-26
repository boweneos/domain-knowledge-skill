"""DOCX parser via Docling — paragraphs + headings → TypedContentItem."""

from pathlib import Path

from docling.document_converter import DocumentConverter

from dks.locators import DocxLocator
from dks.types import BlockType, TypedContentItem


def _block_type_from_label(label: object) -> BlockType:
    """Map a Docling element label to our BlockType. Defaults to 'text'."""
    if label is None:
        return "text"
    label_str = str(label).lower()
    if "header" in label_str:
        return "heading"
    if "list" in label_str or "enumeration" in label_str:
        return "list"
    if "table" in label_str:
        return "table"
    if "code" in label_str:
        return "code"
    return "text"


def parse_docx_file(path: Path) -> list[TypedContentItem]:
    """Parse a DOCX file using Docling and return typed content items.

    Docling labels are mapped to our BlockType via _block_type_from_label:
    - 'header' / 'section_header' → heading
    - 'list' / 'enumeration' / 'list_item' → list
    - 'table' → table
    - 'code' / 'code_block' → code
    - everything else → text

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
