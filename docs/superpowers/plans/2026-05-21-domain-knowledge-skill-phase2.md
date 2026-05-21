# Domain Knowledge Skill — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Round out ingestion (PDF, DOCX, Excel), expose a block-store / PageIndex / wiki CLI surface, and ship the LLM-driven Claude Code skills that orchestrate PageIndex tree builds, wiki compile, and lint. After Phase 2 the user can ingest a real corpus and produce a citation-linked compiled wiki.

**Architecture refinement (locked in 2026-05-21):** The `dks` Python package stays deterministic — parsers, normalization, storage, CLI. All LLM-driven operations are Claude Code skills that invoke the `dks` CLI for deterministic steps and use Claude Code's own LLM access for judgment work. No `ANTHROPIC_API_KEY` lives in `dks`.

**Tech Stack (additions to Phase 1):** openpyxl + pandas (Excel), Docling (DOCX), MinerU (PDF). Skills are Markdown files with frontmatter under a top-level `skills/` directory in the repo.

---

## File Structure Added in Phase 2

```
src/dks/
  parsers/
    excel.py                       # openpyxl + pandas → TypedContentItem
    docx.py                        # Docling → TypedContentItem
    pdf.py                         # MinerU → TypedContentItem
  store/
    __init__.py
    blocks.py                      # read NormalizedBlock from disk by source / block_id
    pageindex.py                   # read/write PageIndex sidecar JSON
    wiki.py                        # read/write compiled wiki articles
  cli.py                           # MODIFIED — add blocks/pageindex/wiki subcommands
  blockref.py                      # MODIFIED — encode PdfLocator.clause
  parsers/markdown.py              # MODIFIED — BOM-tolerant read
tests/
  parsers/
    test_excel.py
    test_docx.py
    test_pdf.py
  store/
    test_blocks.py
    test_pageindex.py
    test_wiki.py
  fixtures/
    sample.xlsx                    # generated in test setup
    sample.docx                    # checked-in binary
    sample.pdf                     # checked-in binary (1-2 pages)
skills/
  dks-build-pageindex/
    SKILL.md                       # Claude Code skill manifest + prompt
  dks-compile-wiki/
    SKILL.md
  dks-lint-wiki/
    SKILL.md
```

---

## Task 0 — Phase 1 Carryover Fixes

**Files:**
- Modify: `src/dks/cli.py` (source_file scoping)
- Modify: `src/dks/blockref.py` (encode PdfLocator.clause)
- Modify: `src/dks/parsers/markdown.py` (BOM-tolerant read)
- Modify: `tests/test_blockref.py` (add clause-encoding test)
- Modify: `tests/parsers/test_markdown.py` (add BOM fixture test)

- [ ] **Step 1: Update `encode_blockref` to encode `PdfLocator.clause`**

Edit `src/dks/blockref.py`, locate the `PdfLocator` branch in `encode_blockref`:

```python
    if isinstance(locator, PdfLocator):
        suffix = f"p{locator.page}"
        if locator.section:
            suffix += f"#{locator.section}"
        if locator.clause:
            suffix += f"#{locator.clause}"
        return f"{source_file}#{suffix}"
```

Update `_PDF_RE` to capture optional clause:

```python
_PDF_RE = re.compile(r"^p(?P<page>\d+)(?:#(?P<section>[^#]+))?(?:#(?P<clause>.+))?$")
```

Update the decode branch to read `clause`:

```python
    if m := _PDF_RE.match(locator_str):
        page = int(m.group("page"))
        section = m.group("section")
        clause = m.group("clause")
        return source_file, PdfLocator(page=page, section=section, clause=clause)
```

- [ ] **Step 2: Add tests for clause encoding**

Append to `tests/test_blockref.py`:

```python
def test_encode_pdf_with_section_and_clause():
    ref = encode_blockref("policies/claims.pdf", PdfLocator(page=14, section="3.2", clause="3.2.1"))
    assert ref == "policies/claims.pdf#p14#3.2#3.2.1"


def test_roundtrip_pdf_with_clause():
    original = PdfLocator(page=14, section="3.2", clause="3.2.1")
    ref = encode_blockref("policies/claims.pdf", original)
    src, loc = decode_blockref(ref)
    assert src == "policies/claims.pdf"
    assert loc == original
```

Run: `uv run pytest tests/test_blockref.py -v` — 11 passed (was 9).

- [ ] **Step 3: Update Markdown parser to handle BOM**

Edit `src/dks/parsers/markdown.py`:

```python
def parse_markdown_file(path: Path) -> list[TypedContentItem]:
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    # ... rest unchanged
```

- [ ] **Step 4: Add BOM test**

Append to `tests/parsers/test_markdown.py`:

```python
def test_parse_markdown_strips_utf8_bom(tmp_path):
    src = tmp_path / "bom.md"
    # Write with explicit BOM
    src.write_bytes("﻿# Heading\n\nA paragraph.\n".encode("utf-8"))
    items = parse_markdown_file(src)
    # First heading should not have BOM prefix or be misclassified
    headings = [i for i in items if i.block_type == "heading"]
    assert len(headings) == 1
    assert "# Heading" in headings[0].content
    assert "﻿" not in headings[0].content
```

- [ ] **Step 5: Update `cli.ingest` to scope source_file to repo-relative path**

Edit `src/dks/cli.py`. Change the `ingest` command to accept an optional `--root` and compute `source_file` relative to it:

```python
@app.command()
def ingest(
    path: Path = typer.Argument(..., help="Source file to ingest."),
    output_dir: Path = typer.Option(
        Path("normalized"), "--output-dir", "-o", help="Where to write normalized blocks."
    ),
    root: Path = typer.Option(
        Path("raw"), "--root", "-r", help="Root directory the source path is relative to; defaults to ./raw"
    ),
) -> None:
    if not path.exists() or not path.is_file():
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(code=2)

    try:
        source_file = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        # path is not under root; fall back to filename
        source_file = path.name

    try:
        parser = get_parser(path)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e

    items = parser(path)
    blocks = normalize(source_file=source_file, items=items)
    written = write_blocks(blocks, output_dir=output_dir)
    typer.echo(f"wrote {len(written)} blocks to {output_dir}/{source_file}/")
```

Update `tests/test_cli.py` to assert on the relative-path behavior; existing tests still pass because tmp_path will not be under `./raw` so the fallback to `path.name` kicks in. Add a new test:

```python
def test_ingest_uses_path_relative_to_root(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    nested = root / "policies"
    nested.mkdir()
    source = nested / "claims.md"
    source.write_text("A claim rule.\n")
    output = tmp_path / "out"

    result = runner.invoke(
        app,
        ["ingest", str(source), "--output-dir", str(output), "--root", str(root)],
    )
    assert result.exit_code == 0
    # source_file should be "policies/claims.md", and the writer flattens to dir name
    files = list((output / "claims.md").glob("*.md"))
    assert len(files) == 1
    # Parse one to verify the source_file frontmatter
    from dks.block import parse_markdown
    parsed = parse_markdown(files[0].read_text())
    assert parsed.source_file == "policies/claims.md"
```

- [ ] **Step 6: Run full suite + commit**

```bash
uv run pytest
uv run mypy src
uv run ruff check src tests
git add -A
git commit -m "fix: phase-1 carryovers (encode clause, BOM-tolerant md, root-scoped source_file)"
```

Expected: 47+ tests pass.

---

## Task 1 — Excel parser

**Files:**
- Create: `src/dks/parsers/excel.py`
- Create: `tests/parsers/test_excel.py`
- Modify: `src/dks/parsers/__init__.py` (register `.xlsx`)
- Modify: `pyproject.toml` (add `openpyxl>=3.1`)

**Strategy:** Each non-empty row becomes one `TypedContentItem` with `ExcelLocator(sheet, cells="<col_start><row>:<col_end><row>")`. Content is tab-joined cell values. Rows are scanned per sheet.

- [ ] **Step 1: Add openpyxl to deps**

In `pyproject.toml`, add `"openpyxl>=3.1"` to `dependencies`. Then `uv sync`.

- [ ] **Step 2: Write the failing tests**

`tests/parsers/test_excel.py`:
```python
from pathlib import Path

import openpyxl
from openpyxl import Workbook

from dks.parsers.excel import parse_excel_file
from dks.locators import ExcelLocator


def _make_xlsx(path: Path) -> None:
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Mortality"
    sheet.append(["Age", "Rate"])
    sheet.append([20, 0.001])
    sheet.append([21, 0.0012])
    wb.create_sheet("Lapse")
    wb["Lapse"].append(["Policy", "Year1"])
    wb["Lapse"].append(["Term-10", 0.07])
    wb.save(path)


def test_parse_excel_yields_one_item_per_nonempty_row(tmp_path):
    src = tmp_path / "assumptions.xlsx"
    _make_xlsx(src)
    items = parse_excel_file(src)

    # Mortality: 3 rows (header + 2 data); Lapse: 2 rows (header + 1 data) → 5 items total
    assert len(items) == 5
    sheets = {i.locator.sheet for i in items if isinstance(i.locator, ExcelLocator)}
    assert sheets == {"Mortality", "Lapse"}


def test_parse_excel_locator_carries_sheet_and_cells(tmp_path):
    src = tmp_path / "a.xlsx"
    _make_xlsx(src)
    items = parse_excel_file(src)
    first = items[0]
    assert isinstance(first.locator, ExcelLocator)
    assert first.locator.sheet == "Mortality"
    assert first.locator.cells == "A1:B1"
    assert first.block_type == "table"


def test_parse_excel_content_is_tab_joined(tmp_path):
    src = tmp_path / "a.xlsx"
    _make_xlsx(src)
    items = parse_excel_file(src)
    header = items[0]
    assert header.content == "Age\tRate"


def test_parse_excel_skips_fully_empty_rows(tmp_path):
    src = tmp_path / "gaps.xlsx"
    wb = Workbook()
    sheet = wb.active
    sheet.title = "S"
    sheet.append(["A"])
    sheet.append([None])
    sheet.append(["B"])
    wb.save(src)
    items = parse_excel_file(src)
    assert [i.content for i in items] == ["A", "B"]
```

- [ ] **Step 3: Run tests to verify failure**

`uv run pytest tests/parsers/test_excel.py -v` — ImportError expected.

- [ ] **Step 4: Implement `src/dks/parsers/excel.py`**

```python
"""Excel parser — each non-empty row in each sheet becomes a TypedContentItem."""

from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from dks.locators import ExcelLocator
from dks.types import TypedContentItem


def parse_excel_file(path: Path) -> list[TypedContentItem]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    items: list[TypedContentItem] = []

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            cells = list(row)
            if all(c is None or (isinstance(c, str) and c.strip() == "") for c in cells):
                continue
            # Trim trailing None
            while cells and cells[-1] is None:
                cells.pop()
            if not cells:
                continue
            last_col_letter = get_column_letter(len(cells))
            cell_range = f"A{row_idx}:{last_col_letter}{row_idx}"
            content = "\t".join("" if c is None else str(c) for c in cells)
            items.append(
                TypedContentItem(
                    content=content,
                    block_type="table",
                    locator=ExcelLocator(sheet=sheet_name, cells=cell_range),
                )
            )
    return items
```

- [ ] **Step 5: Register `.xlsx` in the parser registry**

Edit `src/dks/parsers/__init__.py`:

```python
from dks.parsers.excel import parse_excel_file
from dks.parsers.markdown import parse_markdown_file

_REGISTRY: dict[str, ParserFn] = {
    ".md": parse_markdown_file,
    ".xlsx": parse_excel_file,
}
```

- [ ] **Step 6: Run tests + commit**

```bash
uv run pytest
uv run mypy src
uv run ruff check src tests
git add -A
git commit -m "feat: Excel parser with row-level ExcelLocator citations"
```

Expected: 51+ tests pass.

---

## Task 2 — DOCX parser

**Files:**
- Create: `src/dks/parsers/docx.py`
- Create: `tests/parsers/test_docx.py`
- Create: `tests/fixtures/sample.docx` (small generated fixture)
- Modify: `src/dks/parsers/__init__.py` (register `.docx`)
- Modify: `pyproject.toml` (add `docling>=2.0`)

**Strategy:** Docling parses DOCX into a `DoclingDocument`. Iterate its text-level elements; map paragraphs to `block_type="text"` with `DocxLocator(section=<current_heading_or_"body">, paragraph_idx=<sequence>)` and headings to `block_type="heading"`. Tables map to `block_type="table"` with tab-joined content.

- [ ] **Step 1: Add Docling to deps**

In `pyproject.toml`, add `"docling>=2.0"`. Then `uv sync`.

⚠ **First-run note**: Docling downloads ML models on first use (~1 GB). If `uv sync` succeeds but tests time out fetching models, escalate as BLOCKED and report the network issue.

- [ ] **Step 2: Generate test fixture**

Run once locally to produce `tests/fixtures/sample.docx`:

```bash
uv run python -c "
from docx import Document  # python-docx, separate from docling
d = Document()
d.add_heading('Claims Handling', level=1)
d.add_paragraph('Claims must be filed within 30 days.')
d.add_heading('Filing Window', level=2)
d.add_paragraph('Subject to subsection 2, the window may be extended.')
d.save('tests/fixtures/sample.docx')
"
```

If `python-docx` isn't installed, add it as a `[dependency-groups]` dev dep for fixture generation:

```toml
dev = [
  "pytest>=8.0",
  "ruff>=0.6",
  "mypy>=1.10",
  "python-docx>=1.1",  # fixture generation only
]
```

Then `git add tests/fixtures/sample.docx` (binary).

- [ ] **Step 3: Write the failing tests**

`tests/parsers/test_docx.py`:
```python
from pathlib import Path

from dks.locators import DocxLocator
from dks.parsers.docx import parse_docx_file


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_docx_yields_headings_and_paragraphs():
    items = parse_docx_file(FIXTURES / "sample.docx")
    # 2 headings + 2 paragraphs
    headings = [i for i in items if i.block_type == "heading"]
    paragraphs = [i for i in items if i.block_type == "text"]
    assert len(headings) == 2
    assert len(paragraphs) == 2
    assert any("Claims Handling" in h.content for h in headings)


def test_parse_docx_locator_carries_section_and_index():
    items = parse_docx_file(FIXTURES / "sample.docx")
    paragraphs = [i for i in items if i.block_type == "text"]
    p = paragraphs[0]
    assert isinstance(p.locator, DocxLocator)
    assert p.locator.section  # non-empty
    assert p.locator.paragraph_idx >= 0
```

- [ ] **Step 4: Run tests to verify failure**

`uv run pytest tests/parsers/test_docx.py -v` — ImportError expected.

- [ ] **Step 5: Implement `src/dks/parsers/docx.py`**

```python
"""DOCX parser via Docling — paragraphs + headings → TypedContentItem."""

from pathlib import Path

from docling.document_converter import DocumentConverter

from dks.locators import DocxLocator
from dks.types import TypedContentItem


def parse_docx_file(path: Path) -> list[TypedContentItem]:
    converter = DocumentConverter()
    result = converter.convert(str(path))
    doc = result.document

    items: list[TypedContentItem] = []
    current_section = "body"
    paragraph_idx = 0

    for element in doc.texts:  # docling exposes a flat text list with element types
        text = element.text.strip()
        if not text:
            continue
        label = getattr(element, "label", None)  # "section_header", "paragraph", etc.

        if label and "header" in str(label).lower():
            current_section = text
            items.append(
                TypedContentItem(
                    content=text,
                    block_type="heading",
                    locator=DocxLocator(section=current_section, paragraph_idx=paragraph_idx),
                )
            )
        else:
            items.append(
                TypedContentItem(
                    content=text,
                    block_type="text",
                    locator=DocxLocator(section=current_section, paragraph_idx=paragraph_idx),
                )
            )
        paragraph_idx += 1

    return items
```

**Note on the Docling API:** The exact attribute names (`doc.texts`, `element.label`) reflect Docling's 2.x API at time of plan writing. If the implementer finds the API differs (Docling is fast-moving), the test must still pass. Adjust the iteration accordingly; the *output contract* (list of `TypedContentItem` with `DocxLocator`) is what matters.

- [ ] **Step 6: Register `.docx` and run + commit**

Edit `src/dks/parsers/__init__.py`:
```python
from dks.parsers.docx import parse_docx_file
# ...
    ".docx": parse_docx_file,
```

```bash
uv run pytest
uv run mypy src
uv run ruff check src tests
git add -A
git commit -m "feat: DOCX parser via Docling"
```

---

## Task 3 — PDF parser

**Files:**
- Create: `src/dks/parsers/pdf.py`
- Create: `tests/parsers/test_pdf.py`
- Create: `tests/fixtures/sample.pdf` (small 2-page fixture)
- Modify: `src/dks/parsers/__init__.py` (register `.pdf`)
- Modify: `pyproject.toml` (add `magic-pdf` or `mineru` — see notes)

**Strategy:** MinerU parses PDFs into a typed content list with `page_idx`. Map directly to `TypedContentItem` with `PdfLocator(page=page_idx+1, section=...)`. Sections are derived from heading-like elements when MinerU labels them.

⚠ **Important install note:** MinerU's PyPI package name has changed across versions. As of late 2025, it's distributed as `mineru` (or the legacy `magic-pdf`). The implementer should check `pip search` / PyPI to confirm the current package name before committing the dep. If install fails, escalate as BLOCKED with the error so we can pick the right package.

- [ ] **Step 1: Add MinerU to deps**

Likely: `"mineru>=1.0"` in `pyproject.toml` dependencies. Run `uv sync`. On first run MinerU downloads layout/table/OCR models (~1–2 GB). If sync fails or hangs > 5 min, escalate as BLOCKED.

- [ ] **Step 2: Acquire a tiny PDF fixture**

Generate a 2-page PDF programmatically (one-time, then commit the binary):

```bash
uv run python -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/fixtures/sample.pdf')
c.setFont('Helvetica-Bold', 16)
c.drawString(72, 720, 'Claims Handling')
c.setFont('Helvetica', 12)
c.drawString(72, 700, 'Claims must be filed within 30 days.')
c.showPage()
c.setFont('Helvetica-Bold', 14)
c.drawString(72, 720, 'Filing Window')
c.setFont('Helvetica', 12)
c.drawString(72, 700, 'Subject to subsection (2), the window may be extended.')
c.save()
"
```

Add `"reportlab>=4.0"` to `[dependency-groups].dev` for fixture generation only.

`git add tests/fixtures/sample.pdf`.

- [ ] **Step 3: Write the failing tests**

`tests/parsers/test_pdf.py`:
```python
from pathlib import Path

from dks.locators import PdfLocator
from dks.parsers.pdf import parse_pdf_file


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_pdf_extracts_text_with_page_locator():
    items = parse_pdf_file(FIXTURES / "sample.pdf")
    assert len(items) >= 2
    pages = {i.locator.page for i in items if isinstance(i.locator, PdfLocator)}
    assert 1 in pages
    assert 2 in pages


def test_parse_pdf_content_includes_known_text():
    items = parse_pdf_file(FIXTURES / "sample.pdf")
    blob = " ".join(i.content for i in items)
    assert "Claims must be filed" in blob
    assert "Filing Window" in blob
```

- [ ] **Step 4: Run tests, observe failure, implement**

`src/dks/parsers/pdf.py`:
```python
"""PDF parser via MinerU — produces TypedContentItem with PdfLocator(page,...)."""

from pathlib import Path

from dks.locators import PdfLocator
from dks.types import TypedContentItem


def parse_pdf_file(path: Path) -> list[TypedContentItem]:
    # MinerU API (1.x): magic_pdf.tools.cli or programmatic. Use whichever
    # the installed version exposes; the test fixture is tiny so the
    # implementer can verify by running the parser and inspecting output.
    from mineru.cli.common import do_parse  # placeholder; adjust to actual API

    # Convert and read MinerU's content_list output
    raw = do_parse(str(path))  # placeholder
    items: list[TypedContentItem] = []
    for entry in raw.get("content_list", []):
        page = int(entry.get("page_idx", 0)) + 1
        text = entry.get("text", "").strip()
        if not text:
            continue
        block_type = "heading" if entry.get("type") == "title" else "text"
        section = entry.get("section_path") or None
        items.append(
            TypedContentItem(
                content=text,
                block_type=block_type,
                locator=PdfLocator(page=page, section=section),
            )
        )
    return items
```

**Important:** the MinerU API may differ from the placeholder above. The implementer should:
1. Install the package, look at `mineru.__version__` and its public API surface.
2. Find the right "convert this PDF to a content list" entry point (likely `do_parse`, `MagicPDFAPI`, or similar).
3. Adjust the import + call so the test passes.

If MinerU's API is too divergent, escalate as NEEDS_CONTEXT with a short summary of what's available.

- [ ] **Step 5: Register + commit**

```python
# in parsers/__init__.py
from dks.parsers.pdf import parse_pdf_file
# ...
    ".pdf": parse_pdf_file,
```

```bash
uv run pytest
git add -A
git commit -m "feat: PDF parser via MinerU"
```

---

## Task 4 — Block store API + `dks blocks` CLI

**Files:**
- Create: `src/dks/store/__init__.py`
- Create: `src/dks/store/blocks.py`
- Create: `tests/store/test_blocks.py`
- Modify: `src/dks/cli.py` (add `blocks` subcommands)
- Create: `tests/store/__init__.py`

**Purpose:** Skills need to list and fetch normalized blocks from disk. Provide a clean Python API + matching CLI.

- [ ] **Step 1: Write the failing tests**

`tests/store/test_blocks.py`:
```python
from pathlib import Path

from dks.block import NormalizedBlock
from dks.blockref import encode_blockref
from dks.locators import MarkdownLocator
from dks.store.blocks import get_block, list_blocks
from dks.writer import write_blocks


def _seed(tmp_path: Path) -> Path:
    loc1 = MarkdownLocator(heading_path=[], line_start=1, line_end=1)
    loc2 = MarkdownLocator(heading_path=[], line_start=3, line_end=3)
    blocks = [
        NormalizedBlock(
            source_file="claims.md",
            block_id=encode_blockref("claims.md", loc1),
            locator=loc1,
            block_type="text",
            content="first",
        ),
        NormalizedBlock(
            source_file="claims.md",
            block_id=encode_blockref("claims.md", loc2),
            locator=loc2,
            block_type="text",
            content="second",
        ),
    ]
    write_blocks(blocks, output_dir=tmp_path)
    return tmp_path


def test_list_blocks_for_source(tmp_path):
    _seed(tmp_path)
    ids = list_blocks(normalized_dir=tmp_path, source_file="claims.md")
    assert sorted(ids) == ["claims.md#L1-1", "claims.md#L3-3"]


def test_list_blocks_for_unknown_source(tmp_path):
    _seed(tmp_path)
    assert list_blocks(normalized_dir=tmp_path, source_file="nope.md") == []


def test_get_block_returns_full_block(tmp_path):
    _seed(tmp_path)
    block = get_block(normalized_dir=tmp_path, block_id="claims.md#L1-1")
    assert block.content == "first"
    assert block.locator.line_start == 1


def test_get_block_missing_raises(tmp_path):
    import pytest

    _seed(tmp_path)
    with pytest.raises(FileNotFoundError):
        get_block(normalized_dir=tmp_path, block_id="claims.md#L99-99")
```

- [ ] **Step 2: Implement `src/dks/store/blocks.py`**

```python
"""Block store reader — load NormalizedBlocks from disk."""

from pathlib import Path

from dks.block import NormalizedBlock, parse_markdown
from dks.writer import safe_filename


def list_blocks(normalized_dir: Path, source_file: str) -> list[str]:
    """Return all block_ids written for the given source_file."""
    source_dir = normalized_dir / Path(source_file).name
    if not source_dir.is_dir():
        return []
    ids: list[str] = []
    for md_file in source_dir.glob("*.md"):
        block = parse_markdown(md_file.read_text())
        if block.source_file == source_file:
            ids.append(block.block_id)
    return ids


def get_block(normalized_dir: Path, block_id: str) -> NormalizedBlock:
    """Load and return the NormalizedBlock with the given block_id."""
    source_part = block_id.split("#", 1)[0]
    source_basename = Path(source_part).name
    target = normalized_dir / source_basename / f"{safe_filename(block_id)}.md"
    if not target.exists():
        raise FileNotFoundError(f"block {block_id!r} not found at {target}")
    return parse_markdown(target.read_text())
```

`src/dks/store/__init__.py`:
```python
```

`tests/store/__init__.py`:
```python
```

- [ ] **Step 3: Add CLI subcommands**

Edit `src/dks/cli.py`. Add a `blocks` sub-app:

```python
import json

from dks.store.blocks import get_block, list_blocks

blocks_app = typer.Typer(no_args_is_help=True, help="Inspect normalized blocks.")
app.add_typer(blocks_app, name="blocks")


@blocks_app.command("list")
def blocks_list(
    source_file: str = typer.Argument(..., help="Source file (relative to root)."),
    normalized_dir: Path = typer.Option(
        Path("normalized"), "--normalized-dir", "-n"
    ),
) -> None:
    """List block_ids for a source file."""
    ids = list_blocks(normalized_dir=normalized_dir, source_file=source_file)
    for bid in ids:
        typer.echo(bid)


@blocks_app.command("get")
def blocks_get(
    block_id: str = typer.Argument(..., help="The block_id to fetch."),
    normalized_dir: Path = typer.Option(
        Path("normalized"), "--normalized-dir", "-n"
    ),
) -> None:
    """Print the normalized block (JSON) for a block_id."""
    try:
        block = get_block(normalized_dir=normalized_dir, block_id=block_id)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e
    typer.echo(block.model_dump_json(indent=2))
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest
git add -A
git commit -m "feat: block store reader + dks blocks list/get CLI"
```

---

## Task 5 — PageIndex storage + `dks pageindex` CLI

**Files:**
- Create: `src/dks/store/pageindex.py`
- Create: `tests/store/test_pageindex.py`
- Modify: `src/dks/cli.py` (add `pageindex` subcommands)

**Purpose:** Persist and load per-document PageIndex trees as sidecar JSON. The tree is `dict[str, Any]` — schema is intentionally loose at this layer (the LLM produces it; storage just persists it).

- [ ] **Step 1: Write tests**

`tests/store/test_pageindex.py`:
```python
import json
from pathlib import Path

import pytest

from dks.store.pageindex import read_pageindex, write_pageindex


def test_write_and_read_roundtrip(tmp_path):
    tree = {
        "title": "Claims Handling",
        "nodes": [
            {"title": "Filing Window", "block_ids": ["claims.pdf#p1#1.1"], "children": []},
        ],
    }
    target = write_pageindex(tmp_path, source_file="claims.pdf", tree=tree)
    assert target.exists()
    loaded = read_pageindex(tmp_path, source_file="claims.pdf")
    assert loaded == tree


def test_read_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_pageindex(tmp_path, source_file="absent.pdf")
```

- [ ] **Step 2: Implement `src/dks/store/pageindex.py`**

```python
"""PageIndex tree storage — sidecar JSON per source document."""

import json
from pathlib import Path
from typing import Any


def _target(index_dir: Path, source_file: str) -> Path:
    basename = Path(source_file).name
    return index_dir / f"{basename}.pageindex.json"


def write_pageindex(index_dir: Path, source_file: str, tree: dict[str, Any]) -> Path:
    index_dir.mkdir(parents=True, exist_ok=True)
    target = _target(index_dir, source_file)
    target.write_text(json.dumps(tree, indent=2))
    return target


def read_pageindex(index_dir: Path, source_file: str) -> dict[str, Any]:
    target = _target(index_dir, source_file)
    if not target.exists():
        raise FileNotFoundError(f"no PageIndex for {source_file!r} at {target}")
    return json.loads(target.read_text())
```

- [ ] **Step 3: CLI subcommands**

In `cli.py`:
```python
from dks.store.pageindex import read_pageindex, write_pageindex

pageindex_app = typer.Typer(no_args_is_help=True, help="Manage PageIndex trees.")
app.add_typer(pageindex_app, name="pageindex")


@pageindex_app.command("write")
def pageindex_write(
    source_file: str = typer.Argument(..., help="Source file the tree describes."),
    index_dir: Path = typer.Option(Path("index"), "--index-dir", "-i"),
) -> None:
    """Read a JSON tree from stdin and persist it."""
    import sys
    tree = json.loads(sys.stdin.read())
    target = write_pageindex(index_dir, source_file=source_file, tree=tree)
    typer.echo(f"wrote {target}")


@pageindex_app.command("read")
def pageindex_read(
    source_file: str = typer.Argument(...),
    index_dir: Path = typer.Option(Path("index"), "--index-dir", "-i"),
) -> None:
    """Print the PageIndex tree (JSON) for a source."""
    try:
        tree = read_pageindex(index_dir, source_file=source_file)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e
    typer.echo(json.dumps(tree, indent=2))
```

- [ ] **Step 4: Commit**

```bash
uv run pytest
git add -A
git commit -m "feat: PageIndex storage + dks pageindex read/write CLI"
```

---

## Task 6 — Claude Code skill: `dks-build-pageindex`

**Files:**
- Create: `skills/dks-build-pageindex/SKILL.md`
- Modify: `README.md` (add a "Skills" section pointing at `skills/`)

**Purpose:** Given a source file, the skill (a) lists all normalized blocks via `dks blocks list`, (b) fetches their content via `dks blocks get`, (c) reasons over the structure to produce a hierarchical tree of section titles + assigned block_ids, (d) persists via `dks pageindex write`.

This is a Claude Code skill, not Python code. No TDD needed — the skill is a Markdown prompt. Testing happens by manually invoking the skill against the project's own corpus and verifying the produced tree.

- [ ] **Step 1: Write `skills/dks-build-pageindex/SKILL.md`**

```markdown
---
name: dks-build-pageindex
description: Build a hierarchical PageIndex tree for a source document already ingested by dks. Use when the user wants to construct or refresh the per-document tree of contents that the consumer-facing dks-search skill uses for navigation.
---

# dks-build-pageindex

You build a hierarchical PageIndex tree for a single source document that has already been ingested by the `dks` package.

## Input

The user names a `source_file` (e.g. `policies/claims_handling.pdf`). They may also override `--normalized-dir` and `--index-dir`; default both to the project's `normalized/` and `index/`.

## Procedure

1. **List the blocks.** Run:
   ```bash
   dks blocks list "$SOURCE_FILE"
   ```
   This prints one block_id per line.

2. **Fetch every block's content.** For each block_id, run:
   ```bash
   dks blocks get "$BLOCK_ID"
   ```
   This prints the block as JSON. Capture the `content`, `block_type`, and `locator` of each.

3. **Reason over the structure.** Headings (`block_type == "heading"`) define section boundaries; text/table/list/code blocks belong to the most recent heading. Build a tree where each node has:
   - `title`: the heading text (or a synthesized title for the root)
   - `block_ids`: the list of block_ids that fall directly under this node (between this heading and the next sibling/parent heading)
   - `children`: a list of child nodes (deeper headings)

   The tree must be JSON-serializable and use the schema:
   ```json
   {
     "title": "string",
     "block_ids": ["string", ...],
     "children": [ { "title": ..., "block_ids": ..., "children": ... }, ... ]
   }
   ```

4. **Persist the tree.** Pipe the JSON into:
   ```bash
   echo '<json-tree>' | dks pageindex write "$SOURCE_FILE"
   ```

5. **Report back.** Tell the user the path the tree was written to and a one-line summary (top-level section count, deepest nesting depth, total nodes).

## Constraints

- **Never invent block_ids.** Only assign block_ids that were returned by `dks blocks list`. If a block's content suggests it belongs somewhere unexpected, still place it; the tree reflects the document, not your judgment about correctness.
- **Every block_id must appear in the tree exactly once.** If a block is orphaned (no preceding heading), place it under a synthetic root node.
- **Don't summarize the content.** This skill produces structure, not summaries. The wiki-compile skill is where summarization happens.
- **Fail loudly.** If `dks blocks list` returns nothing, tell the user the source hasn't been ingested yet — don't fabricate a tree.

## Cost guidance

A typical 50-page policy PDF has 100–300 blocks. Reading all of them and constructing a tree is one Sonnet-class prompt with ~50K tokens of context. Don't loop over blocks one at a time with LLM calls; fetch them all, then reason once.
```

- [ ] **Step 2: Update README to point at skills**

Append a "Skills" section to `README.md`:

```markdown
## Skills

LLM-driven operations are exposed as Claude Code skills under `skills/`. Copy them into your `~/.claude/skills/` directory to enable:

- `dks-build-pageindex` — construct a hierarchical tree for an ingested source.
- `dks-compile-wiki` (Phase 2c) — compile citation-preserving wiki articles.
- `dks-lint-wiki` (Phase 2c) — scan the wiki for broken refs and contradictions.

Skills invoke the `dks` CLI for all deterministic operations; the LLM work happens inside Claude Code with its own auth.
```

- [ ] **Step 3: Commit**

```bash
git add skills/ README.md
git commit -m "feat: dks-build-pageindex Claude Code skill"
```

---

## Task 7 — Wiki storage + `dks wiki` CLI

**Files:**
- Create: `src/dks/store/wiki.py`
- Create: `tests/store/test_wiki.py`
- Modify: `src/dks/cli.py` (add `wiki` subcommands)

A wiki article is a Markdown file with frontmatter listing the citation refs it uses. Storage layout: `wiki/<topic-slug>.md`. Frontmatter schema:

```yaml
---
{
  "topic": "PII handling rules in life-insurance products",
  "slug": "pii-handling-rules",
  "source_refs": ["claims.pdf#p14#3.2", "specs/pii.docx#§Intro#p0"],
  "compiled_at": "2026-05-22T10:15:00Z"
}
---
<article body>
```

- [ ] **Step 1: Tests**

`tests/store/test_wiki.py`:
```python
from pathlib import Path

import pytest

from dks.store.wiki import WikiEntry, list_wiki_entries, read_wiki_entry, write_wiki_entry


def _entry() -> WikiEntry:
    return WikiEntry(
        topic="PII handling rules",
        slug="pii-handling-rules",
        source_refs=["claims.pdf#p14#3.2"],
        body="When capturing customer details, fields A and B must be encrypted.",
    )


def test_write_read_roundtrip(tmp_path):
    target = write_wiki_entry(tmp_path, _entry())
    assert target.exists()
    loaded = read_wiki_entry(tmp_path, "pii-handling-rules")
    assert loaded.topic == "PII handling rules"
    assert loaded.source_refs == ["claims.pdf#p14#3.2"]
    assert "fields A and B" in loaded.body


def test_list_returns_all_slugs(tmp_path):
    write_wiki_entry(tmp_path, _entry())
    other = _entry()
    other.slug = "data-retention"
    other.topic = "Data retention rules"
    write_wiki_entry(tmp_path, other)
    slugs = sorted(list_wiki_entries(tmp_path))
    assert slugs == ["data-retention", "pii-handling-rules"]


def test_read_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_wiki_entry(tmp_path, "absent")
```

- [ ] **Step 2: Implement `src/dks/store/wiki.py`**

```python
"""Wiki entry storage — one Markdown file per topic, with JSON frontmatter."""

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

_FENCE = "---"


class WikiEntry(BaseModel):
    topic: str
    slug: str
    source_refs: list[str]
    body: str
    compiled_at: str | None = None


def write_wiki_entry(wiki_dir: Path, entry: WikiEntry) -> Path:
    wiki_dir.mkdir(parents=True, exist_ok=True)
    if not entry.compiled_at:
        entry.compiled_at = datetime.now(timezone.utc).isoformat()
    frontmatter = entry.model_dump_json(exclude={"body"}, indent=2)
    target = wiki_dir / f"{entry.slug}.md"
    target.write_text(f"{_FENCE}\n{frontmatter}\n{_FENCE}\n{entry.body}\n")
    return target


def read_wiki_entry(wiki_dir: Path, slug: str) -> WikiEntry:
    target = wiki_dir / f"{slug}.md"
    if not target.exists():
        raise FileNotFoundError(f"no wiki entry for slug {slug!r}")
    text = target.read_text()
    if not text.startswith(_FENCE + "\n"):
        raise ValueError(f"missing frontmatter fence in {target}")
    rest = text[len(_FENCE) + 1 :]
    close = rest.find("\n" + _FENCE + "\n")
    if close == -1:
        raise ValueError(f"missing closing frontmatter fence in {target}")
    front = json.loads(rest[:close])
    body = rest[close + len(_FENCE) + 2 :].rstrip("\n")
    front["body"] = body
    return WikiEntry.model_validate(front)


def list_wiki_entries(wiki_dir: Path) -> list[str]:
    if not wiki_dir.is_dir():
        return []
    return [p.stem for p in wiki_dir.glob("*.md")]
```

- [ ] **Step 3: CLI subcommands**

```python
from dks.store.wiki import WikiEntry, list_wiki_entries, read_wiki_entry, write_wiki_entry

wiki_app = typer.Typer(no_args_is_help=True, help="Manage compiled wiki entries.")
app.add_typer(wiki_app, name="wiki")


@wiki_app.command("write")
def wiki_write(
    slug: str = typer.Argument(...),
    wiki_dir: Path = typer.Option(Path("wiki"), "--wiki-dir", "-w"),
) -> None:
    """Read a JSON {topic, slug, source_refs, body} object from stdin and persist."""
    import sys
    data = json.loads(sys.stdin.read())
    data["slug"] = slug
    entry = WikiEntry.model_validate(data)
    target = write_wiki_entry(wiki_dir, entry)
    typer.echo(f"wrote {target}")


@wiki_app.command("read")
def wiki_read(
    slug: str = typer.Argument(...),
    wiki_dir: Path = typer.Option(Path("wiki"), "--wiki-dir", "-w"),
) -> None:
    """Print a wiki entry (frontmatter + body) for a slug."""
    try:
        entry = read_wiki_entry(wiki_dir, slug)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e
    typer.echo(entry.model_dump_json(indent=2))


@wiki_app.command("list")
def wiki_list(
    wiki_dir: Path = typer.Option(Path("wiki"), "--wiki-dir", "-w"),
) -> None:
    """List all wiki slugs."""
    for slug in sorted(list_wiki_entries(wiki_dir)):
        typer.echo(slug)
```

- [ ] **Step 4: Commit**

```bash
uv run pytest
git add -A
git commit -m "feat: wiki entry storage + dks wiki list/read/write CLI"
```

---

## Task 8 — Claude Code skill: `dks-compile-wiki`

**Files:**
- Create: `skills/dks-compile-wiki/SKILL.md`

The skill: given a topic + a list of source_files (or block_ids), produce a Markdown article that ALWAYS cites each claim back to a block_id, and persist via `dks wiki write`.

- [ ] **Step 1: Write `skills/dks-compile-wiki/SKILL.md`**

```markdown
---
name: dks-compile-wiki
description: Compile a citation-preserving wiki article on a domain topic. Use when the user wants to summarize a body of normalized blocks into a topic article that consumer agents can read for discovery. Every claim in the output must cite a block_id.
---

# dks-compile-wiki

You compile a Markdown article on a domain topic from a set of normalized source blocks. Every factual claim in the article must include an inline citation to a block_id.

## Input

The user names:
- A **topic** (free text), e.g. *"PII handling rules in life-insurance products"*
- A **slug** (kebab-case, no spaces), e.g. `pii-handling-rules`
- A set of **source_files** OR **block_ids** to draw from. If only source_files, list the blocks for each.

## Procedure

1. **Gather blocks.** For each source_file, run `dks blocks list <source>`. For each block_id (whether from the user or from the list), run `dks blocks get <block_id>` and capture the JSON.

2. **Compose the article.** Write a Markdown article on the topic. Rules:
   - Every factual statement must end with an inline citation: `[ref: <block_id>]`.
   - Multiple citations: `[ref: id1, id2]`.
   - Do not synthesize claims that aren't supported by a block. If two blocks contradict, write "X says A [ref: ...] but Y says B [ref: ...]" and surface the conflict.
   - Use the canonical block_id strings exactly as returned by the CLI. Do not abbreviate them.
   - Open with a short summary paragraph (1–2 sentences) of the topic before going into specifics.
   - Use H2/H3 to organize sub-topics if the material warrants it.

3. **Collect the unique source_refs.** Extract every distinct block_id you cited; that's the `source_refs` list.

4. **Persist.** Build a JSON object:
   ```json
   {
     "topic": "<topic>",
     "source_refs": ["<id>", "<id>", ...],
     "body": "<full article markdown>"
   }
   ```
   Pipe it into `dks wiki write <slug>`.

5. **Report.** Tell the user the slug, the path written, the source_ref count, and the article length in words.

## Constraints

- **No uncited claim, ever.** If you start a sentence and can't end with `[ref: ...]`, you don't have evidence — either find a block that supports it, or omit the sentence.
- **No paraphrase past recognition.** Reword for clarity but don't change meaning. The wiki is for discovery; the underlying block is the source of truth.
- **No silent block dropping.** If a block in the user-provided set is irrelevant to the topic, you may exclude it from `source_refs`, but tell the user in your report which blocks were excluded and why.
- **Slug discipline.** The slug becomes a filename. Reject slugs with `/`, spaces, or uppercase; ask the user for a fixed slug if theirs is invalid.

## Cost guidance

Compiling one wiki article from ~50 blocks should fit comfortably in a single Sonnet-class prompt. Don't loop per-block.
```

- [ ] **Step 2: Commit**

```bash
git add skills/dks-compile-wiki/
git commit -m "feat: dks-compile-wiki Claude Code skill"
```

---

## Task 9 — Claude Code skill: `dks-lint-wiki`

**Files:**
- Create: `skills/dks-lint-wiki/SKILL.md`

The skill: scan all wiki entries, verify every cited block_id exists, look for contradictions across entries, report.

- [ ] **Step 1: Write `skills/dks-lint-wiki/SKILL.md`**

```markdown
---
name: dks-lint-wiki
description: Scan compiled wiki entries for broken citations, contradictions, and stale references. Use periodically or after re-ingesting source documents.
---

# dks-lint-wiki

You audit the compiled wiki for citation integrity and consistency.

## Procedure

1. **List all entries.** Run `dks wiki list` to get every slug.

2. **For each entry,** run `dks wiki read <slug>`. From the result:
   - Verify every `block_id` in `source_refs` still exists by running `dks blocks get <block_id>`. Record any that return `error: block ... not found`.
   - Verify every inline `[ref: <id>]` in the body is also present in `source_refs`. Inconsistencies are bugs.
   - Note the entry's topic.

3. **Cross-entry contradiction scan.** Read each entry's body. Flag any pair of entries that make opposing claims on the same topic (e.g. one says "30 days", another says "60 days" without a versioning context). Be conservative — only flag when the contradiction is direct, not when the entries simply scope differently.

4. **Report.** Produce a structured report:
   ```
   ## Wiki lint report
   
   ### Broken citations
   - entry `<slug>`: block_id `<id>` no longer exists
   
   ### Inline-vs-source_refs drift
   - entry `<slug>`: body cites `<id>` but it isn't in source_refs (or vice versa)
   
   ### Possible contradictions
   - `<slug-a>` says "<claim>" [<id>] but `<slug-b>` says "<other>" [<id>] — same topic area
   
   ### Summary
   N entries scanned, X broken citations, Y drift issues, Z possible contradictions.
   ```

5. **Don't auto-fix.** This skill reports. Fixing broken citations means re-compiling the affected entries — that's the user's call.

## Constraints

- **No false positives on contradictions.** Same word ≠ contradiction. Look for actual conflicting facts on the same topic. When in doubt, don't flag.
- **No editing.** This skill is read-only. It runs `dks blocks get` and `dks wiki read`; it does not run `dks wiki write`.
```

- [ ] **Step 2: Commit + push + tag**

```bash
git add skills/dks-lint-wiki/
git commit -m "feat: dks-lint-wiki Claude Code skill"
git push origin main
git tag phase-2-complete
git push --tags
```

---

## Self-review

- **Spec coverage:** Layers 1 (full — all 4 parsers), 2 (already in Phase 1), 3 (PageIndex storage + build skill), 4 (wiki storage + compile/lint skills) all addressed. Layer 5 (consumer-facing skill) and Layer 6 (eval) are Phase 3.
- **Carryover items resolved:** Task 0 addresses source_file scoping, PdfLocator.clause encoding, BOM handling.
- **Skill-based LLM orchestration architecture is honored:** No Python LLM client added. All LLM work is in `skills/`.
- **Placeholder scan:** MinerU API is intentionally approximate (the package's API surface is fast-moving) — the implementer is instructed to escalate rather than guess. This is a known unknown, not a placeholder.
- **Type consistency:** `NormalizedBlock`, `BlockRef`, `TypedContentItem`, `Locator` all reused from Phase 1 without redefinition.

## What Phase 3 takes

- **Consumer-facing skill** (`dks-search`): the two-tool contract from the spec — `search_topic` calls `dks wiki list/read` + ranks against query; `get_source` calls `dks blocks get`.
- **Eval harness**: ~20 coding tasks in a compliance area, baseline vs treatment runs (treatment = with the consumer-facing skill), scoring rubric.
