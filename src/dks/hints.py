"""Ingest-time advisory hints.

Currently exposes `pageindex_hint`: returns a HINT string when a freshly
ingested source is structurally large enough that a navigation tree would help,
and no pageindex.json exists yet. Returns None otherwise.
"""

import os
from pathlib import Path
from typing import Final

from dks.block import NormalizedBlock
from dks.layers import KbLayer
from dks.locators import DocxLocator, ExcelLocator, Locator, MarkdownLocator, PdfLocator

_DEFAULT_BLOCKS_THRESHOLD: Final[int] = 80
_DEFAULT_SECTIONS_THRESHOLD: Final[int] = 8


def _section_key(loc: Locator) -> str | None:
    """Best-effort 'which section is this block in' key, or None if unknown.

    Headerless PDFs (no `section` set) intentionally return None so they only
    trip the hint via block count, not by counting one section per page.
    """
    if isinstance(loc, PdfLocator):
        return loc.section
    if isinstance(loc, DocxLocator):
        return loc.section
    if isinstance(loc, ExcelLocator):
        return loc.sheet
    if isinstance(loc, MarkdownLocator):
        return loc.heading_path[0] if loc.heading_path else None
    return None


def _thresholds() -> tuple[int, int]:
    blocks_t = int(os.environ.get("DKS_PAGEINDEX_HINT_BLOCKS", _DEFAULT_BLOCKS_THRESHOLD))
    sections_t = int(os.environ.get("DKS_PAGEINDEX_HINT_SECTIONS", _DEFAULT_SECTIONS_THRESHOLD))
    return blocks_t, sections_t


def pageindex_hint(
    layer: KbLayer, source_file: str, blocks: list[NormalizedBlock]
) -> str | None:
    """Advise the operator to build a pageindex when the source is structurally large.

    Returns the hint string if all of the following hold:
    - block count >= DKS_PAGEINDEX_HINT_BLOCKS (default 80), OR
    - distinct section count >= DKS_PAGEINDEX_HINT_SECTIONS (default 8); AND
    - no `<source>.pageindex.json` already exists in the layer's index dir.

    Otherwise returns None.
    """
    blocks_t, sections_t = _thresholds()

    n_blocks = len(blocks)
    section_keys = {key for b in blocks if (key := _section_key(b.locator)) is not None}
    n_sections = len(section_keys)

    if n_blocks < blocks_t and n_sections < sections_t:
        return None

    pageindex_path = layer.index_dir / f"{Path(source_file).name}.pageindex.json"
    if pageindex_path.exists():
        return None

    return (
        f"HINT: {source_file}: {n_blocks} blocks across {n_sections} sections — "
        f"consider running the dks-build-pageindex skill for navigation"
    )
