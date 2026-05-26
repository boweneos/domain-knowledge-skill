"""Markdown pass-through parser.

Walks a .md file line by line, maintaining a heading path, and emits one
TypedContentItem per heading, paragraph, or fenced code block.

Code fences (``` or ~~~) are detected and emitted as block_type="code".
The fence lines themselves are excluded from the content. Unterminated fences
(missing closing fence) are gracefully handled by emitting the accumulated
code content up to EOF.
"""

import re
from pathlib import Path

from dks.locators import MarkdownLocator
from dks.types import TypedContentItem

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^(```|~~~)")


def parse_markdown_file(path: Path) -> list[TypedContentItem]:
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    items: list[TypedContentItem] = []
    heading_path: list[str] = []
    para_buf: list[str] = []
    para_start: int | None = None

    # Code-fence state
    in_code: bool = False
    code_buf: list[str] = []
    code_start: int | None = None
    code_fence: str | None = None

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
        if in_code:
            # Look for the matching closing fence
            fm = _FENCE_RE.match(line)
            if fm and code_fence is not None and line.lstrip().startswith(code_fence):
                # Closing fence found — emit the code block (excluding fence lines)
                if code_buf and code_start is not None:
                    items.append(
                        TypedContentItem(
                            content="\n".join(code_buf),
                            block_type="code",
                            locator=MarkdownLocator(
                                heading_path=list(heading_path),
                                line_start=code_start,
                                line_end=idx,
                            ),
                        )
                    )
                in_code = False
                code_buf = []
                code_start = None
                code_fence = None
            else:
                code_buf.append(line)
            continue

        fm = _FENCE_RE.match(line)
        if fm:
            # Opening fence — flush any in-progress paragraph first
            flush_paragraph(idx - 1)
            in_code = True
            code_fence = fm.group(1)
            code_start = idx
            code_buf = []
            continue

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

    # Flush any unterminated code fence gracefully
    if in_code and code_buf and code_start is not None:
        items.append(
            TypedContentItem(
                content="\n".join(code_buf),
                block_type="code",
                locator=MarkdownLocator(
                    heading_path=list(heading_path),
                    line_start=code_start,
                    line_end=len(lines),
                ),
            )
        )

    flush_paragraph(len(lines))
    return items
