"""Parser registry: dispatch a file path to the right parser by suffix."""

from collections.abc import Callable
from pathlib import Path

from dks.parsers.markdown import parse_markdown_file
from dks.types import TypedContentItem

ParserFn = Callable[[Path], list[TypedContentItem]]

_REGISTRY: dict[str, ParserFn] = {
    ".md": parse_markdown_file,
}


def get_parser(path: Path) -> ParserFn:
    suffix = path.suffix.lower()
    if suffix not in _REGISTRY:
        raise ValueError(f"no parser registered for suffix {suffix!r} (path={path})")
    return _REGISTRY[suffix]
