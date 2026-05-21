"""Markdown pass-through parser.

Walks a .md file line by line, maintaining a heading path, and emits one
TypedContentItem per heading and per paragraph. Code fences and list blocks
are treated as paragraphs in Phase 1; refinement is a Phase 2 concern.
"""

import re
from pathlib import Path

from dks.locators import MarkdownLocator
from dks.types import TypedContentItem

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def parse_markdown_file(path: Path) -> list[TypedContentItem]:
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    items: list[TypedContentItem] = []
    heading_path: list[str] = []
    para_buf: list[str] = []
    para_start: int | None = None

    def flush_paragraph(end_line: int) -> None:
        nonlocal para_buf, para_start
        if para_buf and para_start is not None:
            items.append(
                TypedContentItem(
                    content="\n".join(para_buf),
                    block_type="text",
                    locator=MarkdownLocator(
                        heading_path=list(heading_path),
                        line_start=para_start,
                        line_end=end_line,
                    ),
                )
            )
        para_buf = []
        para_start = None

    for idx, line in enumerate(lines, start=1):
        m = _HEADING_RE.match(line)
        if m:
            flush_paragraph(idx - 1)
            level = len(m.group(1))
            title = m.group(2)
            # Truncate heading_path to depth = level-1, then append
            heading_path = heading_path[: level - 1] + [title]
            items.append(
                TypedContentItem(
                    content=line,
                    block_type="heading",
                    locator=MarkdownLocator(
                        heading_path=list(heading_path),
                        line_start=idx,
                        line_end=idx,
                    ),
                )
            )
        elif line.strip() == "":
            flush_paragraph(idx - 1)
        else:
            if para_start is None:
                para_start = idx
            para_buf.append(line)

    flush_paragraph(len(lines))
    return items
