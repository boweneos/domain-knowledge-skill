"""Typer CLI: `dks ingest <path>`."""

import json
from pathlib import Path

import typer

from dks.normalizer import normalize
from dks.parsers import get_parser
from dks.search import search_wiki
from dks.store.blocks import get_block, list_blocks
from dks.store.pageindex import read_pageindex, write_pageindex
from dks.store.wiki import WikiEntry, list_wiki_entries, read_wiki_entry, write_wiki_entry
from dks.writer import write_blocks

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """dks — domain knowledge skill CLI."""


blocks_app = typer.Typer(no_args_is_help=True, help="Inspect normalized blocks.")
app.add_typer(blocks_app, name="blocks")

pageindex_app = typer.Typer(no_args_is_help=True, help="Manage PageIndex trees.")
app.add_typer(pageindex_app, name="pageindex")

wiki_app = typer.Typer(no_args_is_help=True, help="Manage compiled wiki entries.")
app.add_typer(wiki_app, name="wiki")


@pageindex_app.command("write")
def pageindex_write(
    source_file: str = typer.Argument(..., help="Source file the tree describes."),  # noqa: B008
    index_dir: Path = typer.Option(Path("index"), "--index-dir", "-i"),  # noqa: B008
) -> None:
    """Read a JSON tree from stdin and persist it."""
    import sys
    tree = json.loads(sys.stdin.read())
    target = write_pageindex(index_dir, source_file=source_file, tree=tree)
    typer.echo(f"wrote {target}")


@pageindex_app.command("read")
def pageindex_read(
    source_file: str = typer.Argument(...),  # noqa: B008
    index_dir: Path = typer.Option(Path("index"), "--index-dir", "-i"),  # noqa: B008
) -> None:
    """Print the PageIndex tree (JSON) for a source."""
    try:
        tree = read_pageindex(index_dir, source_file=source_file)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e
    typer.echo(json.dumps(tree, indent=2))


@blocks_app.command("list")
def blocks_list(
    source_file: str = typer.Argument(..., help="Source file (relative to root)."),  # noqa: B008
    normalized_dir: Path = typer.Option(  # noqa: B008
        Path("normalized"), "--normalized-dir", "-n"
    ),
) -> None:
    """List block_ids for a source file."""
    ids = list_blocks(normalized_dir=normalized_dir, source_file=source_file)
    for bid in ids:
        typer.echo(bid)


@blocks_app.command("get")
def blocks_get(
    block_id: str = typer.Argument(..., help="The block_id to fetch."),  # noqa: B008
    normalized_dir: Path = typer.Option(  # noqa: B008
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


@wiki_app.command("write")
def wiki_write(
    slug: str = typer.Argument(..., help="Slug for the wiki entry (kebab-case)."),  # noqa: B008
    wiki_dir: Path = typer.Option(Path("wiki"), "--wiki-dir", "-w"),  # noqa: B008
) -> None:
    """Read a JSON {topic, source_refs, body} object from stdin and persist as <slug>.md."""
    import sys
    data = json.loads(sys.stdin.read())
    data["slug"] = slug
    entry = WikiEntry.model_validate(data)
    target = write_wiki_entry(wiki_dir, entry)
    typer.echo(f"wrote {target}")


@wiki_app.command("read")
def wiki_read(
    slug: str = typer.Argument(...),  # noqa: B008
    wiki_dir: Path = typer.Option(Path("wiki"), "--wiki-dir", "-w"),  # noqa: B008
) -> None:
    """Print a wiki entry (JSON) for a slug."""
    try:
        entry = read_wiki_entry(wiki_dir, slug)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e
    typer.echo(entry.model_dump_json(indent=2))


@wiki_app.command("list")
def wiki_list(
    wiki_dir: Path = typer.Option(Path("wiki"), "--wiki-dir", "-w"),  # noqa: B008
) -> None:
    """List all wiki slugs."""
    for slug in sorted(list_wiki_entries(wiki_dir)):
        typer.echo(slug)


@wiki_app.command("search")
def wiki_search(
    query: str = typer.Argument(..., help="Search query (case-insensitive substring)."),  # noqa: B008
    wiki_dir: Path = typer.Option(Path("wiki"), "--wiki-dir", "-w"),  # noqa: B008
) -> None:
    """Print matching wiki entries (JSON list)."""
    hits = search_wiki(wiki_dir=wiki_dir, query=query)
    typer.echo(json.dumps([h.model_dump() for h in hits], indent=2))


@app.command()
def ingest(
    path: Path = typer.Argument(..., help="Source file to ingest."),  # noqa: B008
    output_dir: Path = typer.Option(  # noqa: B008
        Path("normalized"), "--output-dir", "-o", help="Where to write normalized blocks."
    ),
    root: Path = typer.Option(  # noqa: B008
        Path("raw"),
        "--root",
        "-r",
        help="Root directory the source path is relative to; defaults to ./raw",
    ),
) -> None:
    """Parse, normalize, and persist a source document."""
    if not path.exists() or not path.is_file():
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(code=2)

    try:
        source_file = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        # path is not under root; fall back to basename
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


if __name__ == "__main__":
    app()
