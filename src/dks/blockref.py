"""Encode / decode BlockRef strings.

A BlockRef is the canonical string form `<source_file>#<locator>` used as a
stable opaque identifier. `decode_blockref` reconstructs the source path and a
minimal Locator; some metadata that is not part of the stable identifier (e.g.
markdown heading_path) is not recovered by decode.
"""

import re

from dks.locators import DocxLocator, ExcelLocator, Locator, MarkdownLocator, PdfLocator


def encode_blockref(source_file: str, locator: Locator) -> str:
    if isinstance(locator, PdfLocator):
        suffix = f"p{locator.page}"
        if locator.section:
            suffix += f"#{locator.section}"
        if locator.clause:
            suffix += f"#{locator.clause}"
        return f"{source_file}#{suffix}"
    if isinstance(locator, DocxLocator):
        return f"{source_file}#§{locator.section}#p{locator.paragraph_idx}"
    if isinstance(locator, ExcelLocator):
        return f"{source_file}#s{locator.sheet}!{locator.cells}"
    if isinstance(locator, MarkdownLocator):
        return f"{source_file}#L{locator.line_start}-{locator.line_end}"
    raise TypeError(f"Unknown locator type: {type(locator).__name__}")


_PDF_RE = re.compile(r"^p(?P<page>\d+)(?:#(?P<section>[^#]+))?(?:#(?P<clause>.+))?$")
_DOCX_RE = re.compile(r"^§(?P<section>.+?)#p(?P<idx>\d+)$")
_EXCEL_RE = re.compile(r"^s(?P<sheet>[^!]+)!(?P<cells>.+)$")
_MD_RE = re.compile(r"^L(?P<start>\d+)-(?P<end>\d+)$")


def decode_blockref(ref: str) -> tuple[str, Locator]:
    if "#" not in ref:
        raise ValueError(f"malformed BlockRef (no '#'): {ref!r}")

    source_file, _, locator_str = ref.partition("#")
    if not locator_str:
        raise ValueError(f"malformed BlockRef (empty locator): {ref!r}")

    if m := _PDF_RE.match(locator_str):
        page = int(m.group("page"))
        section = m.group("section")
        clause = m.group("clause")
        return source_file, PdfLocator(page=page, section=section, clause=clause)

    if m := _DOCX_RE.match(locator_str):
        return source_file, DocxLocator(
            section=m.group("section"), paragraph_idx=int(m.group("idx"))
        )

    if m := _EXCEL_RE.match(locator_str):
        return source_file, ExcelLocator(sheet=m.group("sheet"), cells=m.group("cells"))

    if m := _MD_RE.match(locator_str):
        return source_file, MarkdownLocator(
            heading_path=[],
            line_start=int(m.group("start")),
            line_end=int(m.group("end")),
        )

    raise ValueError(f"unknown locator format: {locator_str!r}")
