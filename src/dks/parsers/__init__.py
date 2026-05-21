"""Parser registry: dispatch a file path to the right parser by suffix."""

from collections.abc import Callable
from pathlib import Path

from dks.parsers.docx import parse_docx_file
from dks.parsers.excel import parse_excel_file
from dks.parsers.markdown import parse_markdown_file
from dks.parsers.pdf import parse_pdf_file
from dks.types import TypedContentItem

ParserFn = Callable[[Path], list[TypedContentItem]]

_REGISTRY: dict[str, ParserFn] = {
    ".md": parse_markdown_file,
    ".xlsx": parse_excel_file,
    ".docx": parse_docx_file,
    ".pdf": parse_pdf_file,
}


def get_parser(path: Path) -> ParserFn:
    suffix = path.suffix.lower()
    if suffix not in _REGISTRY:
        raise ValueError(f"no parser registered for suffix {suffix!r} (path={path})")
    return _REGISTRY[suffix]
